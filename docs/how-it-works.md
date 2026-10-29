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
when you're cold, 1 when hot, from flags at `[[main+0x395ea40]]+0x658` (the GOT slot is `0x395ea40`; Ghidra calls it
`DAT_03a5ea40`). The game writes `HoldAnimationType` too, from the weapon in your hands as far as I can tell (twins gave
him your sword): I only found out because skipping our write for a few frames made him play his last emote again. So:

- the RomFS mod (`mod/make_mod.py`, built with [dt-12345/asb](https://github.com/dt-12345/asb)) points the selector's
  cases 1 to 5 (renumbered 11 to 15, below) straight at five of the menu's weapon-equip clips (only reachable from those cases), renamed to
  `Nml_Move_Walk`, `Nml_Move_Run`, `Nml_Move_Dash`, `Demo_Get_Cooking_VeryGood` (his party after a gift) and
  `Fall_Loop`.
  PouchPlayer already loads all of Link's animations.
- the patch plays `PauseMenuWait` once (in his body's slot, 1: slot 0 is his face, and starting it there took his
  face's place) and then sets `HoldAnimationType` every frame, after the game, through the blackboard's vtable `+0x30`
  (int by name; string `+0x28`, float `+0x38`, bool `+0x40`): `set(bb, &{"HoldAnimationType", 0}, value)`, the
  blackboard being `[as+0x40]` (`as` = his animation state, the chain `0xba8ed0` walks). Standing, he's the plain idle,
  so he shivers in the snow and sweats in the heat by himself.
- idle, walk below 4 m/s, run below 7.3, sprint above, at Link's own speeds measured from a trace (5.7 running, 9
  sprinting). Link's tree fades the walk into the run between 2.9 and 5.6 m/s; Lonk switches at 4. (He had no walk
  for a while: keeping your walking pace on the run clip looked like running while holding back.) The clip's rate
  (`slot+0xd0`) is the one Link's own tree uses (its frame controllers: walk 0.9, run 1.5, sprint 1.75), scaled by
  his speed against Link's. Matching his steps to the ground by measurement instead came out at 1.1 to 1.2, and
  Camille saw it: a bit slow.
- he speeds up and brakes like Link: from Camille's own runs in the traces, standing to 7.5 m/s takes about 6 frames
  and a 9.9 m/s sprint stops in about 13, so 60 m/s² up and 45 down, braking in time to stop at his stop distance
  (v² = 2 x braking x the room left). The gait comes from the speed he means to go, not his measured one: that lagged
  20 frames, held another 12, and he ran on the spot for half a second after every stop. Braking to a stop, he goes to
  the idle at once (Link's brake starts as soon as you let go), and its fade ends about when he stops. Between run and
  sprint a new gait still holds for 12 frames; to start or stop, 2.

The first version drove `Temperature` instead (cold idle = walk). Fighting the menu's node over it every frame flipped
him between the idle and the walk, and each flip restarted the walk: a few steps, snap back, again. He also blushed
and puffed cold breath in warm caves, since that comes with the cold idle node.

The moves carry him forward inside the clip (root motion, in the `Root` bone): over one loop his body runs about 3 m
ahead of where he's put, then snaps back when the clip loops. The real Player's movement absorbs that; nothing does for
him. For days the patch undid it: placed him behind his spot by (metres per loop) x (loop position at `slot+0x1e0`),
first with metres by eye, then measured (3.04 run, 3.09 sprint), then fading with the game's own blend weight
(`slot+0x184`, 10 frames eased) at every switch. Every version still snapped now and then on a stop, because the game's
blend of two moving clips can't be seen from outside, only guessed.

So the mod removes the drift instead. PouchPlayer's tree has bone blenders (two children: the first drives the bones in
its bone group, the second everything else), and Link's own tree has a bone group for just his top bone, `Skl_Root`. The
mod puts the one free blender (node 340, an unused bow pose) over all of `PauseMenuWait`: `Skl_Root` and `Root` come
from a standing clip (`Nml_Wait`), the rest from his tree. Its bone group is the Lift group (only for carrying things),
weighted on those two bones alone. Two things to get right: a bone group's own default weight (`Unknown`) covers the
bones it doesn't list, and Lift's was 1 (his arms took the standing pose: he ran like Naruto, hands straight behind
him); and `Skl_Root` alone left the drift in, it's in `Root`. No more cancelling in the patch, no more snaps.

A second blender does the same over the `UseItem` command (his emotes and his take-off): the take-off clip lifts `Root`
like a real jump, and that came on top of the patch's own jump physics, so he went up twice as high. It's node 229, a
blender only reachable from an idle branch's weapon cases 2 and 3, which the idle never sees (2 and 3 are his run and
sprint, straight from the root), with 340's settings copied over. Traced: his jump is 0.65 m and 0.38 s, yours 0.63 m
and 0.40 s.

With that blender over `UseItem`, the game stopped ending his emotes: it fades him back to `PauseMenuWait` when the
command's clip is done, and the blender's standing side is a loop that never ends. He held each emote's last pose until
a backup timer ran out (a startle: 0.7 s of clip, 5.5 s in all). Now an emote also ends when its clip has sat at its
last frame (loop position 1) for two frames. And shoved in the middle of one, he lets it go and steps out of your way,
instead of sliding along in its pose.

`Root` also carries the run's bounce, so without it he ran level, "pressed". The patch puts the bounce back: twice a
stride on his loop, 4 cm (Camille, by eye), less on the walk; the sprint keeps its own in other bones. `survey lonk bob
<metres> <phase>` changes it while playing.

Switching between run and sprint still made a little snip: the new clip started its loop from 0, so his body jumped
back by however far into the old loop he was. The Player's own run and dash leaves avoid that with "InitialFrame"
nodes (start where the previous animation was in its loop). Two of PouchPlayer's leaves have one too, but it did
nothing here (the loop still restarted, measured in the trace). What works is the command's first node's `Is Sync`:
with it on, every switch keeps the loop phase (normalized), and the trace shows the loop running straight through run
-> sprint -> run. Only a command's first node can do it (those are the only selectors with Sync Controls), and it
reaches through everything below, so anything else under it starts wherever his loop was. (It still works with the
bone blender over it: in the trace a sprint -> run switch carries on from the sprint's loop position.) (That's why the emotes are
a command of their own now, below. The party is still under it and waits for his loop to come round.)

More emotes than slots: the selector only has cases 1 to 5, and adding cases crashes. But PouchPlayer has a second
full-body command, `UseItem`: a selector on the blackboard *string* `UseItem` (eat food, eat a meal, eat a skewer, eat
something gross, drink, use a fairy...), one clip each. The menu's AI never writes that string (it writes `Arrow`,
through the setter at vtable `+0x28`), so the patch picks his emote with it: three eating clips stay as they are (a
bite, a meal, a gross one), and five get renamed: `DemoLookAround` (his look around), `DemoLookUp`, `Nml_Wait_Jump` (his
take-off), `Demo_Get_Cooking_Bad` (a sulk) and `Demo_Surprise` (his startle). For an emote the patch starts the
`UseItem` command in his body's slot (the request names the slot: `0x4dc628` writes the rate to
`[as+0x20] + slot x 0x48 + 0xd0` and starts the command there). A command of its own starts at its first frame at once
(traced: frame 0.7 of 29); when the clip's done, the game fades him back to `PauseMenuWait` by itself (the ASB's
`UseItem` -> `PauseMenuWait` transition, 10 frames), and that's when the emote ends. Before, the emotes went through
`PauseMenuWait`'s case 1, under the root's sync: each one waited up to 40 frames for his loop to come round (running on
the spot), an emote that started at the very end of a loop played only its last frame, and a look around was a second of
clip and three of standing in its last pose. His face follows on its own: the game switches his face slot to
`FaceUseItem`, the eating expressions.

## Time

The game animates by real time, and it doesn't always run at 60 frames a second: on the sky island it ran at about 40.
Lonk used to count 1/60 of a second a frame, so there he moved at two thirds of his speed under legs going at full
speed, and fell at less than half his gravity. Now his speed, braking, jumps, falls, turning and smoothing use the
frame's real length, read off his own clip clock: `+0x1ec` counts the frame's real time in 30ths of a second, whatever
rate we set (checked by tripling the rate). It's steadier than the wall clock between two of our frames (23 to 25 ms
where the wall clock said 17 to 37). His timers (moods, emotes, cooldowns, "lost for 3 seconds") count real 60ths of a
second too. A standing jump at 40 frames a second: 0.46 s in the air, 0.63 m up (Link's: 0.4 s, 0.64 m).

When the game's paused (the menu), his clip clock stops, and so does yours: he waits. Before, his clip froze
mid-stride while he ran on (6 m in a 3-second menu) and even started his arrival emote in there.

He watches the player's animation slots the same way his own are read (`[as+0x20]`, 0x48 apart, the command's name at
`+0x10`): slot 0 is the body (`Wait`, `Move`, `Jump`, `Land`...), slot 4 the face, then skin colour and the Zonai arm.
Slots 0 to 3 are the body (the lower body, the upper body and two more; an action can play in one or several: the
whistle, `HorseCall`, only plays in slot 1). When one of them changes he reacts: `Jump`, `BackFlip`, `SideStep`,
`FrontRoll` (copycat jump), `Damage*`, `Freeze`, `Eaten` (startle), `CutS1`..`CutS4`, `CutSF`, `CutDash`, `ChargeAttack*`
within 3 m and facing him (he runs), `HorseCall` (he comes: buddy mode), `OpenTreasureBox*`, `Get`,
`GetCookingGood/VeryGood` (party), `GetCookingBad` (yuck), `Climb*`, `Glide`, `ParasailGlide` (looks up),
`UltraHandStart`, `LookAround*`, `Talk`, `TalkHello` (looks around). The names come from the Player's ASB command list (532 of them). Tested: jump, a
spawned Bokoblin hitting the player (`DamageL`, `DamageS`), the whistle, and a sword swing at him (`CutS1`).

The copycat jump: on the player's `Jump`, Lonk starts the jump clip, and once it's actually playing his feet get 6.4 m/s upwards and the falling code does the rest:
0.64 m up, 0.4 s in the air, like Link's own (traced frame by frame from the player's height: that takes gravity of
32 m/s², about 3 times the real thing; with real gravity he floated for a second and Camille noticed straight away,
and my first, coarser measurement still had him a little high). He takes off on the same frame as you. Shoved for 1.5 seconds (you within 1.2 m, moving), he sulks.

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

Outfits: every armor set uses one number for its three pieces (`Armor_1046_Head/Upper/Lower` is the froggy set), and the
names come from the game's own text (`Mals/USen.Product.142.sarc.zs`, `ActorMsg/PouchContent.msbt`, `Armor_*_Name`).
Some names appear under several numbers (upgraded copies), so `survey lonk outfit` uses the lowest one of each.

Weapons work the same way: slots 0 (weapon), 7 (bow) and 8 (shield), and the empty name copies yours. The game adds the
sheath and the quiver by itself. All of an equipment user's pieces sit in one array of ActorLinks from `eu+0x20`, 0x18
apart, in their own order (weapon 0, bow 3, shield 4, head 8, upper 9, lower 10, sheath 11, quiver 14, the arm 18; found
with `survey peek euscan`), and every one of them gets put back in the world scene each frame, like the clothes. Without
that, the weapons were the ones that showed up near his legs the first night.

His weapons came out drawn whenever he moved: the menu's AI reads `HoldAnimationType` as the type of weapon he holds,
and his walk, run, sprint, party and fall were cases 1 to 5, so moving, the menu drew his sword and shield for him
(standing, at 0, they went back on his back). The mod moves his clips to cases 11 to 15, which the menu doesn't know,
and the patch adds the 10: they stay on his back. (The menu's own sheathe is `OneShotChangeDrawnSwordStateForPouchPlayer`,
run method `0x2507a80`: with nothing held it calls `0x4f5194(eu, link, 0)` on the weapon (0), the shield (4) and the bow
(3); `survey lonk sheathe` does the same: it changed their states, not where his sword was.)

As your twin he draws when you draw and puts them away when you do: each frame, his weapon (0) and shield (4) follow
yours, through the game's own draw `0x4f5700(eu, link)` and put-away `0x4f5194(eu, link, 0)`, checked with
`0x3e322c(eu, link)` (is it drawn). Not yet: the reach for his back (Link plays a draw and a sheathe animation; his just
move), and fused weapons (he carries the plain one).

Weapons out, he walks and runs like you do with them out: Link's tree lays the weapon's `_Upper` run clip
(`Sword_Move_Run_Upper`, `Lsword_...`, `Spear_...`) over his run's arms. Lonk's walk and run cases go through a bool
selector on `IsAttachedWeapon`, which the patch sets when his weapons are out, then string selectors on `Arrow` (the
menu's only for the bow), which the patch sets to the weapon's kind from its name. All of it is nodes of the menu's
weapon poses he never reaches. He plays that clip as his whole body: laid over his run with a bone blender, the
blender sat under the stand-still blender and the run's drift came back in (tested with the run on both sides of the
blender: still drifting, so it's the nesting, not the clip). The clip's own legs are a little plainer than the run's,
and its own bounce is smaller, so the patch's bounce is a quarter bigger with weapons out.

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
how he walked up walls and onto cave roofs. Floor lower than his feet and he falls (Link's 32 m/s², down to that floor);
floor too steep (normal y under 0.6) and he doesn't step onto it.

The same raycast steers him: before each step he probes 1 m ahead at chest height (anything there is a wall) and at knee height, and if something's there (and it isn't
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
Link's height. Up a staircase or off on a run of his own is fine. Following you for 4 s without getting any closer
(pacing along a ledge he can't get over) counts as lost too. The "behind" mood's teleport uses the same spot.

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
  walls, so he walks off and the falling code takes him down. When you're 0.6 to 7 m above and within 20 m, and he's been
  blocked for a quarter of a second or hasn't got any closer for three quarters, he jumps, but only right at the foot of the ledge, the wall within 1.2 m his way (Camille found it first: when
  he paced along a ledge, jumping made him copy the jump, and that got him over): upward speed sqrt(2 g (height +
  0.6 m)), the jump clip, and he keeps heading for you in the air (aiming 0.6 m from you, so he lands beside you, not at
  the foot). The knee-high wall check rises with his feet, so he moves on once he's above the edge. 4 s between tries.
- Hide and seek (a mood of its own, weight 10): 24 directions, 6 to 14 m, each walkable in a straight line
  (`path_free`, at least 6 m), with floor at the end, and hidden: a ray from your eyes (1.6 m up) to his chest there
  hits something at least 0.8 m before it. He runs there and faces you; within 3 m once he's there, you've found him
  (startle, flee; counted from the start, he was found on the spot every time, since he starts right beside you);
  after 25 s he gives up and follows you again.
- A wander, after its emote and a couple of seconds' rest, goes on somewhere else (with the brain off it used to be one
  trip, then standing there for the rest of the hour).
- Block can't always get in front of you (a wall in the way): stuck for a second there, he follows you instead. Before,
  he got "lost", popped behind you, and tried again, every 3 seconds.
- Buddy mode, both standing still for 7 s: now and then he looks up, looks around or snacks.

## What he costs

The `lonk stats` line (every 10 s) also says how long the survey's frame tick took: about 0.2 ms a frame on average
with the whole brain running (floor and wall rays, the enemy scan, dressing, the animation), 1 ms at worst, on an M4
MacBook Air. A frame at 60 fps has 16.7 ms.

## Coming back

Every frame each body piece's name is read back from the actor (`actor+0x218`); a piece that no longer reads back is
forgotten. If that was PouchPlayer, Lonk respawns two seconds after the player stands somewhere real again (the player
actor that exists on the loading screen sits at the origin, so that doesn't count), whether his brain runs or a single
mood does (with the brain off he used to stay gone: Camille fast-travelled and lost him). Nothing of the old body
carries over: its animation slot (freed with it), a jump or an emote in progress. Tested by dropping Link from 150 m:
game over, Continue, and he's back, dressed, picking his next mood.

## The brain

Every 6 to 12 seconds a weighted dice roll picks a behaviour: stalk 25, buddy, block, behind, wander and gift 15 each,
never two gifts in a row. Buddy walks 1.6 m to one side of Link at Link's own (smoothed) speed. A gift spawns an apple
(`Item_Fruit_A`), a fish (`Item_FishGet_A`), a monster part (`Item_Enemy_01`) or a `BarrelBomb` next to Link through the
same spawn call,
then Lonk celebrates for two and a half seconds and flees for four.


What you're doing changes his dice: moving (your speed averaged over a few seconds above 3 m/s) he mostly buddies up or
follows you (wandering off or hiding would only leave him behind); standing still for 10 s he plays more (wander, hide
and seek, gifts, creeping up behind you); freezing or too hot, gifts get a big bonus, since that's when he brings a
pepper or a hydromelon.

## Jumping

Link's own jump is three commands in a row (`Jump`, `Fall`, `Land`), and the Player's AI switches between them. Lonk
has two commands, so the patch does the switching: the take-off clip (`Nml_Wait_Jump`, the `UseItem` command, at rate 1
like in the Player's tree, where it has no frame controller) when he leaves the ground, and `Fall_Loop` (case 5 of
`PauseMenuWait`'s selector) once he's past the top, or after a fifth of a second off a ledge. As its own command the
take-off plays from its first frame (it used to start at the run's loop position under the root's sync, so it was over
in a frame or two and he held its last pose the whole way up). His feet touching the floor is the landing (that frame
used to count as still falling, and the next one went back to the take-off clip for a frame, after every jump).

In the air he follows Camille's rule: he copies the player's take-off once, then keeps the way and speed he took off
with (stopping only at a wall: it used to be the ledge check too, so over any drop he stopped dead mid-air), ignores the player and every other reaction, and only lands when his feet reach a
floor. Jumping off the run used to switch to the running jump clip, which moves forward by itself, and nothing undid
that (jumps had no root compensation): most likely why he snapped back on landing. Every jump uses the standing
take-off now.

## His hair

The ponytail is cloth on the hair piece (`Armor_999_Head`, the same as yours), and the game doesn't simulate its
inertia: each cloth part has `ClothReaction` settings keyed on how fast its owner moves (`ReactionSpeed` 5, 15, 20, each
with its own drag and wind). His hung still. He's placed every frame with `forceSetMatrix` (main `0x69a18c`), and with
flags 0 the game takes that as a teleport and resets his cloth: as far as it knew, he never moved. With flags 1 his hair
moves with him (Camille: it works). A real jump of over a metre in a frame (popping back behind you, a respawn) still
goes as a teleport, so his hair doesn't whip across the map with him. (The pause menu's own set-transform, `0x2ba758`,
didn't put him where asked: he stood on a boulder metres away.)
