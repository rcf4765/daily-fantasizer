#!/usr/bin/env python3
"""Draw the home-screen icons for the league website (docs/icons/).

Run once, or again if the look changes: python3 make_app_icons.py
A newspaper front page: Honolulu-blue masthead band, "DF" in ink, column rules.
Everything sits inside the middle 80% so Android's round/squircle masks don't crop it.
"""
import pathlib
from PIL import Image, ImageDraw, ImageFont

ROOT = pathlib.Path(__file__).resolve().parent
OUT = ROOT / "docs" / "icons"
FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSerif-Bold.ttf"

PAPER = "#f4f5f0"
INK = "#151a24"
BLUE = "#0076b6"
YELLOW = "#f2c230"
RULE = "#9aa1a8"

S = 1024  # draw big, scale down


def draw():
    im = Image.new("RGB", (S, S), PAPER)
    d = ImageDraw.Draw(im)
    # masthead band
    d.rectangle([0, 0, S, 300], fill=BLUE)
    d.rectangle([0, 300, S, 322], fill=YELLOW)
    # "DF" centered in the paper area
    font = ImageFont.truetype(FONT, 400)
    box = d.textbbox((0, 0), "DF", font=font)
    w, h = box[2] - box[0], box[3] - box[1]
    x = (S - w) / 2 - box[0]
    y = 360 - box[1]
    d.text((x, y), "DF", font=font, fill=INK)
    # double rule under the letters, then three columns of "text" lines
    d.rectangle([150, 795, S - 150, 805], fill=INK)
    d.rectangle([150, 815, S - 150, 819], fill=INK)
    col_w = (S - 300 - 2 * 30) / 3
    for c in range(3):
        x0 = 150 + c * (col_w + 30)
        for r in range(3):
            y0 = 845 + r * 30
            d.rectangle([x0, y0, x0 + col_w, y0 + 12], fill=RULE)
    # masthead rule lines (a hint of the nameplate) inside the safe zone
    d.rectangle([150, 120, S - 150, 136], fill=PAPER)
    d.rectangle([250, 170, S - 250, 182], fill=PAPER)
    return im


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    big = draw()
    for size, name in [(512, "icon-512.png"), (192, "icon-192.png"), (180, "apple-touch-icon.png"), (32, "favicon-32.png")]:
        big.resize((size, size), Image.LANCZOS).save(OUT / name, optimize=True)
    print("icons written to", OUT)


if __name__ == "__main__":
    main()
