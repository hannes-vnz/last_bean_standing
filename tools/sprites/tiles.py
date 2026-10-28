"""Ground tiles for the three garden beds (Paket F), own pixel work.

Usage (from the repo root): python tools/sprites/tiles.py
Writes assets/tiles/<biome>.png: one row of 16 x 16 tiles per bed (index 0-3 plain variants,
4-7 features), and <biome>_decor.png: transparent decorations (pebbles, flowers, leaves, ...)
that the renderer scatters over the ground. Variants are picked by position and shaded in
large patches, so the ground never repeats visibly.
Also writes docs/art/tiles_preview.png.
"""

import os
import random
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from px import dark, hx, light  # noqa: E402

ROOT = HERE.parents[1]
T = 16  # tile size in canvas pixels


def tile(base, rnd, specks=()):
    """Plain ground with a few speck colours."""
    g = [[base] * T for _ in range(T)]
    for color, n in specks:
        for _ in range(n):
            g[rnd.randrange(T)][rnd.randrange(T)] = color
    return g


def seedbed(rnd):
    soil, row, sprout = "#b98a62", "#9c7050", "#9be27f"
    tiles = [tile(soil, rnd, [(dark(soil, 0.08), 10), (light(soil, 0.15), 6)]) for _ in range(4)]
    for k in range(4):  # furrows with seedlings: the bed is sown in rows
        g = tile(soil, rnd, [(dark(soil, 0.08), 6)])
        for x in range(T):
            g[7][x] = g[8][x] = row
            g[9][x] = dark(row, 0.15)
        if k < 3:
            x = 3 + 5 * k
            g[6][x] = g[5][x] = sprout
            g[4][x - 1] = g[4][x + 1] = light(sprout, 0.2)
            g[5][x - 1] = dark(sprout, 0.2)
        tiles.append(g)
    return tiles


def veggiebed(rnd):
    grass, blade, soil = "#a8d887", "#8fc46f", "#9a6d4c"
    tiles = [tile(grass, rnd, [(blade, 14), (light(grass, 0.25), 6)]) for _ in range(4)]
    g = tile(soil, rnd, [(dark(soil, 0.1), 12)])  # soil patch
    tiles.append(g)
    g = tile(grass, rnd, [(blade, 10)])  # little flower
    for x, y in ((7, 6), (8, 7), (6, 7), (7, 8)):
        g[y][x] = "#ffffff"
    g[7][7] = "#ffd45e"
    tiles.append(g)
    g = tile(soil, rnd, [(dark(soil, 0.1), 8)])  # carrot top peeking out of the vegetable row
    for x, y in ((6, 9), (7, 8), (8, 9), (7, 7), (9, 7)):
        g[y][x] = "#6fbf5a"
    g[10][7] = g[10][8] = "#ff9a4a"
    tiles.append(g)
    g = tile(grass, rnd, [(blade, 8), ("#ff9fc0", 2)])
    tiles.append(g)
    return tiles


def compost(rnd):
    base, crumb, toxic = "#8c7a6a", "#77665a", "#b6e05a"
    tiles = [tile(base, rnd, [(crumb, 14), (light(base, 0.12), 6), ("#6a5a4c", 4)]) for _ in range(4)]
    g = tile(base, rnd, [(crumb, 8)])  # toxic puddle
    for y in range(5, 12):
        for x in range(4, 13):
            if (x - 8) ** 2 / 20 + (y - 8) ** 2 / 9 <= 1:
                g[y][x] = toxic if (x + y) % 5 else light(toxic, 0.4)
    tiles.append(g)
    g = tile(base, rnd, [(crumb, 8)])  # eggshell
    for x, y in ((6, 7), (7, 7), (8, 8), (7, 8)):
        g[y][x] = "#fff1d6"
    tiles.append(g)
    g = tile(base, rnd, [(crumb, 8)])  # leaf
    for x, y in ((5, 9), (6, 8), (7, 8), (8, 7), (9, 7), (7, 9)):
        g[y][x] = "#a0784f"
    tiles.append(g)
    g = tile(base, rnd, [(crumb, 6), ("#8a6aff", 2), (toxic, 3)])
    tiles.append(g)
    return tiles


BEDS = {"seedbed": seedbed, "veggiebed": veggiebed, "compost": compost}


# ---------------------------------------------------------------------------- decorations (transparent, no collision)
def deco(draw):
    g = [[None] * T for _ in range(T)]

    def put(x, y, c):
        if 0 <= x < T and 0 <= y < T:
            g[y][x] = c

    draw(put)
    ink = "#4a3358"
    out = [row[:] for row in g]  # soft dark edge so decorations read on any ground
    for y in range(T):
        for x in range(T):
            if g[y][x] is None and any(0 <= x + dx < T and 0 <= y + dy < T and g[y + dy][x + dx] not in (None, ink)
                                       for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1))):  # fmt: skip
                out[y][x] = ink
    return out


def pebbles(put, c="#c8bfb4"):
    for x, y in ((5, 9), (6, 9), (5, 10), (6, 10), (9, 11), (10, 11), (8, 7)):
        put(x, y, c)
    put(5, 9, light(c, 0.4))
    put(9, 11, light(c, 0.4))


def flowers(put, petal):
    for cx, cy in ((5, 7), (10, 9), (7, 12)):
        for dx, dy in ((0, -1), (-1, 0), (1, 0), (0, 1)):
            put(cx + dx, cy + dy, petal)
        put(cx, cy, "#ffd45e")


def leaf(put, c="#d9a05a"):
    for i in range(5):
        put(5 + i, 10 - i // 2, c)
        put(5 + i, 11 - i // 2, dark(c, 0.15))
    put(4, 11, dark(c, 0.3))


def mushroom(put, cap="#ff8f8f"):
    for x in range(5, 11):
        put(x, 7, cap)
        put(x, 8, cap)
    for x in range(6, 10):
        put(x, 6, cap)
    put(6, 7, "#ffffff")
    put(9, 6, "#ffffff")
    for y in (9, 10, 11):
        put(7, y, "#fff1d6")
        put(8, y, "#fff1d6")


def tuft(put, c="#7ccf6a"):
    for x, h in ((5, 3), (6, 5), (7, 4), (8, 6), (9, 3), (10, 4)):
        for y in range(12 - h, 12):
            put(x, y, c if y > 12 - h else light(c, 0.3))


def twig(put):
    for i in range(8):
        put(4 + i, 9 + (i % 3 == 0), "#8a6a4a")
    put(7, 8, "#8a6a4a")
    put(8, 7, "#8a6a4a")


def ladybug(put):
    for x, y in ((7, 8), (8, 8), (6, 9), (7, 9), (8, 9), (9, 9), (7, 10), (8, 10)):
        put(x, y, "#ff6b6b")
    put(7, 7, "#4a3358")
    put(8, 7, "#4a3358")
    put(6, 9, "#4a3358")


def eggshell(put):
    for x, y in ((5, 9), (6, 8), (7, 8), (8, 9), (9, 10), (10, 10), (6, 10), (7, 10)):
        put(x, y, "#fff1d6")
    put(6, 9, "#e8dcc4")


def peel(put):
    for i in range(6):
        put(5 + i, 8 + abs(3 - i) // 2, "#ffd45e")
    put(4, 9, "#8a6a4a")
    put(11, 9, "#8a6a4a")


def apple_core(put):
    for y in range(7, 12):
        put(7, y, "#fff1d6")
        put(8, y, "#fff1d6")
    for x in (6, 9):
        put(x, 7, "#ff6b6b")
        put(x, 11, "#ff6b6b")
    put(8, 6, "#8a6a4a")


def spores(put):
    for x, y in ((5, 8), (8, 6), (10, 9), (7, 11), (11, 12)):
        put(x, y, "#b6e05a")
        put(x + 1, y, light("#b6e05a", 0.4))


def lettuce(put):
    for x in range(4, 12):
        for y in range(7, 12):
            if (x - 7.5) ** 2 / 14 + (y - 9.5) ** 2 / 5 <= 1:
                put(x, y, "#9be27f" if (x + y) % 3 else "#c8f0a8")


DECOR = {
    "seedbed": [pebbles, lambda p: flowers(p, "#ffffff"), leaf, tuft, twig, ladybug, mushroom,
                lambda p: flowers(p, "#ff9fc0")],
    "veggiebed": [lambda p: flowers(p, "#ffffff"), lambda p: flowers(p, "#ffd45e"), lettuce, tuft, ladybug,
                  lambda p: pebbles(p, "#d8d0c4"), lambda p: flowers(p, "#b8a0ff"), mushroom],
    "compost": [eggshell, peel, apple_core, spores, lambda p: leaf(p, "#a0784f"), lambda p: mushroom(p, "#c8f06a"),
                twig, lambda p: pebbles(p, "#9a8a7a")],
}  # fmt: skip


def main():
    os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
    import pygame

    out = ROOT / "assets" / "tiles"
    out.mkdir(parents=True, exist_ok=True)
    sheets = []
    for bed, items in DECOR.items():
        sheet = pygame.Surface((T * len(items), T), pygame.SRCALPHA)
        for i, draw in enumerate(items):
            for y, row in enumerate(deco(draw)):
                for x, c in enumerate(row):
                    if c is not None:
                        sheet.set_at((i * T + x, y), (*hx(c), 255))
        pygame.image.save(sheet, str(out / f"{bed}_decor.png"))
    for bed, fn in BEDS.items():
        tiles = fn(random.Random(bed))
        sheet = pygame.Surface((T * len(tiles), T))
        for i, g in enumerate(tiles):
            for y, row in enumerate(g):
                for x, c in enumerate(row):
                    sheet.set_at((i * T + x, y), hx(c))
        pygame.image.save(sheet, str(out / f"{bed}.png"))
        sheets.append(sheet)
    scale = 4
    prev = pygame.Surface((max(s.get_width() for s in sheets) * scale, len(sheets) * (T + 2) * scale))
    for i, s in enumerate(sheets):
        prev.blit(pygame.transform.scale(s, (s.get_width() * scale, T * scale)), (0, i * (T + 2) * scale))
    pygame.image.save(prev, str(ROOT / "docs" / "art" / "tiles_preview.png"))
    print("wrote", ", ".join(f"{b}.png" for b in BEDS))


if __name__ == "__main__":
    main()
