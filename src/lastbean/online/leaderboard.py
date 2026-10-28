"""Online leaderboard client (DESIGN.md section 19).

The game always works offline: finished runs go into a queue in the profile
(`pending_submissions`) and are sent whenever the server is reachable. `run_id` makes
re-sending safe. The server URL comes from `LBS_LEADERBOARD_URL` or `DEFAULT_URL`;
when both are empty, online features are simply switched off.
"""

from __future__ import annotations

import os
import secrets
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from .. import __version__
from . import http

# Set once the server is deployed (see server/README.md). Empty = offline only.
DEFAULT_URL = ""
REFRESH_S = 60
MAX_QUEUE = 50

Requester = Callable[..., Awaitable[tuple[int, Any]]]


def server_url() -> str:
    return os.environ.get("LBS_LEADERBOARD_URL", DEFAULT_URL).rstrip("/")


def build_submission(result: dict, profile: dict, version: str = __version__) -> dict:
    """Payload for POST /v1/scores from RunResult.to_dict() and the profile."""
    return {
        "run_id": secrets.token_hex(12),
        "client_token": profile["token"],
        "name": profile["nickname"],
        "character": result["character"],
        "mode": "normal",
        "score": int(result["score"]),
        "seconds": max(1, int(result["seconds"])),
        "wave": int(result["wave"]) + 1,  # the server counts waves from 1 (seconds // 30 + 1)
        "kills": int(result["kills"]),
        "level": int(result["level"]),
        "bosses": int(result["bosses"]),
        "difficulty": float(result["difficulty"]),
        "swarm_seconds": int(result.get("swarm_seconds", 0)),
        "victory": bool(result.get("victory", False)),
        "version": version,
        "seed": int(result["seed"]),
    }


@dataclass
class SyncReport:
    sent: int = 0
    dropped: int = 0
    offline: bool = False
    last_rank: int | None = None
    last_rank_character: int | None = None
    error: str = ""


class Leaderboard:
    def __init__(self, base_url: str | None = None, requester: Requester | None = None) -> None:
        self.base_url = (server_url() if base_url is None else base_url).rstrip("/")
        self.request = requester or http.request

    @property
    def enabled(self) -> bool:
        return bool(self.base_url)

    def queue(self, profile: dict, result: dict) -> dict | None:
        """Put a finished run into the profile's queue (only with a nickname). Returns the payload."""
        if not profile.get("nickname"):
            return None
        payload = build_submission(result, profile)
        q = profile["pending_submissions"]
        q.append(payload)
        del q[:-MAX_QUEUE]
        return payload

    async def sync(self, profile: dict) -> SyncReport:
        """Send queued runs, oldest first. Network trouble keeps them for later; rejected ones are dropped."""
        report = SyncReport()
        if not self.enabled:
            report.offline = True
            return report
        q = profile["pending_submissions"]
        while q:
            payload = q[0]
            status, data = await self.request("POST", self.base_url + "/v1/scores", payload)
            if status == 200 and isinstance(data, dict):
                q.pop(0)
                report.sent += 1
                report.last_rank = data.get("rank_overall")
                report.last_rank_character = data.get("rank_character")
                online = profile.setdefault("online", {"best_rank": None})
                if isinstance(report.last_rank, int) and (
                    online["best_rank"] is None or report.last_rank < online["best_rank"]
                ):
                    online["best_rank"] = report.last_rank
            elif status == 0 or status == 429 or status >= 500:
                report.offline = status == 0
                report.error = "Server nicht erreichbar" if status == 0 else f"Server meldet {status}"
                break
            else:  # 4xx: the server will never accept this entry (e.g. failed plausibility check)
                q.pop(0)
                report.dropped += 1
                report.error = str((data or {}).get("detail", status)) if isinstance(data, dict) else str(status)
        return report

    async def top(self, period: str = "all", character: str | None = None, limit: int = 10) -> list[dict] | None:
        """Leaderboard entries, or None when the server cannot be reached."""
        if not self.enabled:
            return None
        url = f"{self.base_url}/v1/leaderboard?mode=normal&period={period}&limit={limit}"
        if character:
            url += f"&character={character}"
        status, data = await self.request("GET", url)
        if status != 200 or not isinstance(data, dict):
            return None
        return list(data.get("entries", []))

    async def delete_mine(self, profile: dict) -> int | None:
        if not self.enabled:
            return None
        status, data = await self.request(
            "DELETE", self.base_url + "/v1/me", None, {"X-Client-Token": profile["token"]}
        )
        return int(data.get("deleted", 0)) if status == 200 and isinstance(data, dict) else None
