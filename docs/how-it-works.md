# How Lonk works

There's no source code for the game. MacNativeGames runs the original ARM64 code natively and replaces the console's
OS, graphics and input underneath it, so everything here is about finding the right function in the binary and
calling it ourselves. Addresses are for 1.4.3 (`main` offsets) unless they say otherwise.

## Spawning

`engine::actor::ActorMgr::requestCreateActorAsync` creates any actor by name, the same way the game does. Its 1.0.0
address comes from [totk-lotuskit](https://github.com/aquacluck/totk-lotuskit)'s symbols (`0xa5fdf8`). For 1.4.3 it
was found by matching instead of guessing:

- five functions use the strings `Pack/Actor/`, `.pack` and `ActorMgr`
- only one has 1.0.0's entry (same register saves, `ldr [x29,#0x68]` then `ldrb [x0,#0xe1]`) and reads the same
  `CreateArg` fields (`+0x48..+0x88`): `0x599670`
- 87 of its 108 callers load `ActorMgr::sInstance` through one GOT slot, as 87 of 105 do in 1.0.0: `0x3ad7450`

`CreateArg` is 0x98 bytes (layout from lotuskit): position, a row-major rotation, scale, flags, and
`transform_flags = 7` to use all three. The actor shows up in the returned `PreActor` 2 to 3 frames later.
The patch checks the first ten instruction words before calling anything, and logs instead of calling if they differ.

## Picking a body

`Player` crashes when spawned twice. The armor-shop mannequins `Mannequin_001_Head`, `_Upper` and `_Lower` render in
the world, and stacked on one spot they look like a Link with nobody inside. That was the first body.

`PouchPlayer`, the inventory Link, uses the same model and animations as the real one. It spawns into the world scene
with its draw masks already on, and looked invisible only because it moves itself to (0, 0, 0) every frame. Setting
its transform every frame like any other piece makes it show up. Nothing ever starts its animation outside the menu,
so the patch starts it itself, the way the game's own C++ callers do: a 0x30-byte request
`{actor, name, slot 0, rate 1, -1, -1, 1}` passed to `0x4dc628`.

## Walking and running

PouchPlayer's ASB (`AS/PouchPlayer.root.asb`) has twelve commands and only one of them moves the whole body: the pause
menu's `PauseMenuWait`. For a long time Lonk only ever got `FaceDefault` (which the game starts itself, face only) and
`Nml_Wait` (not a command at all: the request is accepted and does nothing), so he stood in his rest pose, which looks
like an idle. His skeleton was fine all along.

`PauseMenuWait` starts with a selector on the ASB blackboard int `HoldAnimationType` (the weapon he holds in the menu):
1 to 5 go to the weapon poses, anything else to the plain idle, which picks cold, normal, hot or tired from the
blackboard's `Temperature` and `Stamina`. The menu's AI node `ExecutePouchPlayerSetASBBParameter` (`0x241cc08`) writes
those two (and `Burning`, `ShieldEquip`, `Arrow`, `Carrying`, `Size`...) every frame from your state: `Temperature` is -1
when you're cold, 1 when hot, from flags at `[[main+0x395ea40]]+0x658` (the GOT slot is `0x395ea40`; Ghidra calls it `DAT_03a5ea40`). It never writes `HoldAnimationType` for him. So:

- the RomFS mod (`mod/make_mod.py`, built with [dt-12345/asb](https://github.com/dt-12345/asb)) points the selector's
  cases 1 to 5 straight at five of the menu's weapon-equip clips (only reachable from those cases), renamed to
  `Nml_Move_Walk`, `Nml_Move_Run`, `Nml_Move_Dash`, `Demo_Get_Cooking_VeryGood` (his party after a gift) and
  `Demo_Surprise` (you turn round on him). PouchPlayer already loads all of Link's animations.
- the patch plays `PauseMenuWait` once and then sets `HoldAnimationType` every frame, through the blackboard's vtable
  `+0x30` (int by name; float `+0x38`, bool `+0x40`): `set(bb, &{"HoldAnimationType", 0}, value)`, the blackboard
  being `[as+0x40]` (`as` = his animation state, the chain `0xba8ed0` walks). Idle below 0.4 m/s, walk up to 3.2, run
  up to 5.5, dash above; the bands overlap by 0.3 m/s and a new gait has to hold for 12 frames, because every switch
  restarts the clip. Standing, he's the plain idle, so he shivers in the snow and sweats in the heat by himself.
- no walk (Camille's call: Link mostly runs or sprints, and the slow walk looked off): idle, run below 7.3 m/s, sprint
  above, at Link's own speeds measured from a trace (5.7 running, 9 sprinting). The clip's rate (`slot+0xd0`) makes his
  steps match the ground: the loop position moves k per frame per unit of rate (measured as he goes), and a loop
  covers the clip's root motion, so rate = speed / (60 x metres per loop x k). The game routes each command to its own slot: 0 is the face, 1 the body, 2 the skin colour.

The first version drove `Temperature` instead (cold idle = walk). Fighting the menu's node over it every frame flipped
him between the idle and the walk, and each flip restarted the walk: a few steps, snap back, again. He also blushed
and puffed cold breath in warm caves, since that comes with the cold idle node.

The moves carry him forward inside the clip (root motion): over one loop his body walks ahead of where he's put, then
snaps back when the clip loops. The real Player's movement absorbs that; nothing does for him. The body slot has the
loop position, 0 to 1, at `slot+0x1e0` (`+0xf8` counts frames, `+0x1ec` total time), so he's placed behind his spot by
(metres the clip travels per loop) x (loop position), and the two cancel out. The metres are tuned by eye:
`survey lonk root <walk> <run> <dash>`. (With the mod installed you can watch the raw clip: hold a sword in the menu
and the inventory Link walks three steps and snaps back, forever.)

Switching between run and sprint still made a little snip: the new clip started its loop from 0, so his body jumped
back by however far into the old loop he was. The Player's own run and dash leaves avoid that with "InitialFrame"
nodes (start where the previous animation was in its loop). Two of PouchPlayer's leaves have one too, but it did
nothing here (the loop still restarted, measured in the trace). What works is the command's first node's `Is Sync`:
with it on, every switch keeps the loop phase (normalized), and the trace shows the loop running straight through run
-> sprint -> run. Only a command's first node can do it (those are the only selectors with Sync Controls), and it
reaches through everything below, so an emote would start wherever his loop was (the party started 31% through, or
at its last frame). So the patch starts an emote only on a frame where his loop has just come round (under 6%), which
costs at most a fraction of a second. Writing 0 into the loop's frame first doesn't work: the sync then lands on 1.0.
The compensation follows the sync: over the 5 frames a new clip fades in, the metres per loop fade from the old gait's
to the new one's, at the same loop position.

More emotes than slots: the selector only has cases 1 to 5, and adding cases crashes. But the walk's case (he only runs
and sprints now) can lead anywhere in the tree, so it goes to the UseItem command's first node: a selector on the
blackboard *string* `UseItem` (eat food, eat a meal, eat a skewer, eat something gross, drink, use a fairy...), one clip
each. The menu's AI never writes that string (it writes `Arrow`, through the setter at vtable `+0x28`), so the patch
picks his emote with it: three eating clips stay as they are (a bite, a meal, a gross one), the drink too, and four get
renamed: `DemoLookAround` (his look around is back), `DemoLookUp`, `Nml_Wait_Jump` and `Demo_Get_Cooking_Bad` (a sulk).
That selector reads the string only when it starts, so between two of those emotes he spends one frame in the idle. His
face follows on its own: the game switches his face slot to `FaceUseItem`, the eating expressions. Checked in the trace:
each emote plays a clip of its own length (eat 30 frames, look around 29, look up 24, sulk 208).

The copycat jump: when the player's height starts rising faster than 3.5 m/s after standing still on the ground, Lonk
starts the jump clip, and once it's actually playing his feet get 4.5 m/s upwards and the falling code does the rest
(about a metre up, about a second in the air). Shoved for 1.5 seconds (you within 1.2 m, moving), he sulks.

Floor rays: the filter I copied from the game's cliff check (`0xfffcffff00000011`) also hits big invisible volumes
(bit 4 of the low word). The Temple of Time's hall sits inside a 15 m tall one, so every floor ray "hit" right where it
started and he climbed to its top. The low word is now `1`, and a hit right at a ray's start counts as no floor.
`survey raylayers <hex>` tries others, and `survey height` logs the hit record.

Adding new commands or nodes to the ASB crashes his spawn (a null arena at `0xb6def4` while his animation state is
built), even a clone of an existing node, and so does pointing a face command at a body node (it starts, nothing moves).
A plain decode and re-encode of the file loads fine, and so does renaming clips, which is all the mod does.

## Dressing him

The real Player dresses itself when its `EquipmentUser` component starts (`0xc45d8c`), but only if a parameter that
reads like `IsPouchUser` is set, which it isn't for `PouchPlayer`. That one waits for the pause menu's AI node
`OneShotChangeEquipmentForPouch` to dress it, so outside the menu he had no hair, no clothes and no right arm.

The patch dresses him the same way the menu does, 60 frames after he spawns:

- `eu = 0xcbffa0(actor)` is his EquipmentUser (`[[actor+0x228]+0x230]`).
- `0x1b6cd78(eu, slot, &name, -1, 0, 0)` equips one slot. `name` points at a `const char*`, and an empty name means
  "dress like the player", or the defaults when the game decides the player wears nothing: `Armor_999_Head` (the
  hair), `Armor_Default_Upper` and `Armor_Default_Lower`.
- Slots 9, 10 and 11 are head, upper and lower. The Zonai arm is slot 19 ("Extra"), `PlayerRaulHand`, the same thing the
  real Player equips on itself at startup.
- The pieces are separate actors, spawned asynchronously; `0x1b7be9c(eu)` turns nonzero when they're all in. Their
  ActorLinks are at `eu+0xe0+(slot-9)*0x18`, read with `0x1afbe4` (it returns `{actor, holds a reference}`).
- A pouch user's pieces are made for the menu's model scene, so each one is bound to the world scene like the body.
  The game binds them back to the menu's scene every frame (all four pieces, every frame), so the patch rebinds them
  every frame for as long as he's around. Rebinding only for the first 10 seconds made his legs and arm flash and then
  vanish.

Real armor works too, since the pieces get put back in the world scene every frame. The night before, I'd only rebound
them once, and every real piece was invisible (he turned into a floating face, since a piece also hides the body under it),
while the defaults drew. I'd written it up as the big open problem: a real piece is its own model (with cloth, helper bones
and an AS for the cold-skin colour), while `Armor_Default_*` is a plain model, so I suspected its skeleton only got posed
in the menu. When I tried again tonight, the Hylian trousers, tunic and hood drew right away, and moved with his run.
Whatever the menu scene was doing to them, it was the same fight as the flashing legs.

So `survey lonk twin` gives you matching outfits: it equips slots 9 to 11 with an empty name, which the game reads as
"whatever the player has on" (the reason his first outfit was a floating head). Once a second it reads the names of your
own pieces (your EquipmentUser has the same layout), and a slot that changed is copied onto him again.

Weapons work the same way: slots 0 (weapon), 7 (bow) and 8 (shield), and the empty name copies yours. The game adds the
sheath and the quiver by itself. All of an equipment user's pieces sit in one array of ActorLinks from `eu+0x20`, 0x18
apart, in their own order (weapon 0, bow 3, shield 4, head 8, upper 9, lower 10, sheath 11, quiver 14, the arm 18; found
with `survey peek euscan`), and every one of them gets put back in the world scene each frame, like the clothes. Without
that, the weapons were the ones that showed up near his legs the first night.

`survey drop` takes pieces off him. There's no delete call yet, so each one gets view mask 0 (`0x50138c`) and is
moved 50 m underground.

## The "ForSale" crash

Spawned mannequins crashed the game about half a second after Link walked up, before any prompt.

- The player's nearby-interaction search (`0x5e3294`) finds the mannequin's type `0x17` entry and calls
  `0x21368b4` → `0x2136620`.
- That looks up the actor's outgoing link named `"ForSale"` (`0x2136510`) in the actor link graph
  (`[0x3ad74b8]+0x240`, one node per actor at `actor+0x370`). In a shop the mannequin is linked to the item it sells.
- Ours has no link, the lookup returns null, and the incoming-link count at `0x2b05778` reads `null+0xf4`.

The fix reorders the count's first eight instructions so a null node counts zero links, with one `cbz` added and the
loop's branch target kept in place. Real nodes get the same result as before. It's applied only in test mode, after
checking the original words. As a bonus, the mannequin turns into a working shop in the middle of nowhere
("Hylian Tunic, 130 rupees").

## Moving

`forceSetMatrix` (`0x45ce70` in 1.4.3) sets an actor's full transform through its physics component. Every frame
every body piece is set to the same anchor point, turned to face Link (yaw only). That keeps the three pieces one
figure.

Height comes from a physics raycast straight down, set up the way the AI node
`QueryCheckCliffRayCast` (`0x260b30c`) builds one on its stack:

- a 0x178-byte query: vtable `[main+0x395d990]+0x10`, start at `+0x08`, end at `+0x14`, fraction `-1` at `+0x3c`
- a collision filter at `+0x128` (vtable `[main+0x3988178]+0x10`, layers `0xfffcffff00000011`), pointed to by `+0x60`
- `bool 0x1952a4(&query, 0)` casts it and leaves the hit position at `+0x24`. Its cleanup calls are empty.

It hits whatever Link can stand on, sky islands and rocks included (checked against Link himself, dropped on the same
spot: both 1520.99). Where it misses, the game's terrain heightmap (the AI node `QueryTerrainGetGroundHeight`:
`T = [main+0x3add550]`, `scene = 0x2b7332c(T, pos, 1, 0, 300.0)`, then `0x5db4c0(&height, xz, scene, -1, 0, 1, 0)`
answers 1 or 2) was the fallback before he had feet, then Link's own footsteps: a ring of his last 512 positions, one every
25 cm. Letting gravity do it doesn't work, because setting the transform every frame keeps gravity from ever catching up.

He has feet now. The ray starts a step (0.7 m) above them, not above his head: starting from 3 m above the higher of him
and Link, a boulder up to 3 m tall counted as floor, so he stepped onto it, and the next ray started higher still. That's
how he walked up walls and onto cave roofs. Floor lower than his feet and he falls (9.8 m/s², down to that floor);
floor too steep (normal y under 0.6) and he doesn't step onto it.

The same raycast steers him: before each step he probes 1 m ahead at knee height, and if something's there (and it isn't
a walkable slope, judged by the hit normal at `+0x30`) he tries 30, 45, 90 and then 120 degrees to one side, then the
other, starting with whichever side worked last so he doesn't dither. A ledge counts too: no floor within 2.5 m below his
feet 0.8 m ahead. Boxed in, he waits.

He also looks before he picks where to go. A wander tries 8 random directions and measures how far each one is really
walkable (the knee-high ray for walls, then a floor ray every metre, following the floor up and down), and goes to the
best one, stopping short of the wall or ledge. More than 15 m from Link, the directions are all roughly towards him. A
flee takes the clearest way near "straight away from Link", and when he gets stuck the sides come first. Tested in the
Temple of Time's hall (walls, pillars, stairs): wanders and flees back to back for 100 s, 99-100% of the frames he
tried to move he got somewhere (`lonk stats` in the log every 10 s).

Stranded for 3 seconds (5 m above or below Link or 30 m away while getting nowhere, 60 m away, stuck against something,
or no floor), he pops back next to Link: behind him, else to a side, else in front, wherever a ray finds flat floor at
Link's height. Up a staircase or off on a run of his own is fine. The "behind" mood's teleport uses the same spot.

Walking through Link puts the mannequin's collision above Link's head, which the game reads as a low ceiling, and
forces a crouch. Lonk keeps 1.1 m away and slides around instead, unless that would put him in a wall or off a ledge
(which is how you could shove him through walls).

## Seeing enemies

To pick fights he has to see enemies, and there's no actor list I could find (lotuskit only tracks the "resident" actors,
and scanning the actor manager's memory for his own pointer only found heap noise). Rays turned out to be the way. The
game's AI node `QueryPhysicsRaycastIsHitDynamicActor` (vtable found through its name string: `getName` at `0x26f0760`,
its run method `0x26f0448`) casts the same query as his floor ray and then reads the actor off the hit: the body at
`q+0x170`, its ActorLink at `[body+0x110]+0x18` (through `0x1cf46d4`), and the actor at `[link object+0x40]` while
`[object+0x48]` still matches the link's id (`0x5fe3b0` does it with a reference). The query's 64-bit filter: the high
word is a collision mask (the game takes it from a preset table, `0xb693dc(filter, preset, 1)` writes `filter+0xc`), the
low word says what kinds of bodies count: bit 0 the world, bit 1 characters, bit 4 big invisible volumes.

So every 15 frames he casts 16 chest-high rays out to 18 m (characters on: `0xfffcffff00000003`), and the nearest hit
actor named `Enemy_*` within 6 m of his height is "seen" for 3 seconds. Tested with a spawned Bokoblin: "spotted
Enemy_Bokoblin_Junior, 10.4 m away", then the fight (bomb barrel spawned at an exact spot halfway to it, startle, flee
from the enemy, not from you), and another 25 s later. The same scan found the shrine gate and you (`Player`).

Enemies aren't always a fight: one time in three he startles and hides behind you instead (the "behind" mood's teleport
makes it look like he dove there).

## Small things

- Gifts: freezing (the player's cold flag), he brings a spicy pepper (`Item_Fruit_I`, the only fruit with `ResistCold`);
  too hot, a hydromelon (`Item_Fruit_F`, `ResistHot`). The flags are bits 39 and 40 of `[[main+0x395ea40]]+0x658`, the
  ones the menu turns into `Temperature`, and `+0x6ec` right next to them is the temperature where you stand (15 degrees
  in the Temple of Time).
- Ledges, following you (stalk, buddy, block, behind, gift): when you're 1.5 to 12 m below him, ledges stop counting as
  walls, so he walks off and the falling code takes him down. When you're 1.2 to 7 m above and within 9 m, and he's been
  blocked for a third of a second or hasn't got any closer for two thirds, he jumps: upward speed sqrt(2 g (height +
  0.6 m)), the jump clip, and he keeps heading for you in the air (aiming 0.6 m from you, so he lands beside you, not at
  the foot). The knee-high wall check rises with his feet, so he moves on once he's above the edge. 4 s between tries.
- Buddy mode, both standing still for 7 s: now and then he looks up, looks around, snacks or drinks.

## Coming back

Every frame each body piece's name is read back from the actor (`actor+0x218`); a piece that no longer reads back is
forgotten. If that was PouchPlayer and the brain is running, Lonk respawns two seconds after the player stands somewhere
real again: the player actor that exists on the loading screen sits at the origin, so that doesn't count. Tested by
dropping Link from 150 m: game over, Continue, and he's back, dressed, picking his next mood.

## The brain

Every 6 to 12 seconds a weighted dice roll picks a behaviour: stalk 25, buddy, block, behind, wander and gift 15 each,
never two gifts in a row. Buddy walks 1.6 m to one side of Link at Link's own (smoothed) speed. A gift spawns an apple
(`Item_Fruit_A`), a fish (`Item_FishGet_A`), a monster part (`Item_Enemy_01`) or a `BarrelBomb` next to Link through the
same spawn call,
then Lonk celebrates for two and a half seconds and flees for four.
