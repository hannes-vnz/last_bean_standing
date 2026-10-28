"""Balancing runs: let the heuristic bot play many seeds headless and report when it dies.

Usage: python tools/balance.py [--seeds 20] [--limit 1200]
Compare with the target curve in docs/DESIGN.md section 4 (beginners die at 3 to 5 minutes).
Reports the garden bed reached and wins (Paket F).
"""

from __future__ import annotations

import argparse
import statistics
import time

from lastbean.bots import heuristic_input
from lastbean.data import load_content
from lastbean.sim import World, WorldConfig


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--seeds", type=int, default=20)
    ap.add_argument("--limit", type=int, default=1200, help="stop a run after this many seconds")
    ap.add_argument("--character", default="ranger")
    args = ap.parse_args()

    cfg = WorldConfig.from_content(load_content(), args.character)
    t0 = time.perf_counter()
    rows = []
    for seed in range(1, args.seeds + 1):
        w = World(seed, cfg)
        while w.time_s < args.limit and not w.over:
            w.step([heuristic_input(w)])
        p = w.players[0]
        rows.append((w.time_s, p.level, p.kills, w.stage + 1, w.victory))
        end = "SIEG" if w.victory else f"Beet {w.stage + 1}" + (" Flut" if w.flood_s > 0 else "")
        print(f"seed {seed:3d}: {_mmss(w.time_s)}  level {p.level:2d}  kills {p.kills:4d}  {end}")
    times = [r[0] for r in rows]
    print(
        f"\nbot ({args.character}): median death {_mmss(statistics.median(times))}, "
        f"min {_mmss(min(times))}, max {_mmss(max(times))}, median level {statistics.median(r[1] for r in rows):.0f}"
        f", beds reached {[sum(1 for r in rows if r[3] >= b) for b in (1, 2, 3)]}, wins {sum(r[4] for r in rows)}"
        f"  ({time.perf_counter() - t0:.0f} s wall)"
    )


def _mmss(s: float) -> str:
    return f"{int(s) // 60}:{int(s) % 60:02d}"


if __name__ == "__main__":
    main()
