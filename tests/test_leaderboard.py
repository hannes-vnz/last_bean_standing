"""Leaderboard client: payload, queue, error handling, and a real round trip against server/app.py."""

import asyncio
import os
import socket
import subprocess
import sys
import time
from pathlib import Path

import pytest

from lastbean.meta.profile import new_profile, set_nickname
from lastbean.online import http
from lastbean.online.leaderboard import Leaderboard, build_submission

ROOT = Path(__file__).resolve().parents[1]


def result(score=1234, seconds=200, kills=150, level=6, wave=6):
    return dict(score=score, seconds=seconds, kills=kills, level=level, bosses=0, wave=wave, character="ranger",
                seed=42, difficulty=1.0, swarm_seconds=0, victory=False)  # fmt: skip


def profile(name="Fenn"):
    p = new_profile()
    set_nickname(p, name)
    return p


def test_submission_payload_matches_server_rules():
    p = profile()
    s = build_submission(result(wave=6), p)
    assert s["wave"] == 7  # server counts waves from 1
    assert s["name"] == "Fenn" and s["client_token"] == p["token"] and len(s["run_id"]) == 24
    assert build_submission(result(seconds=0), p)["seconds"] == 1


def test_queue_needs_nickname_and_is_capped():
    lb = Leaderboard("http://example.invalid")
    p = new_profile()
    assert lb.queue(p, result()) is None and p["pending_submissions"] == []
    set_nickname(p, "Mira")
    for _ in range(60):
        lb.queue(p, result())
    assert len(p["pending_submissions"]) == 50


class FakeServer:
    def __init__(self, *responses):
        self.responses = list(responses)
        self.calls = []

    async def __call__(self, method, url, body=None, headers=None):
        self.calls.append((method, url, body))
        return self.responses.pop(0)


def test_sync_handles_answers():
    p = profile()
    for _ in range(4):
        Leaderboard("http://x").queue(p, result())
    fake = FakeServer(
        (200, {"rank_overall": 3, "rank_character": 1}),
        (422, {"detail": "Punkte passen nicht"}),
        (429, {"detail": "zu viele Anfragen"}),
    )
    report = asyncio.run(Leaderboard("http://x", fake).sync(p))
    assert report.sent == 1 and report.dropped == 1 and report.last_rank == 3
    assert len(p["pending_submissions"]) == 2  # rate-limited ones stay for later
    assert p["online"]["best_rank"] == 3
    report = asyncio.run(Leaderboard("http://x", FakeServer((0, None))).sync(p))
    assert report.offline and len(p["pending_submissions"]) == 2


def test_disabled_without_url():
    lb = Leaderboard("")
    assert not lb.enabled
    assert asyncio.run(lb.top()) is None
    assert asyncio.run(lb.sync(profile())).offline


def test_offline_server_keeps_queue():
    p = profile()
    lb = Leaderboard(f"http://127.0.0.1:{free_port()}")
    lb.queue(p, result())
    report = asyncio.run(lb.sync(p))
    assert report.offline and len(p["pending_submissions"]) == 1


def test_chunked_response_parsing():
    raw = b'HTTP/1.1 200 OK\r\nTransfer-Encoding: chunked\r\n\r\n5\r\n{"a":\r\n2\r\n1}\r\n0\r\n\r\n'
    assert http._parse_response(raw) == (200, {"a": 1})


# ---------------------------------------------------------------------------- real server


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture
def server(tmp_path):
    pytest.importorskip("fastapi")
    pytest.importorskip("uvicorn")
    port = free_port()
    env = dict(os.environ, LEADERBOARD_DB=str(tmp_path / "lb.db"), RATE_LIMIT_PER_MIN="1000")
    proc = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "uvicorn",
            "app:app",
            "--host",
            "127.0.0.1",
            "--port",
            str(port),
            "--log-level",
            "warning",
        ],
        cwd=ROOT / "server",
        env=env,
    )
    url = f"http://127.0.0.1:{port}"
    deadline = time.time() + 15
    while time.time() < deadline:
        status, _ = asyncio.run(http.request("GET", url + "/v1/health"))
        if status == 200:
            break
        time.sleep(0.1)
    else:
        proc.kill()
        pytest.fail("server did not start")
    yield url
    proc.terminate()
    proc.wait(5)


def test_round_trip_with_reference_server(server, make_config):
    from lastbean.bots import heuristic_input
    from lastbean.sim import World

    lb = Leaderboard(server)
    me, friend = profile("Hannes"), profile("Kumpel")
    w = World(9, make_config())
    while not w.over and w.time_s < 120:
        w.step([heuristic_input(w)])
    real = w.result().to_dict()  # a genuine run must pass the server's plausibility checks
    lb.queue(me, real)
    report = asyncio.run(lb.sync(me))
    assert report.sent == 1 and report.last_rank == 1, report
    lb.queue(friend, {**real, "score": real["score"] - 10})
    assert asyncio.run(lb.sync(friend)).last_rank == 2
    lb.queue(friend, {**real, "score": 10**7})  # impossible score: rejected and dropped
    report = asyncio.run(lb.sync(friend))
    assert report.dropped == 1 and not friend["pending_submissions"]
    top = asyncio.run(lb.top())
    assert [e["name"] for e in top] == ["Hannes", "Kumpel"]
    assert asyncio.run(lb.top(period="week"))[0]["name"] == "Hannes"
    assert asyncio.run(lb.delete_mine(me)) == 1
    assert [e["name"] for e in asyncio.run(lb.top())] == ["Kumpel"]
