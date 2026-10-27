"""`tools/build_content.py` is the source of the data. Running it must not change anything tracked."""

import hashlib
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GENERATED = sorted((ROOT / "data").glob("*.json")) + [ROOT / "docs" / "CONTENT.md"]


def digest() -> dict[str, str]:
    return {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in GENERATED}


def test_build_content_is_reproducible():
    before = digest()
    subprocess.run([sys.executable, str(ROOT / "tools" / "build_content.py")], check=True, capture_output=True)
    assert digest() == before, "data/ or docs/CONTENT.md is out of sync with tools/build_content.py"
