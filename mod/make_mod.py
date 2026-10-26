#!/usr/bin/env python3
"""Builds Lonk's RomFS mod from your own game files: his run, sprint and his emotes.

The inventory Link (PouchPlayer) has one full-body animation command, the pause menu's PauseMenuWait. Its tree starts
with a selector on the ASB blackboard int "HoldAnimationType" (the weapon he holds in the menu): 1 to 5 go to the weapon
poses, anything else to the plain idle. The game never writes that int itself, unlike "Temperature" and "Stamina", which
the menu's AI sets every frame from where you are (so using those, he fought the game for his walk, and his clip kept
restarting). This mod points cases 2 to 5 at four of the menu's weapon-equip clips, renamed to Link's run, sprint, the
cooking "great meal" celebration (his party) and a startle, and case 1 at the UseItem command's eating tree, where the
blackboard string "UseItem" picks one of eight more emotes. The patch sets the int (and the string).
Adding new commands or nodes to the ASB crashes the game, so nothing else changes. (Side effect: with the mod installed,
the inventory Link runs, sprints, celebrates, startles or eats when you hold a weapon in the menu.)

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
CASES = {2: ('PauseMenu_Equip_Lsword', 'Nml_Move_Run'), 3: ('PauseMenu_Equip_Spear', 'Nml_Move_Dash'),
         4: ('PauseMenu_Equip_SwordNoShield', 'Demo_Get_Cooking_VeryGood'), 5: ('PauseMenu_Equip_Shield', 'Demo_Surprise')}
# Case 1 (the walk, which he doesn't use) leads to the UseItem command's tree instead: a selector on the blackboard
# string "UseItem", which the menu's AI never writes, so the patch picks his emote with it. Three of its eating clips stay
# (one-handed, a meal, a bad one) plus the drink, and four get renamed (UseItem value -> what it plays now).
USE_ITEM = 202
USES = {'EatCookingSkewer': 'DemoLookAround', 'EatTooHard': 'Nml_Wait_Jump',
        'UseFairy': 'Demo_Get_Cooking_Bad', 'UseEnergyMaterial': 'DemoLookUp'}


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
    entries[1]['Node Index'] = USE_ITEM
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
