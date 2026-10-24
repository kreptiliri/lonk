# Lonk

A stupid, unkillable second Link for *The Legend of Zelda: Tears of the Kingdom* (1.4.3), running on the
[MacNativeGames](https://github.com/ly05010419/MacNativeGames) native macOS port.

Lonk shows up, stares at you, stands in your way, drops apples (and sometimes bomb barrels) at your feet, runs off,
and teleports behind you when you're not looking. He's an empty suit of clothes and he's dressed better than you.

> Status: early and test-mode only. Lonk runs inside the port's survey test mode, on a copy of your save.

## What's in here

Only our own code: a patch for the MacNativeGames runtime, plus notes. **No game files, keys, or extracted game data**
are included or needed beyond what the port itself already requires from your own legally dumped copy.

```
patches/lonk.patch     changes to games/totk/runtime/world_survey.c and game_version.h
patches/BASE_COMMIT    the MacNativeGames commit the patch applies to
docs/how-it-works.md   reverse-engineering notes (actor spawning, the "ForSale" crash, movement)
apply.sh               applies the patch to a MacNativeGames checkout
```

## How it works (short version)

- **Body:** the game's own `ActorMgr::requestCreateActorAsync` spawns three armor-shop mannequin pieces
  (`Mannequin_001_Head/Upper/Lower`). Stacked, they look like a Link with nobody inside.
- **Crash fix:** spawned mannequins crash the game when you walk up, because they look for a "ForSale" link to the
  item they sell and don't have one. The patch adds a null check to that count (test mode only).
- **Movement:** every frame all pieces are placed at one anchor point with the game's `forceSetMatrix`, facing you.
  Height comes from your recent footsteps, since you always walk on the ground.
- **Brain:** a dice roll every 6 to 12 seconds picks a behaviour.

| Behaviour | Chance | What he does |
|---|---|---|
| stalk | 30% | walks up and stares at you from 1.5 m |
| block | 20% | sprints to the spot right in front of you |
| gift | 20% | walks up, drops an apple (75%) or a bomb barrel (25%), runs away |
| behind | 15% | teleports right behind you, then creeps closer |
| wander | 15% | forgets you exist and wanders off |

## Use

1. Build MacNativeGames' TotK app as its README describes, at the commit in `patches/BASE_COMMIT`.
2. `./apply.sh /path/to/MacNativeGames` and rebuild.
3. Start a test session on a **copy** of your save, with `TOTK_SURVEY=1`, `TOTK_SLOT_OWNER=<anything but user>`,
   `TOTK_PROFILE_DIR=<save copy>` and `TOTK_INPUT_FILE=<commands.txt>`.
4. Load your save, then append commands to the input file:

```
survey spawn m1 Mannequin_001_Upper 10 0 0
survey spawn m2 Mannequin_001_Lower 10 0 0
survey spawn m3 Mannequin_001_Head 10 0 0
survey lonk brain 36000
```

Other commands: `survey lonk <stalk|block|behind|wander|gift|flee> <frames>`, `survey lonk stop`,
`survey stalk <frames> [m/s [stop m]]`, `survey ground <trail|player|physics>`.

## Known issues

- On hills he can still float or sink a little (no real ground query yet).
- Block happily stands over cliffs, in mid-air.
- Each piece still has its own physics, so sometimes the pants arrive first.

## License

MIT, see [LICENSE](LICENSE). The patch modifies MacNativeGames, which is MIT licensed
(Copyright (c) 2026 MacNativeGames contributors); see [NOTICE](NOTICE).
Not affiliated with Nintendo. You need your own legally obtained copy of the game.
