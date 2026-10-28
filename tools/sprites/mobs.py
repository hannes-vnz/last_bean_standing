"""Enemy and boss sprites in the pastel bean style (own work) and the game's sprite export.

Usage (from the repo root): python tools/sprites/mobs.py
Writes assets/sprites/sprites.json (palette + pixel rows for every sprite the game draws)
and docs/art/mobs_preview.png. Sources: player beans from docs/art/beans.json, garden pests
and the three bed bosses drawn here (Paket F).
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


def eyes(p, y, x1, x2, angry=False):
    for x in (x1, x2):
        p.set(x, y, "#ffffff")
        p.set(x, y + 1, INK)
    if angry:  # slanted brows
        p.set(x1 - 1, y - 1, INK)
        p.set(x2 + 1, y - 1, INK)


# Paket F: garden pests and poisoned vegetables (the Schnitter's rot), pastel with dark outlines.
def slug():
    p = PX(16, 12)
    c = "#d9b36a"
    p.ell(8, 8, 7, 3.4, c)
    p.rect(1, 9, 14, 10, dark(c, 0.12))
    p.ell(12, 6, 3, 3, light(c, 0.15))
    p.pts([(13, 2), (13, 3), (11, 2), (11, 3)], dark(c, 0.3))  # feelers
    p.pts([(13, 1), (11, 1)], INK)
    for x in (4, 7):
        p.set(x, 7, light(c, 0.5))
    outline_sel(p, 0.55)
    p.set(13, 6, INK)
    p.set(11, 6, INK)
    return p


def aphid():
    p = PX(10, 9)
    c = "#9be27f"
    p.ell(5, 5, 3.6, 3, c)
    p.ell(4, 4, 1.2, 0.8, light(c, 0.5), False)
    p.pts([(1, 8), (3, 8), (6, 8), (8, 8)], dark(c, 0.4))  # legs
    p.pts([(2, 1), (8, 1)], dark(c, 0.4))  # feelers
    outline_sel(p, 0.55)
    p.set(4, 5, INK)
    p.set(6, 5, INK)
    return p


def snail():
    p = PX(20, 18)
    body, shell = "#e8c9a0", "#c98d6a"
    p.ell(10, 14, 8.5, 3, body)
    p.ell(9, 8, 6.5, 6, shell)
    for a, r in ((0, 4), (1, 2.4)):
        p.ell(9 + a * 0.5, 8 + a * 0.5, r, r * 0.9, dark(shell, 0.12 + 0.12 * a), False)
    p.set(9, 8, light(shell, 0.4))
    p.pts([(17, 9), (17, 10), (19, 8), (19, 9)], dark(body, 0.25))
    outline_sel(p, 0.55)
    eyes(p, 12, 15, 17)
    return p


def mold():
    p = PX(16, 16)
    cap = "#b7a6e0"
    p.rect(5, 9, 10, 14, "#f3eadb")  # stem
    p.ell(8, 6.5, 7, 4.2, cap)
    p.rect(1, 7, 14, 8, cap)
    for x, y in [(4, 4), (9, 3), (12, 6), (6, 7)]:
        p.set(x, y, "#d8ffb0")  # mould spots
    outline_sel(p, 0.55)
    eyes(p, 10, 6, 9, angry=True)
    return p


def potato_beetle():
    p = PX(14, 14)
    shell = "#ffd45e"
    p.ell(7, 8, 5, 5.2, shell)
    for x in (4, 7, 10):
        p.line(x, 4, x, 12, "#6b4a32")  # stripes
    p.ell(7, 3, 3, 2, "#e8823a")
    p.pts([(1, 6), (1, 9), (13, 6), (13, 9), (2, 12), (12, 12)], INK)
    outline_sel(p, 0.55)
    p.set(6, 3, INK)
    p.set(8, 3, INK)
    return p


def toxic_carrot():
    p = PX(14, 20)
    c = "#ff9a4a"
    p.poly([(3, 6), (11, 6), (7.5, 19)], c)
    for y in (9, 12, 15):
        p.line(5, y, 7, y, dark(c, 0.2))
    for x, top in ((5, 1), (7, 0), (9, 1)):
        p.line(x, top, 7, 5, "#7ed957")
    p.pts([(10, 9), (6, 14)], "#b6e05a")  # poison drips
    outline_sel(p, 0.55)
    eyes(p, 8, 5, 9, angry=True)
    return p


def spray_cucumber():
    p = PX(18, 12)
    c = "#6fbf5a"
    p.ell(8, 6, 7.5, 4.2, c)
    for x, y in [(4, 4), (8, 3), (12, 5), (6, 8), (11, 8)]:
        p.set(x, y, light(c, 0.45))
    p.rect(15, 4, 17, 7, "#b6e05a")  # nozzle
    outline_sel(p, 0.55)
    eyes(p, 5, 6, 9, angry=True)
    return p


def pest_tomato():
    p = PX(14, 14)
    c = "#ff6b6b"
    p.ell(7, 8, 6, 5.4, c)
    p.ell(4.5, 6, 1.6, 1.2, light(c, 0.5), False)
    p.pts([(5, 2), (7, 1), (9, 2), (6, 3), (8, 3)], "#7ed957")
    p.pts([(10, 10), (3, 11)], "#b6e05a")  # pesticide blotches
    outline_sel(p, 0.55)
    eyes(p, 8, 5, 9, angry=True)
    return p


def vole():
    p = PX(20, 16)
    fur = "#a58a7a"
    p.ell(9, 10, 8, 5, fur)
    p.ell(16, 8, 3.6, 3.2, light(fur, 0.1))
    p.ell(13, 4.5, 1.8, 1.6, "#ff9fc0")  # ear
    p.set(19, 8, "#ff8fb8")  # nose
    p.line(1, 13, 0, 15, dark(fur, 0.3))  # tail
    p.pts([(5, 15), (12, 15)], dark(fur, 0.35))
    outline_sel(p, 0.55)
    p.set(16, 7, INK)
    p.set(17, 10, "#ffffff")  # teeth
    return p


def spray_shroom():
    p = PX(16, 16)
    cap = "#c8f06a"
    p.rect(5, 9, 10, 14, "#f3eadb")
    p.ell(8, 6.5, 7, 4.4, cap)
    p.rect(1, 7, 14, 8, cap)
    for x, y in [(3, 5), (7, 3), (11, 4), (12, 7)]:
        p.set(x, y, "#8a6aff")  # toxic dots
    p.pts([(7, 0), (9, 1), (5, 1)], light(cap, 0.4))  # spray puffs
    outline_sel(p, 0.55)
    eyes(p, 10, 6, 9, angry=True)
    return p


MOBS = {"slug": slug, "aphid": aphid, "snail": snail, "mold": mold, "potato_beetle": potato_beetle,
        "toxic_carrot": toxic_carrot, "spray_cucumber": spray_cucumber, "pest_tomato": pest_tomato, "vole": vole,
        "spray_shroom": spray_shroom}  # fmt: skip


def snail_queen():
    p = PX(32, 32)
    body, shell = "#f0d2b0", "#d07aa0"
    p.ell(16, 25, 14, 5, body)
    p.ell(14, 15, 10, 9.5, shell)
    for r, k in ((7, 0.12), (4.5, 0.24), (2.2, 0.36)):
        p.ell(14.5, 15.5, r, r * 0.95, dark(shell, k), False)
    for x in (8, 12, 16, 20):  # crown
        p.poly([(x - 1.5, 6), (x + 1.5, 6), (x, 2)], "#ffd45e")
    p.rect(7, 6, 21, 7, "#ffd45e")
    p.pts([(26, 18), (27, 16), (29, 15), (29, 17)], dark(body, 0.25))
    outline_sel(p, 0.5)
    eyes(p, 21, 24, 27, angry=True)
    p.pts([(23, 24), (24, 25), (25, 25), (26, 24)], INK)
    return p


def beetle_king():
    p = PX(32, 32)
    shell = "#ffd45e"
    p.ell(16, 19, 11, 11, shell)
    for x in (9, 13, 16, 19, 23):
        p.line(x, 10, x, 29, "#6b4a32")
    p.ell(16, 7, 6, 4, "#e8823a")
    for x in (11, 15, 19):  # crown spikes
        p.poly([(x - 1.5, 3), (x + 2.5, 3), (x + 0.5, 0)], "#ff6b6b")
    for sx in (-1, 1):
        for y in (13, 19, 25):
            p.line(16 + sx * 11, y, 16 + sx * 15, y + 2, INK)
    outline_sel(p, 0.5)
    p.set(14, 7, "#ffffff")
    p.set(18, 7, "#ffffff")
    p.set(14, 8, INK)
    p.set(18, 8, INK)
    return p


def reaper():
    p = PX(32, 32)
    robe = "#3b2c4f"
    p.poly([(9, 10), (23, 10), (27, 31), (5, 31)], robe)
    for x in (10, 16, 22):
        p.line(x, 14, x + (x - 16) // 3, 30, light(robe, 0.15))
    p.ell(16, 9, 7, 7, robe)
    p.ell(16, 10, 4.5, 4.5, "#1d1428")
    p.set(14, 10, "#b6e05a")
    p.set(18, 10, "#b6e05a")  # glowing eyes
    p.line(28, 2, 28, 30, "#8a6a4a")  # scythe handle
    p.poly([(28, 2), (18, 3), (12, 7), (20, 5), (28, 5)], "#d8dde8")
    p.line(13, 6, 27, 3, "#ffffff")
    p.pts([(7, 31), (11, 31), (21, 31), (25, 31)], "#b6e05a")  # rot at the hem
    p.outline()
    return p


BOSSES = {"snail_queen": snail_queen, "beetle_king": beetle_king, "reaper": reaper}


def build() -> dict:
    out = {}
    beans = json.loads((ROOT / "docs" / "art" / "beans.json").read_text(encoding="utf-8"))
    out["ranger"] = beans["ranger"]
    for mid, fn in {**MOBS, **BOSSES}.items():
        out[mid] = fn().export()
    return out


def preview(sprites: dict, path: Path) -> None:
    os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
    import pygame

    scale, pad = 6, 12
    w = sum(s["w"] * scale + pad for s in sprites.values()) + pad
    h = max(s["h"] for s in sprites.values()) * scale + 2 * pad
    sheet = pygame.Surface((w, h))
    sheet.fill(hx("#a6dd82"))
    x = pad
    for s in sprites.values():
        for yy, row in enumerate(s["rows"]):
            for xx, ch in enumerate(row):
                if ch != ".":
                    sheet.fill(hx(s["pal"][ch]), (x + xx * scale, pad + yy * scale, scale, scale))
        x += s["w"] * scale + pad
    pygame.image.save(sheet, str(path))


def main():
    sprites = build()
    out = ROOT / "assets" / "sprites"
    out.mkdir(parents=True, exist_ok=True)
    (out / "sprites.json").write_text(json.dumps(sprites, indent=1) + "\n", encoding="utf-8")
    preview(sprites, ROOT / "docs" / "art" / "mobs_preview.png")
    print("wrote", out / "sprites.json", "with", ", ".join(sprites))


if __name__ == "__main__":
    main()
