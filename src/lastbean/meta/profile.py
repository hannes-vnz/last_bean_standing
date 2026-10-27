"""Save game storage behind a small interface (DESIGN.md sections 17 and 18).

Desktop stores `profile.json` in a user folder; the browser build and a later cloud
save get their own `ProfileStore`. The profile content itself arrives in M5.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Protocol

SCHEMA_VERSION = 1


def new_profile() -> dict[str, Any]:
    return {"schema_version": SCHEMA_VERSION}


class ProfileStore(Protocol):
    def load(self) -> dict[str, Any]: ...

    def save(self, profile: dict[str, Any]) -> None: ...


class MemoryProfileStore:
    """For tests and headless runs."""

    def __init__(self) -> None:
        self._data: str | None = None

    def load(self) -> dict[str, Any]:
        return json.loads(self._data) if self._data else new_profile()

    def save(self, profile: dict[str, Any]) -> None:
        self._data = json.dumps(profile)


class FileProfileStore:
    """JSON file on disk. A missing or broken file yields a fresh profile (the broken one is kept)."""

    def __init__(self, path: Path | str) -> None:
        self.path = Path(path)

    def load(self) -> dict[str, Any]:
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            return new_profile()
        except (json.JSONDecodeError, UnicodeDecodeError):
            self.path.replace(self.path.with_suffix(".broken.json"))
            return new_profile()
        if not isinstance(data, dict) or not isinstance(data.get("schema_version"), int):
            return new_profile()
        return data

    def save(self, profile: dict[str, Any]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(profile, ensure_ascii=False, indent=1), encoding="utf-8")
        os.replace(tmp, self.path)


def default_profile_path() -> Path:
    base = os.environ.get("XDG_DATA_HOME") or (Path.home() / ".local" / "share")
    return Path(base) / "last-bean-standing" / "profile.json"
