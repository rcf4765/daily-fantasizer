#!/usr/bin/env python3
"""Draw the home-screen icons for the league website (docs/icons/).

Run once, or again if the look changes: python3 make_app_icons.py
"Blue masthead" (picked 2026-10-19): a navy nameplate bar reading THE DAILY over a gold
rule, a big cream serif "DF" on Honolulu blue, gold and cream rules, MEN FANTASIZING.
"""
import math
import pathlib

import numpy as np
from PIL import Image, ImageDraw, ImageFont

ROOT = pathlib.Path(__file__).resolve().parent
OUT = ROOT / "docs" / "icons"
SERIF = "/usr/share/texmf/fonts/opentype/public/tex-gyre/texgyrebonum-bold.otf"  # TeX Gyre Bonum Bold

NAVY, GOLD, CREAM = "#0b1433", "#e8b931", "#f5efe0"
S = 1024  # draw big, scale down
C = S / 2


def hx(h):
    h = h.lstrip("#")
    return np.array([int(h[i:i + 2], 16) for i in (0, 2, 4)], float)


def vertical_gradient(top, bottom):
    t = np.linspace(0, 1, S)[:, None, None] * np.ones((1, S, 1))
    rgb = hx(top) + (hx(bottom) - hx(top)) * t
    return Image.fromarray(rgb.astype("uint8"), "RGB")


def center_text(d, text, font, cy, fill, shadow=None):
    b = d.textbbox((0, 0), text, font=font)
    x = C - (b[2] - b[0]) / 2 - b[0]
    y = cy - (b[3] - b[1]) / 2 - b[1]
    if shadow:
        d.text((x + shadow[0], y + shadow[1]), text, font=font, fill=shadow[2])
    d.text((x, y), text, font=font, fill=fill)


def draw():
    im = vertical_gradient("#0a86c8", "#005f94")
    d = ImageDraw.Draw(im)
    d.rectangle([0, 0, S, 210], fill=NAVY)
    d.rectangle([0, 210, S, 232], fill=GOLD)
    center_text(d, "THE DAILY", ImageFont.truetype(SERIF, 64), 120, GOLD)
    center_text(d, "DF", ImageFont.truetype(SERIF, 470), 560, CREAM, shadow=(10, 12, "#082850"))
    d.rectangle([170, 800, S - 170, 810], fill=GOLD)
    d.rectangle([170, 826, S - 170, 830], fill=CREAM)
    center_text(d, "MEN FANTASIZING", ImageFont.truetype(SERIF, 54), 885, CREAM)
    return im


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    big = draw()
    for size, name in [(512, "icon-512.png"), (192, "icon-192.png"), (180, "apple-touch-icon.png"), (32, "favicon-32.png")]:
        big.resize((size, size), Image.LANCZOS).save(OUT / name, optimize=True)
    print("icons written to", OUT)


if __name__ == "__main__":
    main()
