#!/usr/bin/env python3
"""lens.py: the observatory's views over a whole session recording (lonk_session_*.obs). Each prints ~10-30 lines.

  lens.py sessions                       the recordings (newest last): length, frames, marks
  lens.py [@..] check                    is anything missing: frame gaps (where, how long), frames per build, rate
  lens.py [@..] bones <him|you> <bone|part|*> [t0 [t1]] [step]   bones over time: height over his/your floor, speed, from
                                         (bone names as in the skeleton, e.g. Waist Toe_L Head; parts: "hand L" waist...;
                                         "lens.py bones names" lists them)
  lens.py [@..] input [t0 [t1]]          your keys / mouse / buttons / sticks on every change; the camera (where, which way,
                                         how far behind you), whether he's on your screen or hidden by rock
  lens.py [@..] input summary [t0 [t1]]  how much of the time he was on your screen, hidden by rock, off screen
  lens.py [@..] gear [t0 [t1]]           what each of you wears and holds (on every change), drawn or away
  lens.py [@..] compare jumps [t0 [t1]]  every take-off of yours (your Jump command) and his (his jump gait): speed, peak
  lens.py [@..] compare feet|bounce|turns [t0 [t1]]   him vs you: lowest toe over the floor by slope band; waist
                                         height while running (bob); turn speed while moving
  lens.py [@..] slice <t> [his|your|x|z] [half-width m] [tall] [around him|you]   SIDE view of the rock (from the 3D scans)
                                         along his facing (default), yours, or a world axis: # rock, - its top surface,
                                         ^ an overhang's underside, . air, blank = not scanned; bodies: O head C chest
                                         W waist H hands K knees F feet (UPPER = him, lower = you; within 0.5 m of the cut)
  lens.py [@..] top <t> [feet|knee|chest|head|<m>] [around him|you]  the same from above at that height over his feet,
                                         his facing up
  lens.py [@..] inside [t0 [t1]]         in rock, exactly (a column + 8 side rays through each of the 15 parts, every 2nd
                                         frame): per Link touching (<10 cm) / in (10-30) / deep (30+), which parts, his
                                         runs with 3+ parts 10 cm+ in (your Link, tested: never past 0.23 m)
  lens.py [@..] near <t> [r] [around you] [all]   actors round him (or you) then (recorded once a second, 25 m): name,
                                         how far, where from him (ahead/behind, left/right, up); his/your gear, cameras,
                                         level chunks hidden unless "all"
  lens.py [@..] odd <mK | t0 t1> [n]     FIRST LOOK at any moment: his ~60 numbers a frame (speeds, turns, each part
                                         against the waist, heights, in rock, not drawn, apart, side flips, changes,
                                         alarms) in the window vs his own usual (the rest of the session) and vs your
                                         Link's usual; the n (15) most unusual, one line each. mK = 15 s before to 3 s after
  lens.py [@..] find <what> [t0 [t1]]    when did it happen (whole session by default; up to 30): "in rock" (his runs,
                                         3+ parts 10 cm+), "jump" (yours and his), "climb" (his climb starts), "top" (his
                                         "over the top"), "teleport", "side" (you switched sides of him), "alarm <kind>",
                                         "said <text>" (his decisions), "mark"
  lens.py [@N|@path] marks               the bookmarks (button, "survey lonk mark", alarms): number, time, why
  lens.py [@..] story [t0 [t1]] [every]  the timeline: a row on every change of his state / your move, his decisions
                                         (SAID), teleports, new body, alarms, BURIED; and every <every> s (0.5)
                                         a heartbeat row: you from him (right/forward/up), his floor, rock near him
Times: HH:MM:SS[.s] | +S (from the start) | -S (before the end) | mK (bookmark K) | mK-5 (5 s before it).
A single mK as the window = 15 s before it to 3 s after. The default session is the newest (@-2 the one before, ...).
"""
import collections, math, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import obs

args = sys.argv[1:]
paths = obs.sessions()
pick = paths[-1] if paths else None
if args and args[0].startswith('@'):
    a = os.path.expanduser(args.pop(0)[1:])
    if not os.path.exists(a) and os.path.exists(os.path.join(obs.LOGS, a)):
        a = os.path.join(obs.LOGS, a)   # (a bare file name: next to the log)
    pick = a if os.path.exists(a) else paths[-1] if a in ('', 'last') else paths[int(a)]
what = args.pop(0) if args else 'sessions'


def window(s, a, whole=False):
    """(t0, t1, rest of args) from the view's args; no times: the whole session if whole, else its last 60 s"""
    t0, t1 = s.span()
    if not whole:
        t0 = max(t0, t1 - 60)
    if a and (a[0].startswith('m') and a[0][1:2].isdigit()) and (len(a) == 1 or not (a[1][:1] in '+-' or ':' in a[1] or a[1].startswith('m'))):
        m = obs.parse_time(a[0], s)
        return m - 15, m + 3, a[1:]
    if a and (a[0][:1] in '+-' or ':' in a[0] or a[0].startswith('m')):
        t0 = obs.parse_time(a[0], s); a = a[1:]
        if a and (a[0][:1] in '+-' or ':' in a[0] or a[0].startswith('m')):
            t1 = obs.parse_time(a[0], s); a = a[1:]
    return t0, t1, a


if what == 'sessions':
    for i, p in enumerate(paths):
        s = obs.Session(p)
        t0, t1 = s.span()
        print(f'{i - len(paths):>3} {os.path.basename(p)}  {obs.hms(t0, False)}-{obs.hms(t1, False)}  {(t1 - t0) / 60:.1f} min  '
              f'{s.count()} frames  {len(s.marks)} marks  {os.path.getsize(p) / 1e6:.1f} MB  {len(s.layouts)} layouts')
    sys.exit(0)

if not pick:
    sys.exit('no session recordings yet')
s = obs.Session(pick)
L = s.layout
names = L.names if L else {}
gaits, moods, alarms, clips = names.get('gaits', []), names.get('moods', []), names.get('alarms', []), names.get('clips', [])


def nm(tab, k):
    return tab[k] if 0 <= k < len(tab) else str(k)


if what == 'marks':
    print(f'{os.path.basename(pick)}: {len(s.marks)} bookmarks')
    for i, m in enumerate(s.marks):
        print(f'm{i:<3} {obs.hms(s.wall(m["ns"]))}  f={m["frame"]}  {m["why"][:70]}  {m["note"][:40]}')
    sys.exit(0)

if what == 'check':
    fr = s.frames(fields=['paused'])
    t0, t1 = s.span()
    print(f'{os.path.basename(pick)}: {len(fr)} frames, {obs.hms(t0)} - {obs.hms(t1)} ({(t1 - t0) / 60:.1f} min), '
          f'{len(fr) / max(t1 - t0, 1e-9):.1f} a second, {os.path.getsize(pick) / 1e6:.2f} MB')
    per = {}
    lay_of = {id(L): k for k, L in s.layouts.items()}
    for b in s.blocks:
        per[lay_of[id(b['L'])]] = per.get(lay_of[id(b['L'])], 0) + b['n']
    print('blocks per build (layout): ' + ', '.join(f'{k}: {v} frames' for k, v in sorted(per.items())) + f'; {sum(per.values()) - len(fr)} recorded twice')
    gaps = [(a, b) for a, b in zip(fr, fr[1:]) if b['frame'] != a['frame'] + 1]
    print(f'{len(gaps)} gaps in the frame numbers' + (':' if gaps else ''))
    for a, b in gaps[:15]:
        print(f'  after {obs.hms(a["t"])} f={a["frame"]}: {b["frame"] - a["frame"] - 1} frames, {b["t"] - a["t"]:.2f} s missing')
    if s.skel_names:
        worst, n = {}, 0
        for f in s.frames(fields=['has', 'bone', 'skel', 'you', 'him'], every=30):
            if 'skel' not in f:
                continue
            for who in (0, 1):
                for p, bn in enumerate(obs.PART_BONES):
                    i = s.skel_names.index(bn) if bn in s.skel_names else None
                    if i is None or not (f['has'][who] >> p & 1):
                        continue
                    b = obs.bone(f, who, i)
                    if not b:
                        worst[('missing', who, bn)] = worst.get(('missing', who, bn), 0) + 1; continue
                    old_ = f['bone'][(who * 15 + p) * 3:(who * 15 + p) * 3 + 3]
                    d = math.dist(b, old_); n += 1
                    if d > worst.get((who, bn), 0):
                        worst[(who, bn)] = d
        far = sorted(((v, k) for k, v in worst.items() if k[0] != 'missing'), reverse=True)[:3]
        miss = [(k, v) for k, v in worst.items() if k[0] == 'missing']
        print(f'skeleton vs the 15 parts (every 30th frame): {n} pairs, worst ' + ', '.join(f'{"him" if k[0] else "you"} {k[1]} {v * 1000:.1f} mm' for v, k in far) +
              (f'; missing: {miss[:4]}' if miss else ''))
    slow = sum(1 for a, b in zip(fr, fr[1:]) if b['frame'] == a['frame'] + 1 and b['t'] - a['t'] > 0.1)
    print(f'{slow} frame steps over 0.1 s (the game hitching or paused)')
    sys.exit(0)

def bone_idx(name):
    name = obs.PART_ALIAS.get(name, name)
    if name in s.skel_names:
        return s.skel_names.index(name)
    low = [n.lower() for n in s.skel_names]
    return low.index(name.lower()) if name.lower() in low else None


if what == 'bones':
    if args and args[0] == 'names':
        print(f'{len(s.skel_names)} bones: ' + ' '.join(s.skel_names)); sys.exit(0)
    who = 1 if args and args[0] == 'him' else 0
    a = args[1:]
    want = []
    while a and not (a[0][:1] in '+-' or ':' in a[0] or (a[0].startswith('m') and a[0][1:2].isdigit()) or a[0].replace('.', '').isdigit()):
        want.append(a.pop(0))
    idx = [(w, bone_idx(w)) for w in want]
    bad = [w for w, i in idx if i is None]
    if bad:
        sys.exit(f'no such bone: {bad} (lens.py bones names)')
    t0, t1, a = window(s, a)
    step = float(a[0]) if a else 0.25
    fr = s.frames(t0, t1, ['skel', 'skel_from', 'him', 'you', 'has_scene', 'under'])
    print(f'{"him" if who else "you"}: ' + ', '.join(f'{w}' for w, i in idx) + ': height over the floor under the actor (m), speed (m/s), from (model, * = drawn this frame)')
    last_t, prev, floor = -1e18, None, None
    rows = 0
    for f in fr:
        if f['has_scene'] and obs.finite(f['under'][who]):
            floor = (f['him'] if who else f['you'])[1] + f['under'][who]
        if f['t'] - last_t < step:
            continue
        cells = []
        for w, i in idx:
            b = obs.bone(f, who, i)
            if not b:
                cells.append(f'{w[:10]:>10} -'); continue
            sp = ''
            if prev and obs.bone(prev, who, i):
                q = obs.bone(prev, who, i); dt = max(f['t'] - prev['t'], 1e-6)
                sp = f'{math.dist(b, q) / dt:4.1f}'
            src = obs.bone_from(f, who, i)
            cells.append(f'{w[:10]:>10} {b[1] - floor if floor is not None else float("nan"):+.2f} {sp:>4} {"bhula"[src[0]]}{"*" if src[1] else " "}')
        print(f'{obs.hms(f["t"])} ' + ' '.join(cells))
        last_t, prev = f['t'], f
        rows += 1
        if rows >= 40:
            print('... (40 rows: narrow the window or raise step)'); break
    sys.exit(0)

def cam_view(f):
    """(heading of the camera's look in degrees, its pitch, metres behind you, his place on screen: 'on' | 'off' | 'hidden')"""
    c = f['cam']
    if not obs.finite(c[0]):
        return None
    d = (c[3] - c[0], c[4] - c[1], c[5] - c[2]); l = math.sqrt(sum(x * x for x in d)) or 1
    d = tuple(x / l for x in d)
    head = math.degrees(math.atan2(d[0], d[2])); pitch = math.degrees(math.asin(max(-1, min(1, d[1]))))
    back = math.dist((c[0], c[1], c[2]), f['you'])
    him = 'none'
    if obs.finite(f['cam_head'][1]):
        h = tuple(f['bone'][(15 + 13) * 3:(15 + 13) * 3 + 3]) if f['has'][1] >> 13 & 1 else None   # (his head: part 13)
        if h:
            v = (h[0] - c[0], h[1] - c[1], h[2] - c[2]); vl = math.sqrt(sum(x * x for x in v)) or 1
            # camera axes: forward d, right = d x up, up' = right x d; fov 50 deg vertical, 16:9 (an assumption)
            up = (c[6], c[7], c[8])
            rx = (d[1] * up[2] - d[2] * up[1], d[2] * up[0] - d[0] * up[2], d[0] * up[1] - d[1] * up[0]); rl = math.sqrt(sum(x * x for x in rx)) or 1
            rx = tuple(x / rl for x in rx)
            ux = (rx[1] * d[2] - rx[2] * d[1], rx[2] * d[0] - rx[0] * d[2], rx[0] * d[1] - rx[1] * d[0])
            zf = sum(a * b for a, b in zip(v, d)); xs = sum(a * b for a, b in zip(v, rx)); ys = sum(a * b for a, b in zip(v, ux))
            t = math.tan(math.radians(25))
            on = zf > 0.1 and abs(ys / zf) < t and abs(xs / zf) < t * 16 / 9
            hid = obs.finite(f['cam_hit'][1]) and f['cam_hit'][1] < f['cam_head'][1] - 0.3
            him = ('hidden' if hid else 'on') if on else 'off'
            if on:
                him += f'({xs / zf / (t * 16 / 9):+.1f},{ys / zf / t:+.1f})'
    return head, pitch, back, him


if what == 'input' and args and args[0] == 'summary':
    t0, t1, a = window(s, args[1:], whole=True)
    fr = [f for f in s.frames(t0, t1, ['in_user', 'cam', 'cam_head', 'cam_hit', 'you', 'him', 'bone', 'has'], every=3) if 'in_user' in f]
    import collections
    c, onx = collections.Counter(), []
    for f in fr:
        cv = cam_view(f)
        w = cv[3].split('(')[0] if cv else 'no camera'
        c[w] += 1
    tot = sum(c.values()) or 1
    print(f'{obs.hms(t0)} - {obs.hms(t1)}: him on your screen ' + ', '.join(f'{k} {v / tot * 100:.0f}%' for k, v in c.most_common()))
    sys.exit(0)

if what == 'input':
    t0, t1, a = window(s, args)
    fr = [f for f in s.frames(t0, t1, ['in_user', 'in_synth', 'in_mouse', 'in_buttons', 'in_pad_buttons', 'in_stick', 'in_look', 'cam', 'cam_head',
                                       'cam_hit', 'you', 'him', 'bone', 'has']) if 'in_user' in f]
    print(f'{"time":>10}  keys (yours / file)       mouse look   buttons          sticks L / R            camera look/pitch/back  him on screen')
    last, rows, last_t = None, 0, -1e18
    for f in fr:
        ku, ks = obs.keys_held(f['in_user']), obs.keys_held(f['in_synth'])
        mo = ['L', 'R', 'M', '4', '5']
        mb = [mo[k] for k in range(5) if f['in_mouse'] >> k & 1]
        b = obs.buttons(f['in_buttons'] | f['in_pad_buttons'])
        st = f['in_stick']
        look = f['in_look']
        cv = cam_view(f)
        key = (tuple(ku), tuple(ks), tuple(mb), tuple(b), tuple(st), abs(look[0]) > 0.05 or abs(look[1]) > 0.05, cv[3].split('(')[0] if cv else None)
        if key == last and f['t'] - last_t < 2:
            continue
        last, last_t = key, f['t']
        cam = f'{cv[0]:+5.0f} {cv[1]:+4.0f} {cv[2]:4.1f}m' if cv else '-'
        print(f'{obs.hms(f["t"])}  {"+".join(ku) or "-":<12} / {"+".join(ks) or "-":<10} {"+".join(mb) or "":<2}{look[0]:+.2f},{look[1]:+.2f}  {" ".join(b) or "-":<16} '
              f'{st[0]:+6d},{st[1]:+6d} / {st[2]:+6d},{st[3]:+6d}  {cam:<22}  {cv[3] if cv else "-"}')
        rows += 1
        if rows >= 40:
            print('... (40 rows)'); break
    sys.exit(0)

if what == 'gear':
    t0, t1, a = window(s, args)
    fr = [f for f in s.frames(t0, t1, ['ygear_out', 'gear_out', 'armed']) if 'ygear_out' in f]
    names = [(f, g) for f, g in s.gear]
    print('names (on a change):')
    shown = 0
    for f, g in names:
        tf = s.t_of_frame(f)
        if tf is not None and t0 - 60 <= tf <= t1:
            print(f'  {obs.hms(tf)}  {g[:200]}'); shown += 1
    if not shown and names:
        print(f'  (before the window) {names[-1][1][:200]}')
    def gear_angles(f):
        """per piece (weapon, bow, shield): the angle between his and yours, each in its Link's own frame (deg)"""
        if 'gear_rot' not in f:
            return None
        out = []
        for k in range(3):
            R = []
            for w, face in ((0, f['yface']), (1, f['hface'])):
                m = f['gear_rot'][w * 27 + k * 9:w * 27 + k * 9 + 9]
                if not obs.finite(m[0]):
                    R = None; break
                fx, fz = face
                cols = [(m[0], m[3], m[6]), (m[1], m[4], m[7]), (m[2], m[5], m[8])]
                R.append([(c[0] * -fz + c[2] * fx, c[0] * fx + c[2] * fz, c[1]) for c in cols])
            if not R:
                out.append(None); continue
            tr = sum(sum(a * b for a, b in zip(R[0][i], R[1][i])) for i in range(3))
            out.append(math.degrees(math.acos(max(-1, min(1, (tr - 1) / 2)))))
        return out
    fr2 = [f for f in s.frames(t0, t1, ['gear_rot', 'yface', 'hface', 'ygear_out', 'gear_out'], every=15) if 'gear_rot' in f]
    if fr2:
        print('his gear vs yours, the angle between them in each one\'s own frame (weapon / bow / shield; - = one of you has none), every ~0.5 s:')
        last, rows = None, 0
        for f in fr2:
            g = gear_angles(f)
            key = tuple(None if v is None else round(v / 10) for v in g)
            if key == last:
                continue
            last = key
            print(f'  {obs.hms(f["t"])}  ' + ' / '.join('-' if v is None else f'{v:3.0f} deg' for v in g) + f'   drawn you {list(f["ygear_out"])} him {list(f["gear_out"])}')
            rows += 1
            if rows >= 25:
                break
    print('drawn (1) / away (0) / none (-1), weapon bow shield, on every change:')
    last, rows = None, 0
    for f in fr:
        key = (tuple(f['ygear_out']), tuple(f['gear_out']), f['armed'])
        if key == last:
            continue
        last = key
        print(f'  {obs.hms(f["t"])}  you {list(f["ygear_out"])}  him {list(f["gear_out"])} (his armed flag {f["armed"]})'); rows += 1
        if rows >= 30:
            break
    sys.exit(0)

if what == 'compare':
    kind = args.pop(0) if args else 'jumps'
    t0, t1, a = window(s, args, whole=True)
    fr = s.frames(t0, t1, ['you', 'him', 'you_cmds', 'gait'])
    if kind in ('feet', 'bounce', 'turns'):
        def pct(xs, q):
            xs = sorted(xs); return xs[min(len(xs) - 1, int(q * len(xs)))] if xs else float('nan')
        res = {0: collections.defaultdict(list), 1: collections.defaultdict(list)}
        t = t0
        while t < t1:
            prev = None
            for f in s.frames(t, min(t + 60, t1), ['you', 'him', 'yface', 'hface', 'bone', 'has', 'fresh', 'has_scene', 'under', 'under_deg', 'paused'], every=2):
                if f['paused']:
                    prev = None; continue
                for w in (0, 1):
                    pos = f['him'] if w else f['you']
                    if not obs.finite(pos[0]):
                        continue
                    if kind == 'feet' and f['has_scene'] and obs.finite(f['under'][w]) and f['fresh'][w] >> 6 & 1 and f['fresh'][w] >> 7 & 1:
                        floor = pos[1] + f['under'][w]; deg = f['under_deg'][w]
                        toe = min(f['bone'][(w * 15 + 6) * 3 + 1], f['bone'][(w * 15 + 7) * 3 + 1]) - floor
                        if abs(f['under'][w]) < 0.3:   # (standing on it, not jumping)
                            res[w]['0-20 deg' if deg < 20 else '20-35 deg' if deg < 35 else '35+ deg'].append(toe)
                    if prev is not None and obs.finite((prev['him'] if w else prev['you'])[0]):
                        pp = prev['him'] if w else prev['you']; dt = f['t'] - prev['t']
                        if not 0.005 < dt < 0.2:
                            continue
                        sp = math.hypot(pos[0] - pp[0], pos[2] - pp[2]) / dt
                        if kind == 'bounce' and sp > 4 and f['fresh'][w] >> 12 & 1 and f['has_scene'] and obs.finite(f['under'][w]) and abs(f['under'][w]) < 0.3 and f['under_deg'][w] < 15:
                            # (over the floor under him, flat ground: his bob moves his whole placement, so not over his actor position)
                            res[w]['waist over the floor, running, flat'].append(f['bone'][(w * 15 + 12) * 3 + 1] - (pos[1] + f['under'][w]))
                        if kind == 'turns' and sp > 1:
                            fa, pa = (f['hface'], prev['hface']) if w else (f['yface'], prev['yface'])
                            d = math.degrees(math.atan2(fa[0], fa[1]) - math.atan2(pa[0], pa[1]))
                            res[w]['turn deg/s, moving'].append(abs((d + 180) % 360 - 180) / dt)
                prev = f
            t += 60
        print(f'{kind}: him vs you, {obs.hms(t0)} - {obs.hms(t1)} (p5 / median / p95, samples)')
        for key in sorted(set(res[0]) | set(res[1])):
            row = []
            for w in (1, 0):
                xs = res[w].get(key, [])
                if kind == 'bounce' and xs:
                    row.append(f'{"him" if w else "you"} {pct(xs, .05):+.2f} / {pct(xs, .5):+.2f} / {pct(xs, .95):+.2f} (range {pct(xs, .95) - pct(xs, .05):.2f}) n={len(xs)}')
                else:
                    row.append(f'{"him" if w else "you"} {pct(xs, .05):+.2f} / {pct(xs, .5):+.2f} / {pct(xs, .95):+.2f} n={len(xs)}')
            print(f'  {key:<28} ' + '   '.join(row))
        sys.exit(0)
    if kind != 'jumps':
        sys.exit('compare jumps|feet|bounce|turns')
    jg = gaits.index('jump') if 'jump' in gaits else -1
    out = []
    for who in (0, 1):
        i = 0
        while i < len(fr):
            f = fr[i]
            p = fr[i - 1] if i else None
            if who == 0:
                start = p is not None and 'Jump' in f['you_cmds'].split('|') and 'Jump' not in p['you_cmds'].split('|')
            else:
                start = p is not None and f['gait'] == jg and p['gait'] != jg
            if not start:
                i += 1; continue
            pos = lambda x: x['him'] if who else x['you']
            y0 = pos(f)[1]
            back = next((q for q in reversed(fr[max(0, i - 12):i]) if f['t'] - q['t'] >= 0.1), None)
            sp = math.hypot(pos(f)[0] - pos(back)[0], pos(f)[2] - pos(back)[2]) / (f['t'] - back['t']) if back else float('nan')
            peak, tp, j = y0, f['t'], i
            while j < len(fr) and fr[j]['t'] - f['t'] < 2.0:
                y = pos(fr[j])[1]
                if y > peak:
                    peak, tp = y, fr[j]['t']
                if fr[j]['t'] - f['t'] > 0.2 and y <= y0 + 0.02:
                    break
                j += 1
            out.append((f['t'], who, sp, peak - y0, tp - f['t'], pos(fr[j - 1])[1] - y0 if j > i else 0))
            i = j
    print(f'{"time":>10}  who  speed m/s  peak m  to peak s  landed vs take-off m')
    for t, who, sp, pk, tpk, land in sorted(out)[:40]:
        print(f'{obs.hms(t)}  {"him" if who else "you":<4} {sp:7.2f}  {pk:7.2f}  {tpk:7.2f}  {land:+7.2f}')
    sys.exit(0)

PARTS_DRAW = [('Head', 'o'), ('Spine_2', 'c'), ('Waist', 'w'), ('Finger_C_3_L', 'h'), ('Finger_C_3_R', 'h'), ('Knee_L', 'k'),
              ('Knee_R', 'k'), ('Toe_L', 'f'), ('Toe_R', 'f'), ('Ankle_L', 'f'), ('Ankle_R', 'f')]


def frame_at(t):
    fr = s.frames(t - 0.1, t + 0.1) or s.frames(t - 2, t + 2)
    return min(fr, key=lambda f: abs(f['t'] - t))


def body_points(f):
    out = []
    for who in (0, 1):
        for bn, ch in PARTS_DRAW:
            i = bone_idx(bn)
            b = obs.bone(f, who, i) if i is not None else None
            if b:
                out.append((who, bn, ch.upper() if who else ch, b))
    return out


def inside_list(world, f):
    """(who, bone, depth) for every bone of both of you inside rock"""
    out = []
    for who in (0, 1):
        for i, bn in enumerate(s.skel_names):
            b = obs.bone(f, who, i)
            if b:
                d = world.depth(*b)
                if d:
                    out.append((who, bn, d))
    return out


def print_inside(world, f):
    ins = inside_list(world, f)
    for who in (0, 1):
        mine = sorted([(d, bn) for w_, bn, d in ins if w_ == who], reverse=True)
        n = sum(1 for i in range(len(s.skel_names)) if obs.bone(f, who, i))
        print(f'{"him" if who else "you"}: {len(mine)} of {n} bones inside rock' + (': ' + ', '.join(f'{bn} {d:.2f}' for d, bn in mine[:8]) if mine else ''))


if what in ('slice', 'top'):
    if not args:
        sys.exit('slice|top <t> ...')
    t = obs.parse_time(args[0], s); a = args[1:]
    f = frame_at(t)
    world = obs.World(s, f['t'], f['him'] if 'around' not in sys.argv or sys.argv[sys.argv.index('around') + 1] != 'you' else f['you'])
    who = 1
    if 'around' in a:
        k = a.index('around'); who = 0 if a[k + 1] == 'you' else 1; del a[k:k + 2]
    c = f['him'] if who else f['you']
    face = f['hface'] if who else f['yface']
    pts = body_points(f)
    print(f'{obs.hms(f["t"])} f={f["frame"]}  {len(s.scans)} scans in the session, around {"him" if who else "you"} at {c[0]:.1f},{c[1]:.1f},{c[2]:.1f}')
    if what == 'slice':
        axis = a.pop(0) if a and a[0] in ('his', 'your', 'x', 'z') else 'his'
        half = float(a[0]) if a else 4.0
        d = {'his': f['hface'], 'your': f['yface'], 'x': (1, 0), 'z': (0, 1)}[axis]
        r = (-d[1], d[0])   # (left of the cut is -; the view's right = along d)
        tall = 'tall' in a
        if tall:
            a.remove('tall')
        ys = [p[3][1] for p in pts if abs(p[3][1] - c[1]) < 30] + [c[1]]
        y0, y1 = min(ys) - 1.5, max(ys) + (11.0 if tall else 2.0)
        y0, y1 = max(y0, y1 - (16.0 if tall else 8.0)), y1
        cols = int(half * 2 / 0.25) + 1
        print(f'side view along {axis} facing (left = behind, right = ahead), 0.25 m cells, rows = height from his feet')
        for yi in range(int((y1 - y0) / 0.25), -1, -1):
            y = y0 + yi * 0.25
            row = []
            for ci in range(cols):
                u = -half + ci * 0.25
                x, z = c[0] + d[0] * u, c[2] + d[1] * u
                v = world.solid(x, y + 0.125, z)
                if v is None:
                    ch = ' '
                elif v:
                    above, below = world.solid(x, y + 0.375, z), world.solid(x, y - 0.125, z)
                    ch = '-' if above is False else '^' if below is False else '#'
                else:
                    ch = '.'
                for who_, bn, pc, b in pts:
                    du = (b[0] - c[0]) * d[0] + (b[2] - c[2]) * d[1]
                    dl = (b[0] - c[0]) * r[0] + (b[2] - c[2]) * r[1]
                    if abs(dl) < 0.5 and abs(du - u) < 0.125 and y <= b[1] < y + 0.25:
                        ch = pc
                row.append(ch)
            print(f'{y - c[1]:+5.2f} ' + ''.join(row))
    else:
        hk = {'feet': 0.1, 'knee': 0.5, 'chest': 1.3, 'head': 1.7}
        h = hk.get(a[0], None) if a else 1.3
        if h is None:
            h = float(a[0])
        y = c[1] + h
        fx, fz = face
        rx, rz = -fz, fx   # (his right... as the body log: right = (-fz, fx))
        print(f'from above at {h:+.2f} m over his feet ({"his" if who else "your"} facing up), # rock . air, 0.25 m cells; letters: parts within 0.5 m of that height')
        for fi in range(16, -17, -1):
            row = []
            for ri in range(-16, 17):
                x, z = c[0] + fx * fi * 0.25 - rx * ri * 0.25, c[2] + fz * fi * 0.25 - rz * ri * 0.25
                v = world.solid(x, y, z)
                ch = ' ' if v is None else '#' if v else '.'
                for who_, bn, pc, b in pts:
                    if abs(b[1] - y) < 0.5:
                        fu = (b[0] - c[0]) * fx + (b[2] - c[2]) * fz; ru = -((b[0] - c[0]) * rx + (b[2] - c[2]) * rz)
                        if round(fu / 0.25) == fi and round(ru / 0.25) == ri:
                            ch = pc
                row.append(ch)
            print(''.join(row))
    print_inside(world, f)
    sys.exit(0)

PART_NAMES = None


def rock_parts(f, who, last):
    """the part names of who inside rock on this frame (the last known set when this frame checked the other Link)"""
    if 'rock_in' not in f:
        return None
    v = f['rock_in'][who * 15:(who + 1) * 15]
    if v[0] == 255 and all(x == 255 for x in v):
        return last
    names = s.layout.names.get('parts', [])
    return tuple(names[p] if p < len(names) else str(p) for p in range(15) if v[p] not in (0, 255))


if what == 'inside':
    t0, t1, a = window(s, args, whole=True)
    fr = [f for f in s.frames(t0, t1, ['rock_in', 'rock_top', 'rock_count', 'paused']) if 'rock_in' in f and not f['paused']]
    names = s.layout.names.get('parts', [])
    import collections
    new = any('rock_count' in f for f in fr)
    if not new:
        print('(an older recording: only the old count, which also flags shared faces: read "inside" as "maybe")')
    for who in (0, 1):
        chk = [f for f in fr if f['rock_in'][who * 15] != 255]
        sure = lambda f, p: f['rock_in'][who * 15 + p] not in (0, 255)
        maybe = lambda f, p: 'rock_count' in f and f['rock_in'][who * 15 + p] == 0 and f['rock_count'][who * 15 + p] not in (0, 255)
        depth = lambda f, p: f['rock_top'][who * 15 + p] / 100
        lvl = collections.Counter()
        for f in chk:
            for p in range(15):
                if sure(f, p):
                    d = depth(f, p); lvl['touching (<0.10)' if d < 0.10 else 'in (0.10-0.30)' if d < 0.30 else 'deep (0.30+)'] += 1
        anyin = [f for f in chk if any(sure(f, p) and depth(f, p) >= 0.10 for p in range(15))]
        anymay = [f for f in chk if any(maybe(f, p) for p in range(15))]
        c = collections.Counter(); deep = collections.defaultdict(float)
        for f in anyin:
            for p in range(15):
                if sure(f, p):
                    c[names[p]] += 1; deep[names[p]] = max(deep[names[p]], f['rock_top'][who * 15 + p] / 100)
        print(f'{"him" if who else "you"}: part-frames {dict(lvl)}; a part 10 cm+ in rock in {len(anyin)} of {len(chk)} checked frames ({100 * len(anyin) / max(len(chk), 1):.1f}%)'
              + (': ' + ', '.join(f'{k} {v} (to {deep[k]:.2f} m)' for k, v in c.most_common(8)) if c else '')
              + (f'; maybe (the old count only) in {len(anymay)}' if new else ''))
        if who == 1:
            runs, cur = [], None
            for f in chk:
                n = sum(1 for p in range(15) if sure(f, p) and depth(f, p) >= 0.10)
                if n >= 3:
                    cur = cur or [f['t'], f['t'], 0]; cur[1] = f['t']; cur[2] = max(cur[2], n)
                elif cur and f['t'] - cur[1] > 0.3:
                    runs.append(cur); cur = None
            if cur:
                runs.append(cur)
            print(f'  his runs with 3+ parts 10 cm+ in rock: {len(runs)}' + (':' if runs else ''))
            for r0, r1, n in runs[:15]:
                print(f'    {obs.hms(r0)} - {obs.hms(r1)} ({r1 - r0:.1f} s), up to {n} of 15 parts')
    sys.exit(0)

if what == 'near':
    if not args:
        sys.exit('near <t> [r] [around you] [all]')
    t = obs.parse_time(args[0], s); a = args[1:]
    show_all = 'all' in a
    a = [x for x in a if x != 'all']
    who = 1
    if 'around' in a:
        k = a.index('around'); who = 0 if a[k + 1] == 'you' else 1; del a[k:k + 2]
    r = float(a[0]) if a else 20.0
    tn, acts = s.near_at(t)
    if tn is None:
        sys.exit('no actor lists in this recording')
    f = frame_at(t)
    c = f['him'] if who else f['you']; fx, fz = f['hface'] if who else f['yface']
    hide = ('Weapon_', 'Armor_', 'Accessory_', 'PlayerRaulHand', 'AsbObj_RockParts', 'MergedActor', 'PouchPlayer', 'Player')
    rows = []
    for name, x, y, z in acts:
        if not show_all and (name.startswith(hide) or 'Camera' in name):
            continue
        d = math.dist((x, y, z), c)
        if d > r:
            continue
        ox, oz = x - c[0], z - c[2]
        rows.append((d, name, ox * -fz + oz * fx, ox * fx + oz * fz, y - c[1]))
    rows.sort()
    print(f'{obs.hms(tn)} (list nearest {obs.hms(t)}): {len(rows)} actors within {r:.0f} m of {"him" if who else "you"}' + ('' if show_all else ' (gear, cameras, level chunks hidden: "all" shows them)'))
    for d, name, rx, fw, up in rows[:25]:
        print(f'  {d:5.1f} m  {name:<36} {"ahead" if fw >= 0 else "behind"} {abs(fw):4.1f}  {"right" if rx >= 0 else "left"} {abs(rx):4.1f}  up {up:+5.1f}')
    sys.exit(0)

if what == 'odd':
    import odd
    t0, t1, a = window(s, args)
    n = int(a[0]) if a else 15
    rows, (sw, sa) = odd.rank(s, t0, t1, n)
    print(f'{os.path.basename(pick)} {obs.hms(t0)} - {obs.hms(t1)}: the most unusual about him')
    print(f'{"score":>6}  {"what":<44} {"him":>7} {"peak":>7} {"you":>7} {"usual":>7}  usual = him-you (vs you) / his average (his rate)')
    for score, name, win, peak, usual, you_win, kind, when in rows:
        print(f'{score:6.1f}  {name[4:][:44]:<44} {win:7.2f} {peak:7.2f} {"-" if you_win is None else f"{you_win:7.2f}":>7} {usual:7.2f}  {kind:<8} worst {obs.hms(when + 0.5, False)}')
    print(f'his decisions (SAID lines): {sw:.2f} a second here, {sa:.2f} over the session')
    sys.exit(0)

if what == 'find':
    if not args:
        sys.exit('find <in rock|jump|climb|top|teleport|side|alarm <kind>|said <text>|mark> [t0 [t1]]')
    q = args[0]; a = args[1:]
    istime = lambda x: x[:1] in '+-' or ':' in x or (x.startswith('m') and x[1:2].isdigit())
    if q in ('in', 'alarm') and a:
        q = q + ' ' + a[0]; a = a[1:]
    elif q == 'said':
        words = []
        while a and not istime(a[0]):
            words.append(a.pop(0))
        q = 'said ' + ' '.join(words)
    t0, t1, a = window(s, a, whole=True)
    hits = []
    if q == 'mark':
        hits = [(s.wall(m['ns']), f'm{i} {m["why"][:60]} {m["note"][:30]}') for i, m in enumerate(s.marks)]
    elif q.startswith('said '):
        txt = q[5:].lower()
        for f, line in sorted(s.said.items()):
            if txt in line.lower():
                tt = s.t_of_frame(f)
                if tt is not None:
                    hits.append((tt, line.replace('[survey] lonk: ', '')[:110]))
    elif q == 'top':
        for f, line in sorted(s.said.items()):
            if 'over the top' in line or "wall's gone" in line:
                tt = s.t_of_frame(f)
                if tt is not None:
                    hits.append((tt, line.replace('[survey] lonk: ', '')[:110]))
    else:
        fields = {'in rock': ['rock_in', 'rock_top', 'paused'], 'jump': ['you_cmds', 'gait'], 'climb': ['climb'], 'teleport': ['teleports'],
                  'side': ['him', 'you', 'hface']}
        if q.startswith('alarm '):
            fl = ['alarms']
        elif q in fields:
            fl = fields[q]
        else:
            sys.exit(f'find: what is "{q}"?')
        names = s.layout.names
        jg = names.get('gaits', []).index('jump') if 'jump' in names.get('gaits', []) else -1
        al = names.get('alarms', []).index(q[6:]) if q.startswith('alarm ') and q[6:] in names.get('alarms', []) else None
        if q.startswith('alarm ') and al is None:
            sys.exit(f'alarm kinds: {names.get("alarms")}')
        prev, run = None, None
        t = t0
        while t < t1 and len(hits) < 30:
            for f in s.frames(t, min(t + 60, t1), fl):
                if q == 'in rock':
                    if 'rock_in' in f and f['rock_in'][15] != 255:
                        n = sum(1 for p in range(15) if f['rock_in'][15 + p] not in (0, 255) and f['rock_top'][15 + p] >= 10)
                        if n >= 3 and run is None:
                            run = [f['t'], f['t'], n]
                        elif n >= 3:
                            run[1] = f['t']; run[2] = max(run[2], n)
                        elif run and f['t'] - run[1] > 0.3:
                            hits.append((run[0], f'{run[1] - run[0]:.1f} s, up to {run[2]} of 15 parts')); run = None
                elif prev is not None:
                    if q == 'jump':
                        if 'Jump' in f['you_cmds'].split('|') and 'Jump' not in prev['you_cmds'].split('|'):
                            hits.append((f['t'], 'you jump'))
                        if f['gait'] == jg and prev['gait'] != jg:
                            hits.append((f['t'], 'he jumps'))
                    elif q == 'climb' and f['climb'] == 1 and prev['climb'] == 0:
                        hits.append((f['t'], 'he starts climbing'))
                    elif q == 'teleport' and f['teleports'] != prev['teleports']:
                        hits.append((f['t'], f'teleport #{f["teleports"]}'))
                    elif q == 'side' and obs.finite(f['him'][0]) and obs.finite(prev['him'][0]):
                        rx, prx = obs.rel(f['him'], f['hface'], f['you'])[0], obs.rel(prev['him'], prev['hface'], prev['you'])[0]
                        if (rx > 0.3 and prx < -0.3) or (rx < -0.3 and prx > 0.3):
                            hits.append((f['t'], f'you went to his {"right" if rx > 0 else "left"}'))
                    elif al is not None and f['alarms'] >> al & 1 and not prev['alarms'] >> al & 1:
                        hits.append((f['t'], f'alarm {q[6:]}'))
                prev = f
            t += 60
        if run:
            hits.append((run[0], f'{run[1] - run[0]:.1f} s, up to {run[2]} of 15 parts'))
    hits = [h for h in hits if t0 <= h[0] <= t1]
    print(f'{os.path.basename(pick)}: "{q}" {len(hits)} time(s)' + (' (first 30)' if len(hits) >= 30 else ''))
    for tt, txt in hits[:30]:
        print(f'  {obs.hms(tt)}  {txt}')
    sys.exit(0)

if what == 'story':
    t0, t1, a = window(s, args)
    every = float(a[0]) if a else 0.5
    fr = s.frames(t0, t1, ['kind', 'gait', 'climb', 'clip', 'air', 'swim', 'paused', 'emote', 'you_cmds', 'teleports', 'him_actor', 'alarms',
                           'buried', 'him', 'you', 'hface', 'has_scene', 'under', 'under_deg', 'src', 'scene', 'rock_in'])
    print(f'{os.path.basename(pick)} {obs.hms(t0)} - {obs.hms(t1)}: {len(fr)} frames')
    print(f'{"time":>10}  {"him":<26} {"you":<12} {"you r/f/up":<16} {"his floor":<20} {"rock k/c":<10} | events')
    marks_by_f = {}
    for i, m in enumerate(s.marks):
        marks_by_f.setdefault(m['frame'], []).append(f'MARK m{i} {m["why"][:40]}')
    last_key, last_t, prev, sc = None, -1e18, None, None
    last_rock = [(), ()]
    rows = 0
    for f in fr:
        st = f'{nm(moods, f["kind"])} {nm(gaits, f["gait"])}'
        if f['climb']:
            st += f' climb{f["climb"]} {nm(clips, f["clip"])}'
        fl = [x for x in ('air', 'swim', 'paused', 'emote') if f[x]]
        if fl:
            st += ' ' + ','.join(fl)
        you_cmd = next((x for x in f['you_cmds'].split('|') if x.strip()), '-').strip()[:12]
        ev = list(marks_by_f.get(f['frame'], []))
        if prev:
            if f['teleports'] != prev['teleports']:
                ev.append('TELEPORTED')
            if f['him_actor'] != prev['him_actor'] and prev['him_actor']:
                ev.append('NEW BODY')
        if f['alarms']:
            ev.append('ALARM ' + ' '.join(nm(alarms, k) for k in range(32) if f['alarms'] >> k & 1))
        said = s.said.get(f['frame'])
        if said:
            keep = [x for x in said.split(' ; ') if x and not x.startswith('frame=')]
            if keep:
                ev.append('SAID ' + ' ; '.join(x.replace('[survey] lonk: ', '') for x in keep))
        for who_ in (0, 1):
            rp = rock_parts(f, who_, last_rock[who_])
            if rp is not None and rp != last_rock[who_]:
                ev.append(f'IN ROCK {"him" if who_ else "you"}: ' + (', '.join(rp) if rp else 'out'))
                last_rock[who_] = rp
        bur = f['buried'] >= 5
        key = (st, you_cmd, bur)
        prev = f
        if not (key != last_key or ev or f['t'] - last_t >= every):
            continue
        last_key, last_t = key, f['t']
        r = ''
        if obs.finite(f['him'][0]) and obs.finite(f['you'][0]):
            x, z, y = obs.rel(f['him'], f['hface'], f['you'])
            r = f'{x:+.1f} {z:+.1f} {y:+.1f}'
        if f['has_scene']:
            sc = f
        floor = rock = ''
        if sc:
            f, f_now = sc, f
            u, d = f['under'][1], f['under_deg'][1]
            floor = f'{f["src"]} ' + (f'{u:+.2f}({d:.0f}d)' if obs.finite(u) else '-')
            near = []
            for k in (0, 1):
                v = [x for x in f['scene'][k * 16:(k + 1) * 16] if obs.finite(x)]
                near.append(f'{min(v):.1f}' if v else '-')
            rock = '/'.join(near)
            f = f_now
        if bur:
            ev.append(f'BURIED {f["buried"]}/6')
        print(f'{obs.hms(f["t"])}  {st[:26]:<26} {you_cmd:<12} {r:<16} {floor[:20]:<20} {rock:<10} | {" | ".join(ev)[:160]}')
        rows += 1
        if rows >= 60:
            print('... (60 rows: narrow the window or raise every)')
            break
    sys.exit(0)

sys.exit(__doc__)
