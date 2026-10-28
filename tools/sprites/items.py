"""Item and weapon icons (16 x 16 pixel art, own work) in the pastel garden style.

Usage (from the repo root): python tools/sprites/items.py
Writes assets/sprites/icons.json (same format as sprites.json: palette + rows per icon, keys
"item:<id>" and "weapon:<id>" plus "weapon:start" for the character's bow) and
docs/art/icons_preview.png. The game frames them in their rarity colour (render/icons.py).
"""

import json
import math
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from px import INK, PX, dark, hx, light  # noqa: E402

ROOT = HERE.parents[1]
GOLD, GOLD_L = "#ffc83d", "#fff1a8"
WOOD, WOOD_L = "#a0784f", "#c9a06a"
METAL, METAL_L = "#9aa8c0", "#dfe7f2"
GREEN, GREEN_L = "#6fbf5a", "#a7e08a"
RED = "#ff6b6b"


def icon():
    return PX(16, 16)


def done(p):
    p.outline()
    return p


def shine(p, x, y):
    p.set(x, y, "#ffffff")


# ---------------------------------------------------------------------------- weapons
def w_start():  # bow with arrow
    p = icon()
    for i in range(12):
        a = -1.1 + i * 0.2
        p.set(5 + 6 * math.cos(a), 8 + 6.5 * math.sin(a), WOOD)
        p.set(6 + 6 * math.cos(a), 8 + 6.5 * math.sin(a), WOOD_L)
    p.line(10, 2, 10, 14, "#ffffff")
    p.line(2, 8, 14, 8, WOOD_L)
    p.pts([(14, 7), (14, 9), (15, 8), (13, 8)], METAL_L)
    p.pts([(2, 7), (2, 9), (1, 7), (1, 9)], RED)
    return done(p)


def w_thorn_twig():
    p = icon()
    p.line(2, 14, 13, 2, "#8a5a30", 2)
    for x, y in ((5, 10), (8, 7), (10, 4), (6, 12), (11, 6)):
        p.set(x + 1, y - 1, "#fff1d6")
        p.set(x + 2, y - 2, "#fff1d6")
    p.ell(12, 3, 2.2, 1.6, GREEN)
    p.ell(4, 9, 2, 1.4, GREEN)
    return done(p)


def w_dandelion():
    p = icon()
    p.line(8, 15, 8, 8, GREEN)
    p.ell(8, 6, 5.5, 5.5, "#f6f6ff")
    for a in range(0, 360, 40):
        x, y = 8 + 4.5 * math.cos(math.radians(a)), 6 + 4.5 * math.sin(math.radians(a))
        p.set(x, y, "#c8d0e8")
    p.ell(8, 6, 1.4, 1.4, GOLD)
    p.pts([(13, 2), (14, 1), (2, 3)], "#ffffff")
    return done(p)


def w_pollen_cloud():
    p = icon()
    for cx, cy, r in ((5, 9, 3.6), (9, 7, 4.4), (12, 10, 3.2), (8, 11, 3.6)):
        p.ell(cx, cy, r, r * 0.85, "#fff1a8")
    for x, y in ((4, 8), (8, 6), (11, 9), (7, 11), (10, 12), (6, 5)):
        p.set(x, y, GOLD)
    shine(p, 7, 4)
    return done(p)


def w_bees():
    p = icon()
    p.ell(8, 9, 5, 3.8, GOLD)
    for x in (6, 9):
        p.line(x, 6, x, 12, "#4a3358")
    p.ell(6, 4, 2.6, 2.2, "#e6f4ff")
    p.ell(10, 4, 2.6, 2.2, "#e6f4ff")
    p.set(13, 9, "#4a3358")
    p.pts([(2, 9), (1, 9)], "#4a3358")  # stinger
    shine(p, 12, 8)
    return done(p)


def w_sun_pulse():
    p = icon()
    for a in range(0, 360, 45):
        x, y = 8 + 6.5 * math.cos(math.radians(a)), 8 + 6.5 * math.sin(math.radians(a))
        p.line(8 + 4 * math.cos(math.radians(a)), 8 + 4 * math.sin(math.radians(a)), x, y, GOLD)
    p.ell(8, 8, 4, 4, GOLD)
    p.ell(7, 7, 2, 2, GOLD_L)
    p.pts([(6, 9), (10, 9)], "#4a3358")
    p.pts([(7, 10), (8, 10), (9, 10)], "#ff9f86")
    return done(p)


def w_pumpkin_bomb():
    p = icon()
    for cx in (5, 8, 11):
        p.ell(cx, 10, 3.6, 4.6, "#ff9a3c")
    p.ell(8, 10, 3, 4.6, "#ffb35c")
    p.rect(7, 3, 8, 5, "#6b8a3a")
    p.line(9, 3, 12, 1, "#ffd45e")  # fuse
    p.set(13, 1, "#ff6b6b")
    p.pts([(6, 9), (10, 9), (7, 12), (8, 12), (9, 12)], "#6b3a1a")
    return done(p)


def w_firefly():
    p = icon()
    p.ell(8, 8, 6.5, 6.5, "#fff7c0")
    p.ell(8, 8, 4.5, 4.5, "#fff1a8")
    p.ell(9, 9, 3, 2.2, "#ffd45e")
    p.ell(6, 7, 2, 1.6, "#4a3358")
    p.ell(9, 5, 2.4, 1.6, "#e6f4ff")
    p.pts([(3, 2), (13, 13), (14, 3)], "#ffffff")
    return done(p)


def w_leaf_boomerang():
    p = icon()
    p.poly([(2, 4), (7, 2), (8, 8), (13, 4), (14, 9), (8, 14), (2, 9)], "#ff9a3c")
    p.line(8, 14, 8, 6, "#c0602a")
    p.line(8, 9, 4, 5, "#c0602a")
    p.line(8, 9, 12, 6, "#c0602a")
    shine(p, 4, 6)
    return done(p)


def w_nettle_trail():
    p = icon()
    for x0, h in ((3, 9), (8, 12), (12, 8)):
        p.line(x0, 15, x0, 15 - h, "#4f9a5a")
        p.poly([(x0, 15 - h + 3), (x0 + 3, 15 - h + 1), (x0 + 1, 15 - h + 5)], "#5fb85a")
    p.pts([(1, 15), (5, 14), (10, 15), (14, 14)], "#a0784f")
    p.pts([(6, 4), (11, 7)], "#ffffff")
    return done(p)


def w_cactus():
    p = icon()
    p.rect(6, 3, 9, 14, "#6fbf5a")
    p.rect(2, 6, 4, 9, "#6fbf5a")
    p.rect(4, 8, 6, 9, "#6fbf5a")
    p.rect(11, 5, 13, 8, "#6fbf5a")
    p.rect(9, 7, 11, 8, "#6fbf5a")
    p.rect(4, 13, 11, 15, "#d9805a")
    for x, y in ((7, 5), (8, 9), (7, 12), (3, 7), (12, 6)):
        p.set(x, y, "#fff1d6")
    p.pts([(7, 2), (8, 2)], "#ff9fc0")
    return done(p)


def w_sunbeam():
    p = icon()
    p.ell(4, 12, 3.2, 3.2, METAL)
    p.ell(4, 12, 2, 2, "#cfeaff")
    p.line(6, 10, 15, 1, GOLD_L, 2)
    p.line(7, 10, 15, 2, GOLD)
    p.pts([(12, 2), (14, 5), (10, 3)], "#ffffff")
    return done(p)


def w_garlic_mine():
    p = icon()
    p.ell(8, 10, 5.5, 5, "#fff6ea")
    p.ell(5.5, 10, 2.2, 4, "#efe4d4")
    p.ell(10.5, 10, 2.2, 4, "#efe4d4")
    p.line(8, 5, 8, 2, "#a7e08a")
    p.pts([(7, 1), (9, 1)], "#a7e08a")
    p.pts([(8, 14), (6, 14), (10, 14)], "#d8c8a8")
    shine(p, 6, 8)
    return done(p)


def w_seed_shotgun():
    p = icon()
    p.line(2, 12, 10, 6, WOOD, 2)
    p.line(9, 6, 14, 3, METAL, 2)
    for x, y in ((14, 6), (15, 1), (13, 8), (12, 1)):
        p.set(x, y, GOLD)
    p.rect(2, 12, 4, 14, WOOD_L)
    return done(p)


def w_dragonfly():
    p = icon()
    p.line(3, 13, 11, 5, "#5ab4ff", 2)
    p.ell(12, 4, 2, 2, "#5ab4ff")
    p.ell(6, 6, 3.6, 1.6, "#e6f4ff")
    p.ell(10, 10, 3.6, 1.6, "#e6f4ff")
    p.set(13, 3, "#4a3358")
    return done(p)


def w_sickle():
    p = icon()
    for i in range(10):
        a = math.radians(200 + i * 16)
        p.set(9 + 5.5 * math.cos(a), 7 + 5.5 * math.sin(a), METAL_L)
        p.set(9 + 4.5 * math.cos(a), 7 + 4.5 * math.sin(a), METAL)
    p.line(4, 9, 2, 15, WOOD, 2)
    shine(p, 9, 2)
    return done(p)


# ---------------------------------------------------------------------------- items
def watering_can():
    p = icon()
    p.rect(3, 6, 10, 13, "#7ec4ff")
    p.rect(3, 6, 10, 7, light("#7ec4ff", 0.3))
    p.line(10, 9, 14, 4, "#7ec4ff", 2)
    p.pts([(14, 3), (15, 3), (15, 4)], METAL_L)
    for i in range(6):
        p.set(4 + i, 3 + (1 if i in (0, 5) else 0), "#5a9ad8")
    p.pts([(15, 6), (15, 8), (14, 10)], "#bfe8ff")  # water drops
    return done(p)


def compost():
    p = icon()
    p.ell(8, 11, 6.5, 4, "#8a6a4a")
    p.ell(8, 9, 5, 3, "#a0784f")
    for x, y in ((5, 9), (9, 8), (11, 10), (7, 11)):
        p.set(x, y, "#6fbf5a")
    p.pts([(8, 5), (8, 6), (7, 4), (9, 4)], GREEN_L)  # sprout
    p.pts([(10, 11), (11, 12)], "#fff1d6")
    return done(p)


def garden_gloves():
    p = icon()
    p.rect(4, 7, 10, 14, "#ff9fc0")
    for x in (4, 6, 8, 10):
        p.rect(x, 3, x + 1, 7, "#ff9fc0")
    p.rect(1, 8, 3, 10, "#ff9fc0")
    p.rect(4, 12, 10, 14, "#ffd45e")
    shine(p, 5, 5)
    return done(p)


def straw_hat():
    p = icon()
    p.ell(8, 11, 7.5, 2.8, "#f5d58a")
    p.ell(8, 7, 4.2, 3.6, "#f5d58a")
    p.rect(4, 8, 12, 9, "#ff8fb8")
    for x in (3, 6, 10, 13):
        p.set(x, 11, dark("#f5d58a", 0.15))
    shine(p, 6, 5)
    return done(p)


def seed_pouch():
    p = icon()
    p.ell(8, 10, 5.5, 5, "#c9a06a")
    p.rect(6, 3, 10, 5, "#c9a06a")
    p.line(5, 6, 11, 6, "#8a5a30")
    for x, y in ((7, 10), (9, 11), (8, 12)):
        p.set(x, y, GOLD)
    p.pts([(11, 2), (12, 1)], GOLD)
    return done(p)


def rake():
    p = icon()
    p.line(3, 14, 11, 4, WOOD, 2)
    p.line(8, 1, 15, 6, METAL)
    for i in range(4):
        p.line(9 + 2 * i, 2 + i, 8 + 2 * i, 5 + i, METAL_L)
    return done(p)


def snail_shell():
    p = icon()
    p.ell(8, 9, 6, 5.5, "#d9a07a")
    p.ell(8.5, 9.5, 3.8, 3.4, "#c48660")
    p.ell(9, 10, 1.8, 1.6, "#a86a48")
    shine(p, 5, 6)
    return done(p)


def sprout_boots():
    p = icon()
    p.rect(4, 4, 8, 12, "#7ed957")
    p.rect(4, 11, 13, 14, "#7ed957")
    p.rect(4, 13, 13, 14, "#4f9a5a")
    p.pts([(6, 1), (5, 2), (7, 2), (6, 3)], GREEN_L)
    p.pts([(13, 9), (14, 8), (15, 10)], "#ffffff")  # speed lines
    return done(p)


def magnifier():
    p = icon()
    p.ell(6, 6, 4.6, 4.6, METAL)
    p.ell(6, 6, 3.2, 3.2, "#cfeaff")
    p.line(9, 9, 14, 14, WOOD, 2)
    shine(p, 4, 4)
    shine(p, 5, 4)
    return done(p)


def sundial():
    p = icon()
    p.ell(8, 10, 6.5, 4, "#d8dde8")
    p.poly([(8, 9), (8, 2), (12, 9)], GOLD)
    for x in (3, 13, 8):
        p.set(x, 10 if x != 8 else 13, "#4a3358")
    return done(p)


def earthworm():
    p = icon()
    for i in range(12):
        p.set(2 + i, 9 + 2.5 * math.sin(i * 0.8), "#ff9fb0")
        p.set(2 + i, 10 + 2.5 * math.sin(i * 0.8), "#ff9fb0")
    p.set(13, 9 + 2.5 * math.sin(11 * 0.8) - 1, "#4a3358")
    return done(p)


def garden_twine():
    p = icon()
    p.ell(8, 8, 5.5, 5.5, "#f0d090")
    for y in (5, 7, 9, 11):
        p.line(4, y, 12, y + 1, dark("#f0d090", 0.18))
    p.line(12, 12, 15, 15, "#f0d090")
    return done(p)


def clover():
    p = icon()
    for cx, cy in ((5, 6), (11, 6), (5, 11), (11, 11)):
        p.ell(cx, cy, 3, 3, "#6fd36a")
    p.line(8, 9, 12, 15, "#4f9a5a")
    shine(p, 4, 5)
    return done(p)


def trellis():
    p = icon()
    for x in (3, 8, 13):
        p.line(x, 1, x, 15, WOOD)
    for y in (4, 9, 14):
        p.line(1, y, 15, y, WOOD_L)
    for x, y in ((5, 6), (10, 11), (11, 3)):
        p.ell(x, y, 1.5, 1.2, GREEN)
    return done(p)


def pruning_shears():
    p = icon()
    p.poly([(8, 8), (14, 1), (15, 2)], METAL_L)
    p.poly([(8, 8), (13, 1), (11, 1)], METAL)
    p.ell(5, 11, 2.6, 2.6, RED)
    p.ell(10, 13, 2.6, 2.2, RED)
    p.set(8, 8, "#4a3358")
    return done(p)


def scarecrow():
    p = icon()
    p.line(8, 4, 8, 15, WOOD)
    p.line(2, 7, 14, 7, WOOD)
    p.ell(8, 4, 2.6, 2.6, "#f5d58a")
    p.poly([(4, 2), (12, 2), (8, 0)], "#a86a48")
    p.rect(6, 7, 10, 11, "#7ec4ff")
    p.pts([(7, 4), (9, 4)], "#4a3358")
    p.pts([(1, 6), (15, 6), (1, 8)], "#f5d58a")  # straw
    return done(p)


def deep_roots():
    p = icon()
    p.ell(8, 4, 4, 2.6, GREEN)
    p.line(8, 5, 8, 9, "#8a5a30")
    for dx, ex in ((-1, 3), (1, 13), (0, 8)):
        p.line(8 + dx, 9, ex, 15, "#b88a5a")
    p.line(5, 12, 2, 14, "#b88a5a")
    p.line(11, 12, 14, 12, "#b88a5a")
    return done(p)


def nettle():
    p = icon()
    p.line(8, 15, 8, 4, "#4f9a5a")
    for y, d in ((5, 1), (8, -1), (11, 1)):
        p.poly([(8, y + 1), (8 + 6 * d, y - 2), (8 + 4 * d, y + 3)], "#5fb85a")
    for x, y in ((12, 4), (4, 7), (12, 10)):
        p.set(x, y, "#ffffff")
    return done(p)


def honey_pot():
    p = icon()
    p.ell(8, 10, 5.5, 5, "#e8a85a")
    p.rect(4, 4, 12, 6, "#e8a85a")
    p.rect(4, 3, 12, 4, GOLD)
    p.pts([(10, 6), (10, 7), (11, 8)], GOLD)  # drip
    p.rect(6, 9, 10, 11, "#fff1d6")
    shine(p, 5, 8)
    return done(p)


def cold_frame():
    p = icon()
    p.poly([(1, 13), (15, 13), (15, 6), (1, 10)], "#cfeaff")
    p.line(1, 13, 15, 13, WOOD, 2)
    p.line(1, 10, 15, 6, WOOD)
    p.line(8, 8, 8, 13, WOOD)
    p.pts([(4, 11), (11, 9)], GREEN)
    shine(p, 12, 8)
    return done(p)


def seed_bomb():
    p = icon()
    p.ell(7, 10, 5, 5, "#8a6a4a")
    for x, y in ((5, 9), (8, 11), (9, 8), (6, 12)):
        p.set(x, y, GOLD)
    p.line(10, 6, 13, 2, "#ffd45e")
    p.pts([(14, 1), (13, 1), (14, 2)], RED)
    return done(p)


def twin_pod():
    p = icon()
    p.ell(8, 8, 6.5, 3.4, "#7ed957")
    p.ell(5.5, 8, 1.8, 1.8, GREEN_L)
    p.ell(10.5, 8, 1.8, 1.8, GREEN_L)
    p.line(14, 6, 15, 3, "#4f9a5a")
    return done(p)


def sunflower():
    p = icon()
    p.line(8, 15, 8, 9, "#4f9a5a")
    for a in range(0, 360, 30):
        p.ell(8 + 4 * math.cos(math.radians(a)), 7 + 4 * math.sin(math.radians(a)), 1.6, 1.6, GOLD)
    p.ell(8, 7, 2.6, 2.6, "#8a5a30")
    p.ell(4, 12, 2, 1.2, GREEN)
    return done(p)


def beehive():
    p = icon()
    for i, (y, r) in enumerate(((4, 3.5), (7, 5), (10, 5.8), (13, 5))):
        p.ell(8, y, r, 1.8, GOLD if i % 2 else "#ffb84a")
    p.ell(8, 12, 1.6, 1.4, "#4a3358")
    p.pts([(14, 3), (13, 2)], "#4a3358")
    return done(p)


def rain_barrel():
    p = icon()
    p.rect(3, 4, 12, 14, WOOD)
    for y in (6, 11):
        p.line(3, y, 12, y, METAL)
    p.ell(7.5, 4, 4.5, 1.4, "#7ec4ff")
    p.pts([(13, 1), (13, 2), (14, 3)], "#bfe8ff")
    return done(p)


def golden_leaf():
    p = icon()
    p.poly([(2, 14), (6, 4), (14, 2), (12, 10)], GOLD)
    p.line(2, 14, 12, 4, "#e0a020")
    p.ell(9, 5, 1.5, 1, GOLD_L)
    p.pts([(14, 13), (13, 12), (15, 12)], "#ffffff")
    return done(p)


def oak_acorn():
    p = icon()
    p.ell(8, 10, 4.5, 5, "#c98d5a")
    p.ell(8, 6, 5.5, 2.8, "#8a6a4a")
    for x in (5, 8, 11):
        p.set(x, 6, "#6b4a32")
    p.line(8, 3, 9, 1, "#6b4a32")
    shine(p, 6, 9)
    return done(p)


def greenhouse():
    p = icon()
    p.poly([(1, 7), (8, 1), (15, 7)], "#cfeaff")
    p.rect(2, 7, 14, 14, "#dff2ff")
    for x in (5, 8, 11):
        p.line(x, 4, x, 14, METAL)
    p.line(2, 10, 14, 10, METAL)
    p.pts([(3, 13), (6, 12), (12, 13)], GREEN)
    return done(p)


def gardeners_spade():
    p = icon()
    p.line(10, 1, 7, 9, WOOD, 2)
    p.rect(9, 0, 12, 1, WOOD_L)
    p.poly([(3, 9), (9, 9), (8, 15), (4, 15)], METAL_L)
    p.line(5, 10, 5, 14, METAL)
    p.pts([(12, 12), (13, 11), (14, 12)], GOLD)
    return done(p)


def first_seed():
    p = icon()
    for a in range(0, 360, 45):
        p.set(8 + 6.5 * math.cos(math.radians(a)), 8 + 6.5 * math.sin(math.radians(a)), GOLD_L)
    p.ell(8, 8, 3.6, 4.6, GOLD)
    p.ell(7, 7, 1.4, 2, "#ffffff")
    p.pts([(8, 2), (7, 1), (9, 1)], GREEN_L)
    return done(p)


def copper_wire():
    p = icon()
    for i in range(5):
        p.ell(4 + i * 2, 8, 2, 4.5, "#e08a4a")
        p.ell(4 + i * 2, 8, 1, 3.5, None or "#c06a30", False)
    p.pts([(14, 2), (13, 4), (15, 4), (14, 6)], "#fff1a8")  # spark
    return done(p)


def burning_glass():
    p = magnifier()
    p.ell(6, 6, 3, 3, "#ffb35c")
    p.pts([(5, 5), (6, 7), (7, 5)], "#fff1a8")
    p.pts([(13, 3), (14, 2), (12, 2)], RED)
    p.outline()
    return p


def nettle_brew():
    p = icon()
    p.ell(8, 10, 5, 4.6, "#cfeaff")
    p.ell(8, 11, 4, 3, "#7ed957")
    p.rect(6, 2, 10, 6, "#cfeaff")
    p.rect(6, 1, 10, 2, WOOD)
    p.pts([(7, 10), (10, 12)], "#d8ffb0")
    shine(p, 5, 9)
    return done(p)


def frost_fleece():
    p = icon()
    p.poly([(2, 4), (14, 3), (13, 13), (3, 14)], "#e6f4ff")
    for x, y in ((5, 6), (10, 8), (6, 11), (11, 5)):
        p.pts([(x, y), (x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1)], "#8ec5ff")
    return done(p)


def bird_bath():
    p = icon()
    p.ell(8, 6, 6.5, 2.4, "#d8dde8")
    p.ell(8, 5.5, 5, 1.4, "#7ec4ff")
    p.rect(7, 7, 9, 13, "#c8ccd8")
    p.rect(4, 13, 12, 14, "#c8ccd8")
    p.pts([(12, 2), (13, 1), (14, 2), (13, 3)], "#ff9fc0")  # little bird
    return done(p)


def hedgehog_house():
    p = icon()
    p.poly([(1, 8), (8, 2), (15, 8)], "#a86a48")
    p.rect(3, 8, 13, 14, WOOD)
    p.ell(8, 13, 2.6, 2.4, "#4a3358")
    for x in (2, 5, 8, 11, 14):
        p.set(x, 7 - (2 if x in (5, 11) else 0), "#6b4a32")
    return done(p)


def ladybug():
    p = icon()
    p.ell(8, 9, 6, 5.5, RED)
    p.line(8, 4, 8, 14, "#4a3358")
    p.ell(8, 4, 3, 2, "#4a3358")
    for x, y in ((5, 8), (11, 8), (5, 12), (11, 12)):
        p.ell(x, y, 1, 1, "#4a3358")
    shine(p, 4, 6)
    return done(p)


def bumblebee():
    p = icon()
    p.ell(8, 9, 6, 5, GOLD)
    for x in (5, 8, 11):
        p.line(x, 5, x, 13, "#4a3358")
    p.ell(5, 3, 2.6, 2, "#e6f4ff")
    p.ell(11, 3, 2.6, 2, "#e6f4ff")
    shine(p, 13, 8)
    return done(p)


def weathervane():
    p = icon()
    p.line(8, 4, 8, 15, METAL)
    p.line(3, 13, 13, 13, METAL)
    p.poly([(4, 3), (12, 2), (13, 5), (6, 6)], "#e08a4a")  # rooster body
    p.pts([(12, 1), (13, 1)], RED)
    p.pts([(2, 7), (14, 7), (8, 9)], METAL_L)
    return done(p)


def pitchfork():
    p = icon()
    p.line(8, 6, 8, 15, WOOD, 2)
    p.line(4, 6, 12, 6, METAL)
    for x in (4, 8, 12):
        p.line(x, 0, x, 6, METAL_L)
    return done(p)


def sun_hat():
    p = straw_hat()
    p.rect(4, 8, 12, 9, RED)
    p.ell(12, 7, 1.6, 1.6, GOLD)
    p.outline()
    return p


def rain_gauge():
    p = icon()
    p.rect(5, 2, 10, 14, "#dff2ff")
    p.rect(5, 8, 10, 14, "#7ec4ff")
    for y in (4, 7, 10, 13):
        p.line(5, y, 7, y, METAL)
    p.ell(13, 5, 2, 2.6, "#bfe8ff")
    return done(p)


def garden_gnome():
    p = icon()
    p.poly([(8, 0), (4, 6), (12, 6)], RED)
    p.ell(8, 7, 3, 2.4, "#ffe0c8")
    p.poly([(5, 8), (11, 8), (8, 12)], "#ffffff")  # beard
    p.rect(5, 11, 11, 15, "#7ec4ff")
    p.pts([(7, 7), (9, 7)], "#4a3358")
    p.set(8, 8, "#ff9fc0")
    return done(p)


def bell_jar():
    p = icon()
    p.ell(8, 8, 5.5, 6.5, "#e6f4ff")
    p.rect(2, 13, 14, 14, WOOD)
    p.ell(8, 1.5, 1.5, 1.2, METAL)
    p.pts([(8, 12), (7, 10), (9, 10), (8, 9)], "#ff8fb8")  # rose inside
    shine(p, 5, 5)
    shine(p, 5, 6)
    return done(p)


def thunder_cloud():
    p = icon()
    for cx, cy, r in ((5, 6, 3.6), (9, 4.5, 4.2), (12, 7, 3.2)):
        p.ell(cx, cy, r, r * 0.85, "#9a8fb8")
    p.poly([(9, 8), (6, 12), (8, 12), (6, 15), (11, 10), (9, 10), (10, 8)], GOLD)
    return done(p)


def compost_heart():
    p = icon()
    p.ell(5, 6, 3.6, 3.4, "#7ed957")
    p.ell(11, 6, 3.6, 3.4, "#7ed957")
    p.poly([(1.5, 7), (14.5, 7), (8, 15)], "#7ed957")
    p.ell(6, 6, 1.4, 1, GREEN_L)
    for x, y in ((8, 9), (6, 10), (10, 8), (9, 12)):
        p.set(x, y, "#a0784f")
    p.pts([(13, 1), (14, 2), (15, 1)], GOLD_L)
    return done(p)


WEAPONS = {"start": w_start, "thorn_twig": w_thorn_twig, "dandelion": w_dandelion, "pollen_cloud": w_pollen_cloud,
           "bees": w_bees, "sun_pulse": w_sun_pulse, "pumpkin_bomb": w_pumpkin_bomb, "firefly": w_firefly,
           "leaf_boomerang": w_leaf_boomerang, "nettle_trail": w_nettle_trail, "cactus": w_cactus, "sunbeam": w_sunbeam,
           "garlic_mine": w_garlic_mine, "seed_shotgun": w_seed_shotgun, "dragonfly": w_dragonfly,
           "sickle": w_sickle}  # fmt: skip

def item_ids() -> list[str]:
    """Every item in data/items.json needs a drawing function of the same name above."""
    return [i["id"] for i in json.loads((ROOT / "data" / "items.json").read_text(encoding="utf-8"))["items"]]


def build() -> dict:
    out = {f"weapon:{k}": fn().export() for k, fn in WEAPONS.items()}
    out.update({f"item:{k}": globals()[k]().export() for k in item_ids()})
    return out


def preview(icons: dict, path: Path) -> None:
    os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
    import pygame

    scale, cols = 4, 12
    rows = (len(icons) + cols - 1) // cols
    sheet = pygame.Surface((cols * (16 * scale + 8) + 8, rows * (16 * scale + 8) + 8))
    sheet.fill(hx("#2c2035"))
    for i, s in enumerate(icons.values()):
        ox, oy = 8 + (i % cols) * (16 * scale + 8), 8 + (i // cols) * (16 * scale + 8)
        sheet.fill(hx("#fff8ec"), (ox, oy, 16 * scale, 16 * scale))
        for y, row in enumerate(s["rows"]):
            for x, ch in enumerate(row):
                if ch != ".":
                    sheet.fill(hx(s["pal"][ch]), (ox + x * scale, oy + y * scale, scale, scale))
    pygame.image.save(sheet, str(path))


def main():
    icons = build()
    (ROOT / "assets" / "sprites" / "icons.json").write_text(json.dumps(icons, indent=1) + "\n", encoding="utf-8")
    preview(icons, ROOT / "docs" / "art" / "icons_preview.png")
    print("wrote", len(icons), "icons:", ", ".join(k.split(":")[1] for k in icons))


if __name__ == "__main__":
    main()
