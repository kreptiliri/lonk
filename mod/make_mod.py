#!/usr/bin/env python3
"""Builds Lonk's RomFS mod from your own game files: his walk, run, sprint and his emotes.

The inventory Link (PouchPlayer) has one full-body animation command, the pause menu's PauseMenuWait. Its tree starts
with a selector on the ASB blackboard int "HoldAnimationType" (the weapon he holds in the menu): 1 to 5 go to the weapon
poses, anything else to the plain idle. This mod points cases 1 to 5 at five of the menu's weapon-equip clips, renamed
to Link's walk, run, sprint, the cooking "great meal" celebration (his party) and his fall; the patch sets the int every
frame (the game writes it too). His emotes are PouchPlayer's second full-body command, UseItem: a selector on the
blackboard string "UseItem" picks one of eight. And a bone blender over all of PauseMenuWait keeps the clips from
carrying him around (below). Adding new commands or nodes to the ASB crashes the game, so it only reuses what's there.
(Side effect: with the mod installed, the inventory Link walks, runs, sprints, celebrates or falls when you hold a
weapon in the menu.)

Nothing from the game is in this repo. The script reads AS/PouchPlayer.root.asb.zs and the zstd dictionaries from the RomFS
that MacNativeGames prepared (extracted/v143/romfs: romfs.bin + index.json), edits it with dt-12345's ASB tool, and writes
a mod folder for TOTK_ROMFS_MODS, then runs MacNativeGames' make_mod_manifest.py on it.

usage: make_mod.py <MacNativeGames checkout> <extracted/v143/romfs folder> <dt-12345/asb checkout> <output mod folder>
needs: pip install zstandard mmh3
"""
import json
import struct
import subprocess
import sys
from pathlib import Path

import zstandard

ASB = 'AS/PouchPlayer.root.asb.zs'
ROOT = 205   # PauseMenuWait's first node: the HoldAnimationType selector
# HoldAnimationType -> (the weapon-equip clip whose node gets reused, what it plays now). Only reachable from the root's
# cases 1 to 5, never from the plain idle.
CASES = {1: ('PauseMenu_Equip_Sword', 'Nml_Move_Walk'), 2: ('PauseMenu_Equip_Lsword', 'Nml_Move_Run'), 3: ('PauseMenu_Equip_Spear', 'Nml_Move_Dash'),
         4: ('PauseMenu_Equip_SwordNoShield', 'Demo_Get_Cooking_VeryGood'), 5: ('PauseMenu_Equip_Shield', 'Fall_Loop')}
# The UseItem command's tree: a selector on the blackboard string "UseItem", which the menu's AI never writes, so the patch
# picks his emote with it. Three of its eating clips stay (one-handed, a meal, a bad one), and five get renamed (the drink
# became his startle) (UseItem value -> what it plays now).
USE_ITEM = 202
# The menu's AI reads HoldAnimationType as the weapon type he holds and draws his sword for 1 to 5: his walk and run had
# his sword and shield in his hands. So his clips sit at 11 to 15, which the menu doesn't know (the patch adds the 10).
CASE_SHIFT = 10
# The run and sprint clips carry him forward by themselves (their top bone, Skl_Root, travels about 3 m a stride), while
# the patch places him by code: undoing that drift at every stop and switch never quite matched the game's own blend, and
# he snapped. So his whole PauseMenuWait goes through a bone blender that takes Skl_Root from a standing clip and the rest
# from his tree, the way Link's own tree uses its Skl_Root bone group (Skl_Root and Root: the drift is in Root). Node 340 is the one free blender (an unused bow
# pose, [arms' clip, body's clip]); its group becomes Lift (only for carrying things), weighted on Skl_Root and Root
# alone (Skl_Root alone left the drift in).
STILL = 340
# The same over his emotes and his take-off (the UseItem command): the take-off clip lifts Root like a real jump, on top
# of the patch's own jump physics, so he went up twice as high. Node 229 is a blender only reachable from an idle
# branch's weapon cases 2 and 3, which the idle never sees (2 and 3 are his run and sprint, straight from the root).
STILL_EMOTES = 229
# Weapons out, his walk and run carry them: the weapon's "_Upper" run clip, which Link's tree lays over his run's arms.
# Lonk plays it as his whole body: laid over his run with a bone blender (on the arm group), the blender sat under 340 and
# his run's drift came back in (even with the run on both sides of it); the clip's own legs are a bit plainer than the
# run's. Each moving case goes through a bool selector on IsAttachedWeapon (the patch sets it: his weapons out), then
# string selectors on "Arrow" (the patch sets the weapon's kind): "Lsword", or else "Spear", or else the sword. All nodes
# of the menu's weapon poses he never reaches. (case: (bool selector, [kind selector, kind selector]))
UPPER = {'Sword': (363, 'Sword_Move_Run_Upper'), 'Lsword': (364, 'Lsword_Move_Run_Upper'), 'Spear': (366, 'Spear_Move_Run_Upper')}
ARMED = {11: (223, [220, 259]), 12: (226, [230, 290])}
USES = {'EatCookingSkewer': 'DemoLookAround', 'EatTooHard': 'Nml_Wait_Jump', 'Drink': 'Demo_Surprise',
        'UseFairy': 'Demo_Get_Cooking_Bad', 'UseEnergyMaterial': 'DemoLookUp'}
# Drawing and putting away his weapons: Link's own clips (his hand reaching over his shoulder), played as an emote (so
# only when he stands: the clips are whole-body for him). UseItem "EatCookingDish" (his meal: the patch eats with the
# plain clip now) goes to an int selector on HoldAnimationType, which nothing reads during an emote. Values 21 to 25 pick
# the clip (at 1 to 5 the menu's AI draws his sword), anything else is putting a sword away. The selector is a free one
# (an idle branch's weapon cases), the clips six free leaves with no frame controllers (bow and sword tired poses).
EQUIP_USE, EQUIP = 'EatCookingDish', 239
EQUIP_CLIPS = [(21, 321, 'Equip_Sword_On_Natural'), (22, 322, 'Equip_Lsword_On_Natural'), (23, 324, 'Equip_Spear_On_Natural'),
               (24, 325, 'Equip_Lsword_Off_Natural'), (25, 333, 'Equip_Spear_Off_Natural'), (None, 334, 'Equip_Sword_Off_Natural')]
# Swimming, climbing and gliding: whole-body loops under his fall (HoldAnimationType 15, so the root's bone blender keeps
# them in place too), picked by three bools the patch writes while one is on (all three off is the fall): WeaponGuardEnhance,
# ShieldEquip and WeaponFire. (IsAttachedWeapon was the "a loop, not the fall" switch at first, but it's also what puts the
# weapon arms on his walk: every loop came with his arms holding a bow, and the loop barely showed, seen.) Four bool selectors nothing reaches and four free
# clips (no events, no frame controls but a plain loop: the menu's bow poses, as it happens). A first try hung them on
# an int selector behind his idle, which wasn't free: the idle reaches it (through bool selectors, which the search
# didn't follow), so his tree had a loop in it, and the clips it took were his face's blinks.
LOOP_BOOLS = ('WeaponGuardEnhance', 'ShieldEquip', 'WeaponFire')
# fire alone: swim; fire and guard: glide (those two lie flat: they skip the bone blender, below); guard alone: tread
# water; shield alone: climb; guard and shield: a sword swing, fighting beside you (cling: the climb held still)


def reached(doc):
    """The nodes his commands can get to."""
    nodes = {node['Node Index']: node for node in doc['Nodes']}
    seen, todo = set(), [c['Node Index'] for c in doc['Commands']]
    while todo:
        i = todo.pop()
        if i in seen or i not in nodes:
            continue
        seen.add(i)
        body = nodes[i].get('Body', {})
        for child in body.get('Child Nodes', []):
            if isinstance(child, int):
                todo.append(child)
            elif isinstance(child, dict):   # (a bool selector's are {'Condition True': n}, {'Condition False': n})
                todo += [v for k, v in child.items() if k in ('Node Index', 'Condition True', 'Condition False') and isinstance(v, int)]
        for control in body.get('Frame Controls', []) or []:
            if isinstance(control, int):
                todo.append(control)
    return seen


def romfs_reader(folder):
    index = {f['path']: (f['offset'], f['size']) for f in json.loads((folder / 'index.json').read_text())['files']}
    data = open(folder / 'romfs.bin', 'rb')

    def read(path):
        offset, size = index[path]
        data.seek(offset)
        return data.read(size)
    return read


def sarc(blob):
    """name -> bytes for a SARC archive (little endian)."""
    assert blob[:4] == b'SARC'
    header = struct.unpack_from('<H', blob, 4)[0]
    data_start = struct.unpack_from('<I', blob, 0xc)[0]
    assert blob[header:header + 4] == b'SFAT'
    count = struct.unpack_from('<H', blob, header + 6)[0]
    entries = [struct.unpack_from('<IIII', blob, header + 12 + 16 * i) for i in range(count)]
    names = header + 12 + 16 * count + 8
    files = {}
    for _, attributes, start, end in entries:
        at = names + (attributes & 0xffff) * 4
        files[blob[at:blob.index(b'\0', at)].decode()] = blob[data_start + start:data_start + end]
    return files


def main():
    if len(sys.argv) != 5:
        sys.exit(__doc__)
    mng, romfs, asb_tool, out = (Path(a).resolve() for a in sys.argv[1:])
    read = romfs_reader(romfs)
    dictionaries = sarc(zstandard.ZstdDecompressor().decompress(read('Pack/ZsDic.pack.zs'), max_output_size=1 << 26))
    zs = zstandard.ZstdCompressionDict(dictionaries['zs.zsdic'])
    original = zstandard.ZstdDecompressor(dict_data=zs).decompress(read(ASB), max_output_size=1 << 24)

    sys.path.insert(0, str(asb_tool))
    from asb import ASB as AsbFile   # dt-12345/asb
    tree = AsbFile.from_binary(original)
    work = out.parent / (out.name + '.work')
    work.mkdir(parents=True, exist_ok=True)
    tree.to_json(str(work) + '/')
    doc = json.loads((work / 'PouchPlayer.root.json').read_text('utf-8'))
    nodes = {node['Node Index']: node for node in doc['Nodes']}
    root = nodes.get(ROOT, {})
    entries = {c.get('Condition'): c for c in root.get('Body', {}).get('Child Nodes', [])}
    if root.get('Node Type') != 'IntSelector' or sorted(k for k in entries if k is not None) != [1, 2, 3, 4, 5]:
        sys.exit('PauseMenuWait\'s first node is not the expected HoldAnimationType selector: not the 1.4.3 ASB?')
    for case, (clip, now) in CASES.items():
        leaf = min((n for n in doc['Nodes'] if n['Node Type'] == 'SkeletalAnimation' and n['Body'].get('Animation') == clip),
                   key=lambda n: n['Node Index'], default=None)
        if leaf is None:
            sys.exit(f'no {clip} clip: not the 1.4.3 ASB?')
        leaf['Body']['Animation'] = now
        entries[case]['Node Index'] = leaf['Node Index']
        entries[case]['Condition'] = case + CASE_SHIFT
    # The root keeps the loop phase when it switches (Is Sync): run and sprint flow into each other instead of restarting
    # his stride, which made his body snap. (Only a command's first node can sync: those are the ones with Sync Controls.
    # It reaches through everything below, so the patch starts an emote only when his loop is about to wrap.)
    root['Body']['Is Sync'] = True
    use = nodes.get(USE_ITEM, {})
    uses = {c.get('Condition'): c['Node Index'] for c in use.get('Body', {}).get('Child Nodes', []) if 'Condition' in c}
    if use.get('Node Type') != 'StringSelector' or any(k not in uses for k in USES):
        sys.exit('the UseItem tree is not the expected one: not the 1.4.3 ASB?')
    for value, now in USES.items():
        leaf = nodes[uses[value]]
        if leaf['Node Type'] != 'SkeletalAnimation':
            sys.exit(f'UseItem {value} is not a single clip: not the 1.4.3 ASB?')
        leaf['Body']['Animation'] = now
    still = nodes.get(STILL, {})
    lift = next((g for g in doc['Bone Groups'] if g['Name'] == 'Lift'), None)
    standing = nodes.get(still.get('Body', {}).get('Child Nodes', [None, None])[1], {})
    if still.get('Node Type') != 'BoneBlender' or lift is None or standing.get('Body', {}).get('Animation') != 'Nml_Wait':
        sys.exit('no free bone blender over a standing clip: not the 1.4.3 ASB?')
    lift['Unknown'] = 0   # bones it doesn't list: from his tree (it was 1: his arms took the standing pose, a Naruto run)
    for bone in lift['Bones']:
        bone['Unknown'] = 1.0 if bone['Name'] in ('Skl_Root', 'Root') else 0.0
    still['Body']['Bone Group Name'] = 'Lift'
    still['Body']['Child Nodes'] = [standing['Node Index'], ROOT]
    next(c for c in doc['Commands'] if c['Name'] == 'PauseMenuWait')['Node Index'] = STILL
    still_emotes = nodes.get(STILL_EMOTES, {})
    if still_emotes.get('Node Type') != 'BoneBlender':
        sys.exit('no second bone blender for the emotes: not the 1.4.3 ASB?')
    for key in ('Bone Group Name', 'Unknown 1', 'Blend Rate', 'Unknown 3', 'Unknown 4'):
        still_emotes['Body'][key] = still['Body'][key]
    still_emotes['Body']['Child Nodes'] = [standing['Node Index'], USE_ITEM]
    next(c for c in doc['Commands'] if c['Name'] == 'UseItem')['Node Index'] = STILL_EMOTES
    bools = [b['Name'] for b in doc['Blackboard']['bool']]
    strings = [b['Name'] for b in doc['Blackboard']['string']]
    for kind, (leaf, clip) in UPPER.items():
        if nodes[leaf]['Node Type'] != 'SkeletalAnimation':
            sys.exit(f'node {leaf} is not a clip: not the 1.4.3 ASB?')
        nodes[leaf]['Body']['Animation'] = clip
    for case, (armed, (first, second)) in ARMED.items():
        base = entries[case - CASE_SHIFT]['Node Index']
        if nodes[armed]['Node Type'] != 'BoolSelector' or any(nodes[k]['Node Type'] != 'StringSelector' for k in (first, second)):
            sys.exit('the weapon poses are not the expected nodes: not the 1.4.3 ASB?')
        for node, param in ((armed, bools.index('IsAttachedWeapon')), (first, strings.index('Arrow')), (second, strings.index('Arrow'))):
            nodes[node]['Body']['Parameter']['Blackboard Index'] = param
            nodes[node]['Body']['Parameter']['Select Flag'] = 'SelectOnUpdate'   # (drawn mid-run: switch now, not next time)
        nodes[armed]['Body']['Child Nodes'] = [{'Condition True': first}, {'Condition False': base}]
        nodes[first]['Body']['Child Nodes'] = [{'Condition': 'Lsword', 'Node Index': UPPER['Lsword'][0]},
                                               {'Default': nodes[first]['Body']['Child Nodes'][1]['Default'], 'Node Index': second}]
        nodes[second]['Body']['Child Nodes'] = [{'Condition': 'Spear', 'Node Index': UPPER['Spear'][0]},
                                                {'Default': nodes[second]['Body']['Child Nodes'][1]['Default'], 'Node Index': UPPER['Sword'][0]}]
        entries[case - CASE_SHIFT]['Node Index'] = armed
    equip = nodes.get(EQUIP, {})
    cases = equip.get('Body', {}).get('Child Nodes', [])
    if (equip.get('Node Type') != 'IntSelector' or len(cases) != len(EQUIP_CLIPS) or 'Default' not in cases[-1] or
            any(nodes[leaf]['Node Type'] != 'SkeletalAnimation' or nodes[leaf]['Body'].get('Frame Controls') for _, leaf, _ in EQUIP_CLIPS)):
        sys.exit('no free selector and clips for drawing his weapons: not the 1.4.3 ASB?')
    equip['Body']['Parameter']['Select Flag'] = 'NoSelectOnUpdate'   # (picked when the emote starts)
    for entry, (value, leaf, clip) in zip(cases, EQUIP_CLIPS):
        nodes[leaf]['Body']['Animation'] = clip
        entry['Node Index'] = leaf
        if value is not None:
            entry['Condition'] = value
    next(c for c in use['Body']['Child Nodes'] if c.get('Condition') == EQUIP_USE)['Node Index'] = EQUIP
    taken = reached(doc)

    def plain_loop(leaf):   # no frame controls, or only a frame controller that loops the whole clip at rate 1
        return all(nodes[c]['Node Type'] == 'FrameController' and nodes[c]['Body'].get('Loop Num') == -1 and
                   nodes[c]['Body'].get('Animation Rate') == 1.0 for c in leaf['Body'].get('Frame Controls') or [])
    free = [n for n in doc['Nodes'] if n['Node Type'] == 'SkeletalAnimation' and n['Node Index'] not in taken and
            not n['Body'].get('Events') and plain_loop(n)]
    pickers = [n for n in doc['Nodes'] if n['Node Type'] == 'BoolSelector' and n['Node Index'] not in taken]
    fall = entries[5]   # (keyed by the original cases: 5 is his fall, at 15 now)
    if len(free) < 6 or len(pickers) < 7 or nodes[fall['Node Index']]['Node Type'] != 'SkeletalAnimation':
        sys.exit('no free bool selectors and clips for swimming and climbing: not the 1.4.3 ASB?')
    guard, shield, shield2, fire, fire2, fire3 = pickers[:6]
    clips = iter(free)

    def pick(node, param, if_true, if_false):
        node['Body']['Parameter'] = {'Blackboard Index': bools.index(param), 'Type': 'bool', 'Select Flag': 'SelectOnUpdate'}
        node['Body']['Child Nodes'] = [{'Condition True': if_true}, {'Condition False': if_false}]

    def clip(name):
        leaf = next(clips)
        leaf['Body']['Animation'] = name
        # (a menu pose's frame controller plays it once and holds it: his swim froze, its clock at 1.0, seen, also with the
        # end moved to the clip's end. None, as his walk has: then it loops)
        leaf['Body'].pop('Frame Controls', None)
        print(f'{name}: node {leaf["Node Index"]}')
        return leaf['Node Index']
    G, S, F = LOOP_BOOLS
    pick(fire, F, clip('Float_Glide_N'), clip('Swim_Wait'))
    pick(shield, S, clip('Sword_Attack_S1'), fire['Node Index'])
    pick(fire3, F, clip('Swim_Move_Slow_F'), fall['Node Index'])
    pick(shield2, S, clip('Climb_Wall_Move_U'), fire3['Node Index'])
    pick(guard, G, shield['Node Index'], shield2['Node Index'])
    fall['Node Index'] = guard['Node Index']
    # Swimming and gliding (WeaponFire) his whole tree plays without the bone blender over it: the blender's standing root
    # bones took the swim clip's tilt away, and he swam upright, arms and face up (seen). Treading water stays under it
    # (without, its own root bones sank him, seen)
    water = pickers[6]
    pick(water, F, ROOT, STILL)
    next(c for c in doc['Commands'] if c['Name'] == 'PauseMenuWait')['Node Index'] = water['Node Index']
    if (taken & {n['Node Index'] for n in (guard, shield, shield2, fire, fire3, water)}) or ROOT in reached({'Nodes': doc['Nodes'], 'Commands': [{'Node Index': guard['Node Index']}]}):
        sys.exit('the loops would loop back into his tree')
    AsbFile.from_dict(doc).to_binary(str(work) + '/')
    edited = (work / 'PouchPlayer.root.asb').read_bytes()

    target = out / ASB
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(zstandard.ZstdCompressor(level=16, dict_data=zs).compress(edited))
    subprocess.run([sys.executable, str(mng / 'games/totk/scripts/make_mod_manifest.py'), str(out), '--romfs', str(romfs),
                    '--version', 'v143'], check=True)
    print(f'mod written to {out}: start the game with TOTK_ROMFS_MODS={out}')


if __name__ == '__main__':
    main()
