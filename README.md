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
  every frame. Pinned next to you, he's there: bald, in his underwear, standing in his idle pose. His hair counts as
  part of the outfit, so it's missing until I figure out how to dress him. So is his right arm, which is a separate
  piece in this game.
- **He used to be mannequins.** Before that he was three armor-shop mannequins stacked on one spot, which crashed the
  game when you walked up to them (they went looking for the item they were selling). That fix is still in, and
  `survey drop` gets rid of the mannequins.
- **He moves.** Every frame he walks over the real terrain toward wherever his brain says, and turns to face you.
- **He has a (very small) brain.** Every few seconds he decides what to do:

| Mood | What he does |
|---|---|
| stalk | walks up and stares at you from a step away |
| block | sprints into your path |
| gift | drops an apple at your feet, sometimes a bomb barrel, and runs |
| behind | is suddenly standing right behind you |
| wander | forgets you exist |

## Where he's going

- Clothes, hair and his right arm back
- Walking and running animations, not sliding around in his idle pose
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
- `docs/how-it-works.md`: the reverse-engineering notes. How I found the spawn function in 1.4.3, why the mannequins
  crashed, how he moves.

## Trying it

He only runs in the port's test mode, on a copy of your save.

1. Build MacNativeGames' TotK app at the commit in `patches/BASE_COMMIT`.
2. `./apply.sh /path/to/MacNativeGames`, then rebuild.
3. Start a test session with `TOTK_SURVEY=1`, `TOTK_SLOT_OWNER=<anything but user>`,
   `TOTK_PROFILE_DIR=<a copy of your save folder>` and `TOTK_INPUT_FILE=<commands.txt>`.
4. Load your save and add these lines to the commands file:

```
survey spawn lonk PouchPlayer 4 0 0
survey lonk brain 36000
```

He starts his idle animation on his own. The old mannequin body still works (`survey spawn m1 Mannequin_001_Upper`
and friends), and `survey drop <name start|all>` removes pieces from him again.

You can also force one mood with `survey lonk <stalk|block|behind|wander|gift|flee> <frames>`, and stop him with
`survey lonk stop`.

## Known issues

- He's bald, in his underwear, and missing his right arm.
- He slides everywhere in his idle pose.
- The terrain height ignores bridges, buildings and sky islands, so there he falls back to your footsteps.
- He'll happily block you while standing on thin air over a cliff.
- Wandering off on his own, he walks straight through rocks and trees.
- He jumps when you jump. He has no idea why.

## License

MIT, see [LICENSE](LICENSE). The patch modifies MacNativeGames, which is also MIT
(Copyright (c) 2026 MacNativeGames contributors), see [NOTICE](NOTICE).
Not affiliated with Nintendo.
