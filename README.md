# Lonk

A second Link for *Tears of the Kingdom*. He lives in your world, follows you around, and does his own thing.
Right now his own thing is mostly being in the way.

The goal is a real clone: a Link who walks, reacts, picks fights, gets in trouble and survives everything, with a
mind of his own. What exists today is the first step: a body in the world, moving on its own, driven by a simple
brain. Everything is still being tested.

Runs on the [MacNativeGames](https://github.com/ly05010419/MacNativeGames) native macOS port, game version 1.4.3.

## Where he's at

- **He exists.** I spawn him with the game's own actor manager, in the open world, next to you.
- **He has a body.** Link himself can't be spawned twice, and the inventory Link is invisible outside the menu, so for
  now he's built from the armor-shop mannequins: a hood, a tunic and trousers stacked on one spot. From a distance
  he's Link with nobody inside.
- **He doesn't crash the game anymore.** Mannequins expect to belong to a shop. When you walked up to one, the game
  went looking for the item it was selling, found nothing, and crashed. I patched that check.
- **He moves.** Every frame he walks over the ground toward wherever his brain says, and turns to face you.
- **He has a (very small) brain.** Every few seconds he decides what to do:

| Mood | What he does |
|---|---|
| stalk | walks up and stares at you from a step away |
| block | sprints into your path |
| gift | drops an apple at your feet, sometimes a bomb barrel, and runs |
| behind | is suddenly standing right behind you |
| wander | forgets you exist |

## Where he's going

- A proper Link body with animations, instead of mannequins on stands
- Walking on the real ground, not on your footsteps
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
survey spawn m1 Mannequin_001_Upper 10 0 0
survey spawn m2 Mannequin_001_Lower 10 0 0
survey spawn m3 Mannequin_001_Head 10 0 0
survey lonk brain 36000
```

You can also force one mood with `survey lonk <stalk|block|behind|wander|gift|flee> <frames>`, and stop him with
`survey lonk stop`.

## Known issues

- On hills he still floats or sinks a little.
- He'll happily block you while standing on thin air over a cliff.
- Each piece of him still has its own physics, so sometimes his trousers arrive before he does.

## License

MIT, see [LICENSE](LICENSE). The patch modifies MacNativeGames, which is also MIT
(Copyright (c) 2026 MacNativeGames contributors), see [NOTICE](NOTICE).
Not affiliated with Nintendo.
