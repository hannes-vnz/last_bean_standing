"""Record a gameplay GIF for the README: the heuristic bot plays headless, effects included.

Usage: python tools/make_gif.py [--start 270] [--seconds 30] [--fps 10] [--out docs/media/gameplay.gif]
Needs Pillow (dev only). The bot is kept alive (HP never drops below 25) so the clip shows the
interesting part of the run; everything else is the normal game.
"""

from __future__ import annotations

import argparse
import os
from pathlib import Path

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame  # noqa: E402
from PIL import Image  # noqa: E402

from lastbean.bots import heuristic_input  # noqa: E402
from lastbean.data import load_content  # noqa: E402
from lastbean.render.effects import Effects  # noqa: E402
from lastbean.render.renderer import Renderer, effect_palette  # noqa: E402
from lastbean.sim import TICK_HZ, World, WorldConfig  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--start", type=float, default=270.0, help="game second where the clip starts")
    ap.add_argument("--seconds", type=float, default=30.0)
    ap.add_argument("--fps", type=int, default=10)
    ap.add_argument("--out", default=str(ROOT / "docs" / "media" / "gameplay.gif"))
    args = ap.parse_args()

    content = load_content()
    pygame.init()
    pygame.display.set_mode((1, 1))
    renderer = Renderer(content)
    effects = Effects(*effect_palette(renderer))
    world = World(args.seed, WorldConfig.from_content(content))
    every = TICK_HZ // args.fps
    frames: list[Image.Image] = []
    end = args.start + args.seconds
    while world.time_s < end:
        p = world.players[0]
        p.hp = max(p.hp, 25.0)
        events = world.step([heuristic_input(world)])
        if world.time_s < args.start - 2:
            continue
        effects.handle(events, renderer.boss_names, {q.player_id: (q.x, q.y) for q in world.players})
        effects.update()
        if world.time_s >= args.start and world.tick % every == 0:
            canvas = renderer.draw(world.snapshot(), effects=effects)
            raw = pygame.image.tobytes(canvas, "RGB")
            frames.append(Image.frombytes("RGB", canvas.get_size(), raw).quantize(64))
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    frames[0].save(out, save_all=True, append_images=frames[1:], duration=1000 // args.fps, loop=0, optimize=True)
    print(f"{out}: {len(frames)} frames, {out.stat().st_size / 1e6:.1f} MB")


if __name__ == "__main__":
    main()
