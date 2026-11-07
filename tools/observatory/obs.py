"""obs.py: reads the observatory's session recordings (lonk_session_*.obs next to the game log).

A file is a stream of records {u32 'LOBS', u16 type, u16 layout, u32 bytes, u32 count} + bytes:
  1 layout (text: fields by name/type/count/offset, name tables, clock), 2 frames (raw deflate, count frames),
  3 mark (u64 frame, u64 ns, "why\\tnote"), 4 said (u64 frame, u64 ns, text).
Used by lens.py. No numpy: struct + zlib only.
"""
import glob, math, os, struct, time, zlib

LOGS = os.path.expanduser('~/Library/Logs/MacNativeGames')
MAGIC = 0x53424f4c
NAN = float('nan')


def sessions():
    return sorted(glob.glob(os.path.join(LOGS, 'lonk_session_*.obs')))


class Layout:
    def __init__(self, text):
        self.fields, self.names, self.clock = [], {}, None
        for line in text.splitlines():
            w = line.split()
            if not w:
                continue
            if w[0] == 'frame_size':
                self.size = int(w[1])
            elif w[0] == 'clock':
                self.clock = (float(w[1]), int(w[2]))   # (wall seconds, uptime ns) at the same moment
            elif w[0] == 'field':
                self.fields.append((w[1], w[2], int(w[3]), int(w[4])))
            elif w[0] == 'names':
                rest = line.split(None, 1)[1]
                key, _, vals = rest.partition('|')
                self.names[key.strip()] = vals.split('|')
        fmt, pos, self.slots = '<', 0, []
        for name, ty, cnt, off in sorted(self.fields, key=lambda f: f[3]):
            if off > pos:
                fmt += f'{off - pos}x'
            if ty == 's':
                fmt += f'{cnt}s'; n = 1; size = cnt
            else:
                fmt += f'{cnt}{ty}'; n = cnt; size = cnt * struct.calcsize(ty)
            self.slots.append((name, ty, cnt, n))
            pos = off + size
        if self.size > pos:
            fmt += f'{self.size - pos}x'
        self.st = struct.Struct(fmt)
        self.by_name = {name: (ty, cnt, off) for name, ty, cnt, off in self.fields}
        assert self.st.size == self.size, (self.st.size, self.size)

    def decode_some(self, buf, at, names):
        out = {}
        for name in names:
            sl = self.by_name.get(name)
            if not sl:
                continue
            ty, cnt, off = sl
            if ty == 's':
                out[name] = buf[at + off:at + off + cnt].split(b'\0', 1)[0].decode('latin-1')
            elif cnt == 1:
                out[name] = struct.unpack_from('<' + ty, buf, at + off)[0]
            else:
                out[name] = struct.unpack_from(f'<{cnt}{ty}', buf, at + off)
        return out

    def decode(self, buf, at):
        vals = self.st.unpack_from(buf, at)
        out, k = {}, 0
        for name, ty, cnt, n in self.slots:
            if ty == 's':
                out[name] = vals[k].split(b'\0', 1)[0].decode('latin-1'); k += 1
            elif cnt == 1:
                out[name] = vals[k]; k += 1
            else:
                out[name] = vals[k:k + n]; k += n
        return out


class Session:
    """A recording, read lazily: the frame blocks stay packed and are indexed by their first/last frame and time; a view
    asks frames(t0, t1, fields) and only that window and those fields get unpacked (unpacking a whole hour with every
    bone took several GB and made the Mac swap, 2026-11-07)."""
    def __init__(self, path):
        self.path = path
        self.layouts, self.blocks, self.marks, self.said, self.skel_names = {}, [], [], {}, []
        self.gear, self.cmds = [], []   # (frame, text) on each change
        self.scans = []
        self.near = []   # (ns, frame, packed body): nearby actors once a second; near_at(t) unpacks one
        import mmap
        with open(path, 'rb') as fh:
            data = memoryview(mmap.mmap(fh.fileno(), 0, access=mmap.ACCESS_READ))   # (the OS pages it: not 200 MB of python bytes)
        at = 0
        while at + 16 <= len(data):
            magic, tl, ln, cnt = struct.unpack_from('<IIII', data, at)
            if magic != MAGIC or at + 16 + ln > len(data):
                break   # (a half-written last record)
            typ, lay = tl & 0xffff, tl >> 16
            body = data[at + 16:at + 16 + ln]
            if typ == 1:
                self.layouts[lay] = Layout(bytes(body).decode('latin-1'))
            elif typ == 2:
                L = self.layouts.get(lay)
                if L:
                    raw = zlib.decompress(body, -15)
                    n = min(cnt, len(raw) // L.size)
                    if n:
                        f0, ns0 = struct.unpack_from('<QQ', raw, 0)
                        f1, ns1 = struct.unpack_from('<QQ', raw, (n - 1) * L.size)
                        self.blocks.append({'L': L, 'body': body, 'n': n, 'f0': f0, 'f1': f1, 't0': ns0, 't1': ns1})
            elif typ == 5:
                self.skel_names = bytes(body).decode('latin-1').split('|')
            elif typ == 10:
                f, ns = struct.unpack_from('<QQ', zlib.decompress(body, -15), 0)   # (small: a few KB unpacked)
                self.near.append((ns, f, body))
            elif typ in (8, 9):
                self.scans.append(ScanRef(body, typ == 9, cnt))
            elif typ in (6, 7):
                f, ns = struct.unpack_from('<QQ', body, 0)
                (self.gear if typ == 6 else self.cmds).append((f, bytes(body[16:]).decode('latin-1', 'replace')))
            elif typ in (3, 4):
                f, ns = struct.unpack_from('<QQ', body, 0)
                text = bytes(body[16:]).decode('latin-1', 'replace')
                if typ == 3:
                    why, _, note = text.partition('\t')
                    self.marks.append({'frame': f, 'ns': ns, 'why': why, 'note': note})
                else:
                    self.said[f] = (self.said[f] + ' ; ' if f in self.said else '') + text.strip().replace('\n', ' ; ')
            at += 16 + ln
        for b in self.blocks:
            b['w0'], b['w1'] = self.wall(b['t0'], b['L']), self.wall(b['t1'], b['L'])
        self.blocks.sort(key=lambda b: b['f0'])

    @property
    def layout(self):
        return self.layouts[max(self.layouts)] if self.layouts else None

    def count(self):
        return sum(b['n'] for b in self.blocks)

    def frames(self, t0=None, t1=None, fields=None, every=1):
        """the frames from t0 to t1 (seconds since 1970; None = the start / the end), in frame order, a frame recorded
        twice across a reload once; with fields, only those (plus frame, ns, t) are unpacked; every: keep 1 in n"""
        byf = {}
        want = None if fields is None else set(fields) | {'frame', 'ns'}
        for b in self.blocks:
            if (t0 is not None and b['w1'] < t0) or (t1 is not None and b['w0'] > t1):
                continue
            L = b['L']
            raw = zlib.decompress(b['body'], -15)
            for k in range(0, b['n']):
                f_, ns = struct.unpack_from('<QQ', raw, k * L.size)
                if every > 1 and f_ % every:
                    continue
                t = self.wall(ns, L)
                if (t0 is not None and t < t0) or (t1 is not None and t > t1):
                    continue
                fr = L.decode(raw, k * L.size) if want is None else L.decode_some(raw, k * L.size, want)
                fr['t'] = t
                byf[f_] = fr
        return [byf[f] for f in sorted(byf)]

    def wall(self, ns, L=None):
        """uptime ns -> seconds since 1970 (CLOCK_UPTIME_RAW is the same clock in every build: any layout's clock does)"""
        L = L if L is not None and L.clock else next((x for x in self.layouts.values() if x.clock), None)
        if not L:
            return ns / 1e9
        return L.clock[0] + (ns - L.clock[1]) / 1e9

    def near_at(self, t):
        """(time, [(name, x, y, z)]) of the actor list nearest to t"""
        if not self.near:
            return None, []
        ns, f, body = min(self.near, key=lambda x: abs(self.wall(x[0]) - t))
        raw = zlib.decompress(body, -15)
        out = []
        for line in raw[16:].decode('latin-1').splitlines():
            w = line.split()
            if len(w) == 4:
                out.append((w[0], float(w[1]), float(w[2]), float(w[3])))
        return self.wall(ns), out

    def t_of_frame(self, f):
        """the time of frame number f (from the block holding it, in proportion), None if not recorded"""
        for b in self.blocks:
            if b['f0'] <= f <= b['f1']:
                return b['w0'] + (b['w1'] - b['w0']) * (f - b['f0']) / max(b['f1'] - b['f0'], 1)
        return None

    def span(self):
        if not self.blocks:
            return (0, 0)
        return (min(b['w0'] for b in self.blocks), max(b['w1'] for b in self.blocks))


def hms(t, ms=True):
    lt = time.localtime(t)
    return time.strftime('%H:%M:%S', lt) + (f'.{int((t % 1) * 10)}' if ms else '')


def parse_time(spec, s, base=None):
    """HH:MM:SS[.s] (today, local) | +S (from the start) | -S (before the end) | mK[+-S] (bookmark K) | a float = seconds since 1970"""
    t0, t1 = s.span()
    if spec.startswith('m') and len(spec) > 1:
        num, off = spec[1:], 0.0
        for sep in '+-':
            if sep in num[1:]:
                i = num.index(sep, 1); off = float(num[i:]); num = num[:i]
        m = s.marks[int(num)]
        return s.wall(m['ns']) + off
    if ':' in spec:
        hh, mm, ss = spec.split(':')
        lt = time.localtime(base if base is not None else t1)
        day = time.mktime((lt.tm_year, lt.tm_mon, lt.tm_mday, 0, 0, 0, 0, 0, -1))
        t = day + int(hh) * 3600 + int(mm) * 60 + float(ss)
        if t > t1 + 43200:
            t -= 86400   # (after midnight: the clock reads earlier than the session's start day)
        return t
    if spec.startswith('+'):
        return t0 + float(spec[1:])
    if spec.startswith('-'):
        return t1 + float(spec)
    return float(spec)


PART_BONES = ["Finger_C_3_L", "Wrist_L", "Elbow_L", "Finger_C_3_R", "Wrist_R", "Elbow_R", "Toe_L", "Toe_R",
              "Ankle_L", "Ankle_R", "Knee_L", "Knee_R", "Waist", "Head", "Spine_2"]   # (the 15 parts' bones, as in world_survey.c)
PART_ALIAS = {"hand L": "Finger_C_3_L", "hand R": "Finger_C_3_R", "chest": "Spine_2", "waist": "Waist", "head": "Head"}


def bone(fr, who, idx):
    """bone idx of you (0) or him (1) in world metres, or None"""
    if 'skel' not in fr:
        return None
    k = (who * 128 + idx) * 3
    v = fr['skel'][k:k + 3]
    if v[0] == -32768:
        return None
    base = fr['him'] if who else fr['you']
    return (base[0] + v[0] / 1000, base[1] + v[1] / 1000, base[2] + v[2] / 1000)


def bone_from(fr, who, idx):
    """(model 0-4, drawn this frame) or None"""
    b = fr['skel_from'][who * 128 + idx]
    return None if b == 0xff else (b & 7, bool(b & 8))


KEYS = {0: 'A', 1: 'S', 2: 'D', 3: 'F', 4: 'H', 5: 'G', 6: 'Z', 7: 'X', 8: 'C', 9: 'V', 11: 'B', 12: 'Q', 13: 'W', 14: 'E', 15: 'R',
        16: 'Y', 17: 'T', 31: 'O', 32: 'U', 34: 'I', 35: 'P', 36: 'return', 37: 'L', 38: 'J', 40: 'K', 45: 'N', 46: 'M', 48: 'tab',
        49: 'space', 51: 'delete', 53: 'esc', 56: 'shift', 58: 'option', 59: 'control', 55: 'cmd', 60: 'rshift', 123: 'left',
        124: 'right', 125: 'down', 126: 'up', 18: '1', 19: '2', 20: '3', 21: '4', 23: '5', 22: '6', 26: '7', 28: '8', 25: '9', 29: '0'}
BUTTONS = ['A', 'B', 'X', 'Y', 'LS', 'RS', 'L', 'R', 'ZL', 'ZR', '+', '-', 'Dleft', 'Dup', 'Dright', 'Ddown']


def keys_held(mask):
    return [KEYS.get(k, str(k)) for k in range(128) if mask[k >> 3] >> (k & 7) & 1]


def buttons(b):
    return [BUTTONS[k] if k < len(BUTTONS) else f'b{k}' for k in range(64) if b >> k & 1]


def facing_deg(f2):
    return math.degrees(math.atan2(f2[0], f2[1]))


def rel(him, hface, you):
    """you from him: (right, forward, up) in his facing"""
    fx, fz = hface
    ox, oz = you[0] - him[0], you[2] - him[2]
    return ox * -fz + oz * fx, ox * fx + oz * fz, you[1] - him[1]


def finite(v):
    return v is not None and not (isinstance(v, float) and math.isnan(v))


class ScanRef:
    """a scan still packed: its header (when, where, round whom) read; load() unpacks it"""
    def __init__(self, body, packed, size):
        self.body, self.packed = body, packed
        head = bytes(zlib.decompressobj(-15).decompress(body, 64)) if packed else bytes(body[:44])
        self.frame, self.ns = struct.unpack_from('<QQ', head, 0)
        self.c = struct.unpack_from('<3f', head, 16)
        self.n, self.who, self.why = struct.unpack_from('<HBB', head, 40)
        self._scan = None

    def load(self):
        if self._scan is None:
            self._scan = Scan(zlib.decompress(self.body, -15) if self.packed else bytes(self.body))
        return self._scan


class Scan:
    """one 3D rock scan: columns round a centre, each a list of surfaces (y, underside?, layer), highest first"""
    def __init__(self, b):
        self.frame, self.ns = struct.unpack_from('<QQ', b, 0)
        x, y, z, self.step, top, bot = struct.unpack_from('<6f', b, 16)
        self.c = (x, y, z); self.top, self.bot = y + top, y + bot
        self.n, self.who, self.why = struct.unpack_from('<HBB', b, 40)
        at, half = 44, (self.n - 1) / 2 * self.step
        self.cols = {}
        for ix in range(self.n):
            for iz in range(self.n):
                cnt = b[at]; at += 1
                surf = []
                for k in range(cnt):
                    v, ly = struct.unpack_from('<hB', b, at); at += 3
                    surf.append((y + (v >> 1) / 100, v & 1, ly))
                self.cols[(round((x - half + ix * self.step) / self.step), round((z - half + iz * self.step) / self.step))] = (surf, self.top, self.bot)


class World:
    """the rock round a place from the scans (static: the scan nearest in time to t wins each column); only scans whose
    centre is within reach (m) of where, and at most limit of them, get unpacked"""
    def __init__(self, session, t=None, where=None, reach=10.0, limit=60):
        self.step = 0.25
        self.cols = {}
        sc = session.scans
        if where is not None:
            sc = [x for x in sc if math.hypot(x.c[0] - where[0], x.c[2] - where[2]) < reach and abs(x.c[1] - where[1]) < 15]
        if t is not None:
            sc = sorted(sc, key=lambda s_: abs(session.wall(s_.ns) - t))[:limit]
        else:
            sc = sc[-limit:]
        for ref in sorted(sc, key=lambda s_: -abs(session.wall(s_.ns) - t)) if t is not None else sc:
            s_ = ref.load()
            self.step = s_.step
            self.cols.update(s_.cols)

    def column(self, x, z):
        return self.cols.get((round(x / self.step), round(z / self.step)))

    def solid(self, x, y, z):
        """True / False, or None where no scan reached"""
        c = self.column(x, z)
        if not c or not (c[2] < y < c[1]):
            return None
        surf = c[0]
        d = 1 if surf and surf[0][1] else 0   # (the column's top began inside rock)
        for h, under, ly in surf:
            if h < y:
                break
            d += -1 if under else 1
        return d > 0

    def depth(self, x, y, z):
        """how far a point inside rock is from air (m): the nearest surface above or below in its column, or the nearest
        column that's air at that height (out to 2 m, in rings of cells); 0 if in air, None where nothing was scanned"""
        s_ = self.solid(x, y, z)
        if not s_:
            return None if s_ is None else 0.0
        c = self.column(x, z)[0]
        best = min(min((h - y for h, u, l in c if h >= y), default=9), min((y - h for h, u, l in c if h < y), default=9))
        st = self.step
        for ring in range(1, 9):
            if ring * st >= best:
                break
            for i in range(-ring, ring + 1):
                for j in (-ring, ring):
                    for a, b in ((i, j), (j, i)):
                        if self.solid(x + a * st, y, z + b * st) is False:
                            best = min(best, math.hypot(a, b) * st)
        return best
