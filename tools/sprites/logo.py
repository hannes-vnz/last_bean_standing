"""App icon / logo (own pixel work): Fenn the bean in the seed bed, guarding a sprout with the golden seed.

Usage (from the repo root): python tools/sprites/logo.py
Draws a 48 x 48 master and writes web/icons/ (apple-touch-icon 180, Android 192 and 512, maskable 512,
favicon 32 and 48) plus docs/art/logo_preview.png. Every size is an integer upscale with padding in the
background colour, so the pixels stay crisp.
"""

import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
INK = (74, 51, 88)
M = 48  # master size


def hx(c: str) -> tuple[int, int, int]:
    c = c.lstrip("#")
    return int(c[0:2], 16), int(c[2:4], 16), int(c[4:6], 16)


def master(pygame):
    s = pygame.Surface((M, M))
    sky_top, sky_low = hx("#8fd0ff"), hx("#c9ecff")
    s.fill(sky_top, (0, 0, M, 16))  # sky in two calm bands
    s.fill(sky_low, (0, 16, M, 14))
    # sun
    pygame.draw.circle(s, hx("#fff1a8"), (8, 7), 5)
    pygame.draw.circle(s, hx("#ffd45e"), (8, 7), 4)
    # soil with two furrows
    soil, furrow = hx("#b98a62"), hx("#9c7050")
    s.fill(soil, (0, 30, M, M - 30))
    s.fill(hx("#7ccf6a"), (0, 30, M, 2))  # grass edge
    for y in (37, 43):
        s.fill(furrow, (0, y, M, 2))
    for x, y in ((3, 35), (12, 41), (44, 41), (30, 46)):  # tiny seedlings in the rows
        s.set_at((x, y), hx("#9be27f"))
        s.set_at((x - 1, y - 1), hx("#9be27f"))
        s.set_at((x + 1, y - 1), hx("#9be27f"))
    # the sprout with the golden seed (what the bean defends)
    stem, leaf = hx("#4f9a5a"), hx("#7ed957")
    sx = 39
    s.fill(INK, (sx - 1, 21, 3, 12))
    s.fill(stem, (sx, 22, 1, 11))
    for pts in (((sx, 26), (sx + 7, 22), (sx + 5, 28)), ((sx, 28), (sx - 6, 24), (sx - 4, 30))):
        pygame.draw.polygon(s, INK, pts, 0)
        inner = [(px + (-1 if px > sx else 1 if px < sx else 0), py) for px, py in pts]
        pygame.draw.polygon(s, leaf, inner)
    pygame.draw.circle(s, INK, (sx, 19), 4)
    pygame.draw.circle(s, hx("#ffd45e"), (sx, 19), 3)
    s.set_at((sx - 1, 18), (255, 255, 255))
    for x, y in ((sx - 5, 15), (sx + 5, 16), (sx, 13)):  # sparkle
        s.set_at((x, y), (255, 255, 255))
    # Fenn, the ranger bean, at 2x from the game's sprite
    sprite = json.loads((ROOT / "assets" / "sprites" / "sprites.json").read_text(encoding="utf-8"))["ranger"]
    bean = pygame.Surface((sprite["w"], sprite["h"]), pygame.SRCALPHA)
    for y, row in enumerate(sprite["rows"]):
        for x, ch in enumerate(row):
            if ch != ".":
                bean.set_at((x, y), (*hx(sprite["pal"][ch]), 255))
    big = pygame.transform.scale(bean, (sprite["w"] * 2, sprite["h"] * 2))
    shadow = pygame.Surface((22, 4), pygame.SRCALPHA)
    pygame.draw.ellipse(shadow, (60, 40, 30, 110), shadow.get_rect())
    s.blit(shadow, (7, 41))
    s.blit(big, (3, 44 - sprite["h"] * 2))
    return s


def padded(pygame, src, size: int, safe: float = 1.0):
    """Largest integer upscale that fits `size * safe`, centred; the border repeats the edge pixels,
    so sky and soil simply run on to the edge of the icon."""
    w = src.get_width()
    k = max(1, int(size * safe) // w)
    off = (size - w * k) // 2
    out = pygame.Surface((size, size))
    for y in range(size):
        sy = min(w - 1, max(0, (y - off) // k))
        for x in range(size):
            out.set_at((x, y), src.get_at((min(w - 1, max(0, (x - off) // k)), sy)))
    return out


def main():
    os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
    import pygame

    pygame.init()
    m = master(pygame)
    out = ROOT / "web" / "icons"
    out.mkdir(parents=True, exist_ok=True)
    # Full-bleed and opaque: iOS and Android round or cut the corners themselves.
    pygame.image.save(padded(pygame, m, 180), str(out / "apple-touch-icon.png"))
    pygame.image.save(padded(pygame, m, 192), str(out / "icon-192.png"))
    pygame.image.save(padded(pygame, m, 512), str(out / "icon-512.png"))
    # Android "maskable": the launcher may cut a circle, so the art stays inside the inner 80 %.
    pygame.image.save(padded(pygame, m, 512, safe=0.8), str(out / "icon-maskable-512.png"))
    pygame.image.save(padded(pygame, m, 48), str(out / "favicon-48.png"))
    pygame.image.save(pygame.transform.smoothscale(m, (32, 32)), str(out / "favicon-32.png"))
    pygame.image.save(pygame.transform.scale(m, (M * 6, M * 6)), str(ROOT / "docs" / "art" / "logo_preview.png"))
    print("wrote", ", ".join(sorted(p.name for p in out.iterdir())))


if __name__ == "__main__":
    main()
