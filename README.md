# Lonk

A second Link for *Tears of the Kingdom*. He lives in your world, follows you around, and does his own thing.
Right now his own thing is mostly being in the way, and handing you apples.

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
  after he spawns: his ponytail, his arm and Link's default outfit (his underwear; he doesn't copy yours). The game drags
  those pieces back into the menu's 3D scene every frame, so he pulls them back out every frame too.
- **He used to be mannequins.** Before that he was three armor-shop mannequins stacked on one spot, which crashed the
  game when you walked up to them (they went looking for the item they were selling). That fix is still in, and
  `survey drop` gets rid of the mannequins.
- **He walks and runs.** Every frame he moves toward wherever his brain says, over the real ground (a physics raycast,
  so sky islands, rocks, bridges and caves count too) and around anything in his way, ledges included: he steps up at most
  a stair's height, falls if the floor drops out under him, and pops back next to you if he gets stranded. He uses Link's own walk, run and dash,
  picked from his speed and played at a matching speed, and turns smoothly to face where he's going, then back to you
  when he stops. He also looks around, startles and celebrates. (Well, his brain picks them: his arms and legs don't
  move yet, see Known issues.) The animations need a small RomFS mod (see
  "Trying it"); without it he sweats, shivers or pants his way around instead.
- **He doesn't stay gone.** If his body disappears while his brain runs (you die and reload, a loading zone), he's
  back a couple of seconds after you are.
- **He has a (very small) brain.** Every few seconds he decides what to do:

| Mood | What he does |
|---|---|
| stalk | walks up and stares at you from a step away |
| buddy | walks beside you at your pace, looking where you look |
| block | sprints into your path |
| gift | drops an apple at your feet (sometimes a fish, a monster part or a bomb barrel), celebrates, and runs |
| behind | is suddenly standing right behind you, and startles if you turn around |
| wander | forgets you exist, wanders off and looks around |

## Where he's going

- Real clothes: an actual outfit doesn't show yet (he turns into a floating head)
- Doing things, not just standing near you: fighting, climbing, using items, breaking stuff
- Never dying, whatever you do to him (he already comes back when you die)
- A smarter brain

None of this is promised, it's what I'm working toward.

## What I built

Only my own code is here: a patch for the MacNativeGames runtime, plus notes. No game files, keys or extracted game
data. You need your own legally dumped copy of the game, like the port itself does.

- `patches/lonk.patch`: the changes to `games/totk/runtime/world_survey.c` and `game_version.h`. Spawning, dressing,
  animation, the ground and obstacle raycasts, the brain, and the shop crash fix.
- `patches/BASE_COMMIT`: the MacNativeGames commit the patch applies to.
- `apply.sh`: applies the patch to a MacNativeGames checkout.
- `mod/make_mod.py`: builds his animation mod from your own game files (nothing from the game is in this repo).
- `docs/how-it-works.md`: the reverse-engineering notes. How I found the spawn function in 1.4.3, how he gets dressed,
  how an inventory Link learned to walk, how he finds the ground.

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

That spawns his body 4 m in front of you and runs his brain for an hour (`survey spawn lonk PouchPlayer 4 0 0` plus
`survey lonk brain 216000`, if you want them separately).

He starts his idle animation and gets dressed on his own. `survey equip <slot> <ArmorName> [dye]` puts one piece on him
(9 head, 10 upper, 11 lower, `-` for the default), and `survey dress` redoes the whole outfit. The old mannequin body
still works (`survey spawn m1 Mannequin_001_Upper` and friends), and `survey drop <name start|all>` removes pieces from
him again.

You can also force one mood with `survey lonk <stalk|buddy|block|behind|wander|gift|flee|party> <frames>`, send him
somewhere with `survey lonk goto <metres right> <metres forward> [m/s]` (from you), and stop him with
`survey lonk stop`.

## Known issues

- His arms and legs don't move: he glides around stiff. The animation is set, but his body pieces don't follow it yet.
- He only has his underwear. Real armor (`survey equip 10 Armor_001_Upper`) doesn't draw, and hides the body under it,
  so he turns into a floating head until he's back in the defaults.
- His feet may still slide a little: the clips' own speeds are my estimates.
- With the mod installed, the inventory Link walks, runs or dashes in place in the pause menu when you're somewhere cold
  or hot, or out of stamina, and looks around, startles or celebrates when you equip a two-handed sword, a spear or just
  a shield.
- He doesn't jump, climb or follow you down ledges. He walks around them instead, and if he gets stranded (5 m above or
  below you, 30 m away, stuck, or no floor) for 3 seconds, he pops back next to you.
- He steers around rocks and walls with a knee-high probe, but thin things (trees, fences) can still slip through, and
  anything knee high or lower he just walks over.

## License

MIT, see [LICENSE](LICENSE). The patch modifies MacNativeGames, which is also MIT
(Copyright (c) 2026 MacNativeGames contributors), see [NOTICE](NOTICE).
Not affiliated with Nintendo.
