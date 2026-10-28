"""Player profile: nickname, local token, highscores, totals. Stored behind a small interface.

Desktop stores `profile.json` in a user folder, the browser build uses localStorage
(DESIGN.md sections 17 and 18). An export/import code lets players move their profile,
because browser storage only lives on one device and can be cleared.
"""

from __future__ import annotations

import base64
import json
import os
import re
import secrets
import sys
import zlib
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Protocol

SCHEMA_VERSION = 1
# Same rule as the leaderboard server (server/app.py NAME_RE).
NAME_RE = re.compile(r"^[A-Za-z0-9ÄÖÜäöüß _\-.]{2,16}$")
RECENT_RUNS = 10
EXPORT_PREFIX = "LBS1:"


def new_profile() -> dict[str, Any]:
    return normalize({})


def normalize(data: Any) -> dict[str, Any]:
    """Fill in missing fields and drop wrong types, so old or hand-edited profiles keep working."""
    if not isinstance(data, dict):
        data = {}
    out: dict[str, Any] = {"schema_version": SCHEMA_VERSION}
    nick = data.get("nickname")
    out["nickname"] = nick if isinstance(nick, str) and NAME_RE.match(nick) else None
    token = data.get("token")
    out["token"] = token if isinstance(token, str) and len(token) >= 16 else secrets.token_hex(16)
    hs = data.get("highscores") if isinstance(data.get("highscores"), dict) else {}
    overall = hs.get("overall")
    by_char = hs.get("by_character") if isinstance(hs.get("by_character"), dict) else {}
    out["highscores"] = {
        "overall": overall if _is_entry(overall) else None,
        "by_character": {k: v for k, v in by_char.items() if isinstance(k, str) and _is_entry(v)},
    }
    totals = data.get("totals") if isinstance(data.get("totals"), dict) else {}
    out["totals"] = {k: _num(totals.get(k)) for k in ("runs", "seconds", "kills", "bosses")}
    recent = data.get("recent") if isinstance(data.get("recent"), list) else []
    out["recent"] = [r for r in recent if _is_entry(r)][:RECENT_RUNS]
    pending = data.get("pending_submissions")
    out["pending_submissions"] = [r for r in pending if isinstance(r, dict)] if isinstance(pending, list) else []
    online = data.get("online") if isinstance(data.get("online"), dict) else {}
    best_rank = online.get("best_rank")
    out["online"] = {"best_rank": best_rank if isinstance(best_rank, int) and best_rank > 0 else None}
    return out


def _is_entry(e: Any) -> bool:
    return isinstance(e, dict) and isinstance(e.get("score"), int) and isinstance(e.get("character"), str)


def _num(v: Any) -> int:
    return v if isinstance(v, int) and not isinstance(v, bool) and v >= 0 else 0


def valid_nickname(name: str) -> bool:
    return bool(NAME_RE.match(name.strip()))


def set_nickname(profile: dict[str, Any], name: str) -> None:
    name = name.strip()
    if not valid_nickname(name):
        raise ValueError("Spitzname: 2 bis 16 Zeichen (Buchstaben, Ziffern, Leerzeichen, _ - .)")
    profile["nickname"] = name


def record_run(profile: dict[str, Any], result: dict[str, Any], when: datetime | None = None) -> dict[str, bool]:
    """Add a finished run (RunResult.to_dict()). Returns which highscores it beat."""
    entry = {
        "score": int(result["score"]),
        "seconds": int(result["seconds"]),
        "kills": int(result["kills"]),
        "level": int(result["level"]),
        "bosses": int(result["bosses"]),
        "wave": int(result["wave"]),
        "character": str(result["character"]),
        "seed": int(result["seed"]),
        "date": (when or datetime.now(UTC)).strftime("%Y-%m-%d"),
    }
    hs = profile["highscores"]
    new_best = _better(entry, hs["overall"])
    new_char_best = _better(entry, hs["by_character"].get(entry["character"]))
    if new_best:
        hs["overall"] = entry
    if new_char_best:
        hs["by_character"][entry["character"]] = entry
    t = profile["totals"]
    t["runs"] += 1
    t["seconds"] += entry["seconds"]
    t["kills"] += entry["kills"]
    t["bosses"] += entry["bosses"]
    profile["recent"] = [entry, *profile["recent"]][:RECENT_RUNS]
    return {"new_best": new_best, "new_character_best": new_char_best}


def _better(entry: dict, best: dict | None) -> bool:
    """More points wins; on a tie the shorter run wins (same rule as the online leaderboard)."""
    if best is None:
        return True
    return (entry["score"], -entry["seconds"]) > (best["score"], -best["seconds"])


def export_code(profile: dict[str, Any]) -> str:
    raw = json.dumps(profile, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    return EXPORT_PREFIX + base64.urlsafe_b64encode(zlib.compress(raw, 9)).decode("ascii")


def import_code(code: str) -> dict[str, Any]:
    code = "".join(code.split())
    if not code.startswith(EXPORT_PREFIX):
        raise ValueError("Kein Spielstand-Code von Last Bean Standing")
    try:
        raw = zlib.decompress(base64.urlsafe_b64decode(code[len(EXPORT_PREFIX) :].encode("ascii")))
        return normalize(json.loads(raw.decode("utf-8")))
    except (ValueError, zlib.error, UnicodeDecodeError) as exc:
        raise ValueError("Spielstand-Code ist beschädigt") from exc


# ---------------------------------------------------------------------------- storage


class ProfileStore(Protocol):
    def load(self) -> dict[str, Any]: ...

    def save(self, profile: dict[str, Any]) -> None: ...


class MemoryProfileStore:
    """For tests and headless runs."""

    def __init__(self) -> None:
        self._data: str | None = None

    def load(self) -> dict[str, Any]:
        return normalize(json.loads(self._data)) if self._data else new_profile()

    def save(self, profile: dict[str, Any]) -> None:
        self._data = json.dumps(profile)


class FileProfileStore:
    """JSON file on disk, written atomically. A broken file is kept as backup and a fresh profile starts."""

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
        return normalize(data)

    def save(self, profile: dict[str, Any]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(profile, ensure_ascii=False, indent=1), encoding="utf-8")
        os.replace(tmp, self.path)


class BrowserProfileStore:
    """localStorage of the page (pygbag). Lives only in this browser on this device."""

    KEY = "last-bean-standing/profile"

    def __init__(self, storage=None) -> None:
        if storage is None:
            import platform  # pygbag's bridge to the browser, only present in the web build

            storage = platform.window.localStorage
        self.storage = storage

    def load(self) -> dict[str, Any]:
        raw = self.storage.getItem(self.KEY)
        if not raw:
            return new_profile()
        try:
            return normalize(json.loads(str(raw)))
        except json.JSONDecodeError:
            self.storage.setItem(self.KEY + ".broken", str(raw))
            return new_profile()

    def save(self, profile: dict[str, Any]) -> None:
        self.storage.setItem(self.KEY, json.dumps(profile, ensure_ascii=False))


def default_profile_path() -> Path:
    base = os.environ.get("XDG_DATA_HOME") or (Path.home() / ".local" / "share")
    return Path(base) / "last-bean-standing" / "profile.json"


def default_store() -> ProfileStore:
    """Browser: localStorage; desktop: profile.json. If storage is unavailable the game still runs (in memory)."""
    try:
        if sys.platform == "emscripten":
            return BrowserProfileStore()
        return FileProfileStore(default_profile_path())
    except Exception as exc:  # noqa: BLE001 - any storage problem must not stop the game
        print("Spielstand nur im Speicher:", exc)
        return MemoryProfileStore()
