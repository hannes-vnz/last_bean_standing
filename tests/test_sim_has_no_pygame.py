import ast
import subprocess
import sys
from pathlib import Path

SRC = Path(__file__).resolve().parents[1] / "src" / "lastbean"
HEADLESS = ("sim", "data", "meta")


def test_headless_packages_do_not_import_pygame_statically():
    offenders = []
    for pkg in HEADLESS:
        for path in (SRC / pkg).rglob("*.py"):
            tree = ast.parse(path.read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                names = []
                if isinstance(node, ast.Import):
                    names = [a.name for a in node.names]
                elif isinstance(node, ast.ImportFrom) and node.module:
                    names = [node.module]
                if any(n.split(".")[0] == "pygame" for n in names):
                    offenders.append(str(path.relative_to(SRC)))
    assert offenders == []


def test_running_the_simulation_does_not_load_pygame():
    code = (
        "import sys\n"
        "from lastbean.data import load_content\n"
        "from lastbean.sim import World, WorldConfig, PlayerInput\n"
        "w = World(7, WorldConfig.from_content(load_content()))\n"
        "for _ in range(120): w.step([PlayerInput(0, 1, 0)])\n"
        "assert 'pygame' not in sys.modules, 'pygame was imported'\n"
    )
    subprocess.run([sys.executable, "-c", code], check=True)
