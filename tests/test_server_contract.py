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


# ----------------------------------------------------------------------------- accounts and cloud saves (Paket K)


def test_account_register_login_and_cloud_save(server):
    name = "Bohne" + uuid.uuid4().hex[:6]
    status, acc = call("POST", server + "/v1/account/register", {"name": name, "password": "geheim123"})
    assert status == 200 and acc["name"] == name and len(acc["session"]) >= 32
    assert call("POST", server + "/v1/account/register", {"name": name.upper(), "password": "x" * 8})[0] == 409
    assert call("POST", server + "/v1/account/register", {"name": "x", "password": "geheim123"})[0] == 422
    assert call("POST", server + "/v1/account/login", {"name": name, "password": "falsch!!"})[0] == 401
    status, again = call("POST", server + "/v1/account/login", {"name": name, "password": "geheim123"})
    assert status == 200 and again["session"] != acc["session"]
    auth = {"Authorization": "Bearer " + again["session"]}
    assert call("GET", server + "/v1/save", None, auth)[1] == {"profile": None, "updated_at": 0}
    profile = {"nickname": name, "sparkles": 42, "unlocked": {"characters": ["pyro"]}}
    status, put = call("PUT", server + "/v1/save", {"profile": profile}, auth)
    assert status == 200 and put["updated_at"] > 0
    status, got = call("GET", server + "/v1/save", None, {"Authorization": "Bearer " + acc["session"]})
    assert status == 200 and got["profile"] == profile  # every session of the account sees the same save
    assert call("GET", server + "/v1/save", None, {"Authorization": "Bearer nope"})[0] == 401
    assert call("PUT", server + "/v1/save", {"profile": "x"}, auth)[0] == 422
    assert call("POST", server + "/v1/account/logout", None, auth)[0] == 200
    assert call("GET", server + "/v1/save", None, auth)[0] == 401
    auth = {"Authorization": "Bearer " + acc["session"]}
    assert call("DELETE", server + "/v1/account", None, auth)[1] == {"deleted": True}
    assert call("POST", server + "/v1/account/login", {"name": name, "password": "geheim123"})[0] == 401


def test_google_and_apple_sign_in_wait_for_their_client_ids(server):
    status, cfg = call("GET", server + "/v1/config")
    assert status == 200 and cfg == {"google_client_id": "", "apple_client_id": ""}
    assert call("POST", server + "/v1/account/oauth", {"provider": "google", "id_token": "a.b.c"})[0] == 501


def test_two_devices_share_progress_through_the_cloud(server):
    from lastbean.meta.profile import new_profile, normalize
    from lastbean.online.account import Account, merge

    acc = Account(server)
    name = "Zwei" + uuid.uuid4().hex[:6]
    phone = new_profile()
    phone["totals"]["runs"], phone["sparkles"] = 5, 120
    phone["unlocked"]["characters"], phone["challenges_done"] = ["pyro"], ["unlock_pyro"]
    data, err = asyncio.run(acc.sign_in("register", {"name": name, "password": "bohnen!"}))
    assert data and not err
    assert asyncio.run(acc.store(data["session"], phone)) == 200
    laptop = new_profile()
    laptop["totals"]["runs"], laptop["challenges_done"] = 1, ["unlock_storm"]
    laptop["unlocked"]["characters"] = ["storm"]
    data2, _ = asyncio.run(acc.sign_in("login", {"name": name, "password": "bohnen!"}))
    status, cloud = asyncio.run(acc.load(data2["session"]))
    assert status == 200 and cloud["sparkles"] == 120 and "account" not in cloud
    both = normalize(merge(laptop, cloud))
    assert both["totals"]["runs"] == 5 and both["sparkles"] == 120  # the profile with more runs leads
    assert set(both["unlocked"]["characters"]) == {"pyro", "storm"}
    assert set(both["challenges_done"]) == {"unlock_pyro", "unlock_storm"}
    _, err = asyncio.run(acc.sign_in("login", {"name": name, "password": "falsch!!"}))
    assert err == "Name oder Passwort stimmt nicht"


# ----------------------------------------------------------------------------- passkeys (WebAuthn, Paket K)


def _b64(data: bytes) -> str:
    import base64

    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


class FakeAuthenticator:
    """What Face ID / Touch ID does in the browser: a P-256 key pair, authenticatorData and clientDataJSON."""

    def __init__(self, origin: str = "https://hannes-vnz.github.io", rp_id: str = "hannes-vnz.github.io"):
        pytest.importorskip("cryptography")
        from cryptography.hazmat.primitives.asymmetric import ec

        self.key = ec.generate_private_key(ec.SECP256R1())
        self.cred = _b64(os.urandom(20))
        self.origin, self.rp_id = origin, rp_id

    def _common(self, begin: dict, kind: str) -> tuple[bytes, bytes]:
        import hashlib
        import json

        client = json.dumps({"type": kind, "challenge": begin["challenge"], "origin": self.origin}).encode()
        auth = hashlib.sha256(self.rp_id.encode()).digest() + bytes([0x05]) + (1).to_bytes(4, "big")
        return client, auth

    def create(self, begin: dict) -> dict:
        from cryptography.hazmat.primitives import serialization

        client, auth = self._common(begin, "webauthn.create")
        spki = self.key.public_key().public_bytes(
            serialization.Encoding.DER, serialization.PublicFormat.SubjectPublicKeyInfo
        )
        return {"challenge_id": begin["challenge_id"], "credential_id": self.cred, "public_key": _b64(spki), "alg": -7,
                "authenticator_data": _b64(auth), "client_data_json": _b64(client)}  # fmt: skip

    def get(self, begin: dict) -> dict:
        import hashlib

        from cryptography.hazmat.primitives import hashes
        from cryptography.hazmat.primitives.asymmetric import ec

        client, auth = self._common(begin, "webauthn.get")
        sig = self.key.sign(auth + hashlib.sha256(client).digest(), ec.ECDSA(hashes.SHA256()))
        return {"challenge_id": begin["challenge_id"], "credential_id": self.cred, "authenticator_data": _b64(auth),
                "client_data_json": _b64(client), "signature": _b64(sig)}  # fmt: skip


def begin(server, purpose):
    status, data = call("POST", server + "/v1/passkey/begin", {"purpose": purpose})
    assert status == 200 and data["rp_id"] == "hannes-vnz.github.io", data
    return data


def test_passkey_sign_up_and_face_id_login(server):
    face = FakeAuthenticator()
    status, acc = call("POST", server + "/v1/passkey/register", face.create(begin(server, "register")))
    assert status == 200 and acc["name"] is None and len(acc["session"]) >= 32
    auth = {"Authorization": "Bearer " + acc["session"]}
    assert call("PUT", server + "/v1/save", {"profile": {"sparkles": 7}}, auth)[0] == 200
    status, again = call("POST", server + "/v1/passkey/login", face.get(begin(server, "login")))
    assert status == 200 and again["session"] != acc["session"]
    status, got = call("GET", server + "/v1/save", None, {"Authorization": "Bearer " + again["session"]})
    assert got["profile"] == {"sparkles": 7}
    used = begin(server, "login")
    assert call("POST", server + "/v1/passkey/login", face.get(used))[0] == 200
    assert call("POST", server + "/v1/passkey/login", face.get(used))[0] == 401  # a challenge works once
    bad = face.get(begin(server, "login"))
    bad["signature"] = FakeAuthenticator().get(begin(server, "login"))["signature"]
    assert call("POST", server + "/v1/passkey/login", bad)[0] == 401
    phishing = FakeAuthenticator(origin="https://boese.example")
    phishing.key, phishing.cred = face.key, face.cred
    assert call("POST", server + "/v1/passkey/login", phishing.get(begin(server, "login")))[0] == 401
    assert call("POST", server + "/v1/passkey/login", FakeAuthenticator().get(begin(server, "login")))[0] == 401


def test_passkey_added_to_a_password_account(server):
    name = "Face" + uuid.uuid4().hex[:6]
    _, acc = call("POST", server + "/v1/account/register", {"name": name, "password": "geheim123"})
    face = FakeAuthenticator()
    status, added = call("POST", server + "/v1/passkey/register", face.create(begin(server, "register")),
                         {"Authorization": "Bearer " + acc["session"]})  # fmt: skip
    assert status == 200 and added["name"] == name
    status, login = call("POST", server + "/v1/passkey/login", face.get(begin(server, "login")))
    assert status == 200 and login["name"] == name
