"""Motivation vs Discipline vs Obsession — original-style pull-up short.

Renders a 1080x1920 vertical video (18 s @ 30 fps) with a synthesized beat.
Usage: python3 render.py  -> out/mvd_obsession.mp4
"""
import math, os, random, subprocess, wave
import numpy as np
import cairo

W, H, FPS, DUR = 1080, 1920, 30, 18.0
NF = int(DUR * FPS)
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "out")
os.makedirs(OUT, exist_ok=True)

BAR_Y, GROUND_Y = 720, 1500
T_SKIP0, T_SKIP1 = 8.4, 10.6        # "one year later" transition
T_END = 16.2                         # end card

COL = {
    "mot": (1.00, 0.78, 0.25),       # amber
    "dis": (0.25, 0.85, 0.80),       # teal
    "obs": (1.00, 0.33, 0.45),       # coral / hot pink
}
FONT_BLACK = "Inter Black"
FONT_BOLD = "Inter"

# ---------------------------------------------------------------- helpers
def lerp(a, b, t): return a + (b - a) * t
def clamp(x, a=0.0, b=1.0): return max(a, min(b, x))
def ease(t): t = clamp(t); return t * t * (3 - 2 * t)
def ease_out(t): t = clamp(t); return 1 - (1 - t) ** 3
def ease_back(t):
    t = clamp(t); c = 1.9
    return 1 + (c + 1) * (t - 1) ** 3 + c * (t - 1) ** 2

def lerp_pose(a, b, t):
    return {k: (lerp(a[k][0], b[k][0], t), lerp(a[k][1], b[k][1], t)) for k in a}

def ik(S, Hd, a, b, side):
    dx, dy = Hd[0] - S[0], Hd[1] - S[1]
    d = min(math.hypot(dx, dy), a + b - 0.5)
    th = math.atan2(dy, dx)
    al = math.acos(clamp((a * a + d * d - b * b) / (2 * a * d), -1, 1))
    ang = th + side * al
    return (S[0] + a * math.cos(ang), S[1] + a * math.sin(ang))

# body proportions
HEAD_R, NECK, TORSO, UA, FA, TH, SH, SW, GW = 36, 16, 150, 88, 82, 98, 98, 40, 100

def pose_hang(cx, p, sway=0.0, legs="relaxed"):
    p = ease(p)
    dx = GW - SW
    d0 = (UA + FA) * 0.97
    ys = BAR_Y + lerp(math.sqrt(d0 * d0 - dx * dx), 30, p)
    J = {}
    J["neck"] = (cx, ys - 6)
    J["head"] = (cx, ys - 6 - NECK - HEAD_R)
    J["lsh"], J["rsh"] = (cx - SW, ys), (cx + SW, ys)
    J["lha"], J["rha"] = (cx - GW, BAR_Y), (cx + GW, BAR_Y)
    J["lel"] = ik(J["lsh"], J["lha"], UA, FA, -1)
    J["rel"] = ik(J["rsh"], J["rha"], UA, FA, +1)
    px = cx + sway
    J["pel"] = (px, ys + TORSO)
    if legs == "tucked":     # knees up, ankles crossed (weighted style)
        J["lkn"] = (px - 34, ys + TORSO + 80)
        J["rkn"] = (px + 34, ys + TORSO + 80)
        J["lft"] = (px + 14, ys + TORSO + 160)
        J["rft"] = (px - 14, ys + TORSO + 165)
    else:
        J["lkn"] = (px - 20 + sway * .3, ys + TORSO + TH)
        J["rkn"] = (px + 20 + sway * .3, ys + TORSO + TH)
        J["lft"] = (px - 10 + sway * .6, ys + TORSO + TH + SH)
        J["rft"] = (px + 10 + sway * .6, ys + TORSO + TH + SH)
    return J

def pose_stand(cx):
    fy = GROUND_Y - 8
    pel = fy - SH - TH
    ys = pel - TORSO
    return {
        "neck": (cx, ys - 6), "head": (cx, ys - 6 - NECK - HEAD_R),
        "lsh": (cx - SW, ys), "rsh": (cx + SW, ys),
        "lel": (cx - SW - 14, ys + UA), "rel": (cx + SW + 14, ys + UA),
        "lha": (cx - SW - 10, ys + UA + FA), "rha": (cx + SW + 10, ys + UA + FA),
        "pel": (cx, pel),
        "lkn": (cx - 26, pel + TH), "rkn": (cx + 26, pel + TH),
        "lft": (cx - 30, fy), "rft": (cx + 30, fy),
    }

def pose_sit(cx, breathe=0.0, phone=False):
    fy = GROUND_Y - 8
    pel = (cx, fy - 22)
    ys = pel[1] - TORSO * 0.92 + breathe
    lean = 10
    J = {"pel": pel}
    J["lsh"], J["rsh"] = (cx - SW + lean * .3, ys), (cx + SW + lean * .3, ys)
    J["neck"] = (cx + lean * .3, ys - 4)
    J["lkn"], J["rkn"] = (cx - 70, fy - 120), (cx + 70, fy - 120)
    J["lft"], J["rft"] = (cx - 95, fy), (cx + 95, fy)
    if phone:
        J["head"] = (cx + 4, ys - NECK - HEAD_R + 22)
        J["lha"], J["rha"] = (cx - 18, ys + 70), (cx + 18, ys + 70)
        J["lel"], J["rel"] = (cx - 72, ys + 90), (cx + 72, ys + 90)
    else:  # face in hands, elbows on knees
        J["head"] = (cx + 2, ys - NECK - HEAD_R + 34)
        J["lha"], J["rha"] = (cx - 22, ys - 10), (cx + 22, ys - 10)
        J["lel"], J["rel"] = (cx - 66, fy - 128), (cx + 66, fy - 128)
    return J

# ---------------------------------------------------------------- drawing
def limb(cr, a, b, w, col, alpha=1.0):
    cr.set_source_rgba(*col, alpha)
    cr.set_line_width(w)
    cr.set_line_cap(cairo.LINE_CAP_ROUND)
    cr.set_line_join(cairo.LINE_JOIN_ROUND)
    cr.move_to(*a); cr.line_to(*b); cr.stroke()

def chain(cr, pts, w, col, alpha=1.0):
    cr.set_source_rgba(*col, alpha)
    cr.set_line_width(w)
    cr.set_line_cap(cairo.LINE_CAP_ROUND)
    cr.set_line_join(cairo.LINE_JOIN_ROUND)
    cr.move_to(*pts[0])
    for q in pts[1:]: cr.line_to(*q)
    cr.stroke()

def skeleton(cr, J, col, w=22, alpha=1.0, glow=0.0, who=""):
    shade = tuple(c * 0.72 for c in col)
    if glow > 0:
        for i in range(6, 0, -1):
            a = glow * 0.05 * (7 - i) / 6
            _skel(cr, J, col, col, w + i * 14, a, head_extra=i * 7)
    _skel(cr, J, col, shade, w, alpha)
    hx, hy = J["head"]
    # accessories / faces
    if who == "dis":     # headband
        cr.set_source_rgba(0.06, 0.12, 0.2, alpha)
        cr.set_line_width(9)
        cr.arc(hx, hy, HEAD_R - 1, math.radians(195), math.radians(345)); cr.stroke()
        cr.move_to(hx + HEAD_R - 4, hy - 10); cr.line_to(hx + HEAD_R + 22, hy + 8)
        cr.move_to(hx + HEAD_R - 4, hy - 8); cr.line_to(hx + HEAD_R + 14, hy + 18); cr.stroke()
    elif who == "mot":   # little cap
        cr.set_source_rgba(0.55, 0.36, 0.08, alpha)
        cr.arc(hx, hy - 4, HEAD_R + 1, math.pi, 2 * math.pi); cr.close_path(); cr.fill()
        cr.rectangle(hx - 4, hy - 8, HEAD_R + 22, 10); cr.fill()
    elif who == "obs":   # flame tuft
        cr.set_source_rgba(1.0, 0.75, 0.3, alpha)
        cr.move_to(hx - 22, hy - HEAD_R + 12)
        cr.curve_to(hx - 26, hy - HEAD_R - 26, hx - 6, hy - HEAD_R - 20, hx, hy - HEAD_R - 44)
        cr.curve_to(hx + 8, hy - HEAD_R - 18, hx + 28, hy - HEAD_R - 26, hx + 22, hy - HEAD_R + 12)
        cr.close_path(); cr.fill()

def _skel(cr, J, col, shade, w, alpha, head_extra=0):
    # back limbs darker for depth
    chain(cr, [J["pel"], J["lkn"], J["lft"]], w, shade, alpha)
    chain(cr, [J["pel"], J["rkn"], J["rft"]], w, shade, alpha)
    chain(cr, [J["lsh"], J["rsh"]], w * 1.05, col, alpha)
    chain(cr, [J["neck"], J["pel"]], w * 1.35, col, alpha)
    chain(cr, [J["lsh"], J["lel"], J["lha"]], w * 0.92, col, alpha)
    chain(cr, [J["rsh"], J["rel"], J["rha"]], w * 0.92, col, alpha)
    cr.set_source_rgba(*col, alpha)
    cr.arc(*J["head"], HEAD_R + head_extra, 0, 2 * math.pi); cr.fill()

def text(cr, s, x, y, size, col=(1, 1, 1), alpha=1.0, font=FONT_BLACK,
         slant=cairo.FONT_SLANT_NORMAL, align="c", track=0.0, scale=1.0):
    cr.save()
    cr.select_font_face(font, slant, cairo.FONT_WEIGHT_BOLD)
    cr.set_font_size(size)
    widths = [cr.text_extents(ch).x_advance for ch in s]
    tw = sum(widths) + track * (len(s) - 1)
    asc = cr.font_extents()[0]
    cr.translate(x, y); cr.scale(scale, scale)
    ox = {"c": -tw / 2, "l": 0, "r": -tw}[align]
    cr.set_source_rgba(*col, alpha)
    cx = ox
    for ch, wd in zip(s, widths):
        cr.move_to(cx, asc * 0.36); cr.show_text(ch); cx += wd + track
    cr.restore()
    return tw

def rrect(cr, x, y, w, h, r):
    cr.new_sub_path()
    cr.arc(x + w - r, y + r, r, -math.pi / 2, 0)
    cr.arc(x + w - r, y + h - r, r, 0, math.pi / 2)
    cr.arc(x + r, y + h - r, r, math.pi / 2, math.pi)
    cr.arc(x + r, y + r, r, math.pi, 1.5 * math.pi)
    cr.close_path()

def bubble(cr, s, x, y, tail_x, tail_y, t_in, t_out, t, col=(1, 1, 1), tcol=(0.08, 0.08, 0.14)):
    if t < t_in or t > t_out: return
    k = ease_back((t - t_in) / 0.28) if t < t_in + 0.28 else 1.0
    if t > t_out - 0.2: k *= clamp((t_out - t) / 0.2)
    if k <= 0.01: return
    nchar = int(clamp((t - t_in) / 0.6) * len(s) + 0.999)
    cr.save()
    cr.translate(tail_x, tail_y); cr.scale(k, k); cr.translate(-tail_x, -tail_y)
    cr.select_font_face(FONT_BOLD, cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_BOLD)
    cr.set_font_size(42)
    tw = cr.text_extents(s).x_advance
    bw, bh = tw + 64, 92
    bx, by = x - bw / 2, y - bh / 2
    cr.set_source_rgba(0, 0, 0, 0.25); rrect(cr, bx + 6, by + 10, bw, bh, 30); cr.fill()
    cr.set_source_rgba(*col, 1)
    rrect(cr, bx, by, bw, bh, 30); cr.fill()
    cr.move_to(clamp(tail_x, bx + 40, bx + bw - 40) - 18, by + bh - 2)
    cr.line_to(tail_x, tail_y); cr.line_to(clamp(tail_x, bx + 40, bx + bw - 40) + 18, by + bh - 2)
    cr.close_path(); cr.fill()
    cr.set_source_rgba(*tcol, 1)
    cr.move_to(bx + 32, y + 15); cr.show_text(s[:nchar])
    cr.restore()

# ---------------------------------------------------------------- backgrounds
def make_bg(kind):
    surf = cairo.ImageSurface(cairo.FORMAT_ARGB32, W, H)
    cr = cairo.Context(surf)
    g = cairo.LinearGradient(0, 0, 0, GROUND_Y)
    if kind == "dawn":    # pre-dawn, cold
        stops = [(0, (0.04, 0.04, 0.12)), (0.55, (0.10, 0.09, 0.26)), (0.85, (0.26, 0.17, 0.38)), (1, (0.45, 0.25, 0.38))]
    else:                 # one year later: golden sunrise
        stops = [(0, (0.10, 0.07, 0.25)), (0.45, (0.42, 0.18, 0.42)), (0.78, (0.98, 0.45, 0.35)), (1, (1.0, 0.75, 0.42))]
    for o, c in stops: g.add_color_stop_rgb(o, *c)
    cr.set_source(g); cr.paint()
    rnd = random.Random(7)
    # stars
    for _ in range(90):
        x, y = rnd.uniform(0, W), rnd.uniform(0, 900)
        a = rnd.uniform(0.15, 0.7) * (1 if kind == "dawn" else 0.35)
        cr.set_source_rgba(1, 1, 1, a); cr.arc(x, y, rnd.uniform(1, 2.6), 0, 7); cr.fill()
    # sun
    if kind == "sun":
        for i in range(10, 0, -1):
            cr.set_source_rgba(1, 0.85, 0.5, 0.05)
            cr.arc(W * 0.5, GROUND_Y - 170, 120 + i * 30, 0, 7); cr.fill()
        cr.set_source_rgba(1, 0.92, 0.65, 1); cr.arc(W * 0.5, GROUND_Y - 170, 120, 0, 7); cr.fill()
    else:
        cr.set_source_rgba(0.95, 0.92, 1, 0.9); cr.arc(170, 590, 46, 0, 7); cr.fill()
        cr.set_source_rgb(*[c for c in (0.12, 0.1, 0.28)]); cr.arc(150, 578, 42, 0, 7); cr.fill()
    # skyline (two layers)
    for layer, (shade, hmin, hmax, wy) in enumerate([((0.17, 0.1, 0.27) if kind == "dawn" else (0.5, 0.22, 0.38), 120, 330, 0.55),
                                                       ((0.08, 0.05, 0.15) if kind == "dawn" else (0.25, 0.1, 0.22), 60, 240, 0.8)]):
        x = -20
        while x < W:
            bw = rnd.randint(60, 150); bh = rnd.randint(hmin, hmax)
            cr.set_source_rgb(*shade); cr.rectangle(x, GROUND_Y - bh, bw, bh); cr.fill()
            if layer == 1:
                for wx in range(x + 12, x + bw - 14, 24):
                    for wy_ in range(GROUND_Y - bh + 16, GROUND_Y - 20, 30):
                        if rnd.random() < (0.28 if kind == "dawn" else 0.12):
                            cr.set_source_rgba(1, 0.82, 0.45, 0.75); cr.rectangle(wx, wy_, 10, 14); cr.fill()
            x += bw + rnd.randint(0, 10)
    # rooftop floor
    g = cairo.LinearGradient(0, GROUND_Y, 0, H)
    base = (0.10, 0.08, 0.16) if kind == "dawn" else (0.22, 0.12, 0.2)
    g.add_color_stop_rgb(0, *[c * 1.4 for c in base]); g.add_color_stop_rgb(1, *[c * 0.5 for c in base])
    cr.set_source(g); cr.rectangle(0, GROUND_Y, W, H - GROUND_Y); cr.fill()
    cr.set_source_rgba(1, 1, 1, 0.06); cr.set_line_width(2)
    for i in range(-12, 13):
        cr.move_to(W / 2 + i * 40, GROUND_Y); cr.line_to(W / 2 + i * 260, H); cr.stroke()
    for j in range(1, 8):
        y = GROUND_Y + (H - GROUND_Y) * (j / 8) ** 1.7
        cr.move_to(0, y); cr.line_to(W, y); cr.stroke()
    cr.set_source_rgba(1, 0.8, 0.6, 0.25 if kind == "sun" else 0.12)
    cr.rectangle(0, GROUND_Y - 2, W, 4); cr.fill()
    # pull-up rig
    for px in (70, W - 70):
        cr.set_source_rgb(0.05, 0.05, 0.08); cr.rectangle(px - 13, BAR_Y - 20, 26, GROUND_Y - BAR_Y + 20); cr.fill()
        cr.set_source_rgba(1, 1, 1, 0.08); cr.rectangle(px - 13, BAR_Y - 20, 6, GROUND_Y - BAR_Y + 20); cr.fill()
        cr.set_source_rgb(0.05, 0.05, 0.08); rrect(cr, px - 40, GROUND_Y - 14, 80, 18, 6); cr.fill()
    cr.set_source_rgb(0.16, 0.16, 0.2); cr.set_line_width(16); cr.set_line_cap(cairo.LINE_CAP_ROUND)
    cr.move_to(60, BAR_Y); cr.line_to(W - 60, BAR_Y); cr.stroke()
    cr.set_source_rgba(1, 1, 1, 0.25); cr.set_line_width(4)
    cr.move_to(70, BAR_Y - 4); cr.line_to(W - 70, BAR_Y - 4); cr.stroke()
    # vignette
    rg = cairo.RadialGradient(W / 2, H * 0.45, 300, W / 2, H * 0.45, 1250)
    rg.add_color_stop_rgba(0, 0, 0, 0, 0); rg.add_color_stop_rgba(1, 0, 0, 0, 0.6)
    cr.set_source(rg); cr.paint()
    return surf

# ---------------------------------------------------------------- character logic
X = {"mot": 230, "dis": 540, "obs": 850}

def phase_rep(t, t0, period, base):
    if t < t0: return 0.0, base
    ph = (t - t0) / period
    p = (1 - math.cos(2 * math.pi * ph)) / 2
    return p, base + int(math.floor(ph + 0.5))

def state(t):
    """returns dict who -> (pose, count, extra)"""
    S = {}
    if t < T_SKIP0 + 0.6:          # ---------------- DAY 1
        lt = t
        # Motivation: fast start, fades out, falls, sulks
        if lt < 3.4:
            u = lt / 3.4
            ph = 8 * (1 - (1 - u) ** 1.7)
            p = (1 - math.cos(2 * math.pi * ph)) / 2
            S["mot"] = (pose_hang(X["mot"], p, math.sin(lt * 3) * 6), int(math.floor(ph + 0.5)))
        elif lt < 4.2:   # struggle
            u = (lt - 3.4) / 0.8
            p = 0.38 * math.sin(math.pi * u) + 0.03 * math.sin(lt * 60)
            S["mot"] = (pose_hang(X["mot"], max(0, p), math.sin(lt * 9) * 10), 8)
        elif lt < 4.55:  # drop
            u = (lt - 4.2) / 0.35
            S["mot"] = (lerp_pose(pose_hang(X["mot"], 0), pose_stand(X["mot"]), u * u), 8)
        elif lt < 4.95:
            u = ease((lt - 4.55) / 0.4)
            S["mot"] = (lerp_pose(pose_stand(X["mot"]), pose_sit(X["mot"]), u), 8)
        else:
            S["mot"] = (pose_sit(X["mot"], math.sin(lt * 2.2) * 3), 8)
        p, c = phase_rep(lt, 0.2, 0.78, 0)
        S["dis"] = (pose_hang(X["dis"], p, math.sin(lt * 2) * 4), c)
        p, c = phase_rep(lt, 0.0, 0.42, 0)
        S["obs"] = (pose_hang(X["obs"], p, math.sin(lt * 5) * 8), c)
        S["day"] = 1
    else:                          # ---------------- DAY 365
        lt = t - T_SKIP1 + 0.6
        S["mot"] = (pose_sit(X["mot"], math.sin(lt * 2) * 2, phone=True), 12)
        p, c = phase_rep(lt, 0.0, 0.62, 9864)
        S["dis"] = (pose_hang(X["dis"], p, math.sin(lt * 2) * 3), c)
        p, c = phase_rep(lt, 0.0, 0.34, 24597)
        S["obs"] = (pose_hang(X["obs"], p, math.sin(lt * 6) * 5, legs="tucked"), c)
        S["day"] = 365
    return S

# embers for Obsession
ER = random.Random(3)
EMBERS = [(ER.uniform(0, 30), ER.uniform(-70, 70), ER.uniform(90, 220), ER.uniform(0.9, 2.0), ER.uniform(3, 8))
          for _ in range(160)]

def draw_embers(cr, J, t, intensity):
    cx, cy = J["pel"][0], (J["head"][1] + J["pel"][1]) / 2 + 40
    for (t0, dx, sp, life, r) in EMBERS:
        if intensity < 0.6 and r > 6.5: continue
        age = (t - t0) % life
        k = age / life
        x = cx + dx + math.sin(t0 * 7 + age * 4) * 18
        y = cy + 90 - age * sp
        a = (1 - k) * 0.85 * intensity
        cr.set_source_rgba(1, 0.55 + 0.35 * (1 - k), 0.3, a)
        cr.arc(x, y, r * (1 - k * 0.6), 0, 7); cr.fill()

# ---------------------------------------------------------------- HUD
pop_last = {}
def hud(cr, t, S, alpha):
    if alpha <= 0: return
    day = S["day"]
    text(cr, "DAY", W / 2 - 40, 150, 64, (1, 1, 1), 0.65 * alpha, slant=cairo.FONT_SLANT_ITALIC, align="r", track=4)
    text(cr, f"{day}", W / 2 - 10, 150, 120, (1, 1, 1), alpha, slant=cairo.FONT_SLANT_ITALIC, align="l")
    # year progress bar
    bx, by, bw = 240, 232, 600
    cr.set_source_rgba(1, 1, 1, 0.15 * alpha); rrect(cr, bx, by, bw, 10, 5); cr.fill()
    g = cairo.LinearGradient(bx, 0, bx + bw, 0)
    g.add_color_stop_rgb(0, *COL["dis"]); g.add_color_stop_rgb(1, *COL["obs"])
    cr.set_source(g); rrect(cr, bx, by, max(10, bw * day / 365), 10, 5)
    cr.save(); cr.clip(); cr.paint_with_alpha(alpha); cr.restore()
    names = [("mot", "MOTIVATION"), ("dis", "DISCIPLINE"), ("obs", "OBSESSION")]
    cw, ch, gap = 312, 190, 20
    x0 = (W - 3 * cw - 2 * gap) / 2
    for i, (k, name) in enumerate(names):
        x, y = x0 + i * (cw + gap), 290
        cr.set_source_rgba(0.05, 0.04, 0.1, 0.55 * alpha); rrect(cr, x, y, cw, ch, 28); cr.fill()
        cr.set_source_rgba(*COL[k], 0.9 * alpha); rrect(cr, x, y, cw, 12, 6); cr.fill()
        if k == "mot" and S["mot"][1] == 8 and day == 1 and t > 4.2:
            qa = alpha * clamp((t - 4.2) / 0.25)
            cr.set_source_rgba(0.9, 0.2, 0.25, qa); rrect(cr, x + cw / 2 - 62, y + ch - 20, 124, 40, 20); cr.fill()
            text(cr, "QUIT", x + cw / 2, y + ch, 24, (1, 1, 1), qa, track=4)
        text(cr, name, x + cw / 2, y + 52, 28, COL[k], alpha, font=FONT_BOLD, track=3)
        cnt = S[k][1]
        if pop_last.get(k, (None,))[0] != cnt:
            pop_last[k] = (cnt, t)
        dt = t - pop_last[k][1]
        sc = 1 + 0.22 * math.exp(-dt * 10) if dt < 0.5 else 1
        num = f"{cnt:,}"
        fs = 76 if len(num) <= 4 else 60
        text(cr, num, x + cw / 2, y + 122, fs, (1, 1, 1), alpha, scale=sc)

# ---------------------------------------------------------------- frame
BG_DAWN, BG_SUN = make_bg("dawn"), make_bg("sun")

def frame(t):
    surf = cairo.ImageSurface(cairo.FORMAT_ARGB32, W, H)
    cr = cairo.Context(surf)
    day365 = t >= T_SKIP0 + 0.6
    cr.set_source_surface(BG_SUN if day365 else BG_DAWN); cr.paint()
    S = state(t)

    # Motivation
    Jm = S["mot"][0]
    skeleton(cr, Jm, COL["mot"], who="mot", alpha=1.0 if day365 or t < 4.6 else 0.9)
    if day365:   # phone glow
        hx, hy = (Jm["lha"][0] + Jm["rha"][0]) / 2, Jm["lha"][1] - 20
        for i in range(6, 0, -1):
            cr.set_source_rgba(0.6, 0.85, 1, 0.04); cr.arc(hx, hy, 30 + i * 16, 0, 7); cr.fill()
        cr.set_source_rgb(0.1, 0.1, 0.15); rrect(cr, hx - 20, hy - 34, 40, 64, 8); cr.fill()
        cr.set_source_rgb(0.65, 0.88, 1); rrect(cr, hx - 15, hy - 29, 30, 54, 5); cr.fill()
    # Discipline (gets bigger over the year)
    skeleton(cr, S["dis"][0], COL["dis"], w=30 if day365 else 22, who="dis")
    # Obsession
    Jo = S["obs"][0]
    inten = 1.0 if day365 else clamp(0.35 + t / 8)
    draw_embers(cr, Jo, t, inten)
    if day365:   # weight plate on a chain
        pel = Jo["pel"]; plate = (pel[0], pel[1] + 215)
        cr.set_source_rgba(0.75, 0.75, 0.8, 1); cr.set_line_width(4)
        cr.move_to(pel[0] - 10, pel[1]); cr.line_to(*plate); cr.move_to(pel[0] + 10, pel[1]); cr.line_to(*plate); cr.stroke()
        cr.set_source_rgb(0.12, 0.12, 0.16); cr.arc(*plate, 54, 0, 7); cr.fill()
        cr.set_source_rgb(0.3, 0.3, 0.36); cr.set_line_width(5); cr.arc(*plate, 40, 0, 7); cr.stroke()
        text(cr, "45", plate[0], plate[1] + 2, 30, (1, 1, 1), 0.9)
    skeleton(cr, Jo, COL["obs"], w=26 if day365 else 22, glow=inten, who="obs")

    # speech bubbles
    if not day365:
        bubble(cr, "I'll start Monday…", 300, 1230, X["mot"], 1310, 5.0, 7.9, t)
        bubble(cr, "Again.", 840, 1300, X["obs"], 1220, 2.2, 4.1, t)
        bubble(cr, "Not done.", 820, 1300, X["obs"], 1220, 6.0, 8.2, t)
    else:
        lt = t - T_SKIP1
        bubble(cr, "New year, new me…", 330, 1170, X["mot"], 1250, 0.6, 2.9, lt)
        bubble(cr, "Same time tomorrow.", 540, 1330, X["dis"], 1250, 2.3, 4.6, lt)
        bubble(cr, "Never stop.", 830, 1330, X["obs"], 1250, 4.0, 5.6, lt)

    # HUD
    hud_a = 1.0
    if T_SKIP0 - 0.2 < t < T_SKIP1:
        hud_a = 0.0
    if T_SKIP1 <= t < T_SKIP1 + 0.4:
        hud_a = (t - T_SKIP1) / 0.4
    if t > T_END: hud_a = clamp(1 - (t - T_END) / 0.4)
    hud(cr, t, S, hud_a)

    # transition: one year later
    if T_SKIP0 - 0.3 < t < T_SKIP1 + 0.4:
        a = clamp((t - (T_SKIP0 - 0.3)) / 0.3) * clamp((T_SKIP1 + 0.4 - t) / 0.4)
        cr.set_source_rgba(0.03, 0.02, 0.06, a); cr.paint()
        u = clamp((t - T_SKIP0) / (T_SKIP1 - T_SKIP0 - 0.5))
        d = 1 + int(364 * ease(u))
        sh = (math.sin(t * 80) * 4) if 0.05 < u < 0.95 else 0
        text(cr, "ONE YEAR LATER", W / 2, 800, 58, (1, 1, 1), a * 0.8, font=FONT_BOLD, track=10)
        g = (lerp(0.25, 1.0, u), lerp(0.85, 0.33, u), lerp(0.8, 0.45, u))
        text(cr, f"{d}", W / 2 + sh, 980, 260, g, a, slant=cairo.FONT_SLANT_ITALIC)
        cr.set_source_rgba(1, 1, 1, 0.15 * a); rrect(cr, 290, 1130, 500, 12, 6); cr.fill()
        cr.set_source_rgba(*g, a); rrect(cr, 290, 1130, max(12, 500 * d / 365), 12, 6); cr.fill()

    # end card
    if t > T_END:
        a = clamp((t - T_END) / 0.5)
        cr.set_source_rgba(0.03, 0.02, 0.06, 0.72 * a); cr.paint()
        text(cr, "WHICH ONE", W / 2, 760, 110, (1, 1, 1), a, slant=cairo.FONT_SLANT_ITALIC,
             scale=lerp(1.3, 1, ease_out((t - T_END) / 0.4)))
        text(cr, "ARE YOU?", W / 2, 890, 110, (1, 1, 1), a, slant=cairo.FONT_SLANT_ITALIC,
             scale=lerp(1.3, 1, ease_out((t - T_END - 0.1) / 0.4)))
        for i, (k, nm) in enumerate([("mot", "MOTIVATION"), ("dis", "DISCIPLINE"), ("obs", "OBSESSION")]):
            ai = clamp((t - T_END - 0.35 - i * 0.18) / 0.3)
            text(cr, nm, W / 2, 1060 + i * 78, 50, COL[k], ai, track=6)
    return surf

# ---------------------------------------------------------------- audio
def make_audio(path, sr=44100):
    n = int(DUR * sr); out = np.zeros(n)
    tt = np.arange(n) / sr
    bpm = 96; beat = 60 / bpm

    def add(sig, start):
        i = int(start * sr)
        if i >= n: return
        j = min(n, i + len(sig)); out[i:j] += sig[: j - i]

    def kick(v=1.0):
        x = np.arange(int(0.35 * sr)) / sr
        f = 110 * np.exp(-x * 30) + 45
        return v * np.sin(2 * np.pi * np.cumsum(f) / sr) * np.exp(-x * 9)
    def hat(v=0.25):
        x = np.arange(int(0.06 * sr)) / sr
        return v * np.random.default_rng(1).standard_normal(len(x)) * np.exp(-x * 70)
    def snare(v=0.5):
        x = np.arange(int(0.22 * sr)) / sr
        return v * (np.random.default_rng(2).standard_normal(len(x)) * 0.7 + np.sin(2 * np.pi * 190 * x)) * np.exp(-x * 18)

    def section(t0, t1, full):
        k = 0
        b = t0
        while b < t1 - 0.01:
            add(kick(0.9), b)
            if k % 2 == 1: add(snare(0.45 if full else 0.25), b)
            add(hat(0.18 if full else 0.1), b + beat / 2)
            if full: add(hat(0.1), b + beat / 4); add(hat(0.1), b + 3 * beat / 4)
            b += beat; k += 1

    section(0.0, T_SKIP0, False)
    section(T_SKIP1, T_END + 1.2, True)
    # dark minor pad (A minor -> F) for mood
    def pad(t0, t1, freqs, v):
        i0, i1 = int(t0 * sr), int(t1 * sr)
        x = tt[i0:i1] - t0
        env = np.minimum(1, x / 0.6) * np.minimum(1, (t1 - t0 - x) / 0.6)
        s = sum(np.sin(2 * np.pi * f * x) + 0.3 * np.sin(2 * np.pi * 2 * f * x + 0.3) for f in freqs)
        out[i0:i1] += v * env * s / len(freqs)
    bar = beat * 4
    chords = [[110, 130.81, 164.81], [87.31, 110, 130.81], [98, 123.47, 146.83], [82.41, 103.83, 123.47]]
    tc, ci = 0.0, 0
    while tc < DUR:
        pad(tc, min(DUR, tc + bar), chords[ci % 4], 0.10 if tc < T_SKIP0 else 0.16)
        tc += bar; ci += 1
    # sub bass in second half
    b = T_SKIP1; ci = 0
    while b < T_END + 1.2:
        root = chords[(ci // 4) % 4][0] / 2
        x = np.arange(int(beat * 0.9 * sr)) / sr
        add(0.35 * np.sin(2 * np.pi * root * x) * np.exp(-x * 3), b)
        b += beat; ci += 1
    # riser + whoosh into time skip
    i0, i1 = int((T_SKIP0 - 1.0) * sr), int(T_SKIP1 * sr)
    x = tt[i0:i1] - tt[i0]; L = x[-1]
    f = 200 + 1800 * (x / L) ** 2
    out[i0:i1] += 0.12 * np.sin(2 * np.pi * np.cumsum(f) / sr) * (x / L) ** 2 * np.minimum(1, (L - x) / 0.15)
    noise = np.random.default_rng(5).standard_normal(i1 - i0)
    out[i0:i1] += 0.08 * noise * np.sin(np.pi * x / L) ** 3
    add(kick(1.3), T_SKIP1)
    # fade out
    fo = int(1.2 * sr); out[-fo:] *= np.linspace(1, 0, fo)
    out = np.tanh(out * 1.2) * 0.85
    pcm = (out * 32767).astype(np.int16)
    st = np.stack([pcm, pcm], 1)
    with wave.open(path, "wb") as w:
        w.setnchannels(2); w.setsampwidth(2); w.setframerate(sr); w.writeframes(st.tobytes())

if __name__ == "__main__":
    wav = os.path.join(OUT, "beat.wav")
    make_audio(wav)
    mp4 = os.path.join(OUT, "mvd_obsession.mp4")
    ff = subprocess.Popen(["ffmpeg", "-y", "-v", "error", "-f", "rawvideo", "-pix_fmt", "bgra",
                           "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-", "-i", wav,
                           "-c:v", "libx264", "-preset", "medium", "-crf", "19", "-pix_fmt", "yuv420p",
                           "-c:a", "aac", "-b:a", "192k", "-shortest", "-movflags", "+faststart", mp4],
                          stdin=subprocess.PIPE)
    for i in range(NF):
        ff.stdin.write(bytes(frame(i / FPS).get_data()))
    ff.stdin.close(); ff.wait()
    os.remove(wav)
    print("wrote", mp4)
