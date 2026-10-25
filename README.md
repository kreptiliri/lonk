# Lonk

A second Link for *Tears of the Kingdom*. He lives in your world, follows you around, and does his own thing.
Right now his own thing is mostly being in the way.

The goal is a real clone: a Link who walks, reacts, picks fights, gets in trouble and survives everything, with a
mind of his own. What exists today is the first step: a body in the world, moving on its own, driven by a simple
brain. Everything is still being tested.

Runs on the [MacNativeGames](https://github.com/ly05010419/MacNativeGames) native macOS port, game version 1.4.3.

## Where he's at

- **He exists.** I spawn him with the game's own actor manager, in the open world, next to you.
- **He has a body, Link's own.** Link himself can't be spawned twice, so he's the Link from the inventory screen. That
  one looked invisible outside the menu, but it turned out he was just teleporting himself to the middle of the map
  every frame. Pinned next to you, he's there, standing in his idle pose.
- **He gets dressed.** Hair, his Zonai right arm and his clothes are all separate pieces of equipment in this game, and
  the inventory Link never puts any on outside the menu. Now he dresses himself the way the pause menu does it, a second
  after he spawns: his hair, his arm and Link's default outfit (which is his underwear, so far).
- **He used to be mannequins.** Before that he was three armor-shop mannequins stacked on one spot, which crashed the
  game when you walked up to them (they went looking for the item they were selling). That fix is still in, and
  `survey drop` gets rid of the mannequins.
- **He walks and runs.** Every frame he moves over the real terrain toward wherever his brain says, with Link's own
  walk and run animations picked from his speed, facing where he's going, and he turns to face you when he stops. The
  animations need a small RomFS mod (see "Trying it"); without it he sweats or shivers his way around instead.
- **He has a (very small) brain.** Every few seconds he decides what to do:

| Mood | What he does |
|---|---|
| stalk | walks up and stares at you from a step away |
| block | sprints into your path |
| gift | drops an apple at your feet, sometimes a bomb barrel, and runs |
| behind | is suddenly standing right behind you |
| wander | forgets you exist |

## Where he's going

- Real clothes: picking an actual outfit makes him vanish for now
- Doing things, not just standing near you: fighting, climbing, using items, breaking stuff
- Never dying, whatever you do to him
- A smarter brain

None of this is promised, it's what I'm working toward.

## What I built

Only my own code is here: a patch for the MacNativeGames runtime, plus notes. No game files, keys or extracted game
data. You need your own legally dumped copy of the game, like the port itself does.

- `patches/lonk.patch`: the changes to `games/totk/runtime/world_survey.c` and `game_version.h`. Spawning, the shop
  crash fix, movement and the brain.
- `patches/BASE_COMMIT`: the MacNativeGames commit the patch applies to.
- `apply.sh`: applies the patch to a MacNativeGames checkout.
- `mod/make_mod.py`: builds his animation mod from your own game files (nothing from the game is in this repo).
- `docs/how-it-works.md`: the reverse-engineering notes. How I found the spawn function in 1.4.3, why the mannequins
  crashed, how he moves.

## Trying it

He only runs in the port's test mode, on a copy of your save.

1. Build MacNativeGames' TotK app at the commit in `patches/BASE_COMMIT`.
2. `./apply.sh /path/to/MacNativeGames`, then rebuild.
3. Build the animation mod: `python3 mod/make_mod.py /path/to/MacNativeGames <MacNativeGames build>/extracted/v143/romfs
   /path/to/dt-12345/asb <mod folder>` (needs [dt-12345/asb](https://github.com/dt-12345/asb) and
   `pip install zstandard mmh3`).
4. Start a test session with `TOTK_SURVEY=1`, `TOTK_SLOT_OWNER=<anything but user>`,
   `TOTK_PROFILE_DIR=<a copy of your save folder>`, `TOTK_INPUT_FILE=<commands.txt>` and `TOTK_ROMFS_MODS=<mod folder>`.
5. Load your save and add these lines to the commands file:

```
survey spawn lonk PouchPlayer 4 0 0
survey lonk brain 36000
```

He starts his idle animation and gets dressed on his own. `survey equip <slot> <ArmorName>` puts one piece on him
(9 head, 10 upper, 11 lower, `-` for the default), and `survey dress` redoes the whole outfit. The old mannequin body
still works (`survey spawn m1 Mannequin_001_Upper` and friends), and `survey drop <name start|all>` removes pieces from
him again.

You can also force one mood with `survey lonk <stalk|block|behind|wander|gift|flee> <frames>`, and stop him with
`survey lonk stop`.

## Known issues

- He only has his underwear. Real armor (`survey equip 10 Armor_001_Upper`) makes him disappear until he's back in
  the defaults.
- His feet slide a bit: the walk and run play at one speed whatever his actual speed is.
- With the mod installed, the inventory Link walks or runs in place in the pause menu when you're somewhere cold or hot.
- The terrain height ignores bridges, buildings and sky islands, so there he falls back to your footsteps. On a sky
  island, wandering away from you, that can leave him buried up to the neck.
- He'll happily block you while standing on thin air over a cliff.
- Wandering off on his own, he walks straight through rocks and trees.
- He jumps when you jump. He has no idea why.

## License

MIT, see [LICENSE](LICENSE). The patch modifies MacNativeGames, which is also MIT
(Copyright (c) 2026 MacNativeGames contributors), see [NOTICE](NOTICE).
Not affiliated with Nintendo.
