"""`python -m lastbean` starts the game."""

from __future__ import annotations

import argparse
import asyncio


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="lastbean", description="Last Bean Standing")
    parser.add_argument("--seed", type=int, default=None, help="fixed seed (default: random per run)")
    parser.add_argument("--frames", type=int, default=None, help="quit after N frames (smoke test)")
    args = parser.parse_args(argv)

    from .app import run

    asyncio.run(run(seed=args.seed, max_frames=args.frames))


if __name__ == "__main__":
    main()
