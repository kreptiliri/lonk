#!/usr/bin/env python3
"""live.py: while you play, follow the newest session recording and write short lines to lonk_live.txt
(next to the game log): a line when something changes (what you do, his state, him in rock, alarms, his decisions, gear,
enemies near, your bookmarks) and a heartbeat every 10 s. Read its tail (`tail -20`).
Reads only new records (a file offset), so it costs next to nothing. Stop it with Ctrl-C / kill.

  live.py [seconds to run, default 3600]
"""
import os, struct, sys, time, zlib, math
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import obs

OUT = os.path.join(obs.LOGS, 'lonk_live.txt')
FIELDS = ['frame', 'ns', 'you', 'him', 'yface', 'hface', 'you_cmds', 'kind', 'gait', 'climb', 'clip', 'air', 'swim', 'paused', 'emote', 'you_climb',
          'alarms', 'rock_in', 'rock_top', 'teleports', 'ygear_out', 'gear_out']
HIDE = ('Weapon_', 'Armor_', 'Accessory_', 'PlayerRaulHand', 'AsbObj_', 'MergedActor', 'PouchPlayer', 'Player', 'Area', 'Forbid')


def you_doing(f, speed):
    cmd = next((x for x in f['you_cmds'].split('|') if x.strip()), '-').strip()
    if 'Climb' in cmd or f['you_climb']:
        base = 'climbing'
    elif cmd.startswith(('Cut', 'Charge', 'Attack')):
        base = 'attacking'
    elif cmd.startswith('Bow'):
        base = 'bow'
    elif cmd.startswith('WeaponEquipOn'):
        base = 'drawing'
    elif cmd.startswith('WeaponEquipOff'):
        base = 'sheathing'
    elif 'Jump' in cmd or cmd.startswith(('Fall', 'Land')):
        base = 'jumping/falling'
    elif cmd.startswith(('Glide', 'Para')):
        base = 'gliding'
    elif cmd.startswith('Swim'):
        base = 'swimming'
    elif cmd.startswith('Damage'):
        base = 'hit'
    elif cmd.startswith('WarpHeight'):
        base = 'ascend'
    else:   # (by speed, with some slack so a line isn't written each time it wobbles across a line)
        was = you_doing.last
        if speed > (6.6 if was == 'sprinting' else 7.8):
            base = 'sprinting'
        elif speed > (2.5 if was in ('running', 'sprinting') else 3.5):
            base = 'running'
        elif speed > (0.3 if was in ('walking', 'running', 'sprinting') else 0.8):
            base = 'walking'
        else:
            base = 'standing'
    you_doing.last = base
    return base, cmd


you_doing.last = None


def main():
    run_for = float(sys.argv[1]) if len(sys.argv) > 1 else 3600
    paths = obs.sessions()
    path = paths[-1]
    out = open(OUT, 'a', buffering=1)
    out.write(f'--- live {time.strftime("%H:%M:%S")} following {os.path.basename(path)}\n')
    layouts, at, prev, last = {}, 0, None, {}
    session = obs.Session.__new__(obs.Session)   # (only for wall(): the clock lines of the layouts)
    session.layouts = layouts
    t_end = time.time() + run_for
    last_beat = 0
    pend_said = []
    start = os.path.getsize(path)   # (what's already there: only its layouts are read, the lines start from now)
    while time.time() < t_end:
        newest = obs.sessions()[-1]
        if newest != path:   # (the game restarted: a new session file)
            path, at, layouts, prev, start = newest, 0, {}, None, 0
            session.layouts = layouts
            out.write(f'--- now following {os.path.basename(path)}\n')
        size = os.path.getsize(path)
        if size > at:
            with open(path, 'rb') as fh:
                fh.seek(at)
                data = fh.read(size - at)
            k = 0
            while k + 16 <= len(data):
                magic, tl, ln, cnt = struct.unpack_from('<IIII', data, k)
                if magic != obs.MAGIC or k + 16 + ln > len(data):
                    break
                typ, lay = tl & 0xffff, tl >> 16
                body = data[k + 16:k + 16 + ln]
                if at + k < start and typ != 1:
                    k += 16 + ln
                    continue
                if typ == 1:
                    layouts[lay] = obs.Layout(body.decode('latin-1'))
                elif typ == 2 and lay in layouts:
                    L = layouts[lay]
                    raw = zlib.decompress(body, -15)
                    for j in range(min(cnt, len(raw) // L.size)):
                        if j % 3:
                            continue
                        f = L.decode_some(raw, j * L.size, FIELDS)
                        f['t'] = session.wall(f['ns'], L)
                        lines = summarize(f, prev, last, L, pend_said)
                        for ln_ in lines:
                            out.write(ln_ + '\n')
                        if f['t'] - last_beat >= 10 and not lines:
                            last_beat = f['t']
                            out.write(beat(f, L) + '\n')
                        prev = f
                elif typ == 3:
                    fr, ns = struct.unpack_from('<QQ', body, 0)
                    why, _, note = body[16:].decode('latin-1', 'replace').partition('\t')
                    out.write(f'{obs.hms(session.wall(ns))} BOOKMARK {why[:60]} {note[:30]}\n')
                elif typ == 4:
                    txt = body[16:].decode('latin-1', 'replace').replace('[survey] lonk: ', '').strip()
                    if txt and not txt.startswith('frame='):
                        pend_said.append(txt[:110])
                elif typ == 6:
                    out.write(f'   gear: {body[16:].decode("latin-1", "replace")[:150]}\n')
                elif typ == 10:
                    raw = zlib.decompress(body, -15)
                    fr, ns = struct.unpack_from('<QQ', raw, 0)
                    if prev is not None:
                        en = []
                        for line in raw[16:].decode('latin-1').splitlines():
                            w = line.split()
                            if len(w) == 4 and w[0].startswith('Enemy_') and 'Dummy' not in w[0] and 'Head' not in w[0]:
                                d = math.dist((float(w[1]), float(w[2]), float(w[3])), prev['you'])
                                if d < 15:
                                    en.append(f'{w[0][6:]} {d:.0f}m')
                        key = tuple(sorted(x.split()[0] for x in en))
                        if key != last.get('enemies'):
                            last['enemies'] = key
                            out.write(f'{obs.hms(session.wall(ns))} enemies within 15 m: {", ".join(sorted(en, key=lambda x: float(x.split()[-1][:-1]))) or "none"}\n')
                k += 16 + ln
            at += k
        time.sleep(1.0)


def summarize(f, p, last, L, pend_said):
    lines = []
    if p is None or f['paused']:
        if f['paused'] and not last.get('paused'):
            lines.append(f'{obs.hms(f["t"])} (game paused)')
        last['paused'] = f['paused']
        return lines
    last['paused'] = 0
    dt = max(f['t'] - p['t'], 1e-3)
    sp = math.hypot(f['you'][0] - p['you'][0], f['you'][2] - p['you'][2]) / dt if obs.finite(f['you'][0]) and obs.finite(p['you'][0]) else 0
    doing, cmd = you_doing(f, sp)
    names = L.names
    him = f'{names["moods"][f["kind"]] if 0 <= f["kind"] < len(names["moods"]) else f["kind"]} {names["gaits"][f["gait"]] if 0 <= f["gait"] < len(names["gaits"]) else f["gait"]}'
    if f['climb']:
        him += f' climb{f["climb"]}'
    if f['air']:
        him += ' air'
    if f['swim']:
        him += ' swim'
    ev = []
    if doing != last.get('doing'):
        ev.append(f'you {doing} ({cmd[:18]}, {sp:.1f} m/s)')
        last['doing'] = doing
    if him != last.get('him'):
        ev.append(f'him: {him}')
        last['him'] = him
    if 'rock_in' in f and f['rock_in'][15] != 255:
        n = [L.names['parts'][q] for q in range(15) if f['rock_in'][15 + q] not in (0, 255) and f['rock_top'][15 + q] >= 10]
        st = len(n) >= 3
        if st != last.get('rock', False):
            ev.append(f'HIM IN ROCK ({len(n)} parts: {", ".join(n[:4])})' if st else 'him out of the rock')
            last['rock'] = st
    if f['alarms']:
        ev.append('alarm ' + ' '.join(L.names['alarms'][q] for q in range(len(L.names['alarms'])) if f['alarms'] >> q & 1))
    if f['teleports'] != p['teleports']:
        ev.append('he was teleported')
    if tuple(f['ygear_out']) != tuple(p['ygear_out']):
        ev.append(f'your weapons out {list(f["ygear_out"])}, his {list(f["gear_out"])}')
    if pend_said:
        ev.append('he: ' + ' ; '.join(pend_said[:3]))
        del pend_said[:]
    if ev:
        d = math.dist(f['you'], f['him']) if obs.finite(f['him'][0]) and obs.finite(f['you'][0]) else float('nan')
        lines.append(f'{obs.hms(f["t"])} ' + ' | '.join(ev) + f'  [{d:.1f} m apart]')
    return lines


def beat(f, L):
    d = math.dist(f['you'], f['him']) if obs.finite(f['him'][0]) and obs.finite(f['you'][0]) else float('nan')
    x, z, y = obs.rel(f['him'], f['hface'], f['you']) if obs.finite(f['him'][0]) else (0, 0, 0)
    return f'{obs.hms(f["t"])} . you at {f["you"][0]:.0f},{f["you"][1]:.0f},{f["you"][2]:.0f}; he is {d:.1f} m from you (you: his {"right" if x > 0 else "left"} {abs(x):.1f}, {"ahead" if z > 0 else "behind"} {abs(z):.1f}, up {y:+.1f})'


if __name__ == '__main__':
    main()
