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

`PauseMenuWait` picks its clip from the ASB blackboard every update: the float `Temperature` chooses `Nml_Cold_Wait`
(< 0), `Nml_Wait` (0) or `Nml_Hot_Wait` (> 0), and the bool `Stamina` set to false turns the middle one into
`Nml_Tired_Wait`. So:

- the RomFS mod (`mod/make_mod.py`, built with [dt-12345/asb](https://github.com/dt-12345/asb)) points the cold and hot
  idles at `Nml_Move_Walk` and `Nml_Move_Run`, and the tired one at `Nml_Move_Dash`. PouchPlayer already loads all of
  Link's animations.
- the patch plays `PauseMenuWait` once and then sets the blackboard from his speed every frame: idle below 0.4 m/s,
  walk up to 3.2, run up to 5.5, dash above (the bands overlap by 0.3 m/s, and a new gait has to hold for 12 frames,
  because every switch restarts the clip). Every frame, because the game sets `Temperature` itself from where you are:
  set only when his gait changed, it got overwritten at once, so he only walked where it's cold (with the cold breath
  and red cheeks of the cold idle, which come with the node, not the clip). The clip plays at his speed divided by the clip's own (estimated) speed, written to the
  rate of the body's slot (`slot+0xd0`). The game routes each command to its own slot: 0 is the face, 1 the body, 2 the
  skin colour. Ints go through vtable `+0x30`, bools through `+0x40`, the same way.
- the int `HoldAnimationType` (the weapon he'd be holding in the menu) set to 5, shield only, makes the idle play the
  menu's `PauseMenu_Equip_Shield`, which the mod turns into the cooking celebration `Demo_Get_Cooking_VeryGood`. That's
  his party after a gift. 2 and 3 (two-handed sword, spear) do the same with their equip clips, turned into
  `DemoLookAround_Loop` (he arrives somewhere on a wander and looks around) and `Demo_Surprise` (he's creeping up behind
  you and you turn round). Every other clip Link has can be reached the same way, one idle branch at a time. The blackboard is `[as+0x40]` (`as` being his animation state, the same chain `0xba8ed0` walks), and its
  vtable `+0x38` sets a float by name: `set(bb, &{"Temperature", 0}, value)`, the way the menu's own
  `ExecutePouchPlayerSetASBBParameter` (`0x241cc08`) does it.

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
  vanish. They don't follow his animation yet: he's stiff.

Real armor doesn't work yet. What's known:

- Every real piece tried (a hood, two tops, trousers) is invisible, and the body under it gets hidden as it should, so
  he becomes a floating face. The default pieces, the hair and the arm all draw.
- The same tunic spawned on its own draws fine, in its T-pose. Its draw instance's flags (`instance+0x14`, also at
  `model+0x2b4`) end in `0x09`; equipped, they end in `0xf8`. Bit 0 looks like "draw in the world view": setting it
  makes the equipped tunic appear, crumpled at his feet, so its bones aren't being posed at all.
- Real armor has its own AS, Animation and ColorVariation components, which the defaults don't. My guess is that its
  skeleton follows its own animation system, which only gets driven in the menu.

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
a walkable slope, judged by the hit normal at `+0x30`) he tries 45 and then 90 degrees to one side, then the other,
starting with whichever side worked last so he doesn't dither. A ledge counts too: no floor within 2.5 m below his feet
0.8 m ahead. Boxed in, he waits.

Stranded for 3 seconds (5 m above or below Link, 30 m away, trying to move and not moving, or no floor), he pops back
next to Link: behind him, else to a side, else in front, wherever a ray finds flat floor at Link's height. The "behind"
mood's teleport uses the same spot.

Walking through Link puts the mannequin's collision above Link's head, which the game reads as a low ceiling, and
forces a crouch. Lonk keeps 1.1 m away and slides around instead, unless that would put him in a wall or off a ledge
(which is how you could shove him through walls).

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
