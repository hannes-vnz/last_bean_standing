"""Balancing runs: let the heuristic bot play many seeds headless and report when it dies.

Usage: python tools/balance.py [--seeds 20] [--limit 1200] [--random-cards] [--jobs 4]
Compare with the target curve in docs/DESIGN.md section 4 (beginners die at 3 to 5 minutes).
Reports the garden bed reached, bosses beaten, the level at each boss and wins.
--random-cards plays like a first-timer who picks cards at random (should mostly fail the first boss).
"""

from __future__ import annotations

import argparse
import statistics
import time
from multiprocessing import Pool

from lastbean.bots import first_card_input, heuristic_input, random_card_input
from lastbean.data import load_content
from lastbean.sim import BossKilled, BossSpawned, World, WorldConfig

BOTS = {"heuristic": heuristic_input, "first": first_card_input, "random": random_card_input}


def play(job: tuple[int, str, str, float]) -> tuple:
    seed, character, bot_name, limit = job
    bot = BOTS[bot_name]
    w = World(seed, WorldConfig.from_content(load_content(), character))
    spawned, killed = [], []
    while w.time_s < limit and not w.over:
        for e in w.step([bot(w)]):
            if isinstance(e, BossSpawned):
                spawned.append((round(w.time_s), w.players[0].level))
            elif isinstance(e, BossKilled):
                killed.append(round(w.time_s - spawned[-1][0]) if spawned else 0)
    p = w.players[0]
    return seed, w.time_s, p.level, p.kills, w.stage + 1, w.victory, w.bosses_killed, w.flood_s > 0, \
        w.reward_mult, spawned, killed  # fmt: skip


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--seeds", type=int, default=20)
    ap.add_argument("--limit", type=int, default=1200, help="stop a run after this many seconds")
    ap.add_argument("--character", default="ranger")
    ap.add_argument("--first-card", action="store_true", help="old baseline: always take the first card")
    ap.add_argument("--random-cards", action="store_true", help="a first-time player: random card picks")
    ap.add_argument("--jobs", type=int, default=4)
    args = ap.parse_args()

    bot = "first" if args.first_card else "random" if args.random_cards else "heuristic"
    t0 = time.perf_counter()
    jobs = [(seed, args.character, bot, args.limit) for seed in range(1, args.seeds + 1)]
    with Pool(args.jobs) as pool:
        rows = pool.map(play, jobs)
    for seed, t, level, kills, stage, victory, _bosses, flood, mult, spawned, killed in rows:
        end = "SIEG" if victory else f"Beet {stage}" + (f" Flut x{mult:.1f}" if flood else "")
        fights = zip(spawned, killed + [0] * len(spawned), strict=False)
        boss = " ".join(f"Boss@{_mmss(s)} L{lv}" + (f" {k}s" if i < len(killed) else " tot")
                        for i, ((s, lv), k) in enumerate(fights))  # fmt: skip
        print(f"seed {seed:3d}: {_mmss(t)}  level {level:2d}  kills {kills:4d}  {end:14s} {boss}")
    times = [r[1] for r in rows]
    print(
        f"\nbot ({args.character}, {bot}): median death {_mmss(statistics.median(times))}, "
        f"min {_mmss(min(times))}, max {_mmss(max(times))}, median level {statistics.median(r[2] for r in rows):.0f}"
        f", beds reached {[sum(1 for r in rows if r[4] >= b) for b in (1, 2, 3)]}"
        f", bosses beaten {[sum(1 for r in rows if r[6] >= b) for b in (1, 2, 3)]}, wins {sum(r[5] for r in rows)}"
        f"  ({time.perf_counter() - t0:.0f} s wall)"
    )


def _mmss(s: float) -> str:
    return f"{int(s) // 60}:{int(s) % 60:02d}"


if __name__ == "__main__":
    main()
