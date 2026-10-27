"""Bean mascot drafts v2: kidney-shaped bean body, seam, sprout leaf, all 10 characters.

Usage (from the repo root): python tools/sprites/beans.py
Writes docs/art/characters_beans.png (preview sheet with names) and docs/art/beans.json (pixel data).
"""

import json
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from px import PX, dark, hx, light  # noqa: E402
from variants import outline_sel  # noqa: E402

ROOT = HERE.parents[1]
INK = "#4a3358"
W, H = 16, 18
LEAF = "#7fd16a"


def bean(p, c, flip=False):
    """Kidney-shaped bean: tall ellipse with a notch on one side, top-left light, bottom-right shade."""
    cx, cy, rx, ry = 8.0, 10.0, 5.4, 6.6
    nx = cx + (rx + 0.6) * (1 if flip else -1)
    for y in range(p.h):
        for x in range(p.w):
            u, v = (x - cx) / rx, (y - cy) / ry
            if u * u + v * v > 1 or (x - nx) ** 2 + (y - (cy + 1.5)) ** 2 < 7.5:
                continue
            t = u + v
            p.g[y][x] = light(c, 0.35) if t < -0.8 else dark(c, 0.2) if t > 0.75 else c
    # Seam ("Nabel") along the notch: a short light curve, the bean's signature.
    sx = 4 if not flip else 11
    for y, dx in ((9, 1), (10, 0), (11, 0), (12, 1)):
        p.set(sx + (dx if not flip else -dx), y, light(c, 0.55))


def face(p, y=8, x1=6, x2=10):
    for x in (x1, x2):
        p.set(x, y, "#ffffff")
        p.set(x, y + 1, INK)
        p.set(x + 1, y, INK)
        p.set(x + 1, y + 1, INK)
    p.set(x1 - 1, y + 2, "#ff9fc0")
    p.set(x2 + 2, y + 2, "#ff9fc0")
    p.pts([(8, y + 3), (9, y + 3)], dark(INK, 0))


def feet(p, c):
    p.rect(5, 16, 6, 17, c)
    p.rect(10, 16, 11, 17, c)


def sprout(p, x=8, y=3):
    p.set(x, y, "#5aa05a")
    p.set(x, y - 1, "#5aa05a")
    p.pts([(x + 1, y - 2), (x + 2, y - 2), (x + 1, y - 1)], LEAF)


def finish(p):
    outline_sel(p, 0.55)
    return p


# ---------------------------------------------------------------------------- characters


def fenn():  # ranger
    p = PX(W, H)
    feet(p, "#8a5a30")
    bean(p, "#8fd47a")
    p.ell(8, 5.2, 5.6, 2.4, "#3f8a3f")
    p.pts([(12, 3), (13, 2), (14, 2)], "#ff8fb8")
    p.rect(4, 13, 12, 13, "#8a5a30")
    p.set(8, 13, "#ffd45e")
    for x, y in [(14, 8), (15, 9), (15, 10), (15, 11), (15, 12), (14, 13)]:
        p.set(x, y, "#8a5a30")
    p.line(14, 8, 14, 13, "#ffffff")
    finish(p)
    face(p)
    return p


def mira():  # pyro
    p = PX(W, H)
    feet(p, "#c66f2d")
    bean(p, "#ffab6e")
    p.poly([(8, 0.5), (10.5, 4.5), (5.5, 4.5)], "#ff7a5a")
    p.poly([(8, 2.2), (9.4, 4.6), (6.6, 4.6)], "#ffd45e")
    p.rect(4, 13, 12, 13, "#ffd45e")
    p.ell(14, 11, 1.7, 1.7, "#ff8f3a")
    p.ell(14, 11, 0.9, 0.9, "#fff7a8", False)
    finish(p)
    face(p)
    return p


def kaz():  # rogue
    p = PX(W, H)
    feet(p, "#4b3a7a")
    bean(p, "#9a82d8")
    p.rect(4, 7, 12, 8, "#4b3a7a")
    p.pts([(13, 7), (14, 6), (14, 8)], "#4b3a7a")
    p.rect(14, 10, 14, 13, "#d0d8e8")
    p.set(14, 14, "#8a5a30")
    p.rect(1, 11, 1, 14, "#d0d8e8")
    p.set(1, 15, "#8a5a30")
    finish(p)
    face(p)
    sprout(p)
    return p


def brun():  # guardian
    p = PX(W, H)
    feet(p, "#5a6a8a")
    bean(p, "#c4b08a", flip=True)
    p.ell(8, 5.5, 5.8, 3.0, "#b9c2d4")
    p.rect(4, 6, 12, 7, "#7d8cac")
    p.poly([(8, 1), (9.5, 2.5), (6.5, 2.5)], "#ff8fb8")
    p.ell(2.6, 12, 2.4, 3.2, "#ffd45e")
    p.ell(2.6, 12, 1.0, 1.6, "#ff8fb8", False)
    finish(p)
    face(p, y=9)
    return p


def ysa():  # cryo
    p = PX(W, H)
    feet(p, "#6a9ad0")
    bean(p, "#bfe0ff")
    p.poly([(8, 1), (9.8, 3.4), (8, 5), (6.2, 3.4)], "#7fd6ff")
    p.set(7, 3, "#ffffff")
    p.line(14, 6, 14, 16, "#9fb8d8")
    p.poly([(14, 2.5), (15.6, 4.4), (14, 6.2), (12.4, 4.4)], "#7fd6ff")
    p.pts([(8, 13), (7, 14), (9, 14), (8, 15)], "#ffffff")
    finish(p)
    face(p)
    return p


def thorn():  # summoner
    p = PX(W, H)
    feet(p, "#2f6a5a")
    bean(p, "#7cc9a8")
    p.ell(8, 5.4, 5.8, 3.0, "#3d7f6e")
    p.pts([(3, 6), (2, 7), (13, 6), (14, 7)], "#3d7f6e")
    p.ell(14, 12, 1.6, 2.1, "#eafff6")
    p.set(14, 14, "#eafff6")
    finish(p)
    face(p, y=9)
    p.pts([(13, 11), (15, 11)], INK)
    return p


def vex():  # storm
    p = PX(W, H)
    feet(p, "#4a62c0")
    bean(p, "#8ea8ff")
    p.pts([(5, 3), (6, 2), (7, 3), (8, 1), (9, 3), (10, 2), (11, 3)], "#ffe45c")
    p.rect(5, 4, 11, 4, "#ffe45c")
    p.pts([(15, 8), (14, 9), (13, 10), (14, 10), (15, 10), (14, 11), (13, 12)], "#fff7a8")
    finish(p)
    face(p)
    return p


def orm():  # bomber
    p = PX(W, H)
    feet(p, "#8a5a30")
    bean(p, "#e0b07a")
    p.rect(4, 6, 12, 6, "#8a5a30")
    p.ell(6, 6.5, 1.4, 1.2, "#7fd6ff", False)
    p.ell(10, 6.5, 1.4, 1.2, "#7fd6ff", False)
    p.ell(13.5, 13, 2.2, 2.2, "#5a5a6a")
    p.line(14, 10.5, 15, 9, "#c9a46a")
    p.set(15, 8, "#ffd45e")
    finish(p)
    face(p, y=9)
    sprout(p, y=4)
    return p


def lilu():  # venom
    p = PX(W, H)
    feet(p, "#5a8a3a")
    bean(p, "#c8e68a", flip=True)
    p.ell(8, 4.4, 6.0, 2.4, "#c070d0")
    p.pts([(5, 3), (9, 2), (11, 4)], "#f2d8ff")
    p.rect(1, 11, 3, 14, "#a8ff9a")
    p.rect(2, 10, 2, 10, "#d0d8e8")
    finish(p)
    face(p)
    return p


def aya():  # sniper
    p = PX(W, H)
    feet(p, "#8a5a30")
    bean(p, "#e6d6a6")
    p.ell(8, 4.4, 7.6, 1.2, "#f5d58a")
    p.ell(8, 3.8, 4.2, 2.2, "#f5d58a")
    p.rect(4, 4, 12, 4, "#ff8fb8")
    p.line(0, 13, 15, 12, "#6a6a7a")
    p.rect(0, 13, 2, 14, "#8a5a30")
    finish(p)
    face(p, y=8)
    return p


CAST = [
    ("ranger", fenn),
    ("pyro", mira),
    ("rogue", kaz),
    ("guardian", brun),
    ("cryo", ysa),
    ("summoner", thorn),
    ("storm", vex),
    ("bomber", orm),
    ("venom", lilu),
    ("sniper", aya),
]


def main():
    os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
    import pygame

    chars = {c["id"]: c for c in json.loads((ROOT / "data" / "characters.json").read_text(encoding="utf-8"))}
    pygame.init()
    scale, cols = 7, 5
    cell_w, cell_h = 150, H * scale + 60
    sheet = pygame.Surface((cols * cell_w, 2 * cell_h))
    sheet.fill(hx("#a6dd82"))
    name_font, title_font = pygame.font.Font(None, 26), pygame.font.Font(None, 18)
    export = {}
    for i, (cid, fn) in enumerate(CAST):
        p = fn()
        export[cid] = p.export()
        ox = (i % cols) * cell_w + (cell_w - W * scale) // 2
        oy = (i // cols) * cell_h + 10
        for y, row in enumerate(p.g):
            for x, c in enumerate(row):
                if c:
                    sheet.fill(hx(c), (ox + x * scale, oy + y * scale, scale, scale))
        cx = (i % cols) * cell_w + cell_w // 2
        for text, font, y in (
            (chars[cid]["name"], name_font, oy + H * scale + 6),
            (chars[cid]["title"], title_font, oy + H * scale + 28),
        ):
            img = font.render(text, True, hx(INK))
            sheet.blit(img, (cx - img.get_width() // 2, y))
    out = ROOT / "docs" / "art"
    pygame.image.save(sheet, str(out / "characters_beans.png"))
    (out / "beans.json").write_text(json.dumps(export, indent=1) + "\n", encoding="utf-8")
    print("wrote", out / "characters_beans.png")


if __name__ == "__main__":
    main()
