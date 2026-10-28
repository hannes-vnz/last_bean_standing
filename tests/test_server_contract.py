"""The same HTTP contract for both leaderboard servers: server/app.py (reference) and worker/ (Cloudflare).

Each server is started locally on a free port; the worker needs `npm install` in worker/ (skipped otherwise).
Behaviour that depends on server settings (rate limit, version lock, time filters) is unit-tested in server/tests.
"""

import asyncio
import os
import shutil
import socket
import subprocess
import sys
import time
import uuid
from pathlib import Path

import pytest

from lastbean.online import http

ROOT = Path(__file__).resolve().parents[1]
WRANGLER = ROOT / "worker" / "node_modules" / ".bin" / "wrangler"


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def wait_healthy(url: str, proc: subprocess.Popen, seconds: float = 40) -> None:
    deadline = time.time() + seconds
    while time.time() < deadline:
        if proc.poll() is not None:
            pytest.fail(f"server exited with {proc.returncode}")
        if asyncio.run(http.request("GET", url + "/v1/health"))[0] == 200:
            return
        time.sleep(0.2)
    proc.kill()
    pytest.fail("server did not start")


@pytest.fixture(params=["python", "worker"], scope="module")
def server(request, tmp_path_factory):
    tmp = tmp_path_factory.mktemp(request.param)
    port = free_port()
    if request.param == "python":
        pytest.importorskip("fastapi")
        pytest.importorskip("uvicorn")
        env = dict(os.environ, LEADERBOARD_DB=str(tmp / "lb.db"), ADMIN_TOKEN="geheim", RATE_LIMIT_PER_MIN="1000")
        cmd = [sys.executable, "-m", "uvicorn", "app:app", "--host", "127.0.0.1", "--port", str(port)]
        proc = subprocess.Popen([*cmd, "--log-level", "warning"], cwd=ROOT / "server", env=env)
    else:
        if not WRANGLER.exists() or shutil.which("node") is None:
            pytest.skip("worker: run `npm install` in worker/ first")
        persist = str(tmp / "d1")
        subprocess.run([str(WRANGLER), "d1", "migrations", "apply", "last-bean-standing", "--local", "--persist-to",
                        persist], cwd=ROOT / "worker", check=True, capture_output=True)  # fmt: skip
        cmd = [str(WRANGLER), "dev", "--local", "--ip", "127.0.0.1", "--port", str(port), "--persist-to", persist,
               "--var", "ADMIN_TOKEN:geheim", "--var", "RATE_LIMIT_PER_MIN:1000",
               "--var", "ALLOWED_ORIGINS:*"]  # fmt: skip
        proc = subprocess.Popen(cmd, cwd=ROOT / "worker", stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    url = f"http://127.0.0.1:{port}"
    wait_healthy(url, proc)
    yield url
    proc.terminate()
    try:
        proc.wait(10)
    except subprocess.TimeoutExpired:
        proc.kill()


def call(method, url, body=None, headers=None):
    return asyncio.run(http.request(method, url, body, headers))


def payload(**kw):
    base = dict(run_id=str(uuid.uuid4()), client_token="a" * 32, name="Hannes", character="ranger", mode="normal",
                score=3000, seconds=300, wave=11, kills=400, level=9, bosses=1, difficulty=1.0, swarm_seconds=0,
                victory=False, version="0.6.0")  # fmt: skip
    base.update(kw)
    return base


def board(url, query=""):
    status, data = call("GET", url + "/v1/leaderboard" + query)
    assert status == 200, data
    return data["entries"]


def wipe(url):
    for token in "abcmnz":
        call("DELETE", url + "/v1/me", None, {"X-Client-Token": token * 32})


@pytest.fixture
def srv(server):
    wipe(server)
    yield server
    wipe(server)


def test_submit_and_rank(srv):
    s, d = call("POST", srv + "/v1/scores", payload(score=3000))
    assert s == 200 and d["rank_overall"] == 1 and d["rank_character"] == 1
    s, d = call("POST", srv + "/v1/scores", payload(score=3300, name="Kumpel", client_token="b" * 32))
    assert d["rank_overall"] == 1
    s, d = call("POST", srv + "/v1/scores", payload(score=2000, name="Dritter", client_token="c" * 32))
    assert d["rank_overall"] == 3


def test_sorted_and_filtered(srv):
    for score, ch, tok in [(2500, "ranger", "a"), (3300, "pyro", "b"), (2900, "pyro", "c")]:
        assert call("POST", srv + "/v1/scores", payload(score=score, character=ch, client_token=tok * 32))[0] == 200
    entries = board(srv)
    assert [e["score"] for e in entries] == [3300, 2900, 2500] and entries[0]["rank"] == 1
    assert set(entries[0]) >= {"rank", "name", "character", "score", "seconds", "wave", "kills", "level", "created_at"}
    assert [e["score"] for e in board(srv, "?character=pyro")] == [3300, 2900]
    assert board(srv, "?mode=eternal_night") == []
    assert len(board(srv, "?period=week")) == 3
    assert call("GET", srv + "/v1/leaderboard?character=gibtsnicht")[0] == 422


def test_tie_goes_to_shorter_run(srv):
    call("POST", srv + "/v1/scores", payload(score=3000, seconds=300, name="Lang"))
    call("POST", srv + "/v1/scores", payload(score=3000, seconds=290, wave=10, name="Kurz", client_token="b" * 32))
    assert [e["name"] for e in board(srv)] == ["Kurz", "Lang"]


def test_idempotent_by_run_id(srv):
    p = payload()
    a, b = call("POST", srv + "/v1/scores", p)[1], call("POST", srv + "/v1/scores", p)[1]
    assert a["id"] == b["id"] and len(board(srv)) == 1
    assert call("POST", srv + "/v1/scores", dict(p, client_token="z" * 32))[0] == 409


@pytest.mark.parametrize(
    "kw",
    [dict(score=900000), dict(kills=20000), dict(wave=40), dict(name="<script>"), dict(character="x"),
     dict(swarm_seconds=500), dict(bosses=12), dict(seconds=0), dict(run_id="kurz"), dict(victory="ja")],
)  # fmt: skip
def test_implausible_is_rejected(srv, kw):
    assert call("POST", srv + "/v1/scores", payload(**kw))[0] == 422


def test_flood_from_minute_three_and_eternal_night_points(srv):
    # The flood starts when the first 3:00 bed runs out; eternal night pays 1.5 times the points.
    assert call("POST", srv + "/v1/scores", payload(seconds=300, swarm_seconds=110, wave=11))[0] == 200
    assert call("POST", srv + "/v1/scores", payload(seconds=300, swarm_seconds=130, wave=11))[0] == 422
    assert call("POST", srv + "/v1/scores", payload(score=3500, mode="eternal_night", client_token="n" * 32))[0] == 200
    assert call("POST", srv + "/v1/scores", payload(score=3500, mode="normal", client_token="m" * 32))[0] == 422


def test_difficulty_allows_more_points(srv):
    assert call("POST", srv + "/v1/scores", payload(score=4200, difficulty=1.0))[0] == 422
    assert call("POST", srv + "/v1/scores", payload(score=4200, difficulty=2.0))[0] == 200


def test_delete_own_entries(srv):
    call("POST", srv + "/v1/scores", payload(client_token="m" * 32))
    call("POST", srv + "/v1/scores", payload(client_token="n" * 32))
    assert call("DELETE", srv + "/v1/me", None, {"X-Client-Token": "m" * 32}) == (200, {"deleted": 1})
    assert len(board(srv)) == 1


def test_moderation_needs_token(srv):
    sid = call("POST", srv + "/v1/scores", payload())[1]["id"]
    assert call("DELETE", f"{srv}/v1/scores/{sid}", None, {"X-Admin-Token": "falsch"})[0] == 403
    assert call("DELETE", f"{srv}/v1/scores/{sid}", None, {"X-Admin-Token": "geheim"})[0] == 200
    assert board(srv) == []
