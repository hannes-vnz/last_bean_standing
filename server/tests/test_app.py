import importlib
import time
import uuid

import pytest
from fastapi.testclient import TestClient


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("LEADERBOARD_DB", str(tmp_path / "t.db"))
    monkeypatch.setenv("ADMIN_TOKEN", "geheim")
    monkeypatch.setenv("RATE_LIMIT_PER_MIN", "1000")
    import app as appmod
    importlib.reload(appmod)
    with TestClient(appmod.app) as c:
        yield c, appmod


def payload(**kw):
    base = dict(run_id=str(uuid.uuid4()), client_token="a" * 32, name="Hannes", character="ranger", mode="normal", score=3000,
                seconds=300, wave=11, kills=400, level=9, bosses=1, difficulty=1.0, swarm_seconds=0, victory=False, version="0.1.0")
    base.update(kw)
    return base


def test_einreichen_und_rang(client):
    c, _ = client
    r = c.post("/v1/scores", json=payload(score=3000)); assert r.status_code == 200 and r.json()["rank_overall"] == 1
    r2 = c.post("/v1/scores", json=payload(score=3300, name="Kumpel", client_token="b" * 32)); assert r2.json()["rank_overall"] == 1
    r3 = c.post("/v1/scores", json=payload(score=2000, name="Dritter", client_token="c" * 32)); assert r3.json()["rank_overall"] == 3


def test_bestenliste_sortiert_und_filtert(client):
    c, _ = client
    for score, ch, tok in [(2500, "ranger", "a"), (3300, "pyro", "b"), (2900, "pyro", "c")]:
        assert c.post("/v1/scores", json=payload(score=score, character=ch, client_token=tok * 32, name=f"S{score}")).status_code == 200
    allv = c.get("/v1/leaderboard").json()["entries"]
    assert [e["score"] for e in allv] == [3300, 2900, 2500] and allv[0]["rank"] == 1
    pyro = c.get("/v1/leaderboard", params={"character": "pyro"}).json()["entries"]
    assert [e["score"] for e in pyro] == [3300, 2900]
    assert c.get("/v1/leaderboard", params={"mode": "eternal_night"}).json()["entries"] == []
    assert c.get("/v1/leaderboard", params={"character": "gibtsnicht"}).status_code == 422


def test_zeitraum_filter(client):
    c, appmod = client
    c.post("/v1/scores", json=payload(score=2500))
    import sqlite3
    con = sqlite3.connect(appmod.db_path()); con.execute("UPDATE scores SET created_at=?", (int(time.time()) - 10 * 86400,)); con.commit(); con.close()
    assert len(c.get("/v1/leaderboard", params={"period": "week"}).json()["entries"]) == 0
    assert len(c.get("/v1/leaderboard", params={"period": "month"}).json()["entries"]) == 1


def test_doppeltes_einreichen_ist_idempotent(client):
    c, _ = client
    p = payload()
    a = c.post("/v1/scores", json=p).json(); b = c.post("/v1/scores", json=p).json()
    assert a["id"] == b["id"] and len(c.get("/v1/leaderboard").json()["entries"]) == 1
    assert c.post("/v1/scores", json=dict(p, client_token="z" * 32)).status_code == 409      # fremde run_id


@pytest.mark.parametrize("kw", [dict(score=900000), dict(kills=20000), dict(wave=40), dict(name="<script>"), dict(character="x"),
                                dict(swarm_seconds=500), dict(bosses=12)])
def test_unplausibles_wird_abgelehnt(client, kw):
    c, _ = client
    assert c.post("/v1/scores", json=payload(**kw)).status_code == 422


def test_hoehere_schwierigkeit_erlaubt_mehr_punkte(client):
    c, _ = client
    assert c.post("/v1/scores", json=payload(score=4200, difficulty=1.0)).status_code == 422
    assert c.post("/v1/scores", json=payload(score=4200, difficulty=2.0)).status_code == 200


def test_eigene_eintraege_loeschen(client):
    c, _ = client
    c.post("/v1/scores", json=payload(client_token="m" * 32)); c.post("/v1/scores", json=payload(client_token="n" * 32))
    assert c.delete("/v1/me", headers={"X-Client-Token": "m" * 32}).json() == {"deleted": 1}
    assert len(c.get("/v1/leaderboard").json()["entries"]) == 1


def test_moderation_braucht_token(client):
    c, _ = client
    sid = c.post("/v1/scores", json=payload()).json()["id"]
    assert c.delete(f"/v1/scores/{sid}", headers={"X-Admin-Token": "falsch"}).status_code == 403
    assert c.delete(f"/v1/scores/{sid}", headers={"X-Admin-Token": "geheim"}).status_code == 200
    assert c.get("/v1/leaderboard").json()["entries"] == []


def test_rate_limit(client, monkeypatch):
    c, _ = client
    monkeypatch.setenv("RATE_LIMIT_PER_MIN", "2")
    codes = [c.post("/v1/scores", json=payload()).status_code for _ in range(4)]
    assert codes.count(429) >= 1


def test_version_sperre(client, monkeypatch):
    c, _ = client
    monkeypatch.setenv("ALLOWED_VERSIONS", "0.2.0")
    assert c.post("/v1/scores", json=payload(version="0.1.0")).status_code == 422
