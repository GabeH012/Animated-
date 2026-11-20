"""'The Greenhouse' — wordless short: three gardeners, three habits, three plants.

amber  (motivation): waters eagerly on day one, then sits down with a phone -> plant dries out
teal   (discipline): waters once every day                                -> plant blooms into a sunflower
coral  (obsession) : pours non-stop                                       -> plant shoots up, then drowns

No text, no UI. Rulers (tick marks only) show plant height.
Usage: python3 story3.py -> out/greenhouse.mp4 (1080x1920, 16 s, 30 fps)
"""
import math, os, random, subprocess, wave
import numpy as np
import cairo
from render import lerp, clamp, ease, ease_out, ease_back, rrect, COL, text, FONT_BOLD
from story2 import (walk, stand, sit_phone, celebrate, blend, set_hand, fig, can, phone,
                    drops, sky_day, grad, vignette, heart)

W, H, FPS, DUR = 1080, 1920, 30, 16.0
NF = int(DUR * FPS)
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "out")

FLOOR = 1580
POT_TOP = FLOOR - 125
S = 0.75
MAXH = 640
COLS = {"mot": 175, "dis": 520, "obs": 865}
T_LAPSE0, T_LAPSE1, DAYP = 4.0, 13.0, 0.9
WIN = (240, 170, 600, 470)   # window rect

def daylight(t):
    if t < T_LAPSE0: return 1.0, 0.0
    if t > T_LAPSE1: return 1.0, (T_LAPSE1 - T_LAPSE0) / DAYP
    dp = (t - T_LAPSE0) / DAYP
    return math.cos(2 * math.pi * dp), dp

# ---------------------------------------------------------------- room
def room_bg():
    s = cairo.ImageSurface(cairo.FORMAT_ARGB32, W, H); cr = cairo.Context(s)
    cr.set_source(grad(cr, 0, FLOOR, [(0, (0.93, 0.83, 0.68)), (1, (0.85, 0.68, 0.52))])); cr.paint()
    # wallpaper stripes
    for x in range(0, W, 60):
        cr.set_source_rgba(1, 1, 1, 0.05); cr.rectangle(x, 0, 28, FLOOR); cr.fill()
    # shelves with little pots
    for sx, sy in ((40, 760), (900, 700)):
        cr.set_source_rgb(0.5, 0.33, 0.2); cr.rectangle(sx, sy, 150, 14); cr.fill()
        for i in range(2):
            px = sx + 35 + i * 75
            cr.set_source_rgb(0.75, 0.42, 0.3); cr.move_to(px - 20, sy - 40); cr.line_to(px + 20, sy - 40)
            cr.line_to(px + 14, sy); cr.line_to(px - 14, sy); cr.close_path(); cr.fill()
            cr.set_source_rgb(0.3, 0.6, 0.35)
            for a in (-0.6, 0, 0.6):
                cr.save(); cr.translate(px, sy - 44); cr.rotate(a); cr.scale(8, 22); cr.arc(0, -1, 1, 0, 7); cr.restore(); cr.fill()
    # baseboard + wooden floor
    cr.set_source(grad(cr, FLOOR, H, [(0, (0.55, 0.36, 0.22)), (1, (0.25, 0.15, 0.1))])); cr.rectangle(0, FLOOR, W, H - FLOOR); cr.fill()
    cr.set_source_rgb(0.97, 0.94, 0.88); cr.rectangle(0, FLOOR - 26, W, 26); cr.fill()
    cr.set_source_rgba(0, 0, 0, 0.12); cr.set_line_width(3)
    for i in range(1, 9):
        y = FLOOR + (H - FLOOR) * (i / 9) ** 1.4
        cr.move_to(0, y); cr.line_to(W, y); cr.stroke()
    return s

def window(cr, t):
    e, dp = daylight(t)
    x, y, w, h = WIN
    top, hor = sky_day(e)
    cr.save(); rrect(cr, x, y, w, h, 18); cr.clip()
    cr.set_source(grad(cr, y, y + h, [(0, top), (1, hor)])); cr.paint()
    rnd = random.Random(5)
    for _ in range(40):
        cr.set_source_rgba(1, 1, 1, clamp(-e) * rnd.uniform(0.3, 0.9))
        cr.arc(x + rnd.uniform(0, w), y + rnd.uniform(0, h * 0.7), 2, 0, 7); cr.fill()
    a = 2 * math.pi * dp
    sx, sy = x + w / 2 + 230 * math.sin(a), y + h + 40 - 390 * math.cos(a)
    for i in range(5, 0, -1):
        cr.set_source_rgba(1, 0.9, 0.5, 0.07); cr.arc(sx, sy, 44 + i * 14, 0, 7); cr.fill()
    cr.set_source_rgb(1, 0.93, 0.62); cr.arc(sx, sy, 44, 0, 7); cr.fill()
    mx, my = x + w / 2 - 230 * math.sin(a), y + h + 40 + 390 * math.cos(a)
    cr.set_source_rgb(0.93, 0.93, 1); cr.arc(mx, my, 30, 0, 7); cr.fill()
    # rolling hills
    k = 0.4 + 0.6 * clamp(e * .5 + .5)
    cr.set_source_rgb(0.3 * k, 0.55 * k, 0.35 * k)
    cr.move_to(x, y + h - 70); cr.curve_to(x + 200, y + h - 150, x + 380, y + h - 30, x + w, y + h - 110)
    cr.line_to(x + w, y + h); cr.line_to(x, y + h); cr.fill()
    cr.restore()
    cr.set_source_rgb(0.97, 0.94, 0.88); cr.set_line_width(22)
    rrect(cr, x, y, w, h, 18); cr.stroke()
    cr.set_line_width(12); cr.move_to(x + w / 2, y); cr.line_to(x + w / 2, y + h); cr.move_to(x, y + h / 2); cr.line_to(x + w, y + h / 2); cr.stroke()
    cr.set_source_rgb(0.9, 0.86, 0.8); cr.rectangle(x - 30, y + h + 6, w + 60, 20); cr.fill()

def sunbeam(cr, t):
    e, _ = daylight(t)
    a = clamp(e) * 0.18
    if a <= 0: return
    x, y, w, h = WIN
    cr.set_source_rgba(1, 0.92, 0.65, a)
    cr.move_to(x, y + h); cr.line_to(x + w, y + h); cr.line_to(x + w + 260, FLOOR + 200); cr.line_to(x - 160, FLOOR + 200); cr.close_path(); cr.fill()

# ---------------------------------------------------------------- plant
def pot(cr, cx, col):
    cr.set_source_rgb(0.78, 0.44, 0.3)
    cr.move_to(cx - 78, POT_TOP); cr.line_to(cx + 78, POT_TOP); cr.line_to(cx + 58, FLOOR - 4); cr.line_to(cx - 58, FLOOR - 4); cr.close_path(); cr.fill()
    cr.set_source_rgb(0.85, 0.5, 0.35); rrect(cr, cx - 88, POT_TOP - 8, 176, 30, 8); cr.fill()
    cr.set_source_rgb(*col); cr.rectangle(cx - 58, POT_TOP + 48, 116, 10); cr.fill()   # owner color band
    cr.set_source_rgb(0.3, 0.2, 0.14); cr.save(); cr.translate(cx, POT_TOP - 6); cr.scale(76, 10); cr.arc(0, 0, 1, 0, 7); cr.restore(); cr.fill()

def plant(cr, cx, h, dry=0.0, rot=0.0, bloom=0.0, sway=0.0, dirn=1):
    """returns the (x,y) of the stem tip"""
    base = (cx, POT_TOP - 8)
    L = 30 + h * MAXH
    N = 24
    droop = (dry * 1.3 + rot * 2.0) * dirn
    healthy = (0.3, 0.72, 0.36)
    col = tuple(lerp(healthy[i], (0.6, 0.45, 0.25)[i], dry) for i in range(3))
    col = tuple(lerp(col[i], (0.72, 0.68, 0.22)[i], rot) for i in range(3))
    pts = [base]; ang = -math.pi / 2
    for i in range(1, N + 1):
        u = i / N
        a = ang + droop * u ** 2 + math.sin(sway + u * 2) * 0.04 * u
        p = pts[-1]
        pts.append((p[0] + math.cos(a) * L / N, p[1] + math.sin(a) * L / N))
    cr.set_source_rgb(*col); cr.set_line_width(lerp(7, 16, h)); cr.set_line_cap(cairo.LINE_CAP_ROUND)
    cr.move_to(*pts[0])
    for p in pts[1:]: cr.line_to(*p)
    cr.stroke()
    nleaf = int(2 + h * 12)
    for j in range(nleaf):
        u = (j + 1) / (nleaf + 1)
        i = int(u * N)
        p = pts[i]
        side = 1 if j % 2 else -1
        size = (20 + 40 * h) * (1.1 - u * 0.5)
        tilt = side * (0.9 + dry * 0.8 + rot * 1.0) - (dry + rot) * 0.9 * (1 if side > 0 else -1) * 0 + droop * u ** 2
        cr.save(); cr.translate(*p); cr.rotate(-math.pi / 2 + tilt + (dry + rot) * 0.9 * side)
        cr.scale(size, size * 0.42); cr.arc(1, 0, 1, 0, 7); cr.restore()
        cr.set_source_rgb(*col); cr.fill()
    tip = pts[-1]
    if bloom > 0:
        cr.save(); cr.translate(*tip); cr.scale(bloom, bloom)
        for i in range(8, 0, -1):
            cr.set_source_rgba(1, 0.85, 0.3, 0.05); cr.arc(0, 0, 70 + i * 16, 0, 7); cr.fill()
        for i in range(16):
            cr.save(); cr.rotate(i * 2 * math.pi / 16 + sway * 0.1); cr.scale(62, 20)
            cr.arc(1.25, 0, 1, 0, 7); cr.restore()
            cr.set_source_rgb(1, 0.8 if i % 2 else 0.86, 0.2); cr.fill()
        cr.set_source_rgb(0.42, 0.26, 0.12); cr.arc(0, 0, 46, 0, 7); cr.fill()
        cr.set_source_rgba(0, 0, 0, 0.2)
        for i in range(20):
            a = i * 2.4; r = 6 + i * 1.8
            cr.arc(math.cos(a) * r, math.sin(a) * r, 3, 0, 7); cr.fill()
        cr.restore()
    return tip

def ruler(cr, x, tip_y, col):
    top = POT_TOP - 30 - MAXH
    cr.set_source_rgba(1, 1, 1, 0.55); rrect(cr, x - 12, top, 24, POT_TOP - top, 6); cr.fill()
    cr.set_source_rgba(0.3, 0.2, 0.15, 0.6); cr.set_line_width(3)
    for i in range(0, 21):
        y = POT_TOP - 8 - i * (MAXH + 30) / 20
        cr.move_to(x - 12, y); cr.line_to(x + (2 if i % 5 else 8), y); cr.stroke()
    y = clamp(tip_y, top, POT_TOP)
    cr.set_source_rgb(*col)
    cr.move_to(x + 14, y); cr.line_to(x + 36, y - 14); cr.line_to(x + 36, y + 14); cr.close_path(); cr.fill()
    cr.set_source_rgba(*col, 0.5); cr.set_line_width(3); cr.set_dash([6, 6])
    cr.move_to(x - 12, y); cr.line_to(x - 60, y); cr.stroke(); cr.set_dash([])

def puddle(cr, cx, k):
    if k <= 0: return
    cr.save(); cr.translate(cx, FLOOR + 10); cr.scale(90 + 150 * k, 18 + 28 * k)
    cr.arc(0, 0, 1, 0, 7); cr.restore()
    cr.set_source_rgba(0.4, 0.65, 0.95, 0.55); cr.fill()
    cr.save(); cr.translate(cx - 30, FLOOR + 4); cr.scale(40 + 60 * k, 6 + 6 * k)
    cr.arc(0, 0, 1, 0, 7); cr.restore()
    cr.set_source_rgba(1, 1, 1, 0.35); cr.fill()

def overflow(cr, cx, t, k):
    if k <= 0: return
    for side in (-1, 1):
        for i in range(5):
            ph = (t * 2.2 + i / 5) % 1
            x = cx + side * (84 + ph * 10)
            y = POT_TOP + ph * (FLOOR - POT_TOP)
            cr.set_source_rgba(0.45, 0.7, 1, 0.8 * k); cr.arc(x, y, 6, 0, 7); cr.fill()

# ---------------------------------------------------------------- characters
def gardener(cr, who, t):
    cx = COLS[who]; e, dp = daylight(t)
    x = cx - 110
    col = COL[who]
    props = None
    if who == "mot":
        if t < 0.6:
            xx = lerp(x - 260, x, ease_out(t / 0.6)); J = walk(t * 9, 1)
            props = lambda c, J: can(c, J["rha"], 1, 0.0)
        elif t < 5.4:
            xx = x; J = stand(1)
            pour = (0.7 < t < 2.6) or (4.3 < t < 4.7)
            tilt = 0.9 * (0.6 + 0.4 * math.sin(t * 14)) if pour else 0.0
            set_hand(J, "r", (115, J["rsh"][1] + (45 if pour else 90)), 1)
            props = lambda c, J, tl=tilt: can(c, J["rha"], 1, tl)
            if pour: drops(cr, xx + 200 * S, POT_TOP - 220 * S + 60, t)
        elif t < 5.9:
            u = ease((t - 5.4) / 0.5); xx = x - 40 * u; J = blend(stand(1), sit_phone(1), u)
        else:
            xx = x - 40; J = sit_phone(1, math.sin(t * 2) * 2)
            props = lambda c, J: phone(c, J["lha"])
        fig(cr, J, xx, FLOOR, S, col, who="mot", props=props)
    elif who == "dis":
        if t < 0.8:
            xx = lerp(x - 260, x, ease_out(t / 0.8)); J = walk(t * 8, 1)
            props = lambda c, J: can(c, J["rha"], 1, 0.0)
        elif t < 13.3:
            xx = x; J = stand(1)
            pour = (1.2 < t < 2.4) or (T_LAPSE0 < t < T_LAPSE1 and e > 0.55)
            set_hand(J, "r", (115, J["rsh"][1] + (45 if pour else 90)), 1)
            props = lambda c, J, tl=(0.75 if pour else 0.0): can(c, J["rha"], 1, tl)
            if pour: drops(cr, xx + 200 * S, POT_TOP - 220 * S + 60, t)
        else:
            xx = x; J = celebrate(1, t * 6) if t > 13.8 else stand(1)
        fig(cr, J, xx, FLOOR, S, col, who="dis", props=props)
    else:
        if t < 0.4:
            xx = lerp(x - 260, x, ease_out(t / 0.4)); J = walk(t * 11, 1)
            props = lambda c, J: can(c, J["rha"], 1, 0.0)
        elif t < 12.0:
            xx = x + math.sin(t * 9) * 4; J = stand(1)
            tilt = 1.15 + 0.15 * math.sin(t * 18)
            set_hand(J, "r", (112, J["rsh"][1] + 38 + 6 * math.sin(t * 18)), 1)
            J["head"] = (J["head"][0] + 8, J["head"][1] + 4)
            props = lambda c, J, tl=tilt: can(c, J["rha"], 1, tl)
            drops(cr, xx + 200 * S, POT_TOP - 220 * S + 60, t * 1.6)
            drops(cr, xx + 205 * S, POT_TOP - 220 * S + 60, t * 1.6 + 0.5)
        else:   # drops the can, hand on head
            xx = x; J = stand(1)
            sh = J["lsh"]
            u = ease((t - 12.0) / 0.4)
            set_hand(J, "l", (lerp(sh[0] + 10, J["head"][0] - 10, u), lerp(sh[1] + 150, J["head"][1] - 30, u)), -1)
            props = None
        fig(cr, J, xx, FLOOR, S, col, who="obs", props=props)
        if t >= 12.0:   # the dropped can on its side
            cr.save(); cr.translate(x + 30, FLOOR - 18); cr.rotate(1.4 * ease((t - 12) / 0.3))
            can(cr, (0, 0), 1, 0); cr.restore()

# ---------------------------------------------------------------- frame
BG = None
def scene(cr, t):
    cr.set_source_surface(BG); cr.paint()
    window(cr, t)
    sunbeam(cr, t)
    e, dp = daylight(t)
    sway = t * 1.3
    # growth curves
    hm = 0.06 + 0.12 * ease((t - 0.8) / 4.5); dry = ease((t - 6.5) / 4.5)
    hd = 0.06 + 0.86 * clamp((t - 0.9) / 12.2); bloom = ease_out((t - 13.1) / 1.0)
    ho = 0.06 + 0.78 * ease_out(clamp((t - 0.6) / 7.0)); rot = ease((t - 8.0) / 3.8)
    plants = {"mot": (hm, dry, 0, 0), "dis": (hd, 0, 0, bloom), "obs": (ho, 0, rot, 0)}
    puddle(cr, COLS["obs"] + 70, clamp((t - 2.5) / 9.0))
    for who, cx in COLS.items():
        px = cx + 70
        h, d, r, b = plants[who]
        rx = px + 100
        # draw plant on a scratch pass to know tip, then ruler behind, then plant
        cr.push_group(); tip = plant(cr, px, h, d, r, b, sway, -1 if who == "obs" else 1); grp = cr.pop_group()
        ruler(cr, rx, tip[1], COL[who])
        pot(cr, px, COL[who])
        cr.set_source(grp); cr.paint()
    overflow(cr, COLS["obs"] + 70, t, clamp((t - 3.0) / 2.0) * (1 - ease((t - 12.0) / 0.6)))
    for who in ("mot", "dis", "obs"):
        gardener(cr, who, t)
    # sparkles around the sunflower
    if t > 13.2:
        tip_x, tip_y = COLS["dis"] + 70, POT_TOP - 8 - (30 + hd * MAXH)
        rnd = random.Random(1)
        for i in range(18):
            ph = (t * 0.8 + rnd.random()) % 1
            a = rnd.uniform(0, 2 * math.pi); r = 90 + 140 * ph
            cr.set_source_rgba(1, 0.95, 0.6, (1 - ph) * ease((t - 13.2) / 0.5))
            cr.arc(tip_x + math.cos(a) * r, tip_y + math.sin(a) * r, 5 * (1 - ph) + 2, 0, 7); cr.fill()
        if t > 14.0:
            u = (t - 14.0) / 1.6
            heart(cr, COLS["dis"] - 150, FLOOR - 470 - 80 * u, 1.4, (1, 0.45, 0.55), clamp(1.5 * (1 - u)))
    # night: dim everything except the window
    dark = (1 - clamp(e * 0.5 + 0.5)) * 0.55
    if dark > 0:
        x, y, w, h = WIN
        cr.save(); cr.set_fill_rule(cairo.FILL_RULE_EVEN_ODD)
        cr.rectangle(0, 0, W, H); cr.rectangle(x - 11, y - 11, w + 22, h + 22); cr.clip()
        cr.set_source_rgba(0.05, 0.06, 0.18, dark); cr.paint(); cr.restore()
    vignette(cr, 0.45)

# ---------------------------------------------------------------- titles
def shadow_text(cr, s, x, y, size, col, a, **kw):
    text(cr, s, x + 3, y + 4, size, (0, 0, 0), a * 0.35, **kw)
    text(cr, s, x, y, size, col, a, **kw)

def tag(cr, s, x, y, col, t0, t1, t):
    if not (t0 <= t <= t1): return
    k = ease_back((t - t0) / 0.3) * clamp((t1 - t) / 0.2)
    if k <= 0.01: return
    cr.save(); cr.translate(x, y); cr.scale(k, k)
    cr.select_font_face(FONT_BOLD, 0, 1); cr.set_font_size(30)
    tw = cr.text_extents(s).x_advance + len(s) * 2
    cr.set_source_rgba(*col, 0.95); rrect(cr, -tw / 2 - 20, -26, tw + 40, 52, 26); cr.fill()
    cr.restore()
    text(cr, s, x, y, 30 * k, (0.1, 0.07, 0.08), clamp(k), font=FONT_BOLD, track=2)

def chapter(t):
    e, dp = daylight(t)
    if t < T_LAPSE0: return "PLANTING DAY", 1
    if t < T_LAPSE1: return "THE LONG WAIT", 1 + int(round(29 * dp / ((T_LAPSE1 - T_LAPSE0) / DAYP)))
    return "THE RESULT", 30

def hud(cr, t):
    a = clamp((t - 0.3) / 0.4)
    name, day = chapter(t)
    # chapter title swaps with a quick fade around the boundaries
    fade = 1.0
    for b in (T_LAPSE0, T_LAPSE1):
        if abs(t - b) < 0.2: fade = abs(t - b) / 0.2
    g = cairo.LinearGradient(0, 0, 0, 260)
    g.add_color_stop_rgba(0, 0.05, 0.03, 0.06, 0.55 * a); g.add_color_stop_rgba(1, 0.05, 0.03, 0.06, 0)
    cr.set_source(g); cr.rectangle(0, 0, W, 260); cr.fill()
    shadow_text(cr, name + ".", W / 2, 78, 62, (1, 1, 1), a * fade, track=5)
    shadow_text(cr, f"DAY {day}", W / 2, 136, 32, (1, 0.95, 0.85), a * 0.85, font=FONT_BOLD, track=6)
    labels = [("mot", "MOTIVATION"), ("dis", "DISCIPLINE"), ("obs", "OBSESSION")]
    for who, nm in labels:
        x = COLS[who] + 40
        shadow_text(cr, nm, x, 722, 36, COL[who], a, track=3)
    # status tags (pop in above the names)
    m, d, o = COLS["mot"] + 40, COLS["dis"] + 40, COLS["obs"] + 40
    tag(cr, "LET'S GO!", m, 632, COL["mot"], 0.8, 3.0, t)
    tag(cr, "LATER...", m, 632, COL["mot"], 5.6, 9.0, t)
    tag(cr, "DRIED UP.", m, 632, COL["mot"], 10.6, 16, t)
    tag(cr, "ONE CAN.", d, 632, COL["dis"], 1.4, 3.6, t)
    tag(cr, "EVERY DAY.", d, 632, COL["dis"], 5.0, 12.4, t)
    tag(cr, "BLOOMED.", d, 632, COL["dis"], 13.2, 16, t)
    tag(cr, "MORE!", o, 632, COL["obs"], 0.8, 3.6, t)
    tag(cr, "TOO MUCH!", o, 632, COL["obs"], 5.0, 9.4, t)
    tag(cr, "DROWNED.", o, 632, COL["obs"], 11.6, 16, t)

def frame(t):
    surf = cairo.ImageSurface(cairo.FORMAT_ARGB32, W, H); cr = cairo.Context(surf)
    cr.set_source_rgb(0, 0, 0); cr.paint()
    z = 1 + 0.35 * ease((t - 13.4) / 2.2)       # slow push-in on the sunflower
    fx, fy = COLS["dis"] + 70, 900
    cr.save(); cr.translate(fx, fy); cr.scale(z, z); cr.translate(-fx, -fy)
    scene(cr, t); cr.restore()
    hud(cr, t)
    if t < 0.4: cr.set_source_rgba(0, 0, 0, 1 - t / 0.4); cr.paint()
    if t > DUR - 0.6: cr.set_source_rgba(0, 0, 0, clamp((t - DUR + 0.6) / 0.6)); cr.paint()
    return surf

# ---------------------------------------------------------------- audio
def make_audio(path, sr=44100):
    n = int(DUR * sr); out = np.zeros(n); tt = np.arange(n) / sr
    rng = np.random.default_rng(4)
    def add(sig, start, v=1.0):
        i = int(start * sr)
        if i >= n or i < 0: return
        j = min(n, i + len(sig)); out[i:j] += v * sig[: j - i]
    def lp(x, k): return np.convolve(x, np.ones(k) / k, mode="same")
    def tone(f, dur, decay=4.0):
        x = np.arange(int(dur * sr)) / sr
        return (np.sin(2 * np.pi * f * x) + 0.35 * np.sin(4 * np.pi * f * x) + 0.1 * np.sin(6 * np.pi * f * x)) * np.exp(-x * decay) * np.minimum(1, x / 0.004)
    def pad(t0, t1, fs, v):
        i0, i1 = int(t0 * sr), min(n, int(t1 * sr)); x = tt[i0:i1] - t0
        env = np.minimum(1, x / 0.7) * np.minimum(1, (t1 - t0 - x) / 0.7)
        out[i0:i1] += v * env * sum(np.sin(2 * np.pi * f * x) for f in fs) / len(fs)
    # lo-fi chord loop: Fmaj7 - Em7 - Dm7 - Cmaj7
    chords = [[174.61, 220, 261.63, 329.63], [164.81, 196, 246.94, 293.66], [146.83, 174.61, 220, 261.63], [130.81, 164.81, 196, 246.94]]
    bar = 2.0
    for i in range(int(DUR / bar) + 1):
        pad(i * bar, min(DUR, i * bar + bar + 0.3), chords[i % 4], 0.13)
        for j, f in enumerate(chords[i % 4]):
            add(tone(f * 2, 0.9, 5), i * bar + j * 0.25, 0.05)
    # soft beat
    def kick():
        x = np.arange(int(0.25 * sr)) / sr
        return np.sin(2 * np.pi * np.cumsum(90 * np.exp(-x * 25) + 45) / sr) * np.exp(-x * 12)
    def hat():
        x = np.arange(int(0.04 * sr)) / sr
        return rng.standard_normal(len(x)) * np.exp(-x * 90)
    b = 0.0
    while b < DUR - 0.5:
        add(kick(), b, 0.45); add(hat(), b + 0.25, 0.05); b += 0.5
    # water: pouring sounds
    def pour(t0, t1, v):
        L = int((t1 - t0) * sr)
        if L <= 0: return
        w = lp(rng.standard_normal(L), 3) * (0.6 + 0.4 * np.sin(np.arange(L) / sr * 40))
        env = np.minimum(1, np.arange(L) / sr / 0.1) * np.minimum(1, (L - np.arange(L)) / sr / 0.1)
        add(w * env, t0, v)
    pour(0.7, 2.6, 0.04); pour(1.2, 2.4, 0.03); pour(0.5, 12.0, 0.035)
    # tick per day during the time-lapse
    d = T_LAPSE0
    while d < T_LAPSE1:
        add(tone(1567.98, 0.15, 30), d, 0.06); d += DAYP
    # sad droop note + bloom chime
    add(tone(196, 1.5, 2), 11.2, 0.10); add(tone(185, 1.5, 2), 11.5, 0.08)
    for i, f in enumerate([523.25, 659.25, 783.99, 1046.5, 1318.5]):
        add(tone(f, 2.5, 1.5), 13.1 + i * 0.1, 0.09)
    fo = int(0.8 * sr); out[-fo:] *= np.linspace(1, 0, fo)
    out = np.tanh(out * 1.5) * 0.8
    pcm = (out * 32767).astype(np.int16)
    with wave.open(path, "wb") as w:
        w.setnchannels(2); w.setsampwidth(2); w.setframerate(sr)
        w.writeframes(np.stack([pcm, pcm], 1).tobytes())

BG = room_bg()

if __name__ == "__main__":
    wav = os.path.join(OUT, "greenhouse.wav"); make_audio(wav)
    mp4 = os.path.join(OUT, "greenhouse.mp4")
    ff = subprocess.Popen(["ffmpeg", "-y", "-v", "error", "-f", "rawvideo", "-pix_fmt", "bgra",
                           "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-", "-i", wav,
                           "-c:v", "libx264", "-preset", "medium", "-crf", "19", "-pix_fmt", "yuv420p",
                           "-c:a", "aac", "-b:a", "192k", "-shortest", "-movflags", "+faststart", mp4],
                          stdin=subprocess.PIPE)
    for i in range(NF):
        ff.stdin.write(bytes(frame(i / FPS).get_data()))
    ff.stdin.close(); ff.wait(); os.remove(wav)
    print("wrote", mp4)
