"""Build the browser version with pygbag.

Usage: python tools/build_web.py [--serve]
Stages web/main.py, src/lastbean and data/ in build/web-src and runs pygbag there.
The result is build/web-src/build/web (index.html plus the packed game), ready for GitHub Pages.
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
    # Optional extras (RL, bots) stay out of the web build when they grow dependencies.


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--serve", action="store_true")
    args = ap.parse_args()
    stage()
    cmd = [sys.executable, "-m", "pygbag", "--title", "Last Bean Standing"]
    cmd += [] if args.serve else ["--build"]
    subprocess.run([*cmd, str(STAGE)], check=True, cwd=ROOT)
    print("web build:", STAGE / "build" / "web")


if __name__ == "__main__":
    main()
