"""Measure simulation speed (and optionally drawing) with a given number of enemies.

Usage: python tools/bench.py [--seconds 60] [--enemies 200] [--render]
The player gets effectively infinite HP so the run lasts the whole measurement.
"""

from __future__ import annotations

import argparse
import dataclasses
import os
import time

from lastbean.data import load_content
from lastbean.sim import TICK_HZ, PlayerInput, Rng, World, WorldConfig


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--seconds", type=int, default=60, help="simulated game seconds")
    ap.add_argument("--enemies", type=int, default=200, help="enemies kept alive")
    ap.add_argument("--render", action="store_true", help="also draw every frame (headless pygame)")
    args = ap.parse_args()

    content = load_content()
    cfg = WorldConfig.from_content(content, enemy_target=args.enemies, max_alive_enemies=max(args.enemies, 1))
    cfg = dataclasses.replace(cfg, character=dataclasses.replace(cfg.character, hp=10**9))
    steps = args.seconds * TICK_HZ
    rng = Rng(1)
    inputs = [[PlayerInput(0, rng.randint(-1, 1), rng.randint(-1, 1), choice=0)] for _ in range(steps)]
    world = World(1, cfg)
    # Warm-up: fill the arena with enemies before measuring.
    for _ in range(TICK_HZ * 3):
        world.step()

    renderer = None
    if args.render:
        os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
        import pygame

        from lastbean.render.renderer import Renderer

        pygame.init()
        window = pygame.display.set_mode((1280, 720))
        renderer = Renderer(content)

    sim_t = draw_t = 0.0
    alive = 0
    for inp in inputs:
        t0 = time.perf_counter()
        world.step(inp)
        t1 = time.perf_counter()
        sim_t += t1 - t0
        alive += len(world.enemies)
        if renderer:
            renderer.draw(world.snapshot())
            renderer.present(window)
            draw_t += time.perf_counter() - t1

    print(
        f"enemies alive (avg): {alive / steps:.0f}, kills: {world.players[0].kills}, orbs on floor: {len(world.orbs)}"
    )
    sps = steps / sim_t
    print(f"sim:  {sps:,.0f} steps/s, {1000 / sps:.3f} ms/step ({sps / TICK_HZ:.1f}x real time)")
    if renderer:
        ms = draw_t / steps * 1000
        print(f"draw: {ms:.3f} ms/frame; sim + draw: {(sim_t + draw_t) / steps * 1000:.3f} ms of 16.7 ms budget")


if __name__ == "__main__":
    main()
