#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Generate 7 GRUB2 themes at 2560x1440:
  neongrid  - cyberpunk neon city + grid
  retrowave - outrun sunset + perspective grid
  matrix    - green code rain terminal
  nebula    - minimal deep-space starfield
  panda     - cartoon panda meadow
  clean     - pastel aurora minimal
  blockterm - opencode-style blocky terminal wordmark
Each theme dir gets: bg.png, panel_*.png, hl_*.png (9-slice), *.pf2 fonts,
theme.txt and a WYSIWYG preview.png.

NOTE for GRUB >= 2.12: the theme parser does NOT accept percent arithmetic
("left = 50% - 630") — it fails with 'expected "=" after property name' and
the whole theme silently falls back. Always use pixel values.
"""
import math
import os
import random
import subprocess
import sys

from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageFont

W, H = 2560, 1440
HORIZON = 979
ROOT = os.path.dirname(os.path.abspath(__file__))
FONTDIR = os.path.join(ROOT, "fonts")

TTF = {
    "rb":  os.path.join(FONTDIR, "Rajdhani-Bold.ttf"),
    "rsb": os.path.join(FONTDIR, "Rajdhani-SemiBold.ttf"),
    "rm":  os.path.join(FONTDIR, "Rajdhani-Medium.ttf"),
    "stm": os.path.join(FONTDIR, "ShareTechMono-Regular.ttf"),
    "snig_eb": os.path.join(FONTDIR, "Sniglet-ExtraBold.ttf"),
    "snig": os.path.join(FONTDIR, "Sniglet-Regular.ttf"),
    "plexm": os.path.join(FONTDIR, "IBMPlexMono-Regular.ttf"),
    "fzkai": "/usr/share/fonts/TTF/zh/fz/方正苏新诗柳楷简体.ttf",
    "wqy": "/usr/share/fonts/wenquanyi/wqy-microhei/wqy-microhei.ttc",
    "dvl": "/usr/share/fonts/TTF/DejaVuSans-ExtraLight.ttf",
    "dv":  "/usr/share/fonts/TTF/DejaVuSans.ttf",
    "dvm": "/usr/share/fonts/TTF/DejaVuSansMono.ttf",
    "dvs": "/usr/share/fonts/TTF/DejaVuSerif.ttf",
    "dvb": "/usr/share/fonts/TTF/DejaVuSans-Bold.ttf",
}
FALLBACK = {"rb": "dvb", "rsb": "dv", "rm": "dv", "stm": "dvm",
            "snig_eb": "dvb", "snig": "dv", "plexm": "dvm",
            "fzkai": "wqy", "wqy": "dvm", "dvs": "dv"}

RESOLVED = {}
for k, p in TTF.items():
    if os.path.exists(p):
        RESOLVED[k] = p
for k, alt in FALLBACK.items():
    if k not in RESOLVED:
        RESOLVED[k] = RESOLVED[alt]

_fc = {}
def font(k, px):
    key = (k, px)
    if key not in _fc:
        _fc[key] = ImageFont.truetype(RESOLVED[k], px)
    return _fc[key]

ENTRIES = [
    "Manjaro Linux (kernel: 6.18.49-1-MANJARO)",
    "Advanced options for Manjaro Linux",
    "UEFI Firmware Settings",
    "Windows Boot Manager (on /dev/nvme0n1p1)",
]

# ---------------------------------------------------------------- helpers

def vgrad(stops, w=W, h=H):
    img = Image.new("RGB", (1, h))
    px = img.load()
    for y in range(h):
        t = y / (h - 1)
        for i in range(len(stops) - 1):
            t0, c0 = stops[i]
            t1, c1 = stops[i + 1]
            if t0 <= t <= t1 or i == len(stops) - 2:
                f = 0.0 if t1 <= t0 else min(1.0, max(0.0, (t - t0) / (t1 - t0)))
                px[0, y] = tuple(int(c0[j] + (c1[j] - c0[j]) * f) for j in range(3))
                break
    return img.resize((w, h))

def radial_glow(base, cx, cy, rx, ry, col, k):
    q = 4
    sw, sh = W // q, H // q
    lay = Image.new("RGB", (sw, sh), (0, 0, 0))
    d = ImageDraw.Draw(lay)
    d.ellipse([(cx - rx) / q, (cy - ry) / q, (cx + rx) / q, (cy + ry) / q],
              fill=tuple(int(c * k) for c in col))
    lay = lay.filter(ImageFilter.GaussianBlur(max(8, rx // 5)))
    lay = lay.resize((W, H), Image.BILINEAR)
    return ImageChops.screen(base, lay)

def screen_layer(base, lay, blur):
    if blur:
        lay = lay.filter(ImageFilter.GaussianBlur(blur))
    return ImageChops.screen(base, lay)

def scanlines(base, alpha=18, step=4):
    ov = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(ov)
    for y in range(0, H, step):
        d.line([(0, y), (W, y)], fill=(0, 0, 0, alpha))
    base.paste(ov, (0, 0), ov)

def vignette(base, strength=0.35, color=(0, 0, 0)):
    q = 4
    m = Image.new("L", (W // q, H // q), 0)
    d = ImageDraw.Draw(m)
    d.ellipse([int(-W * 0.30 / q), int(-H * 0.35 / q), int(W * 1.30 / q), int(H * 1.35 / q)], fill=255)
    m = m.filter(ImageFilter.GaussianBlur(60)).resize((W, H), Image.BILINEAR)
    inv = m.point(lambda p: int((255 - p) * strength))
    base.paste(Image.new("RGB", (W, H), color), (0, 0), inv)

def stars(base, n, seed, ymax=H, col=(255, 255, 255), tint=0.2):
    rng = random.Random(seed)
    d = ImageDraw.Draw(base)
    for _ in range(n):
        x, y = rng.uniform(0, W), rng.uniform(0, ymax)
        r = rng.choice([0.6, 0.8, 1.0, 1.3, 1.7])
        a = rng.randint(50, 210)
        c = col if rng.random() > tint else (168, 196, 255)
        d.ellipse([x - r, y - r, x + r, y + r],
                  fill=tuple(int(v * a / 255) for v in c))

def bake_text(base, xy, s, fkey, px, fill, anchor="la", glow=None, glow_r=16, tracking=0,
              stroke=0, stroke_fill=None, shadow=None):
    """Draw text onto RGB base; glow = (r,g,b) halo; shadow = (dx,dy,rgba)."""
    f = font(fkey, px)

    def draw_one(d, p):
        if tracking > 0:
            widths = [d.textlength(ch, font=f) for ch in s]
            total = sum(widths) + tracking * (len(s) - 1)
            x = p[0] - total / 2 if anchor[0] == "m" else (p[0] - total if anchor[0] == "r" else p[0])
            for ch, wd in zip(s, widths):
                d.text((x, p[1]), ch, font=f, fill=fill, anchor="l" + anchor[1],
                       stroke_width=stroke, stroke_fill=stroke_fill)
                x += wd + tracking
        else:
            d.text(p, s, font=f, fill=fill, anchor=anchor,
                   stroke_width=stroke, stroke_fill=stroke_fill)

    ov = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    draw_one(ImageDraw.Draw(ov), xy)
    if shadow:
        sx, sy, scol = shadow
        sh = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        draw_one(ImageDraw.Draw(sh), (xy[0] + sx, xy[1] + sy))
        base.paste(sh, (0, 0), sh)
    if glow:
        a = ov.split()[3].filter(ImageFilter.GaussianBlur(glow_r))
        g = Image.new("RGBA", (W, H), (*glow, 255))
        g.putalpha(a)
        base.paste(g, (0, 0), g)
    base.paste(ov, (0, 0), ov)

def bake_multicolor(base, cx, y, s, colors, fkey, px, tracking=0, stroke=0, stroke_fill=None, shadow=None):
    """Centered text with one color per character (cartoon style)."""
    f = font(fkey, px)
    tmp = ImageDraw.Draw(Image.new("RGB", (8, 8)))
    widths = [tmp.textlength(ch, font=f) for ch in s]
    total = sum(widths) + tracking * (len(s) - 1)

    def draw_one(d, dx, dy, fill_for):
        x = cx - total / 2
        for ch, wd, c in zip(s, widths, colors):
            d.text((x + dx, y + dy), ch, font=f, fill=fill_for(c), anchor="la",
                   stroke_width=stroke, stroke_fill=stroke_fill)
            x += wd + tracking

    ov = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    draw_one(ImageDraw.Draw(ov), 0, 0, lambda c: (*c, 255))
    if shadow:
        sx, sy, scol = shadow
        sh = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        draw_one(ImageDraw.Draw(sh), sx, sy, lambda c: scol)
        base.paste(sh, (0, 0), sh)
    base.paste(ov, (0, 0), ov)

def shape_overlay(w, h, radius, fill, outline=None, ow=2, ss=4):
    """Antialiased rounded-rect RGBA overlay."""
    ov = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    if fill is not None:
        fm = Image.new("L", (w * ss, h * ss), 0)
        ImageDraw.Draw(fm).rounded_rectangle([0, 0, w * ss - 1, h * ss - 1], radius=radius * ss, fill=255)
        fm = fm.resize((w, h), Image.LANCZOS)
        fc = Image.new("RGBA", (w, h), fill)
        fc.putalpha(fm.point(lambda p: p * fill[3] // 255))
        ov = Image.alpha_composite(ov, fc)
    if outline is not None:
        om = Image.new("L", (w * ss, h * ss), 0)
        ImageDraw.Draw(om).rounded_rectangle(
            [ow * ss // 2, ow * ss // 2, w * ss - 1 - ow * ss // 2, h * ss - 1 - ow * ss // 2],
            radius=radius * ss, outline=255, width=ow * ss)
        om = om.resize((w, h), Image.LANCZOS)
        oc = Image.new("RGBA", (w, h), outline)
        oc.putalpha(om.point(lambda p: p * outline[3] // 255))
        ov = Image.alpha_composite(ov, oc)
    return ov

def write_style(outdir, base_name, rad, fill, outline, ow=2):
    size = rad * 3
    src = shape_overlay(size, size, rad, fill, outline, ow)
    boxes = {
        "nw": (0, 0, rad, rad), "n": (rad, 0, 2 * rad, rad), "ne": (2 * rad, 0, 3 * rad, rad),
        "w": (0, rad, rad, 2 * rad), "c": (rad, rad, 2 * rad, 2 * rad), "e": (2 * rad, rad, 3 * rad, 2 * rad),
        "sw": (0, 2 * rad, rad, 3 * rad), "s": (rad, 2 * rad, 2 * rad, 3 * rad), "se": (2 * rad, 2 * rad, 3 * rad, 3 * rad),
    }
    for k, box in boxes.items():
        src.crop(box).save(os.path.join(outdir, f"{base_name}_{k}.png"))

def mkpf2(outdir, prefix, role, fkey, px):
    """Create pf2 and return the full registered font name ("family style size")."""
    family = f"{prefix}{role}"
    out = os.path.join(outdir, f"{prefix.lower()}_{role.lower()}_{px}.pf2")
    subprocess.run(
        ["grub-mkfont", "-s", str(px), "-n", family, "-o", out, RESOLVED[fkey]],
        check=True, capture_output=True)
    txt = subprocess.run(["strings", out], check=True, capture_output=True, text=True).stdout
    for line in txt.splitlines():
        if line.startswith(family + " "):
            return line.strip()
    raise RuntimeError(f"cannot read font name from {out}")

def hexcol(c):
    return "#%02x%02x%02x" % tuple(c[:3])

def grid_lines(d, horizon, cx, color, width=2):
    for i in range(-13, 14):
        f = i / 13 * 1.15
        d.line([(cx + f * 30, horizon), (cx + f * 2600, H)], fill=color, width=width)
    for j in range(1, 16):
        t = j / 15
        y = int(horizon + (H - horizon) * (t ** 2.6))
        d.line([(0, y), (W, y)], fill=color, width=width)

# ---------------------------------------------------------------- backgrounds

def bg_neongrid():
    base = vgrad([(0.0, (3, 5, 13)), (0.42, (5, 9, 26)), (0.665, (10, 16, 44)),
                  (0.675, (14, 22, 58)), (0.68, (6, 9, 24)), (1.0, (3, 5, 12))])
    base = radial_glow(base, 1750, 190, 640, 480, (140, 24, 105), 0.95)
    base = radial_glow(base, 240, 1290, 700, 460, (0, 72, 110), 0.95)
    base = radial_glow(base, 1280, HORIZON, 900, 300, (0, 52, 96), 0.6)
    # city skyline
    rng = random.Random(7)
    d = ImageDraw.Draw(base)
    glow = Image.new("RGB", (W, H), (0, 0, 0))
    gd = ImageDraw.Draw(glow)
    x = -30
    while x < W + 30:
        bw, bh = rng.randint(90, 240), rng.randint(70, 300)
        top = HORIZON - bh
        d.rectangle([x, top, x + bw, HORIZON], fill=(4, 6, 14))
        for wy in range(top + 8, HORIZON - 6, 14):
            for wx in range(x + 6, x + bw - 6, 12):
                r = rng.random()
                if r < 0.30:
                    c = (0, 190, 255) if r < 0.24 else (255, 70, 150)
                    b = rng.uniform(0.35, 1.0)
                    gd.rectangle([wx, wy, wx + 3, wy + 5], fill=tuple(int(v * b) for v in c))
        x += bw + rng.randint(6, 30)
    base = screen_layer(base, glow, 2)
    gl = Image.new("RGB", (W, H), (0, 0, 0))
    grid_lines(ImageDraw.Draw(gl), HORIZON, 1280, (0, 110, 145), 3)
    base = screen_layer(base, gl, 5)
    grid_lines(ImageDraw.Draw(base), HORIZON, 1280, (0, 175, 220), 2)
    scanlines(base, 16, 4)
    vignette(base, 0.34)
    return base

def bg_retrowave():
    base = vgrad([(0.0, (9, 2, 30)), (0.30, (40, 4, 58)), (0.50, (96, 8, 84)),
                  (0.62, (178, 22, 96)), (0.68, (255, 120, 60)), (0.682, (26, 8, 44)), (1.0, (8, 3, 20))])
    base = radial_glow(base, 300, 200, 500, 380, (90, 20, 120), 0.8)
    base = radial_glow(base, 2300, 1150, 520, 400, (150, 30, 90), 0.6)
    stars(base, 150, 3, ymax=430)
    # outrun sun
    cx, cy, r = 1280, 660, 290
    sun = Image.new("RGB", (W, H), (0, 0, 0))
    sd = ImageDraw.Draw(sun)
    c_top, c_bot = (255, 215, 94), (255, 46, 136)
    for y in range(cy - r, cy + r + 1):
        half = math.sqrt(max(0.0, r * r - (y - cy) ** 2))
        if half <= 0:
            continue
        t = (y - (cy - r)) / (2 * r)
        col = tuple(int(c_top[j] + (c_bot[j] - c_top[j]) * t) for j in range(3))
        sd.line([(cx - half, y), (cx + half, y)], fill=col)
    y, g = cy, 6
    while y < cy + r:
        sd.rectangle([cx - r - 8, y, cx + r + 8, y + g], fill=(0, 0, 0))
        y += g * 2 + int(g * 2.6)
        g += 5
    base.paste(sun, (0, 0), sun.convert("L"))
    base = radial_glow(base, cx, cy, 470, 470, (255, 70, 150), 0.5)
    # mountains
    def ridge(seed, amp, color, base_h=0.30):
        rng = random.Random(seed)
        pts = [(-20, HORIZON)]
        x = -20
        while x <= W + 20:
            pts.append((x, HORIZON - amp * (base_h + 0.7 * rng.random())))
            x += rng.randint(70, 140)
        pts.append((W + 20, HORIZON))
        ImageDraw.Draw(base).polygon(pts, fill=color)
    ridge(11, 150, (16, 3, 38))
    ridge(12, 90, (9, 2, 26), 0.2)
    # grid
    gl = Image.new("RGB", (W, H), (0, 0, 0))
    grid_lines(ImageDraw.Draw(gl), HORIZON, 1280, (200, 40, 130), 3)
    base = screen_layer(base, gl, 6)
    grid_lines(ImageDraw.Draw(base), HORIZON, 1280, (255, 130, 205), 2)
    scanlines(base, 18, 4)
    vignette(base, 0.36)
    return base

def bg_matrix():
    base = vgrad([(0.0, (0, 0, 0)), (1.0, (0, 2, 1))])
    base = radial_glow(base, 1280, 700, 900, 520, (0, 44, 16), 0.7)
    rng = random.Random(42)
    d = ImageDraw.Draw(base)
    f = font("stm", 22)
    ch_h = 28
    gap = 34
    cols = W // gap
    chars = "01ABCDEFabcdef<>[]{}#$%*+-=/?\\|"
    rows = H // ch_h
    for c in range(cols):
        x = c * gap + 5
        if rng.random() < 0.12:
            continue
        for stream in range(2):
            head = rng.randint(-6, rows + 4)
            trail = rng.randint(7, 30)
            dim = 0.55 if stream else 1.0
            for k in range(trail):
                row = head - k
                if row < 0 or row >= rows:
                    continue
                p = (1 - k / trail) ** 1.4 * dim
                if p <= 0.02:
                    continue
                col = (int(175 * p), int(255 * p), int(185 * p)) if k == 0 else (0, int(165 * p) + 8, int(42 * p))
                d.text((x, row * ch_h), rng.choice(chars), font=f, fill=col)
    scanlines(base, 26, 3)
    vignette(base, 0.45)
    return base

def bg_nebula():
    base = vgrad([(0.0, (4, 5, 10)), (1.0, (3, 4, 9))])
    q = 4
    lay = Image.new("RGB", (W // q, H // q), (0, 0, 0))
    d = ImageDraw.Draw(lay)
    for (x, y, rx, ry, col) in [
        (1500, 300, 560, 400, (13, 22, 74)),
        (430, 560, 500, 360, (8, 52, 58)),
        (1120, 930, 600, 400, (40, 14, 58)),
        (760, 170, 380, 260, (22, 16, 50)),
    ]:
        d.ellipse([(x - rx) / q, (y - ry) / q, (x + rx) / q, (y + ry) / q], fill=col)
    lay = lay.filter(ImageFilter.GaussianBlur(46)).resize((W, H), Image.BILINEAR)
    base = ImageChops.screen(base, lay)
    # faint ring
    ring = Image.new("RGB", (W, H), (0, 0, 0))
    ImageDraw.Draw(ring).ellipse([1560 - 380, 620 - 380, 1560 + 380, 620 + 380],
                                 outline=(46, 62, 92), width=3)
    base = screen_layer(base, ring, 1)
    stars(base, 460, 5, ymax=H)
    # a few flares
    rng = random.Random(9)
    d = ImageDraw.Draw(base)
    for _ in range(8):
        x, y = rng.uniform(100, W - 100), rng.uniform(80, H - 200)
        ln = rng.uniform(10, 26)
        c = rng.choice([(190, 210, 255), (255, 255, 255), (170, 220, 255)])
        d.line([(x - ln, y), (x + ln, y)], fill=c, width=1)
        d.line([(x, y - ln), (x, y + ln)], fill=c, width=1)
    vignette(base, 0.30)
    return base

# ------------------------------------------------- cartoon / minimal / blockterm bgs

def cloud(base, x, y, s):
    ov = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(ov)
    puffs = [(0, 0, 62, 40), (-58, 12, 44, 30), (60, 12, 46, 32), (-24, -26, 40, 32), (30, -22, 38, 30)]
    for (dx, dy, rx, ry) in puffs:
        d.ellipse([x + dx * s - rx * s, y + (dy + 10) * s - ry * s, x + dx * s + rx * s, y + (dy + 10) * s + ry * s],
                  fill=(168, 206, 236, 255))
    for (dx, dy, rx, ry) in puffs:
        d.ellipse([x + dx * s - rx * s, y + dy * s - ry * s, x + dx * s + rx * s, y + dy * s + ry * s],
                  fill=(255, 255, 255, 255))
    base.paste(ov, (0, 0), ov)

def sparkle(base, x, y, r, color=(255, 255, 255)):
    d = ImageDraw.Draw(base)
    k = 0.28 * r
    d.polygon([(x, y - r), (x + k, y - k), (x + r, y), (x + k, y + k),
               (x, y + r), (x - k, y + k), (x - r, y), (x - k, y - k)], fill=color)

def tree(base, x, y, s):
    d = ImageDraw.Draw(base)
    d.rounded_rectangle([x - 5 * s, y - 46 * s, x + 5 * s, y], radius=3 * s, fill=(124, 84, 56))
    for (dx, dy, r, c) in [(-18, -58, 26, (96, 172, 84)), (18, -58, 26, (96, 172, 84)),
                           (0, -76, 30, (118, 192, 98)), (0, -52, 26, (86, 158, 76))]:
        d.ellipse([x + (dx - r) * s, y + (dy - r) * s, x + (dx + r) * s, y + (dy + r) * s], fill=c)

def hill(base, base_y, amp, color, seed):
    rng = random.Random(seed)
    ph = rng.uniform(0, 6.28)
    f = rng.uniform(0.004, 0.007)
    pts = [(-20, H)]
    for x in range(-20, W + 21, 10):
        y = base_y + amp * math.sin(x * f + ph) + amp * 0.4 * math.sin(x * f * 2.7 + ph * 2)
        pts.append((x, y))
    pts.append((W + 20, H))
    ImageDraw.Draw(base).polygon(pts, fill=color)

def flower(base, x, y, petal=(255, 255, 255), r=6):
    d = ImageDraw.Draw(base)
    for i in range(5):
        a = math.pi * 2 * i / 5 - math.pi / 2
        d.ellipse([x + math.cos(a) * r - r * 0.75, y + math.sin(a) * r - r * 0.75,
                   x + math.cos(a) * r + r * 0.75, y + math.sin(a) * r + r * 0.75], fill=petal)
    d.ellipse([x - 3, y - 3, x + 3, y + 3], fill=(241, 196, 83))

def bamboo_stalk(base, x, top, bottom, w, base_color):
    d = ImageDraw.Draw(base)
    seg_h, y, i = 58, bottom, 0
    while y > top:
        h = min(seg_h, y - top)
        c = tuple(min(255, v + (7 if i % 2 else -5)) for v in base_color)
        d.rounded_rectangle([x - w / 2, y - h, x + w / 2, y], radius=w / 2, fill=c)
        if y - h > top:
            d.rounded_rectangle([x - w / 2 - 3, y - h - 3, x + w / 2 + 3, y - h + 1], radius=2, fill=(74, 132, 52))
        y -= h + 6
        i += 1

def bamboo_leaf(base, x, y, ang, ln, color):
    d = ImageDraw.Draw(base)
    dx, dy = math.cos(ang), math.sin(ang)
    px, py = -dy, dx
    wdt = ln * 0.15
    d.polygon([(x, y), (x + dx * ln * 0.5 + px * wdt, y + dy * ln * 0.5 + py * wdt),
               (x + dx * ln, y + dy * ln), (x + dx * ln * 0.5 - px * wdt, y + dy * ln * 0.5 - py * wdt)],
              fill=color)

def bamboo_cluster(base, cx, ground_y):
    for (ox, top, w, col) in [(-36, ground_y - 330, 15, (96, 164, 70)),
                              (2, ground_y - 395, 13, (112, 182, 82)),
                              (38, ground_y - 295, 11, (86, 150, 64))]:
        bamboo_stalk(base, cx + ox, top, ground_y, w, col)
        for i, (ang, ln, lc) in enumerate([(0.55, 52, (104, 176, 78)), (0.95, 44, (88, 154, 66)),
                                           (math.pi - 0.55, 52, (110, 184, 82)), (math.pi - 0.95, 44, (90, 156, 68))]):
            bamboo_leaf(base, cx + ox, top + 16 + i * 22, ang, ln - i * 3, lc)

def paw_print(base, x, y, s, color):
    d = ImageDraw.Draw(base)
    d.ellipse([x - 11 * s, y - 4 * s, x + 11 * s, y + 12 * s], fill=color)
    for tx, ty in [(-12, -10), (0, -14), (12, -10)]:
        d.ellipse([x + tx * s - 4.5 * s, y + ty * s - 5 * s, x + tx * s + 4.5 * s, y + ty * s + 5 * s], fill=color)

def butterfly(base, x, y, s, col):
    d = ImageDraw.Draw(base)
    d.ellipse([x - 14 * s, y - 10 * s, x - 2 * s, y + 6 * s], fill=col)
    d.ellipse([x + 2 * s, y - 10 * s, x + 14 * s, y + 6 * s], fill=col)
    d.line([(x, y - 8 * s), (x, y + 6 * s)], fill=(70, 60, 55), width=2)

def draw_panda(base, cx, cy):
    """Chibi panda, (cx, cy) = head center."""
    d = ImageDraw.Draw(base)
    ink = (62, 52, 48)
    w = 5
    d.ellipse([cx - 150, cy + 205, cx + 150, cy + 247], fill=(58, 118, 54))
    d.rounded_rectangle([cx - 96, cy + 40, cx + 96, cy + 218], radius=70,
                        fill=(255, 255, 255), outline=ink, width=w)
    d.ellipse([cx - 124, cy + 58, cx - 72, cy + 150], fill=(52, 48, 46), outline=ink, width=w)
    d.ellipse([cx + 72, cy + 58, cx + 124, cy + 150], fill=(52, 48, 46), outline=ink, width=w)
    d.ellipse([cx - 86, cy + 178, cx - 18, cy + 224], fill=(52, 48, 46), outline=ink, width=w)
    d.ellipse([cx + 18, cy + 178, cx + 86, cy + 224], fill=(52, 48, 46), outline=ink, width=w)
    d.ellipse([cx - 62, cy + 192, cx - 42, cy + 210], fill=(240, 236, 232))
    d.ellipse([cx + 42, cy + 192, cx + 62, cy + 210], fill=(240, 236, 232))
    d.ellipse([cx - 128, cy - 186, cx - 52, cy - 110], fill=(52, 48, 46), outline=ink, width=w)
    d.ellipse([cx + 52, cy - 186, cx + 128, cy - 110], fill=(52, 48, 46), outline=ink, width=w)
    d.rounded_rectangle([cx - 132, cy - 150, cx + 132, cy + 56], radius=92,
                        fill=(255, 255, 255), outline=ink, width=w)
    d.rounded_rectangle([cx - 84, cy - 58, cx - 24, cy + 22], radius=28, fill=(52, 48, 46))
    d.rounded_rectangle([cx + 24, cy - 58, cx + 84, cy + 22], radius=28, fill=(52, 48, 46))
    d.ellipse([cx - 66, cy - 38, cx - 42, cy - 14], fill=(255, 255, 255))
    d.ellipse([cx + 42, cy - 38, cx + 66, cy - 14], fill=(255, 255, 255))
    d.ellipse([cx - 60, cy - 33, cx - 46, cy - 19], fill=(25, 22, 20))
    d.ellipse([cx + 46, cy - 33, cx + 60, cy - 19], fill=(25, 22, 20))
    d.ellipse([cx - 59, cy - 32, cx - 55, cy - 28], fill=(255, 255, 255))
    d.ellipse([cx + 47, cy - 32, cx + 51, cy - 28], fill=(255, 255, 255))
    d.ellipse([cx - 13, cy + 8, cx + 13, cy + 26], fill=(40, 36, 34))
    d.arc([cx - 16, cy + 26, cx + 2, cy + 44], 20, 160, fill=ink, width=4)
    d.arc([cx - 2, cy + 26, cx + 16, cy + 44], 20, 160, fill=ink, width=4)
    d.ellipse([cx - 112, cy - 2, cx - 76, cy + 20], fill=(255, 176, 190))
    d.ellipse([cx + 76, cy - 2, cx + 112, cy + 20], fill=(255, 176, 190))

def bg_panda():
    base = vgrad([(0.0, (92, 178, 240)), (0.5, (150, 212, 250)), (1.0, (208, 240, 253))])
    base = radial_glow(base, 2160, 262, 340, 340, (255, 232, 150), 0.5)
    d = ImageDraw.Draw(base)
    scx, scy, sr = 2160, 262, 84
    for i in range(12):
        a = math.pi * 2 * i / 12 + 0.13
        ln = 44 if i % 2 == 0 else 30
        d.line([(scx + math.cos(a) * (sr + 14), scy + math.sin(a) * (sr + 14)),
                (scx + math.cos(a) * (sr + 14 + ln), scy + math.sin(a) * (sr + 14 + ln))],
               fill=(255, 202, 74), width=11)
    for r, c in [(84, (255, 214, 86)), (66, (255, 224, 120)), (46, (255, 233, 150))]:
        d.ellipse([scx - r, scy - r, scx + r, scy + r], fill=c)
    d.arc([scx - 36, scy - 26, scx - 14, scy - 6], 190, 350, fill=(172, 108, 20), width=5)
    d.arc([scx + 14, scy - 26, scx + 36, scy - 6], 190, 350, fill=(172, 108, 20), width=5)
    d.arc([scx - 24, scy + 6, scx + 24, scy + 42], 25, 155, fill=(172, 108, 20), width=6)
    for (x, y, s) in [(320, 185, 1.2), (820, 130, 0.8), (1240, 225, 1.0),
                      (1710, 150, 0.7), (500, 380, 0.6), (1050, 330, 0.5)]:
        cloud(base, x, y, s)
    for (x, y, r) in [(640, 245, 10), (1420, 185, 8), (1830, 335, 9), (240, 320, 7), (1560, 300, 6)]:
        sparkle(base, x, y, r, (255, 255, 255))
    hill(base, 940, 55, (176, 216, 152), 41)
    hill(base, 1005, 62, (136, 200, 112), 42)
    tree(base, 1560, 1015, 1.0)
    tree(base, 1660, 1032, 0.8)
    tree(base, 205, 1038, 0.9)
    tree(base, 2330, 1042, 0.75)
    hill(base, 1065, 58, (100, 178, 84), 44)
    hill(base, 1135, 50, (70, 152, 62), 45)
    rng = random.Random(77)
    for _ in range(12):
        x, y = rng.uniform(60, W - 60), rng.uniform(1170, 1330)
        if abs(x - 400) < 250 or abs(x - 645) < 100:
            continue
        flower(base, x, y, petal=(255, 255, 255) if rng.random() < 0.6 else (255, 176, 196),
               r=rng.uniform(5.5, 8))
    for (px, py, ps) in [(770, 1250, 1.0), (845, 1292, 1.0), (925, 1322, 1.0)]:
        paw_print(base, px, py, ps, (54, 122, 50))
    butterfly(base, 985, 1120, 1.0, (255, 150, 170))
    butterfly(base, 1520, 1165, 0.8, (255, 196, 120))
    bamboo_cluster(base, 645, 1330)
    draw_panda(base, 400, 1120)
    return base

def bg_clean():
    base = vgrad([(0.0, (248, 248, 250)), (1.0, (240, 241, 244))])
    # pastel aurora blobs
    q = 4
    lay = Image.new("RGBA", (W // q, H // q), (0, 0, 0, 0))
    d = ImageDraw.Draw(lay)
    for (x, y, rx, ry, col) in [
        (1720, 300, 520, 380, (188, 168, 255, 115)),
        (2180, 760, 430, 330, (255, 190, 160, 100)),
        (1450, 640, 300, 240, (170, 226, 205, 75)),
    ]:
        d.ellipse([(x - rx) // q, (y - ry) // q, (x + rx) // q, (y + ry) // q], fill=col)
    blob = lay.filter(ImageFilter.GaussianBlur(40)).resize((W, H), Image.BILINEAR)
    base.paste(blob, (0, 0), blob)
    d = ImageDraw.Draw(base)
    d.ellipse([2060 - 420, 470 - 420, 2060 + 420, 470 + 420], outline=(222, 224, 230), width=2)
    d.ellipse([2330 - 170, 250 - 170, 2330 + 170, 250 + 170], outline=(225, 227, 232), width=2)
    d.ellipse([2060 - 7, 50 - 7, 2060 + 7, 50 + 7], fill=(255, 92, 57))
    for (x, y) in [(760, 210), (980, 660)]:
        d.line([(x - 8, y), (x + 8, y)], fill=(208, 211, 218), width=2)
        d.line([(x, y - 8), (x, y + 8)], fill=(208, 211, 218), width=2)
    # two-tone title "minimal."
    f = font("dvl", 72)
    tr = 8
    widths = [d.textlength(c, font=f) for c in "minimal."]
    total = sum(widths) + tr * (len(widths) - 1)
    x = W // 2 - total / 2
    for i, c in enumerate("minimal."):
        col = (255, 92, 57) if c == "." else (36, 39, 46)
        d.text((x, 118), c, font=f, fill=col, anchor="la")
        x += widths[i] + tr
    d.text((W // 2, 262), "a clean & calm bootloader", font=font("plexm", 22),
           fill=(140, 146, 156), anchor="ma")
    # hairlines framing the menu
    d.line([(650, 404), (1910, 404)], fill=(218, 221, 227), width=2)
    d.line([(650, 404), (706, 404)], fill=(255, 92, 57), width=4)
    d.line([(650, 876), (1910, 876)], fill=(218, 221, 227), width=2)
    return base

def bg_blockterm():
    """opencode-style: hand-drawn blocky lowercase wordmark on pure black."""
    GLYPHS = {
        "m": ["##.##", "#.#.#", "#.#.#", "#.#.#", "#.#.#"],
        "a": [".###.", "....#", ".####", "#...#", ".####"],
        "n": ["####.", "#...#", "#...#", "#...#", "#...#"],
        "j": ["..#", "..#", "..#", "..#", "..#", "..#", "###"],
        "r": ["####", "#...", "#...", "#...", "#..."],
        "o": ["#####", "#...#", "#...#", "#...#", "#####"],
    }
    word = "manjaro"
    split_at = 3          # "man" gray | "jaro" white
    B = 26                # block size
    base = Image.new("RGB", (W, H), (5, 5, 5))
    d = ImageDraw.Draw(base)
    for gy in range(56, H, 56):
        for gx in range(56, W, 56):
            d.point((gx, gy), fill=(28, 28, 28))

    GRAY, WHITE, SHADOW = (132, 132, 132), (242, 242, 242), (30, 30, 30)
    total_units = sum(len(GLYPHS[c][0]) for c in word) + (len(word) - 1)
    x0 = W / 2 - total_units * B / 2
    y0 = 178
    for dx, dy, col_map in [
        (0.45, 0.45, {0: SHADOW, 1: SHADOW}),
        (0.0, 0.0, {0: GRAY, 1: WHITE}),
    ]:
        x = x0
        for idx, c in enumerate(word):
            g = GLYPHS[c]
            col = col_map[1] if idx >= split_at else col_map[0]
            for ry, row in enumerate(g):
                for rx, cell in enumerate(row):
                    if cell == "#":
                        bx = x + rx * B + dx * B
                        by = y0 + ry * B + dy * B
                        d.rectangle([bx, by, bx + B, by + B], fill=col)
            x += (len(g[0]) + 1) * B
    d.text((W // 2, 386), "// boot manager // v2.14", font=font("plexm", 22),
           fill=(112, 112, 112), anchor="ma")
    return base

# ---------------------------------------------------------------- themes

THEMES = [
    dict(
        key="neongrid", prefix="NG", label="NEONGRID 赛博朋克",
        desktop_color="#03050d",
        title="NEONGRID", title_px=62, title_font="rb", title_color=(236, 248, 255),
        title_glow=(0, 229, 255), title_glow_r=22, title_y=118, title_tracking=16,
        sub="// BOOT MANAGER //", sub_font="rm", sub_px=24, sub_color=(255, 96, 170),
        sub_glow=(255, 40, 120), sub_glow_r=10, sub_y=228, sub_tracking=8,
        corner_font="stm", corner_px=18, corner_color=(104, 138, 168),
        tl="NEONGRID OS // BOOT SEQUENCE v2.14", tr="CPU OK    MEM OK    GPU OK",
        bl="SECURE BOOT: OFF    MODE: UEFI", br="[ENTER] BOOT NOW",
        hint="ARROW KEYS: SELECT        ENTER: BOOT NOW", hint_px=20, hint_color=(84, 116, 144),
        footer_text="AUTOBOOT IN %d", footer_px=22, footer_color=(128, 244, 255),
        menu=dict(w=1260, top=430, h=420, item_px=30, item_pad=16, item_spacing=18,
                  panel_fill=(8, 14, 32, 170), panel_outline=(0, 229, 255, 80), panel_radius=14,
                  hl_fill=(0, 229, 255, 36), hl_outline=(80, 240, 255, 200), hl_radius=10,
                  item_color=(152, 178, 208), sel_color=(128, 244, 255)),
        fonts=[("Title", "rb", 62), ("Sub", "rm", 24), ("Item", "rsb", 30),
               ("Small", "stm", 18), ("Footer", "stm", 22)],
        item_font_role="Item",
        bg=bg_neongrid,
    ),
    dict(
        key="retrowave", prefix="RW", label="RETROWAVE 复古合成波",
        desktop_color="#0a0314",
        title="RETROWAVE", title_px=68, title_font="rb", title_color=(255, 244, 250),
        title_glow=(255, 70, 180), title_glow_r=24, title_y=112, title_tracking=12,
        sub="1 9 8 4   B O O T   S Y S T E M", sub_font="rm", sub_px=24, sub_color=(255, 208, 235),
        sub_glow=(255, 90, 190), sub_glow_r=10, sub_y=236, sub_tracking=0,
        corner_font="stm", corner_px=18, corner_color=(206, 142, 190),
        tl="SIDE A - NIGHT DRIVE", tr="STEREO // 88.4 MPH",
        bl="TAPE DECK READY", br="MODE: CRUISE",
        hint="ARROW KEYS: SELECT        ENTER: BOOT NOW", hint_px=20, hint_color=(190, 120, 170),
        footer_text="AUTOBOOT IN %d", footer_px=22, footer_color=(255, 150, 215),
        menu=dict(w=1260, top=430, h=420, item_px=30, item_pad=16, item_spacing=18,
                  panel_fill=(26, 6, 48, 185), panel_outline=(255, 110, 210, 90), panel_radius=14,
                  hl_fill=(255, 79, 216, 42), hl_outline=(255, 140, 225, 210), hl_radius=10,
                  item_color=(240, 196, 228), sel_color=(255, 236, 160)),
        fonts=[("Title", "rb", 68), ("Sub", "rm", 24), ("Item", "rsb", 30),
               ("Small", "stm", 18), ("Footer", "stm", 22)],
        item_font_role="Item",
        bg=bg_retrowave,
    ),
    dict(
        key="matrix", prefix="MX", label="MATRIX 黑客帝国",
        desktop_color="#000100",
        title="M A T R I X", title_px=58, title_font="stm", title_color=(186, 255, 196),
        title_glow=(0, 255, 110), title_glow_r=18, title_y=118, title_tracking=0,
        sub="boot sequence v5.3 // enter the grid", sub_font="stm", sub_px=24, sub_color=(110, 200, 130),
        sub_glow=None, sub_glow_r=0, sub_y=234, sub_tracking=0,
        corner_font="stm", corner_px=18, corner_color=(96, 176, 110),
        tl="WAKE UP, NEO...", tr="GRUB 2.14 // RED PILL MODE",
        bl="FOLLOW THE WHITE RABBIT", br="KERNEL: ZION",
        hint="ARROW KEYS: SELECT        ENTER: BOOT NOW", hint_px=20, hint_color=(70, 140, 85),
        footer_text="AUTOBOOT IN %d", footer_px=22, footer_color=(120, 255, 150),
        menu=dict(w=1260, top=430, h=420, item_px=30, item_pad=16, item_spacing=18,
                  panel_fill=(0, 16, 6, 195), panel_outline=(60, 255, 120, 90), panel_radius=14,
                  hl_fill=(60, 255, 120, 38), hl_outline=(120, 255, 160, 220), hl_radius=10,
                  item_color=(120, 205, 140), sel_color=(214, 255, 222)),
        fonts=[("Title", "stm", 58), ("Sub", "stm", 24), ("Item", "stm", 30),
               ("Small", "stm", 18), ("Footer", "stm", 22)],
        item_font_role="Item",
        bg=bg_matrix,
    ),
    dict(
        key="nebula", prefix="NB", label="NEBULA 极简深空",
        desktop_color="#04050a",
        title="deep space", title_px=54, title_font="dvl", title_color=(238, 242, 252),
        title_glow=(110, 160, 255), title_glow_r=28, title_y=126, title_tracking=10,
        sub="// boot manager //", sub_font="stm", sub_px=24, sub_color=(128, 190, 210),
        sub_glow=None, sub_glow_r=0, sub_y=238, sub_tracking=4,
        corner_font="stm", corner_px=18, corner_color=(118, 130, 148),
        tl="deep-space // bootloader", tr="telemetry: nominal",
        bl="signal acquired", br="[enter] boot now",
        hint="arrow keys: select        enter: boot now", hint_px=20, hint_color=(96, 106, 124),
        footer_text="AUTOBOOT IN %d", footer_px=22, footer_color=(160, 200, 220),
        menu=dict(w=1260, top=430, h=420, item_px=30, item_pad=16, item_spacing=18,
                  panel_fill=(10, 14, 22, 130), panel_outline=(140, 170, 210, 55), panel_radius=14,
                  hl_fill=(120, 180, 255, 30), hl_outline=(170, 210, 255, 150), hl_radius=10,
                  item_color=(150, 162, 180), sel_color=(244, 248, 255)),
        fonts=[("Title", "dvl", 54), ("Sub", "stm", 24), ("Item", "dv", 30),
               ("Small", "stm", 18), ("Footer", "stm", 22)],
        item_font_role="Item",
        bg=bg_nebula,
    ),
    dict(
        key="panda", prefix="PA", label="PANDA 卡通乐园",
        desktop_color="#bfe4fa",
        title="PANDA", title_px=66, title_font="snig_eb", title_color=(227, 76, 60),
        title_colors=[(227, 76, 60), (230, 126, 34), (57, 174, 96), (52, 152, 219), (155, 89, 182)],
        title_stroke=8, title_stroke_fill=(255, 255, 255), title_shadow=(5, 8, (40, 90, 130, 70)),
        title_glow=None, title_glow_r=0, title_y=104, title_tracking=10,
        sub="CUTE BOOT MANAGER // V2.14", sub_font="snig", sub_px=24, sub_color=(61, 106, 148),
        sub_glow=None, sub_glow_r=0, sub_y=232, sub_tracking=2,
        corner_font="stm", corner_px=18, corner_color=(61, 106, 148),
        corner_color_bottom=(255, 255, 255),
        tl="PANDA OS // BOOT SEQUENCE V2.14", tr="SUN: HAPPY   MEM: OK   GPU: OK",
        bl="BAMBOO: FRESH   MODE: UEFI", br="[ENTER] LET'S GO!",
        hint="ARROW KEYS: SELECT   |   ENTER: BOOT NOW", hint_px=20,
        hint_font="snig", hint_color=(48, 88, 126),
        footer_text="AUTOBOOT IN %d", footer_px=22, footer_color=(232, 89, 12),
        menu=dict(w=1260, top=430, h=420, item_px=30, item_pad=16, item_spacing=18,
                  panel_fill=(255, 255, 255, 190), panel_outline=(150, 200, 240, 170), panel_radius=18,
                  hl_fill=(255, 209, 102, 95), hl_outline=(232, 119, 34, 230), hl_radius=12,
                  item_color=(61, 90, 120), sel_color=(225, 90, 20)),
        fonts=[("Title", "snig_eb", 66), ("Sub", "snig", 24), ("Item", "snig", 30),
               ("Small", "stm", 18), ("Footer", "snig", 22)],
        item_font_role="Item",
        bg=bg_panda,
    ),
    dict(
        key="clean", prefix="CL", label="CLEAN 极简",
        desktop_color="#f5f6f8",
        no_bake_title=True,
        title="minimal.", title_px=72, title_font="dvl", title_color=(36, 39, 46),
        title_glow=None, title_glow_r=0, title_y=118, title_tracking=8,
        sub="a clean & calm bootloader", sub_font="plexm", sub_px=22, sub_color=(140, 146, 156),
        sub_glow=None, sub_glow_r=0, sub_y=262, sub_tracking=3,
        corner_font="plexm", corner_px=18, corner_color=(154, 161, 171),
        tl="MINIMAL OS // BOOTLOADER V2.14", tr="STATUS: CALM",
        bl="NOTHING EXTRA", br="[ENTER] BOOT",
        hint="ARROWS: SELECT   |   ENTER: BOOT", hint_px=20, hint_color=(154, 161, 171),
        hint_y=902, footer_y=948,
        footer_text="AUTOBOOT IN %d", footer_px=22, footer_color=(255, 92, 57),
        menu=dict(w=1260, top=430, h=420, item_px=30, item_pad=16, item_spacing=18,
                  panel_fill=(255, 255, 255, 95), panel_outline=None, panel_radius=16,
                  hl_fill=(228, 231, 236, 225), hl_outline=None, hl_radius=12,
                  item_color=(90, 98, 112), sel_color=(24, 27, 33)),
        fonts=[("Item", "dv", 30), ("Small", "stm", 18), ("Footer", "plexm", 22)],
        item_font_role="Item",
        bg=bg_clean,
    ),
    dict(
        key="blockterm", prefix="BT", label="BLOCKTERM 终端方块",
        desktop_color="#050505",
        no_bake_title=True,
        title="manjaro", title_px=84, title_font="plexm", title_color=(242, 242, 242),
        title_glow=None, title_glow_r=0, title_y=178, title_tracking=0,
        sub="// boot manager // v2.14", sub_font="plexm", sub_px=22, sub_color=(112, 112, 112),
        sub_glow=None, sub_glow_r=0, sub_y=386, sub_tracking=2,
        corner_font="plexm", corner_px=18, corner_color=(118, 118, 118),
        tl="$ blockterm // boot sequence v2.14", tr="mem ok | nvme ok | gpu ok",
        bl="$ _", br="[enter] boot now",
        hint="ARROWS: SELECT   |   ENTER: BOOT", hint_px=20, hint_color=(108, 108, 108),
        footer_text="AUTOBOOT IN %d", footer_px=22, footer_color=(255, 255, 255),
        menu=dict(w=1260, top=430, h=420, item_px=30, item_pad=16, item_spacing=18,
                  panel_fill=(5, 5, 5, 235), panel_outline=(255, 255, 255, 60), panel_radius=2,
                  hl_fill=(255, 255, 255, 36), hl_outline=(255, 255, 255, 110), hl_radius=2,
                  style_ow=1,
                  item_color=(150, 150, 150), sel_color=(255, 255, 255)),
        fonts=[("Item", "plexm", 30), ("Small", "plexm", 18), ("Footer", "plexm", 22)],
        item_font_role="Item",
        bg=bg_blockterm,
    ),
]

# ---------------------------------------------------------------- baking / theme.txt / preview

def bake_static(t, base):
    if not t.get("no_bake_title"):
        if t.get("title_colors"):
            bake_multicolor(base, W // 2, t["title_y"], t["title"], t["title_colors"],
                            t["title_font"], t["title_px"], tracking=t["title_tracking"],
                            stroke=t.get("title_stroke", 0),
                            stroke_fill=t.get("title_stroke_fill"),
                            shadow=t.get("title_shadow"))
        else:
            bake_text(base, (W // 2, t["title_y"]), t["title"], t["title_font"], t["title_px"],
                      t["title_color"], anchor="ma", glow=t["title_glow"], glow_r=t["title_glow_r"],
                      tracking=t["title_tracking"])
        bake_text(base, (W // 2, t["sub_y"]), t["sub"], t["sub_font"], t["sub_px"],
                  t["sub_color"], anchor="ma", glow=t["sub_glow"], glow_r=t["sub_glow_r"],
                  tracking=t["sub_tracking"])
    cf, cp = t["corner_font"], t["corner_px"]
    cc_top = tuple(list(t["corner_color"]) + [215])
    cc_bot = tuple(list(t.get("corner_color_bottom", t["corner_color"])) + [225])
    bake_text(base, (64, 52), t["tl"], cf, cp, cc_top, anchor="la")
    bake_text(base, (W - 64, 52), t["tr"], cf, cp, cc_top, anchor="ra")
    bake_text(base, (64, H - 96), t["bl"], cf, cp, cc_bot, anchor="la")
    bake_text(base, (W - 64, H - 96), t["br"], t.get("corner_br_font", cf),
              t.get("corner_br_px", cp), cc_bot, anchor="ra")
    hc = tuple(list(t["hint_color"]) + [210])
    bake_text(base, (W // 2, t.get("hint_y", 880)), t["hint"], t.get("hint_font", cf),
              t.get("hint_px", 20), hc, anchor="ma")

def write_theme_txt(t, outdir, fontnames):
    m = t["menu"]
    item_px = m["item_px"]
    item_font = fontnames[t["item_font_role"]]
    footer_font = fontnames["Footer"]
    small_font = fontnames["Small"]
    txt = f"""# {t['label']} — GRUB2 theme (generated)
# Designed for 2560x1440. Set: GRUB_GFXMODE=2560x1440,1920x1080,auto
desktop-image: "bg.png"
desktop-color: "{t['desktop_color']}"
terminal-font: "{small_font}"
title-text: ""

+ boot_menu {{
  left = {W // 2 - m['w'] // 2}
  top = {m['top']}
  width = {m['w']}
  height = {m['h']}
  menu_pixmap_style = "panel_*.png"
  item_font = "{item_font}"
  item_color = "{hexcol(m['item_color'])}"
  selected_item_color = "{hexcol(m['sel_color'])}"
  item_height = {item_px + 2 * m['item_pad']}
  item_padding = {m['item_pad']}
  item_spacing = {m['item_spacing']}
  selected_item_pixmap_style = "hl_*.png"
}}

+ label {{
  id = "__timeout__"
  text = "{t['footer_text']}"
  left = 0
  top = {t.get('footer_y', 924)}
  width = 100%
  align = center
  font = "{footer_font}"
  color = "{hexcol(t['footer_color'])}"
}}
"""
    with open(os.path.join(outdir, "theme.txt"), "w") as f:
        f.write(txt)

def render_preview(t, bg):
    img = bg.copy()
    m = t["menu"]
    x0 = W // 2 - m["w"] // 2
    y0 = m["top"]
    x1 = x0 + m["w"]
    y1 = y0 + m["h"]
    ov = shape_overlay(m["w"], m["h"], m["panel_radius"], m["panel_fill"], m["panel_outline"], 2)
    img.paste(ov, (x0, y0), ov)
    fkey = dict((r, k) for r, k, _ in t["fonts"])[t["item_font_role"]]
    fi = font(fkey, m["item_px"])
    d = ImageDraw.Draw(img)
    ih = m["item_px"] + 2 * m["item_pad"]
    y = y0 + m["item_pad"]
    for i, e in enumerate(ENTRIES):
        if i == 0:
            ov = shape_overlay(m["w"], ih, m["hl_radius"], m["hl_fill"], m["hl_outline"], 2)
            img.paste(ov, (x0, y), ov)
        col = m["sel_color"] if i == 0 else tuple(list(m["item_color"]) + [255])
        d.text((x0 + m["item_pad"], y + ih // 2), e, font=fi, fill=col, anchor="lm")
        y += ih + m["item_spacing"]
    ffkey = dict((r, k) for r, k, _ in t["fonts"])["Footer"]
    d.text((W // 2, t.get("footer_y", 924)), t["footer_text"].replace("%d", "5"),
           font=font(ffkey, t["footer_px"]), fill=tuple(list(t["footer_color"]) + [255]), anchor="ma")
    return img

def main():
    only = sys.argv[1:] or None
    for t in THEMES:
        if only and t["key"] not in only:
            continue
        od = os.path.join(ROOT, t["key"])
        os.makedirs(od, exist_ok=True)
        print(f"[{t['key']}] background ...", flush=True)
        bg = t["bg"]()
        bake_static(t, bg)
        bg.save(os.path.join(od, "bg.png"))
        m = t["menu"]
        write_style(od, "panel", m["panel_radius"], m["panel_fill"], m["panel_outline"],
                    ow=m.get("style_ow", 2))
        write_style(od, "hl", m["hl_radius"], m["hl_fill"], m["hl_outline"],
                    ow=m.get("style_ow", 2))
        fontnames = {}
        for role, fkey, px in t["fonts"]:
            fontnames[role] = mkpf2(od, t["prefix"], role, fkey, px)
        write_theme_txt(t, od, fontnames)
        print(f"[{t['key']}] fonts: {fontnames}", flush=True)
        print(f"[{t['key']}] preview ...", flush=True)
        render_preview(t, bg).save(os.path.join(od, "preview.png"))
        print(f"[{t['key']}] OK -> {od}", flush=True)

if __name__ == "__main__":
    main()
