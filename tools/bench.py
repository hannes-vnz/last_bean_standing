"""Measure headless simulation speed in steps per second.

Usage: python tools/bench.py [--seconds 600]
"""

from __future__ import annotations

import argparse
import time

from lastbean.data import load_content
from lastbean.sim import TICK_HZ, PlayerInput, Rng, World, WorldConfig


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--seconds", type=int, default=600, help="simulated game seconds")
    args = ap.parse_args()
    steps = args.seconds * TICK_HZ
    rng = Rng(1)
    inputs = [[PlayerInput(0, rng.randint(-1, 1), rng.randint(-1, 1))] for _ in range(steps)]
    world = World(1, WorldConfig.from_content(load_content()))
    t0 = time.perf_counter()
    for inp in inputs:
        world.step(inp)
    dt = time.perf_counter() - t0
    print(f"{steps} steps in {dt:.3f} s = {steps / dt:,.0f} steps/s ({steps / dt / TICK_HZ:,.0f}x real time)")


if __name__ == "__main__":
    main()
