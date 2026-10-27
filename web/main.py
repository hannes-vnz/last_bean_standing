"""Browser entry point for pygbag. `python tools/build_web.py` copies this next to the package and data."""

import asyncio

import pygame  # noqa: F401  pygbag only loads pygame when main.py imports it directly

from lastbean.app import run

asyncio.run(run())
