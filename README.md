# Lonk

A second Link for *Tears of the Kingdom*. He lives in your world, follows you around, and does his own thing: he copies
your jumps, picks fights he can't finish, hides from you, dresses like you, and brings you a pepper when you're cold.

The goal is a real clone: a Link who walks, reacts, picks fights, gets in trouble and survives everything, with a mind
of his own. What exists today is a body in the world, moving and reacting on its own, driven by a simple brain.
Everything is still being tested.

Runs on the [MacNativeGames](https://github.com/ly05010419/MacNativeGames) native macOS port, game version 1.4.3.

## Where he's at

- **He has a body, Link's own.** Link himself can't be spawned twice, so he's the Link from the inventory screen, which
  I spawn with the game's own actor manager. That one looked invisible outside the menu, but it turned out he was just
  teleporting himself to the middle of the map every frame. Pinned next to you, he's there.
- **He gets dressed.** Hair, his Zonai arm, clothes and weapons are all separate pieces of equipment in this game, and
  the inventory Link never puts any on outside the menu. He dresses himself the way the pause menu does: his ponytail,
  his arm and his underwear (his look), or, as your twin, your exact outfit with your sword, bow and shield on his back.
  The game drags every piece back into the menu's 3D scene each frame, so he pulls them back out each frame.
- **He runs and sprints** with Link's own animations, at Link's own speeds, over the real ground (physics raycasts, so
  sky islands, caves and bridges count), around walls, off ledges after you, and up onto them when you're up there.
- **He sees.** A ring of rays tells him what's around him: enemies, you, things in the way. He also reads what you're
  doing from your own animation commands.
- **He doesn't stay gone.** You die, he's back a couple of seconds after you are.
- **He has a (small) brain.** Every few seconds he decides what to do, and what you're doing changes his dice: on the
  move he sticks with you, standing around he plays.

| Mood | What he does |
|---|---|
| stalk | walks up and stares at you from a step away |
| buddy | walks beside you at your pace (your run or your sprint), looking where you look; gets bored when you stand still |
| block | sprints into your path |
| gift | drops something at your feet (an apple, a fish, a monster part, a bomb barrel; a pepper if you're freezing, a hydromelon if you're too hot), celebrates, and runs |
| behind | is suddenly standing right behind you, and startles if you turn around |
| wander | wanders off somewhere he can actually get to, then looks around, looks at the sky or has a snack |
| hide | runs off to a spot you can't see; find him and he bolts, give up and so does he |
| fight | (when he sees an enemy) sprints at it, plants a bomb barrel next to it, panics and runs; lighting it is your job |

And whatever the mood, he watches you: you jump, he jumps a beat later; you get hit, he startles; you open a chest or
cook something great, he celebrates; you cook something bad, he's grossed out; you climb or glide, he looks up at you.
Shove him enough and he sulks.

## Where he's going

- Doing things, not just reacting: climbing, swimming, actually fighting, using items, breaking stuff
- Never dying, whatever you do to him
- A smarter brain (maybe one that talks)
- Couple outfits of his own

None of this is promised, it's what I'm working toward.

## What I built

Only my own code is here: a patch for the MacNativeGames runtime, plus notes. No game files, keys or extracted game
data. You need your own legally dumped copy of the game, like the port itself does.

- `patches/lonk.patch`: the changes to `games/totk/runtime/world_survey.c` and `game_version.h`: spawning, dressing,
  animation, the raycasts, the brain, the hot reload, and a crash fix for spawned shop mannequins.
- `patches/BASE_COMMIT`: the MacNativeGames commit the patch applies to.
- `apply.sh`: applies the patch to a MacNativeGames checkout.
- `mod/make_mod.py`: builds his animation mod from your own game files (nothing from the game is in this repo).
- `tools/plugin.sh`: builds his code as a hot-reload plugin (see below).
- `docs/how-it-works.md`: the reverse-engineering notes. How I found the spawn function in 1.4.3, how he gets dressed,
  how an inventory Link learned to run, how he finds the ground and sees enemies.

## Trying it

He only runs in the port's test mode, on a copy of your save.

1. Build MacNativeGames' TotK app at the commit in `patches/BASE_COMMIT`.
2. `./apply.sh /path/to/MacNativeGames`, then rebuild.
3. Build the animation mod: `python3 mod/make_mod.py /path/to/MacNativeGames <MacNativeGames build>/extracted/v143/romfs
   /path/to/dt-12345/asb <mod folder>` (needs [dt-12345/asb](https://github.com/dt-12345/asb) and
   `pip install zstandard mmh3`).
4. Start a test session with `TOTK_SURVEY=1`, `TOTK_SLOT_OWNER=<anything but user>`,
   `TOTK_PROFILE_DIR=<a copy of your save folder>`, `TOTK_INPUT_FILE=<commands.txt>` and `TOTK_ROMFS_MODS=<mod folder>`.
5. Load your save and add this line to the commands file:

```
survey lonk start
```

That spawns him 4 m in front of you and runs his brain for an hour.

### Commands

| Command | |
|---|---|
| `survey lonk start` | spawn him and start his brain |
| `survey lonk twin` / `survey lonk naked` | dress him like you (and follow your changes) / back to his underwear |
| `survey lonk <mood> <frames>` | force a mood: `stalk`, `buddy`, `block`, `behind`, `wander`, `gift`, `flee`, `party`, `fight`, `hide` |
| `survey lonk emote <name>` | `look`, `lookup`, `eat`, `meal`, `drink`, `yuck`, `jump`, `sulk`, `surprise` |
| `survey lonk goto <right> <forward> [m/s]` | send him somewhere (metres from you) |
| `survey lonk stop` | stop his brain |
| `survey equip <slot> <Name> [dye]` | put one piece on him (0 weapon, 7 bow, 8 shield, 9 head, 10 upper, 11 lower; `-` copies yours) |
| `survey spawn prop <Name> [forward [sideways [up]]]` | spawn something on its own (an enemy, to watch him pick a fight) |
| `survey lonk trace` | log his and your positions (and a binary trace next to the log) |

### Changing him without rebuilding the app

Rebuilding the app takes minutes. Start the test session with `TOTK_LONK_PLUGIN=<path>/lonk.dylib` as well, then after
each change to `world_survey.c` run `tools/plugin.sh /path/to/MacNativeGames <MacNativeGames build> <path>/lonk.dylib`
(about a second). The running game picks it up within half a second and swaps his code without a restart. He doesn't
even notice: his state (where he is, his mood, his clothes) carries over, variable by variable. `survey reload` forces a
reload.

## Known issues

- He may still hitch a little as he runs (the run carries him forward by itself, and the amount it's undone by is tuned
  by eye). Switching between run and sprint keeps his stride now, so that snip should be gone.
- He can't climb or swim: walls and ledges over 7 m he walks around, and if he gets stranded (far above or below you,
  far away and getting nowhere, stuck) for 3 seconds, he pops back next to you.
- He steers with a knee-high probe: thin things (trees, fences) can still slip through, and anything knee high or lower
  he just walks over.
- With the mod installed, the inventory Link runs, sprints, celebrates, startles or eats in the pause menu when you hold
  a weapon.

## License

MIT, see [LICENSE](LICENSE). The patch modifies MacNativeGames, which is also MIT
(Copyright (c) 2026 MacNativeGames contributors), see [NOTICE](NOTICE).
