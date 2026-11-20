"""'Show Up' — a wordless three-scene stick-figure short (no text, no UI).

Scenes:
  1. Rain:     someone slips; a passer-by stays on their phone, a friend stops and shares an umbrella.
  2. Garden:   split screen — water once and scroll vs. water every day; a sprout wilts, a tree grows.
  3. Mountain: a storm sends one climber back down; the other summits, then goes back to bring them up.

Usage: python3 story2.py  -> out/show_up.mp4 (1080x1920, 20 s, 30 fps)
"""
import math, os, random, subprocess, wave
import numpy as np
import cairo
from render import (lerp, clamp, ease, ease_out, ik, skeleton, rrect,
                    HEAD_R, NECK, TORSO, UA, FA, TH, SH, COL)

W, H, FPS, DUR = 1080, 1920, 30, 20.0
NF = int(DUR * FPS)
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "out")
os.makedirs(OUT, exist_ok=True)

AMB, TEAL, GRAY = COL["mot"], COL["dis"], (0.6, 0.58, 0.7)
SC_A, SC_B, SC_C = (0.0, 7.0), (6.6, 13.6), (13.2, 20.0)   # scene windows (0.4 s cross-fades)

# ================================================================ poses (local: feet at y=0)
def walk(ph, d=1, amp=1.0, lean=0.06):
    L = TH + SH
    J = {}
    py = -L * 0.97 - 5 * abs(math.cos(ph)) * amp
    pel = (0.0, py); J["pel"] = pel
    for k, (kn, ft) in enumerate((("lkn", "lft"), ("rkn", "rft"))):
        a = 0.45 * amp * math.sin(ph + k * math.pi)
        bend = 0.9 * amp * max(0.0, math.sin(ph + k * math.pi + math.pi / 2)) + 0.05
        knee = (pel[0] + TH * math.sin(a) * d, pel[1] + TH * math.cos(a))
        J[kn] = knee
        J[ft] = (knee[0] + SH * math.sin(a - bend) * d, knee[1] + SH * math.cos(a - bend))
    neck = (pel[0] + math.sin(lean) * TORSO * d, pel[1] - math.cos(lean) * TORSO)
    J["neck"] = neck
    sh = (neck[0], neck[1] + 8)
    J["lsh"] = J["rsh"] = sh
    for k, (el, ha) in enumerate((("lel", "lha"), ("rel", "rha"))):
        s = -0.5 * amp * math.sin(ph + k * math.pi) + 0.05
        e = (sh[0] + UA * math.sin(s) * d, sh[1] + UA * math.cos(s))
        J[el] = e
        J[ha] = (e[0] + FA * math.sin(s + 0.35) * d, e[1] + FA * math.cos(s + 0.35))
    J["head"] = (neck[0] + 6 * d, neck[1] - NECK - HEAD_R)
    return J

def stand(d=1): return walk(0, d, amp=0.0, lean=0.02)

def fallen(d=1, breathe=0.0):
    pel = (0.0, -22.0)
    neck = (-40 * d, pel[1] - 140 + breathe)
    sh = (neck[0], neck[1] + 8)
    J = {"pel": pel, "neck": neck, "lsh": sh, "rsh": sh,
         "lkn": (70 * d, -55), "lft": (150 * d, -4),
         "rkn": (88 * d, -28), "rft": (168 * d, -4),
         "head": (neck[0] + 14 * d, neck[1] - NECK - HEAD_R + 10)}
    J["lha"] = (-80 * d, -6); J["rha"] = (-60 * d, -6)
    J["lel"] = ik(sh, J["lha"], UA, FA, d); J["rel"] = ik(sh, J["rha"], UA, FA, d)
    return J

def kneel(d=1):
    pel = (0.0, -112.0)
    neck = (28 * d, pel[1] - 146)
    sh = (neck[0], neck[1] + 8)
    J = {"pel": pel, "neck": neck, "lsh": sh, "rsh": sh,
         "lkn": (62 * d, -104), "lft": (66 * d, -4),
         "rkn": (-20 * d, -10), "rft": (-112 * d, -6),
         "head": (neck[0] + 8 * d, neck[1] - NECK - HEAD_R)}
    J["lha"] = (40 * d, -60); J["rha"] = (60 * d, -70)
    J["lel"] = ik(sh, J["lha"], UA, FA, d); J["rel"] = ik(sh, J["rha"], UA, FA, d)
    return J

def sit_phone(d=1, breathe=0.0):
    pel = (0.0, -22.0)
    neck = (-12 * d, pel[1] - 145 + breathe)
    sh = (neck[0], neck[1] + 8)
    J = {"pel": pel, "neck": neck, "lsh": sh, "rsh": sh,
         "lkn": (62 * d, -112), "lft": (112 * d, -4),
         "rkn": (52 * d, -106), "rft": (102 * d, -4),
         "head": (neck[0] + 20 * d, neck[1] - NECK - HEAD_R + 14)}
    J["lha"] = J["rha"] = (58 * d, -150 + breathe)
    J["lel"] = ik(sh, J["lha"], UA, FA, -d); J["rel"] = ik(sh, J["rha"], UA, FA, -d)
    return J

def celebrate(d=1, wave_=0.0):
    J = stand(d)
    sh = J["lsh"]
    J["lha"] = (sh[0] - 55, sh[1] - 150 + 10 * math.sin(wave_))
    J["rha"] = (sh[0] + 55, sh[1] - 150 - 10 * math.sin(wave_))
    J["lel"] = ik(sh, J["lha"], UA, FA, -1); J["rel"] = ik(sh, J["rha"], UA, FA, 1)
    J["head"] = (J["neck"][0], J["neck"][1] - NECK - HEAD_R - 4)
    return J

def blend(a, b, u):
    return {k: (lerp(a[k][0], b[k][0], u), lerp(a[k][1], b[k][1], u)) for k in a}

def set_hand(J, side, target, bend):
    sh = J[side + "sh"]
    J[side + "ha"] = target
    J[side + "el"] = ik(sh, target, UA, FA, bend)

# ================================================================ drawing helpers
def fig(cr, J, x, y, s, col, who="", glow=0.0, alpha=1.0, props=None):
    cr.save(); cr.translate(x, y); cr.scale(s, s)
    skeleton(cr, J, col, w=22, glow=glow, alpha=alpha, who=who)
    if props: props(cr, J)
    cr.restore()

def to_local(pt, x, y, s): return ((pt[0] - x) / s, (pt[1] - y) / s)
def to_world(pt, x, y, s): return (x + pt[0] * s, y + pt[1] * s)

def umbrella(cr, hand, col, tilt=0.0, r=125):
    hx, hy = hand
    top = (hx + math.sin(tilt) * 95, hy - math.cos(tilt) * 95)
    cr.set_source_rgb(0.1, 0.1, 0.12); cr.set_line_width(7); cr.set_line_cap(cairo.LINE_CAP_ROUND)
    cr.move_to(hx, hy + 22); cr.line_to(*top); cr.stroke()
    cr.arc(hx - 10, hy + 22, 10, 0, math.pi); cr.stroke()
    cr.save(); cr.translate(*top); cr.rotate(tilt)
    cr.set_source_rgb(*col)
    cr.move_to(-r, 0); cr.curve_to(-r, -r * 0.95, r, -r * 0.95, r, 0)
    for i in range(4, -1, -1):          # scalloped edge
        x0 = -r + i * (2 * r / 5)
        cr.curve_to(x0 + r / 5 * 1.4, -22 + 0, x0 + r / 5 * 0.6, -22, x0, 0) if False else cr.line_to(x0, 0)
    cr.close_path(); cr.fill()
    cr.set_source_rgba(0, 0, 0, 0.18)
    for i in range(5):
        x0 = -r + i * (2 * r / 5)
        cr.arc(x0 + r / 5, 0, r / 5, 0, math.pi); cr.fill()
    cr.set_source_rgba(1, 1, 1, 0.18); cr.set_line_width(4)
    cr.move_to(0, -r * 0.72); cr.curve_to(-r * 0.35, -r * 0.6, -r * 0.6, -r * 0.3, -r * 0.7, 0); cr.stroke()
    cr.restore()

def phone(cr, hand, glow=1.0):
    hx, hy = hand
    for i in range(6, 0, -1):
        cr.set_source_rgba(0.6, 0.85, 1, 0.045 * glow); cr.arc(hx, hy - 10, 26 + i * 14, 0, 7); cr.fill()
    cr.set_source_rgb(0.08, 0.08, 0.12); rrect(cr, hx - 16, hy - 40, 32, 54, 7); cr.fill()
    cr.set_source_rgb(0.65, 0.88, 1); rrect(cr, hx - 12, hy - 36, 24, 46, 4); cr.fill()

def can(cr, hand, d, tilt):
    cr.save(); cr.translate(*hand); cr.scale(d, 1); cr.rotate(tilt)
    cr.set_source_rgb(0.55, 0.62, 0.7)
    rrect(cr, -10, -20, 62, 50, 8); cr.fill()
    cr.set_line_width(9); cr.move_to(48, 12); cr.line_to(92, -16); cr.stroke()
    cr.set_line_width(6); cr.arc(18, -24, 18, math.pi, 0); cr.stroke()
    cr.restore()

def heart(cr, x, y, s, col, a):
    cr.save(); cr.translate(x, y); cr.scale(s, s)
    cr.move_to(0, 12)
    cr.curve_to(-30, -10, -18, -38, 0, -20)
    cr.curve_to(18, -38, 30, -10, 0, 12)
    cr.set_source_rgba(*col, a); cr.fill(); cr.restore()

def vignette(cr, k=0.6):
    rg = cairo.RadialGradient(W / 2, H * 0.48, 320, W / 2, H * 0.48, 1250)
    rg.add_color_stop_rgba(0, 0, 0, 0, 0); rg.add_color_stop_rgba(1, 0, 0, 0, k)
    cr.set_source(rg); cr.paint()

def grad(cr, y0, y1, stops):
    g = cairo.LinearGradient(0, y0, 0, y1)
    for o, c in stops: g.add_color_stop_rgb(o, *c)
    return g

# ================================================================ SCENE 1 — rain
GA, SA = 1480, 1.08
LAMP_X = 700
RR = random.Random(11)
RAIN = [(RR.uniform(-200, W + 200), RR.uniform(0, H), RR.uniform(1500, 2300), RR.uniform(40, 80), RR.uniform(0.15, 0.4))
        for _ in range(260)]

def bg_rain():
    s = cairo.ImageSurface(cairo.FORMAT_ARGB32, W, H); cr = cairo.Context(s)
    cr.set_source(grad(cr, 0, GA, [(0, (0.03, 0.04, 0.09)), (0.7, (0.08, 0.1, 0.18)), (1, (0.14, 0.15, 0.24))])); cr.paint()
    rnd = random.Random(4)
    x = -30
    while x < W:   # wet city blocks
        bw, bh = rnd.randint(90, 190), rnd.randint(300, 760)
        cr.set_source_rgb(0.06, 0.07, 0.13); cr.rectangle(x, GA - bh, bw, bh); cr.fill()
        for wx in range(x + 14, x + bw - 18, 28):
            for wy in range(GA - bh + 20, GA - 40, 38):
                if rnd.random() < 0.18:
                    cr.set_source_rgba(1, 0.8, 0.5, 0.55); cr.rectangle(wx, wy, 12, 18); cr.fill()
        x += bw + rnd.randint(4, 14)
    cr.set_source(grad(cr, GA, H, [(0, (0.12, 0.13, 0.2)), (1, (0.03, 0.03, 0.06))])); cr.rectangle(0, GA, W, H - GA); cr.fill()
    cr.set_source_rgba(1, 1, 1, 0.07); cr.rectangle(0, GA, W, 6); cr.fill()
    # puddles with lamp reflection
    for px, pw in ((260, 220), (720, 300), (980, 160)):
        cr.save(); cr.translate(px, GA + 120); cr.scale(pw, 26)
        cr.arc(0, 0, 1, 0, 7); cr.restore()
        cr.set_source_rgba(0.5, 0.6, 0.85, 0.12); cr.fill()
    cr.save(); cr.translate(LAMP_X, GA + 150); cr.scale(60, 160); cr.arc(0, 0, 1, 0, 7); cr.restore()
    cr.set_source_rgba(1, 0.8, 0.45, 0.04); cr.fill()
    # lamp post
    cr.set_source_rgb(0.04, 0.04, 0.06); cr.rectangle(LAMP_X - 9, 760, 18, GA - 760); cr.fill()
    cr.set_line_width(14); cr.move_to(LAMP_X, 770); cr.curve_to(LAMP_X, 700, LAMP_X - 90, 700, LAMP_X - 110, 740); cr.stroke()
    cr.set_source_rgb(1, 0.88, 0.6); rrect(cr, LAMP_X - 150, 736, 80, 26, 10); cr.fill()
    return s

def lamp_cone(cr, warm):
    cx = LAMP_X - 110
    g = cairo.LinearGradient(0, 760, 0, GA)
    g.add_color_stop_rgba(0, 1, 0.82, 0.5, 0.22 + 0.15 * warm); g.add_color_stop_rgba(1, 1, 0.82, 0.5, 0.0)
    cr.set_source(g)
    cr.move_to(cx - 30, 760); cr.line_to(cx + 30, 760); cr.line_to(cx + 300, GA); cr.line_to(cx - 300, GA); cr.close_path(); cr.fill()
    rg = cairo.RadialGradient(cx, 752, 10, cx, 752, 160)
    rg.add_color_stop_rgba(0, 1, 0.9, 0.6, 0.5); rg.add_color_stop_rgba(1, 1, 0.9, 0.6, 0)
    cr.set_source(rg); cr.arc(cx, 752, 160, 0, 7); cr.fill()

def rain(cr, t, k=1.0, ground=GA):
    cr.set_line_width(2.4); cr.set_line_cap(cairo.LINE_CAP_ROUND)
    for x0, y0, sp, ln, a in RAIN:
        y = (y0 + t * sp) % (ground + 100) - 100
        x = x0 - (y - y0) * 0.12
        cr.set_source_rgba(0.75, 0.82, 1, a * k)
        cr.move_to(x, y); cr.line_to(x - ln * 0.12, y + ln); cr.stroke()
    for i, (x0, y0, sp, ln, a) in enumerate(RAIN[:40]):   # splashes
        ph = (t * 2.3 + i * 0.37) % 1
        cr.set_source_rgba(0.75, 0.82, 1, 0.35 * (1 - ph) * k); cr.set_line_width(2)
        cr.save(); cr.translate((x0 * 3.1) % W, ground + 10 + (i % 5) * 40); cr.scale(1, 0.3)
        cr.arc(0, 0, 6 + 26 * ph, 0, 7); cr.restore(); cr.stroke()

BG_A = None
def scene_rain(cr, t):
    cr.set_source_surface(BG_A); cr.paint()
    warm = ease((t - 5.5) / 1.0)
    lamp_cone(cr, warm)
    rain(cr, t)
    # --- Amber: walks in, slips
    ax = 380
    if t < 1.3:
        xa = lerp(-120, 350, t / 1.3); Ja = walk(t * 9, 1)
    elif t < 1.65:
        u = (t - 1.3) / 0.35; xa = lerp(350, ax, u); Ja = blend(walk(1.3 * 9, 1), fallen(1), ease_out(u))
    elif t < 5.3:
        xa = ax; Ja = fallen(1, math.sin(t * 2.5) * 3)
    elif t < 5.9:
        xa = ax; Ja = blend(fallen(1), stand(1), ease((t - 5.3) / 0.6))
    else:
        xa = ax; Ja = stand(1)
    # --- Teal friend (computed first so Amber can reach for the hand)
    tx = 640
    Jt, xt, t_props = None, None, None
    if t >= 3.6:
        if t < 4.9:
            xt = lerp(1200, tx, ease_out((t - 3.6) / 1.3)); Jt = walk(t * 8.5, -1, amp=clamp((4.9 - t) / 0.4))
        elif t < 5.3:
            xt = tx; Jt = blend(stand(-1), kneel(-1), ease((t - 4.9) / 0.4))
        elif t < 5.9:
            xt = tx; Jt = blend(kneel(-1), stand(-1), ease((t - 5.3) / 0.6))
        else:
            xt = tx; Jt = stand(-1)
        # umbrella hand: over self, then over Amber, then over both
        sh_w = to_world(Jt["lsh"], xt, GA, SA)
        own = (sh_w[0] + 10, sh_w[1] - 140 * SA)
        over_a = (xa + 50 * SA, sh_w[1] - 130 * SA)
        both = ((xa + xt) / 2 + 20, GA - 560 * SA)
        k1 = ease((t - 4.7) / 0.5); k2 = ease((t - 5.6) / 0.6)
        tgt = (lerp(lerp(own[0], over_a[0], k1), both[0], k2), lerp(lerp(own[1], over_a[1], k1), both[1], k2))
        set_hand(Jt, "l", to_local(tgt, xt, GA, SA), 1)
        # helping hand
        if 4.95 < t < 6.2:
            reach = ease((t - 4.95) / 0.35) * (1 - ease((t - 5.9) / 0.3))
            Ja_hand_w = to_world(Ja["lsh"], xa, GA, SA)
            meet = (lerp(sh_w[0] - 60, (Ja_hand_w[0] + sh_w[0]) / 2, reach), lerp(sh_w[1] + 90, (Ja_hand_w[1] + sh_w[1]) / 2 + 30, reach))
            set_hand(Jt, "r", to_local(meet, xt, GA, SA), 1)
            if reach > 0.3:
                set_hand(Ja, "r", to_local(meet, xa, GA, SA), -1)
        if t > 6.0:   # arm around friend
            set_hand(Jt, "r", to_local((xa + 70 * SA, GA - 300 * SA), xt, GA, SA), 1)
        ush = Jt["lha"]
        t_props = lambda c, J: umbrella(c, J["lha"], (0.2, 0.75, 0.72), tilt=-0.15 * ease((t - 4.7) / 0.5) + 0.12 * ease((t - 5.6) / 0.6))
    # --- Gray passer-by: umbrella over self, eyes on phone, never stops
    if 1.7 < t < 4.6:
        xg = lerp(1220, -220, (t - 1.7) / 2.9)
        Jg = walk(t * 8, -1, lean=0.12)
        sh = Jg["lsh"]
        set_hand(Jg, "l", (sh[0] + 4, sh[1] - 115), 1)
        set_hand(Jg, "r", (sh[0] - 50, sh[1] - 6), 1)
        Jg["head"] = (Jg["neck"][0] - 16, Jg["neck"][1] - NECK - HEAD_R + 12)
        fig(cr, Jg, xg, GA, SA, GRAY,
            props=lambda c, J: (umbrella(c, J["lha"], (0.25, 0.25, 0.3)), phone(c, J["rha"])))
    fig(cr, Ja, xa, GA, SA, AMB, who="mot")
    if Jt: fig(cr, Jt, xt, GA, SA, TEAL, who="dis", props=t_props)
    # rain splash where amber slipped
    if 1.35 < t < 2.0:
        u = (t - 1.35) / 0.65
        for i in range(10):
            ang = math.pi + i * math.pi / 9
            r = 30 + 120 * u
            cr.set_source_rgba(0.75, 0.85, 1, 0.8 * (1 - u))
            cr.arc(xa + 60 + math.cos(ang) * r, GA - 10 + math.sin(ang) * r * 0.6 + 80 * u * u, 6, 0, 7); cr.fill()
    if t > 6.1:
        u = (t - 6.1) / 0.9
        heart(cr, (xa + xt) / 2 + 20, GA - 760 * SA - 80 * u, 1.6 + 0.6 * ease_out(u), (1, 0.4, 0.5), clamp(1.6 * (1 - u)))
    vignette(cr)

# ================================================================ SCENE 2 — garden (split)
GB, SB = 1360, 0.62

def sky_day(e):
    night = ((0.03, 0.04, 0.12), (0.1, 0.1, 0.24))
    day = ((0.35, 0.62, 0.95), (0.85, 0.9, 0.95))
    dusk = ((0.3, 0.2, 0.45), (1.0, 0.6, 0.45))
    k = clamp(e * 0.5 + 0.5)
    if k < 0.5: a, b, u = night, dusk, k / 0.5
    else: a, b, u = dusk, day, (k - 0.5) / 0.5
    return [tuple(lerp(a[i][j], b[i][j], u) for j in range(3)) for i in range(2)]

def plant(cr, x, gy, g, wilt=0.0):
    cr.set_source_rgb(0.3, 0.2, 0.14)
    cr.save(); cr.translate(x, gy + 4); cr.scale(70, 22); cr.arc(0, 0, 1, math.pi, 2 * math.pi); cr.restore(); cr.fill()
    green = (lerp(0.35, 0.55, wilt), lerp(0.85, 0.42, wilt), lerp(0.4, 0.2, wilt))
    if g <= 0.0: return
    if g < 0.35:
        h = 25 + 145 * (g / 0.35)
        droop = wilt * 1.6
        top = (x + math.sin(droop) * h * 0.55, gy - h + (1 - math.cos(droop)) * h * 0.55)
        cr.set_source_rgb(*green); cr.set_line_width(9); cr.set_line_cap(cairo.LINE_CAP_ROUND)
        cr.move_to(x, gy); cr.curve_to(x, gy - h * 0.5, top[0] - 10 * math.sin(droop), top[1] + h * 0.3, *top); cr.stroke()
        ls = 14 + 28 * (g / 0.35)
        for sgn in (-1, 1):
            cr.save(); cr.translate(*top); cr.rotate(sgn * (0.7 + wilt * 0.9) + droop)
            cr.scale(ls, ls * 0.45); cr.arc(sgn * 1.0, 0, 1, 0, 7); cr.restore(); cr.fill()
        if wilt > 0.5:   # fallen leaf
            cr.save(); cr.translate(x + 50, gy - 4); cr.scale(16, 6); cr.arc(0, 0, 1, 0, 7); cr.restore()
            cr.set_source_rgba(0.55, 0.42, 0.2, (wilt - 0.5) * 2); cr.fill()
    else:
        u = (g - 0.35) / 0.65
        th, tw = lerp(170, 430, u), lerp(12, 40, u)
        cr.set_source_rgb(0.42, 0.28, 0.18)
        cr.move_to(x - tw / 2, gy); cr.line_to(x - tw / 4, gy - th); cr.line_to(x + tw / 4, gy - th); cr.line_to(x + tw / 2, gy); cr.close_path(); cr.fill()
        cr.set_line_width(tw * 0.35); cr.set_line_cap(cairo.LINE_CAP_ROUND)
        cr.move_to(x, gy - th * 0.6); cr.line_to(x + th * 0.25, gy - th * 0.85); cr.stroke()
        cr.move_to(x, gy - th * 0.7); cr.line_to(x - th * 0.22, gy - th * 0.95); cr.stroke()
        R = lerp(55, 175, u)
        cy = gy - th - R * 0.35
        blobs = [(0, 0, 1), (-0.75, 0.3, 0.7), (0.75, 0.3, 0.72), (-0.4, -0.45, 0.72), (0.42, -0.42, 0.7)]
        for (bx, by, br) in blobs:
            cr.set_source_rgb(0.2, 0.62, 0.35); cr.arc(x + bx * R, cy + by * R, br * R * 0.85, 0, 7); cr.fill()
        for (bx, by, br) in blobs:
            cr.set_source_rgb(0.3, 0.75, 0.42); cr.arc(x + bx * R - R * 0.12, cy + by * R - R * 0.12, br * R * 0.55, 0, 7); cr.fill()
        if u > 0.75:   # glowing fruit
            k = (u - 0.75) / 0.25
            for i, (fx, fy) in enumerate([(-0.5, 0.2), (0.3, 0.45), (0.65, -0.1), (-0.15, -0.35), (0.05, 0.1), (-0.7, -0.15)]):
                if k * 6 < i: continue
                px, py = x + fx * R, cy + fy * R
                for j in range(4, 0, -1):
                    cr.set_source_rgba(1, 0.6, 0.25, 0.08); cr.arc(px, py, 14 + j * 9, 0, 7); cr.fill()
                cr.set_source_rgb(1, 0.55, 0.3); cr.arc(px, py, 15, 0, 7); cr.fill()

def drops(cr, x, y, t, a=1.0):
    for i in range(7):
        ph = (t * 3 + i / 7) % 1
        cr.set_source_rgba(0.55, 0.8, 1, a * (1 - ph))
        cr.arc(x + i * 3 - 9 + ph * 22, y + ph * 120, 5, 0, 7); cr.fill()

def garden_pane(cr, t, x0, side):
    DAY0, DAYP = 0.9, 1.15
    dp = max(0.0, (t - DAY0) / DAYP)
    e = math.cos(2 * math.pi * dp)
    top, hor = sky_day(e)
    cr.set_source(grad(cr, 0, GB, [(0, top), (1, hor)])); cr.rectangle(x0, 0, 540, GB); cr.fill()
    # stars
    rnd = random.Random(9)
    for _ in range(40):
        cr.set_source_rgba(1, 1, 1, clamp(-e) * rnd.uniform(0.3, 0.9))
        cr.arc(x0 + rnd.uniform(0, 540), rnd.uniform(0, 900), 2, 0, 7); cr.fill()
    # sun & moon on an arc
    a = 2 * math.pi * dp
    cx = x0 + 270
    sx, sy = cx + 230 * math.sin(a), 1000 - 620 * math.cos(a)
    for i in range(5, 0, -1):
        cr.set_source_rgba(1, 0.9, 0.5, 0.06); cr.arc(sx, sy, 50 + i * 16, 0, 7); cr.fill()
    cr.set_source_rgb(1, 0.92, 0.6); cr.arc(sx, sy, 50, 0, 7); cr.fill()
    mx, my = cx - 230 * math.sin(a), 1000 + 620 * math.cos(a)
    cr.set_source_rgb(0.92, 0.92, 1); cr.arc(mx, my, 34, 0, 7); cr.fill()
    # hills + ground
    cr.set_source_rgb(*[c * (0.45 + 0.4 * clamp(e * .5 + .5)) for c in (0.25, 0.5, 0.35)])
    cr.move_to(x0, GB - 120); cr.curve_to(x0 + 150, GB - 260, x0 + 330, GB - 60, x0 + 540, GB - 190); cr.line_to(x0 + 540, GB); cr.line_to(x0, GB); cr.fill()
    br = 0.35 + 0.65 * clamp(e * .5 + .5)
    cr.set_source(grad(cr, GB, H, [(0, (0.3 * br, 0.55 * br, 0.28 * br)), (0.08, (0.32 * br, 0.22 * br, 0.15 * br)), (1, (0.08, 0.05, 0.04))]))
    cr.rectangle(x0, GB, 540, H - GB); cr.fill()
    px = x0 + 330
    if side == "L":
        g = 0.12 * ease((t - 0.9) / 0.6)
        wilt = ease((t - 2.4) / 2.2)
        plant(cr, px, GB, g, wilt)
        if t < 0.7:
            fx = lerp(x0 - 80, x0 + 190, t / 0.7); J = walk(t * 8, 1)
            canp = lambda c, J: can(c, J["rha"], 1, 0.0)
        elif t < 1.6:
            fx = x0 + 190; J = stand(1)
            tilt = 0.75 * ease((t - 0.8) / 0.25) * (1 - ease((t - 1.4) / 0.2))
            set_hand(J, "r", (115, J["rsh"][1] + 45), 1)
            canp = lambda c, J, tilt=tilt: can(c, J["rha"], 1, tilt)
            if tilt > 0.3: drops(cr, fx + 195 * SB, GB - 290 * SB, t)
        elif t < 2.0:
            fx = x0 + 190 - 70 * ease((t - 1.6) / 0.4); J = blend(stand(1), sit_phone(1), ease((t - 1.6) / 0.4)); canp = None
        else:
            fx = x0 + 120; J = sit_phone(1, math.sin(t * 2) * 2)
            canp = lambda c, J: phone(c, J["lha"])
        fig(cr, J, fx, GB, SB, AMB, who="mot", props=canp)
        cr.set_source_rgba(0.15, 0.15, 0.2, 0.25 * wilt); cr.rectangle(x0, 0, 540, H); cr.fill()
    else:
        g = ease(clamp((t - 0.9) / 5.2)) ** 0.9
        plant(cr, px, GB, g)
        if t < 0.7:
            fx = lerp(x0 - 80, x0 + 150, t / 0.7); J = walk(t * 8, 1)
            canp = lambda c, J: can(c, J["rha"], 1, 0.0)
        elif t < 6.2:
            fx = x0 + 150; J = stand(1)
            day_ph = (dp % 1.0)
            water = clamp(e) > 0.25 and t > 0.85
            tilt = 0.75 if water else 0.0
            set_hand(J, "r", (115, J["rsh"][1] + 45 + (0 if water else 50)), 1)
            canp = lambda c, J, tilt=tilt: can(c, J["rha"], 1, tilt)
            if water: drops(cr, fx + 195 * SB, GB - 290 * SB, t)
        else:
            fx = x0 + 150; J = celebrate(1, t * 10); canp = None
        fig(cr, J, fx, GB, SB, TEAL, who="dis", props=canp)

def scene_garden(cr, t):
    cr.save(); cr.rectangle(0, 0, 540, H); cr.clip(); garden_pane(cr, t, 0, "L"); cr.restore()
    cr.save(); cr.rectangle(540, 0, 540, H); cr.clip(); garden_pane(cr, t, 540, "R"); cr.restore()
    cr.set_source_rgba(0, 0, 0, 0.6); cr.rectangle(536, 0, 8, H); cr.fill()
    cr.set_source_rgba(1, 1, 1, 0.5); cr.rectangle(539, 0, 2, H); cr.fill()
    vignette(cr, 0.5)

# ================================================================ SCENE 3 — mountain
SM = 0.42
PEAK = (600, 780)
TRAIL = [(140, 1660), (790, 1520), (330, 1320), (740, 1120), (600, PEAK[1] + 6)]
SEG = [math.dist(TRAIL[i], TRAIL[i + 1]) for i in range(len(TRAIL) - 1)]
TOTAL = sum(SEG)

def trail_pt(u):
    d = clamp(u) * TOTAL
    for i, L in enumerate(SEG):
        if d <= L or i == len(SEG) - 1:
            k = clamp(d / L)
            a, b = TRAIL[i], TRAIL[i + 1]
            return (lerp(a[0], b[0], k), lerp(a[1], b[1], k)), (1 if b[0] > a[0] else -1)
        d -= L

def scene_mountain(cr, t):
    dawn = ease((t - 3.8) / 1.4)
    storm = 1 - ease((t - 3.3) / 1.0)
    st = [(0, (0.08, 0.09, 0.13)), (1, (0.25, 0.27, 0.33))]
    sr = [(0, (0.12, 0.1, 0.3)), (0.6, (0.85, 0.42, 0.45)), (1, (1.0, 0.78, 0.45))]
    g = cairo.LinearGradient(0, 0, 0, 1500)
    for (o, a), (_, b) in zip(sorted(st + [(0.6, (0.17, 0.18, 0.24))]), sr):
        g.add_color_stop_rgb(o, *(lerp(a[i], b[i], dawn) for i in range(3)))
    cr.set_source(g); cr.paint()
    # sun rising behind peak
    sy = lerp(1250, 640, dawn)
    for i in range(12, 0, -1):
        cr.set_source_rgba(1, 0.85, 0.5, 0.05 * dawn); cr.arc(840, sy, 110 + i * 34, 0, 7); cr.fill()
    cr.set_source_rgba(1, 0.92, 0.65, dawn); cr.arc(840, sy, 110, 0, 7); cr.fill()
    if dawn > 0.4:   # rays
        cr.save(); cr.translate(840, sy); cr.rotate(t * 0.15)
        for i in range(14):
            cr.rotate(2 * math.pi / 14)
            cr.set_source_rgba(1, 0.9, 0.6, 0.07 * (dawn - 0.4) / 0.6)
            cr.move_to(0, 0); cr.line_to(1200, -60); cr.line_to(1200, 60); cr.close_path(); cr.fill()
        cr.restore()
    # far ridges
    cr.set_source_rgb(*(lerp(a, b, dawn) for a, b in zip((0.12, 0.13, 0.19), (0.45, 0.25, 0.4))))
    cr.move_to(0, 1250); cr.line_to(180, 1050); cr.line_to(330, 1180); cr.line_to(960, 980); cr.line_to(W, 1100); cr.line_to(W, H); cr.line_to(0, H); cr.fill()
    # main mountain
    mc = tuple(lerp(a, b, dawn) for a, b in zip((0.16, 0.17, 0.22), (0.32, 0.18, 0.3)))
    cr.set_source_rgb(*mc)
    cr.move_to(-60, 1820); cr.line_to(150, 1520); cr.line_to(330, 1270); cr.line_to(*PEAK); cr.line_to(880, 1200)
    cr.line_to(1010, 1360); cr.line_to(1140, 1820); cr.close_path(); cr.fill()
    cr.set_source_rgba(0, 0, 0, 0.18)   # shaded face
    cr.move_to(*PEAK); cr.line_to(880, 1200); cr.line_to(1010, 1360); cr.line_to(1140, 1820); cr.line_to(700, 1820); cr.close_path(); cr.fill()
    cr.set_source_rgb(*(lerp(a, b, dawn) for a, b in zip((0.75, 0.78, 0.85), (1, 0.9, 0.85))))   # snow cap
    cr.move_to(*PEAK); cr.line_to(520, 920); cr.line_to(560, 900); cr.line_to(595, 945); cr.line_to(640, 900); cr.line_to(700, 935); cr.close_path(); cr.fill()
    # trail
    cr.set_source_rgba(1, 1, 1, 0.18 + 0.12 * dawn); cr.set_line_width(5); cr.set_dash([14, 14])
    cr.move_to(*TRAIL[0])
    for p in TRAIL[1:]: cr.line_to(*p)
    cr.stroke(); cr.set_dash([])
    # flag
    if t > 3.7:
        k = ease((t - 3.7) / 0.35)
        fx, fy = PEAK[0] + 22, PEAK[1] + 4
        cr.set_source_rgb(0.15, 0.15, 0.18); cr.set_line_width(5)
        cr.move_to(fx, fy); cr.line_to(fx, fy - 120 * k); cr.stroke()
        if k > 0.9:
            cr.set_source_rgb(*TEAL)
            wv = math.sin(t * 8) * 8
            cr.move_to(fx, fy - 120); cr.curve_to(fx + 30, fy - 120 + wv, fx + 50, fy - 112 - wv, fx + 78, fy - 102)
            cr.line_to(fx, fy - 82); cr.close_path(); cr.fill()
    # --- climbers
    # Amber: climbs, storm pushes them back down; later climbs again
    if t < 1.5:
        ua, Ja = lerp(0.0, 0.2, t / 1.5), None
    elif t < 2.2:
        ua = lerp(0.2, 0.05, ease((t - 1.5) / 0.7)); Ja = "fall"
    elif t < 4.4:
        ua = 0.05; Ja = "sit"
    elif t < 5.6:
        ua = lerp(0.05, 0.86, ease((t - 4.4) / 1.2)); Ja = None
    else:
        ua = lerp(0.86, 0.985, ease((t - 5.6) / 0.4)); Ja = "cheer" if t > 6.0 else None
    pa, da = trail_pt(ua)
    if Ja is None: J = walk(t * 9, da, lean=0.2)
    elif Ja == "fall": J = blend(walk(t * 9, da), fallen(da), ease((t - 1.5) / 0.3))
    elif Ja == "sit": J = fallen(da, math.sin(t * 2) * 3)
    else: J = celebrate(1, t * 9)
    if Ja == "sit" and t > 4.0:   # gets back up when friend returns
        J = blend(fallen(da), stand(da), ease((t - 4.0) / 0.4))
    # Teal
    if t < 1.5: ut = lerp(0.0, 0.24, t / 1.5)
    elif t < 3.6: ut = lerp(0.24, 1.0, (t - 1.5) / 2.1)
    elif t < 4.0: ut = 1.0
    elif t < 4.5: ut = lerp(1.0, 0.86, ease((t - 4.0) / 0.5))
    elif t < 5.6: ut = 0.86
    else: ut = lerp(0.86, 1.0, ease((t - 5.6) / 0.4))
    pt, dt_ = trail_pt(ut)
    if t < 3.6: Jt = walk(t * (9 if t < 1.5 else 6.5), dt_, lean=0.35 if t > 1.5 else 0.2)
    elif t < 4.0: Jt = stand(1); set_hand(Jt, "r", (60, Jt["rsh"][1] + 20), 1)
    elif t < 4.5: Jt = walk(t * 8, -dt_, lean=0.1)
    elif t < 5.6:
        Jt = stand(-1)
        sh = Jt["lsh"]; set_hand(Jt, "l", (sh[0] - 120, sh[1] + 70), 1)   # reaching down to friend
    elif t < 6.0: Jt = walk(t * 9, dt_, lean=0.2)
    else: Jt = celebrate(1, t * 9 + 1)
    fig(cr, J, pa[0] - (26 if t > 5.9 else 0), pa[1] + (6 if t > 5.9 else 0), SM, AMB, who="mot")
    fig(cr, Jt, pt[0] + (26 if t > 5.9 else 0), pt[1] + (6 if t > 5.9 else 0), SM, TEAL, who="dis", glow=0.6 * dawn)
    # storm: clouds, wind streaks, rain, lightning
    if storm > 0:
        rain(cr, t, k=storm * 0.9, ground=1800)
        rnd = random.Random(2)
        for i in range(9):
            cx = (rnd.uniform(-100, W + 100) + t * 60 * (1 if i % 2 else -0.6)) % (W + 300) - 150
            cy = rnd.uniform(620, 960)
            for j in range(4):
                cr.set_source_rgba(0.12, 0.13, 0.18, 0.75 * storm)
                cr.arc(cx + j * 60 - 90, cy + (j % 2) * 18, 70 + (j % 3) * 18, 0, 7); cr.fill()
        for ft in (1.45, 2.45):
            if ft < t < ft + 0.25:
                k = 1 - (t - ft) / 0.25
                cr.set_source_rgba(0.85, 0.9, 1, 0.55 * k); cr.paint()
                cr.set_source_rgba(1, 1, 0.95, k); cr.set_line_width(8)
                x = 300 if ft < 2 else 820
                cr.move_to(x, 700); cr.line_to(x - 40, 860); cr.line_to(x + 20, 880); cr.line_to(x - 30, 1080); cr.stroke()
    vignette(cr, 0.55)

# ================================================================ compose
def frame(t):
    surf = cairo.ImageSurface(cairo.FORMAT_ARGB32, W, H)
    cr = cairo.Context(surf)
    cr.set_source_rgb(0, 0, 0); cr.paint()
    for (a, b), fn in ((SC_A, scene_rain), (SC_B, scene_garden), (SC_C, scene_mountain)):
        if not (a - 1e-6 <= t <= b): continue
        alpha = 1.0
        if a > 0: alpha = min(alpha, clamp((t - a) / 0.4))
        if b < DUR: alpha = min(alpha, clamp((b - t) / 0.4) if t > b - 0.4 else 1.0)
        layer = cairo.ImageSurface(cairo.FORMAT_ARGB32, W, H)
        fn(cairo.Context(layer), t - a)
        cr.set_source_surface(layer); cr.paint_with_alpha(alpha)
    if t < 0.4:  # fade in / out
        cr.set_source_rgba(0, 0, 0, 1 - t / 0.4); cr.paint()
    if t > DUR - 0.6:
        cr.set_source_rgba(0, 0, 0, clamp((t - (DUR - 0.6)) / 0.6)); cr.paint()
    return surf

# ================================================================ audio
def make_audio(path, sr=44100):
    n = int(DUR * sr); out = np.zeros(n); tt = np.arange(n) / sr
    rng = np.random.default_rng(0)

    def add(sig, start, v=1.0):
        i = int(start * sr)
        if i >= n: return
        j = min(n, i + len(sig)); out[i:j] += v * sig[: j - i]

    def lowpass(x, k):
        return np.convolve(x, np.ones(k) / k, mode="same")

    def tone(f, dur, decay=3.0, harm=(1, 0.4, 0.15)):
        x = np.arange(int(dur * sr)) / sr
        s = sum(a * np.sin(2 * np.pi * f * (i + 1) * x) for i, a in enumerate(harm))
        return s * np.exp(-x * decay) * np.minimum(1, x / 0.005)

    def pad(t0, t1, freqs, v):
        i0, i1 = int(t0 * sr), min(n, int(t1 * sr)); x = tt[i0:i1] - t0
        env = np.minimum(1, x / 0.8) * np.minimum(1, (t1 - t0 - x) / 0.8)
        s = sum(np.sin(2 * np.pi * f * x + 0.2 * np.sin(2 * np.pi * 0.3 * x)) for f in freqs)
        out[i0:i1] += v * env * s / len(freqs)

    # scene 1: rain bed, minor pad, slow sad plucks, then warm resolve
    rainn = lowpass(rng.standard_normal(int(7.6 * sr)), 6) * 0.11
    rainn *= np.minimum(1, np.arange(len(rainn)) / sr / 0.5) * np.minimum(1, (len(rainn) / sr - np.arange(len(rainn)) / sr) / 0.6)
    add(rainn, 0)
    pad(0, 4.0, [110, 130.81, 164.81], 0.12)          # Am
    pad(3.6, 7.2, [87.31, 130.81, 174.61], 0.12)      # F
    pad(5.6, 7.4, [130.81, 164.81, 196.0], 0.14)      # C (warm)
    for i, f in enumerate([440, 392, 329.6, 293.7, 329.6, 261.6]):
        add(tone(f, 1.2, 2.5), 0.4 + i * 0.75, 0.10)
    add(tone(523.25, 2.0, 1.5), 6.1, 0.12); add(tone(659.25, 2.0, 1.5), 6.2, 0.10)
    # scene 2: playful plucks per "day", ticking clock feel
    pad(6.8, 13.8, [130.81, 164.81, 196.0], 0.10)
    scale = [523.25, 587.33, 659.25, 783.99, 880.0, 1046.5]
    k = 0; b = 6.6 + 0.9
    while b < 13.2:
        add(tone(scale[k % len(scale)], 0.5, 6.0), b, 0.09)
        add(tone(scale[(k + 2) % len(scale)] / 2, 0.5, 6.0), b + 0.575, 0.06)
        b += 0.575; k += 1
    # light kick/hat groove
    def kick():
        x = np.arange(int(0.3 * sr)) / sr
        f = 100 * np.exp(-x * 30) + 45
        return np.sin(2 * np.pi * np.cumsum(f) / sr) * np.exp(-x * 10)
    def hat():
        x = np.arange(int(0.05 * sr)) / sr
        return rng.standard_normal(len(x)) * np.exp(-x * 80)
    b = 7.4
    while b < 13.2:
        add(kick(), b, 0.5); add(hat(), b + 0.2875, 0.06); b += 0.575
    # scene 3: storm -> summit
    m0 = SC_C[0]
    wind = lowpass(rng.standard_normal(int(4.0 * sr)), 30) * 0.5
    wind *= np.sin(np.linspace(0, np.pi, len(wind)))
    add(wind, m0 + 0.2, 0.35)
    for ft in (1.45, 2.45):
        x = np.arange(int(1.8 * sr)) / sr
        thunder = lowpass(rng.standard_normal(len(x)), 60) * np.exp(-x * 2.2) * np.minimum(1, x / 0.02)
        add(thunder, m0 + ft, 2.2)
    pad(m0, m0 + 3.8, [98.0, 116.54, 146.83], 0.12)               # tense
    pad(m0 + 3.6, DUR, [130.81, 164.81, 196.0, 261.63], 0.18)     # triumphant C
    for i, f in enumerate([523.25, 659.25, 783.99, 1046.5]):
        add(tone(f, 2.5, 1.2), m0 + 3.75 + i * 0.12, 0.10)
    b = m0 + 3.75
    while b < DUR - 0.5:
        add(kick(), b, 0.7); add(hat(), b + 0.21, 0.08); b += 0.42
    for i, f in enumerate([783.99, 880.0, 1046.5, 1318.5]):
        add(tone(f, 2.0, 1.4), m0 + 5.95 + i * 0.1, 0.10)
    fo = int(0.8 * sr); out[-fo:] *= np.linspace(1, 0, fo)
    out = np.tanh(out * 1.4) * 0.8
    pcm = (out * 32767).astype(np.int16)
    with wave.open(path, "wb") as w:
        w.setnchannels(2); w.setsampwidth(2); w.setframerate(sr)
        w.writeframes(np.stack([pcm, pcm], 1).tobytes())

BG_A = bg_rain()

if __name__ == "__main__":
    wav = os.path.join(OUT, "show_up.wav"); make_audio(wav)
    mp4 = os.path.join(OUT, "show_up.mp4")
    ff = subprocess.Popen(["ffmpeg", "-y", "-v", "error", "-f", "rawvideo", "-pix_fmt", "bgra",
                           "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-", "-i", wav,
                           "-c:v", "libx264", "-preset", "medium", "-crf", "19", "-pix_fmt", "yuv420p",
                           "-c:a", "aac", "-b:a", "192k", "-shortest", "-movflags", "+faststart", mp4],
                          stdin=subprocess.PIPE)
    for i in range(NF):
        ff.stdin.write(bytes(frame(i / FPS).get_data()))
    ff.stdin.close(); ff.wait(); os.remove(wav)
    print("wrote", mp4)
