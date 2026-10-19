#!/usr/bin/env python3
"""Draw the home-screen icons for the league website (docs/icons/).

Run once, or again if the look changes: python3 make_app_icons.py
"Dreaming of football" (picked 2026-10-19): a football glowing like the moon in a starry
navy-to-blue night sky, "zzz", and a navy MEN FANTASIZING banner over THE DAILY.
"""
import math
import pathlib
import random

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

ROOT = pathlib.Path(__file__).resolve().parent
OUT = ROOT / "docs" / "icons"
GY = "/usr/share/texmf/fonts/opentype/public/tex-gyre/"
SERIF = GY + "texgyrebonum-bold.otf"  # TeX Gyre Bonum Bold
SANS = "/usr/share/fonts/opentype/inter/InterDisplay-BlackItalic.otf"

NAVY, CREAM, YEL = "#0b1433", "#f5efe0", "#ffcf3a"
S = 1024  # draw big, scale down
C = S / 2


def hx(h):
    h = h.lstrip("#")
    return np.array([int(h[i:i + 2], 16) for i in (0, 2, 4)], float)


def vgrad(a, b):
    t = np.linspace(0, 1, S)[:, None, None] * np.ones((1, S, 1))
    return Image.fromarray((hx(a) + (hx(b) - hx(a)) * t).astype("uint8")).convert("RGBA")


def ct(d, text, font, cy, fill, cx=C):
    b = d.textbbox((0, 0), text, font=font)
    d.text((cx - (b[2] - b[0]) / 2 - b[0], cy - (b[3] - b[1]) / 2 - b[1]), text, font=font, fill=fill)


def star(d, x, y, r, fill):
    pts = []
    for i in range(10):
        a = -math.pi / 2 + i * math.pi / 5
        rr = r if i % 2 == 0 else r * 0.42
        pts.append((x + rr * math.cos(a), y + rr * math.sin(a)))
    d.polygon(pts, fill=fill)


def football(w, h, angle):
    """Leather ball with white end stripes and laces, rotated, on a transparent layer."""
    y, x = np.mgrid[0:h, 0:w].astype(float)
    hw, hh = w / 2, h / 2
    R = (hw * hw + hh * hh) / (2 * hh)
    inside = (np.hypot(x - hw, y - (hh - R + hh)) <= R) & (np.hypot(x - hw, y - (hh + R - hh)) <= R)
    shade = 1 - ((y / h) * 0.5 + np.abs(x - hw) / hw * 0.3)
    rgb = hx("#5e2a10") + (hx("#b8642a") - hx("#5e2a10")) * np.clip(shade, 0, 1)[..., None]
    L = Image.fromarray(np.dstack([rgb, inside * 255.0]).astype("uint8"), "RGBA")
    mask = Image.fromarray(inside.astype("uint8") * 255)
    st = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    sd = ImageDraw.Draw(st)
    for cx in (w * 0.2, w * 0.8):
        sd.rectangle([cx - w * 0.022, 0, cx + w * 0.022, h], fill=(250, 246, 236, 255))
    st.putalpha(Image.fromarray(np.minimum(np.array(st)[..., 3], np.array(mask))))
    L = Image.alpha_composite(L, st)
    d = ImageDraw.Draw(L)
    wh, t = (250, 246, 236, 255), h * 0.03
    d.rounded_rectangle([w * 0.32, h * 0.46 - t, w * 0.68, h * 0.46 + t], radius=t, fill=wh)
    for i in range(6):
        lx = w * 0.35 + i * (w * 0.30 / 5)
        d.rounded_rectangle([lx - t, h * 0.46 - h * 0.1, lx + t, h * 0.46 + h * 0.1], radius=t, fill=wh)
    return L.rotate(angle, resample=Image.BICUBIC, expand=True)


def draw():
    im = vgrad(NAVY, "#0a5fa8")
    d = ImageDraw.Draw(im)
    rnd = random.Random(7)
    for _ in range(40):
        x, y, r = rnd.randint(60, S - 60), rnd.randint(60, 640), rnd.choice([3, 4, 5, 6])
        d.ellipse([x - r, y - r, x + r, y + r], fill=(255, 255, 255, 200))
    for x, y, r in [(190, 190, 26), (820, 520, 20), (260, 560, 16)]:
        star(d, x, y, r, YEL)

    # moon glow, then the ball with a soft shadow
    glow = Image.new("RGBA", im.size, (0, 0, 0, 0))
    ImageDraw.Draw(glow).ellipse([260, 160, 820, 620], fill=(255, 210, 90, 70))
    im = Image.alpha_composite(im, glow.filter(ImageFilter.GaussianBlur(60)))
    ball = football(560, 330, -28)
    bx, by = int(540 - ball.width / 2), int(400 - ball.height / 2)
    sh = Image.new("RGBA", im.size, (0, 0, 0, 0))
    sh.paste((5, 12, 40, 120), (bx + 10, by + 16), ball)
    im = Image.alpha_composite(im, sh.filter(ImageFilter.GaussianBlur(18)))
    im.alpha_composite(ball, (bx, by))

    d = ImageDraw.Draw(im)
    for x, y, sz in [(760, 190, 70), (830, 130, 54), (885, 85, 40)]:
        ct(d, "z", ImageFont.truetype(SANS, sz), y, CREAM, cx=x)

    top, bot = 740, 880
    d.polygon([(120, top), (S - 120, top), (S - 140, bot), (140, bot)], fill=NAVY)
    d.rectangle([120, top, S - 120, top + 10], fill=YEL)
    d.rectangle([140, bot - 10, S - 140, bot], fill=YEL)
    ct(d, "MEN FANTASIZING", ImageFont.truetype(SERIF, 70), (top + bot) / 2, YEL)
    ct(d, "THE DAILY", ImageFont.truetype(SERIF, 50), 940, CREAM)
    return im.convert("RGB")


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    big = draw()
    for size, name in [(512, "icon-512.png"), (192, "icon-192.png"), (180, "apple-touch-icon.png"), (32, "favicon-32.png")]:
        big.resize((size, size), Image.LANCZOS).save(OUT / name, optimize=True)
    print("icons written to", OUT)


if __name__ == "__main__":
    main()
