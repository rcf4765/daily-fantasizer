#!/usr/bin/env python3
"""Draw the home-screen icons for the league website (docs/icons/).

Run once, or again if the look changes: python3 make_app_icons.py
A leather football on a royal-to-Honolulu-blue sunburst, with a yellow "DF" banner.
Everything important sits inside the middle ~80% so Android's masks don't crop it.
"""
import math
import pathlib

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

ROOT = pathlib.Path(__file__).resolve().parent
OUT = ROOT / "docs" / "icons"
FONT = "/usr/share/fonts/opentype/inter/InterDisplay-BlackItalic.otf"

S = 1024  # draw big, scale down
C = S / 2


def hexrgb(h):
    h = h.lstrip("#")
    return np.array([int(h[i:i + 2], 16) for i in (0, 2, 4)], dtype=float)


def background():
    y, x = np.mgrid[0:S, 0:S].astype(float)
    # diagonal royal blue -> Honolulu -> bright cyan
    t = np.clip((x + y) / (2 * S), 0, 1)[..., None]
    a, b, c = hexrgb("#1a2f9e"), hexrgb("#0076b6"), hexrgb("#14b8e6")
    rgb = np.where(t < 0.5, a + (b - a) * (t / 0.5), b + (c - b) * ((t - 0.5) / 0.5))
    # soft glow behind the ball
    r = np.hypot(x - C, y - C * 0.92) / S
    rgb += (np.clip(0.55 - r, 0, None) / 0.55)[..., None] * 70
    im = Image.fromarray(np.clip(rgb, 0, 255).astype("uint8"), "RGB").convert("RGBA")

    # sunburst rays
    rays = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    d = ImageDraw.Draw(rays)
    n = 16
    for i in range(n):
        a0 = (i * 2) * math.pi / (2 * n)
        a1 = (i * 2 + 1) * math.pi / (2 * n) * 1.0
        a0, a1 = i * 2 * math.pi / n, (i + 0.5) * 2 * math.pi / n
        pts = [(C, C * 0.92)] + [(C + 900 * math.cos(a), C * 0.92 + 900 * math.sin(a)) for a in (a0, a1)]
        d.polygon(pts, fill=(255, 255, 255, 26))
    return Image.alpha_composite(im, rays)


def football(w=640, h=380):
    """A lens-shaped leather ball, laces and white end stripes, on a transparent layer."""
    L = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    y, x = np.mgrid[0:h, 0:w].astype(float)
    # lens = intersection of two big circles
    half_w, half_h = w / 2, h / 2
    R = (half_w ** 2 + half_h ** 2) / (2 * half_h)
    inside = (np.hypot(x - half_w, y - (half_h - R + h / 2)) <= R) & (np.hypot(x - half_w, y - (half_h + R - h / 2)) <= R)
    # leather shading: lighter top-left, darker bottom-right
    shade = 1 - ((y / h) * 0.55 + np.abs(x - half_w) / half_w * 0.35)
    dark, light = hexrgb("#6b2f12"), hexrgb("#c46a2c")
    rgb = dark + (light - dark) * np.clip(shade, 0, 1)[..., None]
    alpha = inside.astype(float) * 255
    arr = np.dstack([rgb, alpha]).astype("uint8")
    L = Image.fromarray(arr, "RGBA")
    d = ImageDraw.Draw(L)
    mask = Image.fromarray(inside.astype("uint8") * 255)

    # white stripes near each end, clipped to the ball
    stripes = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    sd = ImageDraw.Draw(stripes)
    for cx in (w * 0.19, w * 0.81):
        sd.rectangle([cx - 14, 0, cx + 14, h], fill=(250, 248, 240, 255))
    clipped = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    clipped.paste(stripes, (0, 0), Image.fromarray((np.array(stripes)[..., 3] > 0).astype("uint8") * 255).point(lambda v: v) )
    clipped.putalpha(Image.fromarray(np.minimum(np.array(clipped)[..., 3], np.array(mask))))
    L = Image.alpha_composite(L, clipped)
    d = ImageDraw.Draw(L)

    # laces
    white = (250, 248, 240, 255)
    d.rounded_rectangle([w * 0.30, h * 0.47 - 9, w * 0.70, h * 0.47 + 9], radius=9, fill=white)
    for i in range(7):
        lx = w * 0.33 + i * (w * 0.34 / 6)
        d.rounded_rectangle([lx - 8, h * 0.47 - 40, lx + 8, h * 0.47 + 40], radius=8, fill=white)

    # glossy highlight
    hl = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    ImageDraw.Draw(hl).ellipse([w * 0.22, h * 0.10, w * 0.62, h * 0.32], fill=(255, 255, 255, 60))
    hl = hl.filter(ImageFilter.GaussianBlur(14))
    hl.putalpha(Image.fromarray(np.minimum(np.array(hl)[..., 3], np.array(mask))))
    return Image.alpha_composite(L, hl)


def draw():
    im = background()

    ball = football().rotate(28, resample=Image.BICUBIC, expand=True)
    bx, by = int(C - ball.width / 2), int(C * 0.86 - ball.height / 2)
    shadow = Image.new("RGBA", im.size, (0, 0, 0, 0))
    shadow.paste((10, 20, 60, 140), (bx + 18, by + 30), ball)
    im = Image.alpha_composite(im, shadow.filter(ImageFilter.GaussianBlur(22)))
    im.alpha_composite(ball, (bx, by))

    # yellow banner with "DF"
    banner = Image.new("RGBA", im.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(banner)
    top, bot = 660, 850
    left, right = 190, S - 190
    d.polygon([(left + 26, top), (right + 26, top), (right - 26, bot), (left - 26, bot)], fill=(10, 20, 60, 120))
    sh = banner.filter(ImageFilter.GaussianBlur(14))
    im = Image.alpha_composite(im, sh.transform(sh.size, Image.AFFINE, (1, 0, -6, 0, 1, -14)))
    d2 = ImageDraw.Draw(im)
    d2.polygon([(left + 26, top), (right + 26, top), (right - 26, bot), (left - 26, bot)], fill="#ffd23f")
    d2.polygon([(left + 26, top), (right + 26, top), (right + 20, top + 14), (left + 20, top + 14)], fill="#fff1a8")
    font = ImageFont.truetype(FONT, 168)
    box = d2.textbbox((0, 0), "DF", font=font)
    tw, th = box[2] - box[0], box[3] - box[1]
    tx, ty = C - tw / 2 - box[0], (top + bot) / 2 - th / 2 - box[1]
    d2.text((tx + 6, ty + 6), "DF", font=font, fill="#e0a800")
    d2.text((tx, ty), "DF", font=font, fill="#14215e")
    return im.convert("RGB")


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    big = draw()
    for size, name in [(512, "icon-512.png"), (192, "icon-192.png"), (180, "apple-touch-icon.png"), (32, "favicon-32.png")]:
        big.resize((size, size), Image.LANCZOS).save(OUT / name, optimize=True)
    print("icons written to", OUT)


if __name__ == "__main__":
    main()
