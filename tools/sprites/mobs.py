"""Phase-1 enemy sprites in the pastel bean style (own work) and the game's sprite export.

Usage (from the repo root): python tools/sprites/mobs.py
Writes assets/sprites/sprites.json (palette + pixel rows for every sprite the game draws)
and docs/art/mobs_preview.png. Sources: player beans from docs/art/beans.json, Ildra from
docs/art/sprites.json, enemies drawn here.
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


def slimeling():
    p = PX(16, 16)
    c = "#ff8fb8"
    p.ell(8, 10.5, 6.5, 5.2, c)
    p.rect(2, 12, 13, 14, c)
    p.rect(2, 14, 13, 14, dark(c, 0.15))
    p.ell(5, 7.5, 1.4, 1.0, light(c, 0.6), False)  # shine
    outline_sel(p, 0.55)
    eyes(p, 9, 6, 10)
    p.set(8, 12, INK)
    return p


def batswarm():
    p = PX(14, 12)
    c = "#7a5cc0"
    p.ell(7, 6, 3, 3, c)
    p.poly([(4, 5), (0, 2), (1, 6), (0, 9), (4, 8)], dark(c, 0.15))
    p.poly([(10, 5), (14, 2), (13, 6), (14, 9), (10, 8)], dark(c, 0.15))
    p.pts([(5, 2), (9, 2)], c)  # ears
    outline_sel(p, 0.55)
    eyes(p, 5, 6, 8)
    return p


def rootguard():
    p = PX(20, 20)
    bark = "#a07850"
    p.rect(4, 7, 15, 17, bark)
    p.rect(2, 17, 6, 18, bark)
    p.rect(13, 17, 17, 18, bark)
    p.ell(10, 5, 7.5, 3.8, "#6fbf5a")  # leafy top
    p.ell(7, 4, 2, 1.2, light("#6fbf5a", 0.4), False)
    for y in (10, 13):
        p.set(6, y, dark(bark, 0.25))
        p.set(13, y + 1, dark(bark, 0.25))
    outline_sel(p, 0.55)
    eyes(p, 9, 7, 12, angry=True)
    p.pts([(8, 13), (9, 12), (10, 12), (11, 13)], INK)
    return p


def sporeshooter():
    p = PX(16, 16)
    cap = "#d48ae0"
    p.rect(5, 9, 10, 14, "#fff1d6")  # stem
    p.ell(8, 6.5, 7, 4.2, cap)
    p.rect(1, 7, 14, 8, cap)
    for x, y in [(4, 4), (9, 3), (12, 6), (6, 7)]:
        p.set(x, y, "#ffffff")
    outline_sel(p, 0.55)
    eyes(p, 10, 6, 9)
    return p


MOBS = {"slimeling": slimeling, "batswarm": batswarm, "rootguard": rootguard, "sporeshooter": sporeshooter}


def build() -> dict:
    out = {}
    beans = json.loads((ROOT / "docs" / "art" / "beans.json").read_text(encoding="utf-8"))
    out["ranger"] = beans["ranger"]
    for mid, fn in MOBS.items():
        out[mid] = fn().export()
    drafts = json.loads((ROOT / "docs" / "art" / "sprites.json").read_text(encoding="utf-8"))
    ildra = next(b for b in drafts["bosses"] if b["n"].startswith("Ildra"))
    out["ildra"] = {"w": ildra["w"], "h": ildra["h"], "pal": ildra["pal"], "rows": ildra["rows"]}
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
