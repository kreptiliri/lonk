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
so the patch starts `Nml_Wait` itself, the way the game's own C++ callers do: a 0x30-byte request
`{actor, name, slot 0, rate 1, -1, -1, 1}` passed to `0x4dc628`.

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
  They follow his skeleton by themselves.

Real armor (`Armor_001_Upper`, the Hylian tunic) makes the whole figure disappear, hair included, and putting the
default back brings him back. Not solved yet.

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

Height comes from the game's terrain query, the one behind the AI node `QueryTerrainGetGroundHeight`:
`T = [main+0x3add550]`, `scene = 0x2b7332c(T, pos, 1, 0, 300.0)`, then `0x5db4c0(&height, xz, scene, -1, 0, 1, 0)`
answers 1 or 2 on success. It's the heightmap only, so where it doesn't answer (or answers far from Link's height,
like on a bridge) Lonk falls back to Link's own footsteps: a ring of his last 512 positions, one every 25 cm, using the
nearest one. Letting gravity do it doesn't work, because setting the transform every frame keeps gravity from ever
catching up, and he sinks into hills.

Walking through Link puts the mannequin's collision above Link's head, which the game reads as a low ceiling, and
forces a crouch. Lonk keeps 1.1 m away and slides around instead.

## The brain

Every 6 to 12 seconds a weighted dice roll picks a behaviour: stalk 30, block 20, gift 20, behind 15, wander 15, never
two gifts in a row. A gift spawns `Item_Fruit_A` (75%) or `BarrelBomb` (25%) next to Link through the same spawn call,
then Lonk flees for four seconds.
