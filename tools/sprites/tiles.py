"""Ground tiles for the three garden beds (Paket F), own pixel work.

Usage (from the repo root): python tools/sprites/tiles.py
Writes assets/tiles/<biome>.png: one row of 16 x 16 tiles per bed (index 0-3 plain variants,
4-7 features). The renderer picks variants by position, so the ground never repeats visibly.
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


def main():
    os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
    import pygame

    out = ROOT / "assets" / "tiles"
    out.mkdir(parents=True, exist_ok=True)
    sheets = []
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
