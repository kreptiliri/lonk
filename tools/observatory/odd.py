"""odd.py: what's unusual in a window of a recording, without knowing what the bug is (lens.py odd).

Every frame (every 2nd) becomes ~60 numbers a Link (speeds, turn rate, each part's speed against the waist and height
over the feet, depth in rock, parts not drawn, distance apart, how often his gait / mood / side / clip change, alarms,
his decisions...). The session is cut into 1 s buckets (mean of each number); the window's mean is scored against his
own buckets for the rest of the session (robust z: median and MAD) and against your buckets of the same number
(the reference for "normal": the game moves your Link correctly). Ranked by the larger score.
"""
import math, collections
import obs

PARTS = ['hand L', 'wrist L', 'elbow L', 'hand R', 'wrist R', 'elbow R', 'toe L', 'toe R', 'ankle L', 'ankle R',
         'knee L', 'knee R', 'waist', 'head', 'chest']
FIELDS = ['you', 'him', 'yface', 'hface', 'bone', 'has', 'fresh', 'rock_in', 'rock_top', 'gait', 'kind', 'climb', 'clip',
          'alarms', 'teleports', 'paused', 'anchor', 'rate', 'loop', 'air', 'swim', 'emote', 'gear_rot']


def gear_angle(f, k):
    """his piece k (0 weapon, 1 bow, 2 shield) against yours, each in its own Link's frame (deg), None if one has none"""
    R = []
    for w, face in ((0, f['yface']), (1, f['hface'])):
        m = f['gear_rot'][w * 27 + k * 9:w * 27 + k * 9 + 9]
        if not obs.finite(m[0]):
            return None
        fx, fz = face
        R.append([(c[0] * -fz + c[2] * fx, c[0] * fx + c[2] * fz, c[1]) for c in ((m[0], m[3], m[6]), (m[1], m[4], m[7]), (m[2], m[5], m[8]))])
    tr = sum(sum(a * b for a, b in zip(R[0][i], R[1][i])) for i in range(3))
    return math.degrees(math.acos(max(-1, min(1, (tr - 1) / 2))))


def frame_feats(p, f, alarms):
    """{name: value} for frame f (p = the previous kept frame); names start with 'him ' or 'you '"""
    out = {}
    dt = f['t'] - p['t']
    if not (0.005 < dt < 0.5) or f['paused']:
        return out
    for w, tag in ((1, 'him'), (0, 'you')):
        pos, pp = (f['him'], p['him']) if w else (f['you'], p['you'])
        face, pface = (f['hface'], p['hface']) if w else (f['yface'], p['yface'])
        if not (obs.finite(pos[0]) and obs.finite(pp[0])):
            continue
        out[f'{tag} speed'] = math.hypot(pos[0] - pp[0], pos[2] - pp[2]) / dt
        out[f'{tag} up/down speed'] = abs(pos[1] - pp[1]) / dt
        turn = math.degrees(math.atan2(face[0], face[1]) - math.atan2(pface[0], pface[1]))
        out[f'{tag} turn rate'] = abs((turn + 180) % 360 - 180) / dt
        fresh, has = f['fresh'][w], f['has'][w]
        out[f'{tag} parts not drawn'] = sum(1 for k in range(15) if not fresh >> k & 1) / 15
        b = lambda fr, k: fr['bone'][(w * 15 + k) * 3:(w * 15 + k) * 3 + 3]
        if has >> 12 & 1 and p['has'][w] >> 12 & 1:
            wa, pwa = b(f, 12), b(p, 12)
            out[f'{tag} waist jump'] = math.dist(wa, pwa) / dt
            for k in range(15):
                if k == 12 or not (has >> k & 1 and p['has'][w] >> k & 1 and fresh >> k & 1):
                    continue
                rel = [b(f, k)[i] - wa[i] for i in range(3)]; prel = [b(p, k)[i] - pwa[i] for i in range(3)]
                out[f'{tag} {PARTS[k]} speed against the waist'] = math.dist(rel, prel) / dt
                out[f'{tag} {PARTS[k]} height over the feet'] = b(f, k)[1] - pos[1]
        ri = f['rock_in'][w * 15:(w + 1) * 15] if 'rock_in' in f else (255,)
        if ri[0] != 255:
            for k in range(15):
                if ri[k] not in (0, 255):
                    out[f'{tag} {PARTS[k]} in rock (m)'] = max(out.get(f'{tag} {PARTS[k]} in rock (m)', 0), f['rock_top'][w * 15 + k] / 100)
                elif ri[k] == 0:
                    out.setdefault(f'{tag} {PARTS[k]} in rock (m)', 0.0)
    if obs.finite(f['him'][0]) and obs.finite(f['you'][0]):
        out['him distance from you'] = math.dist(f['him'], f['you'])
        rx = obs.rel(f['him'], f['hface'], f['you'])[0]; prx = obs.rel(p['him'], p['hface'], p['you'])[0]
        out['him side flips (you right/left of him)'] = 1.0 / dt if (rx > 0.3 and prx < -0.3) or (rx < -0.3 and prx > 0.3) else 0.0
        if 'anchor' in f and obs.finite(f['anchor'][0]):
            out['him placed vs where the game has him (m)'] = math.dist(f['anchor'], f['him'])
    if 'gear_rot' in f:
        for k, nm in enumerate(('weapon', 'bow', 'shield')):
            g = gear_angle(f, k)
            if g is not None:
                out[f'him {nm} angle vs yours (deg)'] = g
    out['him gait changes'] = (f['gait'] != p['gait']) / dt
    out['him mood changes'] = (f['kind'] != p['kind']) / dt
    out['him climb state changes'] = (f['climb'] != p['climb'] or f['clip'] != p['clip']) / dt
    out['him teleports'] = (f['teleports'] != p['teleports']) / dt
    out['him in the air'] = float(f['air'])
    out['him clip rate'] = f['rate'] if obs.finite(f['rate']) else 0.0
    for k, nm in enumerate(alarms):   # (0 when it didn't go off: a bucket's mean is then a rate a second)
        out[f'him alarm {nm}'] = (1.0 / dt) if f['alarms'] >> k & 1 else 0.0
    return out


def buckets(s, t0, t1, every=3):   # (3: the rock check alternates him (even frames) and you (odd): both get read)
    """{name: {second: [sum, n]}} over t0..t1, read a minute at a time"""
    alarms = s.layout.names.get('alarms', [])
    acc = collections.defaultdict(dict)
    t = t0
    prev = None
    while t < t1:
        fr = s.frames(t, min(t + 60, t1), FIELDS, every=every)
        for f in fr:
            if prev is not None:
                sec = int(f['t'])
                for k, v in frame_feats(prev, f, alarms).items():
                    if v != v:
                        continue
                    a = acc[k].setdefault(sec, [0.0, 0])
                    a[0] += v; a[1] += 1
            prev = f
        t += 60
    return acc


def said_rate(s, t0, t1):
    n = sum(1 for f in s.said if (lambda tt: tt is not None and t0 <= tt <= t1)(s.t_of_frame(f)))
    return n / max(t1 - t0, 1e-6)


RATES = ('changes', 'flips', 'teleports', 'alarm ', 'in the air')


def cached_buckets(s):
    """buckets() over the whole session, kept next to it (odd_cache) and only topped up for what was recorded since"""
    import os, pickle
    path = s.path + '.odd_cache'
    t0, t1 = s.span()
    acc, done = {}, t0
    try:
        with open(path, 'rb') as fh:
            c = pickle.load(fh)
        if c.get('v') == 5:
            acc, done = c['acc'], c['done']
    except Exception:
        pass
    if done < t1 - 1:
        new = buckets(s, max(t0, done - 1), t1)
        for k, by in new.items():
            acc.setdefault(k, {}).update(by)
        try:
            with open(path, 'wb') as fh:
                pickle.dump({'v': 5, 'acc': acc, 'done': t1}, fh)
        except Exception:
            pass
    return acc


def noise_floor(name):
    """the least difference that means anything, in the channel's own units (so a still second's tiny spread doesn't
    turn 0.2 m/s into a score of 20)"""
    for key, v in (('speed', 0.1), ('height', 0.03), ('in rock', 0.05), ('turn rate', 10.0), ('distance', 0.2), ('not drawn', 0.05),
                   ('waist jump', 0.1), ('placed vs', 0.05), ('clip rate', 0.1)):
        if key in name:
            return v
    return 0.01


def robust(xs):
    xs = sorted(xs)
    med = xs[len(xs) // 2]
    mad = sorted(abs(x - med) for x in xs)[len(xs) // 2]
    return med, mad


def rank(s, w0, w1, top=15):
    t0, t1 = s.span()
    acc = cached_buckets(s)
    mean = lambda by, sec: by[sec][0] / by[sec][1]
    inwin = lambda sec: w0 <= sec + 0.5 <= w1
    away = lambda sec: not (w0 - 5 <= sec + 0.5 <= w1 + 5)
    rows = []
    for name, by in acc.items():
        if not name.startswith('him '):
            continue
        secs = [sec for sec in by if inwin(sec)]
        if not secs:
            continue
        win = sum(mean(by, x) for x in secs) / len(secs)
        peak = max(mean(by, x) for x in secs)
        yn = 'you ' + name[4:]
        yby = acc.get(yn)
        you_win = None
        if name.endswith('angle vs yours (deg)'):
            # his piece against yours: the same piece held the same way is 0, ~15 deg of wobble (the bow, measured)
            score = (win - 15) / 10
            usual, kind, you_win = 0.0, 'vs 0 deg', None
            when = max(secs, key=lambda x: mean(by, x))
        elif yby and not name[4:].startswith(RATES):
            # him - you, second by second: the window's against how much he usually differs from you
            both = [sec for sec in by if sec in yby]
            d_win = [mean(by, x) - mean(yby, x) for x in both if inwin(x)]
            ys = [mean(yby, x) for x in secs if x in yby]
            if not d_win or not ys:
                continue
            yw = sum(ys) / len(ys)
            d_rest = []
            for lo, hi in ((0.6, 1.6), (0.3, 3.0), (0.0, 1e9)):   # (seconds where your value was like yours here: like with like)
                d_rest = [mean(by, x) - mean(yby, x) for x in both if away(x) and lo * yw - 0.05 <= mean(yby, x) <= hi * yw + 0.05]
                if len(d_rest) >= 20:
                    break
            if len(d_rest) < 20:
                continue
            med, mad = robust(d_rest)
            dw = sum(d_win) / len(d_win)
            score = (dw - med) / (1.4826 * mad + 0.05 * (abs(med) + abs(dw)) + noise_floor(name))
            you_win = yw
            usual = med
            kind = 'vs you'
            when = max(secs, key=lambda x: abs((mean(by, x) - mean(yby, x) if x in yby else 0) - med))
        else:
            # his own rate here against his rate over the session (per-second spread)
            rest = [mean(by, x) for x in by if away(x)]
            nsec = max(1, int(t1 - t0) - len(secs))
            avg = sum(rest) / nsec
            var = sum(v * v for v in rest) / nsec - avg * avg
            score = (win - avg) / (math.sqrt(max(var, 0)) + 0.05 * avg + 1e-3)
            usual = avg
            kind = 'his rate'
            when = max(secs, key=lambda x: mean(by, x))
        rows.append((score, name, win, peak, usual, you_win, kind, when))
    rows.sort(key=lambda r: -abs(r[0]))
    sr_w, sr_all = said_rate(s, w0, w1), said_rate(s, t0, t1)
    return rows[:top], (sr_w, sr_all)
