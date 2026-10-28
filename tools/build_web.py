"""Build the browser version with pygbag.

Usage: python tools/build_web.py [--serve]
Stages web/main.py, src/lastbean and data/ in build/web-src and runs pygbag there.
The result is build/web-src/build/web (index.html plus the packed game, app icons and manifest), ready for GitHub Pages.
`--serve` starts pygbag's local test server on http://localhost:8000 instead of only building.
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STAGE = ROOT / "build" / "web-src"


def stage() -> None:
    if STAGE.exists():
        shutil.rmtree(STAGE)
    STAGE.mkdir(parents=True)
    shutil.copy(ROOT / "web" / "main.py", STAGE / "main.py")
    ignore = shutil.ignore_patterns("__pycache__", "*.pyc")
    shutil.copytree(ROOT / "src" / "lastbean", STAGE / "lastbean", ignore=ignore)
    shutil.copytree(ROOT / "data", STAGE / "data", ignore=ignore)
    shutil.copytree(ROOT / "assets", STAGE / "assets", ignore=ignore)
    # Optional extras (RL, bots) stay out of the web build when they grow dependencies.


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--serve", action="store_true")
    args = ap.parse_args()
    stage()
    # web/template.tmpl is pygbag's default page (0.9.3) with the canvas kept at 16:9 instead of stretched.
    cmd = [
        sys.executable,
        "-m",
        "pygbag",
        "--title",
        "Last Bean Standing",
        "--template",
        str(ROOT / "web" / "template.tmpl"),
    ]
    cmd += [] if args.serve else ["--build"]
    subprocess.run([*cmd, str(STAGE)], check=True, cwd=ROOT)
    if not args.serve:
        index = STAGE / "build" / "web" / "index.html"
        index.write_text(
            index.read_text(encoding="utf-8").replace("LBS_BEAN_DATA_URI", bean_data_uri()), encoding="utf-8"
        )
        # App icon and manifest for "Zum Home-Bildschirm" (made by tools/sprites/logo.py)
        shutil.copytree(ROOT / "web" / "icons", index.parent / "icons", dirs_exist_ok=True)
        shutil.copy(ROOT / "web" / "manifest.webmanifest", index.parent / "manifest.webmanifest")
    print("web build:", STAGE / "build" / "web")


def bean_data_uri() -> str:
    """Fenn's sprite as an inline PNG for the loading screen (shown before Python is ready)."""
    import base64
    import json
    import os

    os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
    import pygame

    sprite = json.loads((ROOT / "assets" / "sprites" / "sprites.json").read_text(encoding="utf-8"))["ranger"]
    surf = pygame.Surface((sprite["w"], sprite["h"]), pygame.SRCALPHA)
    for y, row in enumerate(sprite["rows"]):
        for x, ch in enumerate(row):
            if ch != ".":
                surf.set_at((x, y), pygame.Color(sprite["pal"][ch]))
    path = STAGE / "bean.png"
    pygame.image.save(surf, str(path))
    return "data:image/png;base64," + base64.b64encode(path.read_bytes()).decode("ascii")


if __name__ == "__main__":
    main()
