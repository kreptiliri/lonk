#!/usr/bin/env python3
"""Builds Lonk's RomFS mod from your own game files: his walk, run, dash and party.

The inventory Link (PouchPlayer) has one full-body animation command, the pause menu's PauseMenuWait. It's an idle that
plays Nml_Cold_Wait, Nml_Wait or Nml_Hot_Wait depending on the ASB blackboard float "Temperature", and Nml_Tired_Wait
when the bool "Stamina" is false, or the shield-equip clip when the int "HoldAnimationType" is 5. This mod points the
cold, hot and tired idles at Link's own Nml_Move_Walk, Nml_Move_Run and Nml_Move_Dash, and the shield clip at the cooking
"great meal" celebration (his party), and the patch drives the blackboard.
Adding new commands or nodes to the ASB crashes the game, so nothing else changes. (Side effect: with the mod installed,
the inventory Link walks, runs or dashes in place when you open the menu somewhere cold or hot, or out of stamina, and
celebrates when you equip a shield with no weapon.)

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
MOVES = {'Nml_Cold_Wait': 'Nml_Move_Walk', 'Nml_Hot_Wait': 'Nml_Move_Run', 'Nml_Tired_Wait': 'Nml_Move_Dash',
         'PauseMenu_Equip_Shield': 'Demo_Get_Cooking_VeryGood'}


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
    changed = 0
    for node in doc['Nodes']:
        if node['Node Type'] == 'SkeletalAnimation' and node['Body'].get('Animation') in MOVES:
            node['Body']['Animation'] = MOVES[node['Body']['Animation']]
            changed += 1
    if changed != len(MOVES):
        sys.exit(f'expected {len(MOVES)} idle clips to repoint, found {changed}: not the 1.4.3 ASB?')
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
