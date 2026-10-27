"""Referenz-Server fuer die Online-Bestenliste von Last Bean Standing.

Bewusst klein: FastAPI plus SQLite, keine Konten. Spieler haben einen Spitznamen und ein zufaelliges
Token, das nur lokal liegt (der Server speichert nur dessen Hash). Mit dem Token kann man alle eigenen
Eintraege loeschen. Ergebnisse werden auf Plausibilitaet geprueft (Stufe 1). Eine Pruefung per Replay
(Stufe 2, deterministische Simulation erneut laufen lassen) ist vorbereitet: das Feld `replay` wird gespeichert.

Start:  uvicorn app:app --host 0.0.0.0 --port 8000
Umgebungsvariablen: LEADERBOARD_DB (Pfad), ADMIN_TOKEN (Moderation), ALLOWED_ORIGINS (Komma-Liste, Standard "*"),
                    ALLOWED_VERSIONS (Komma-Liste, leer = alle), RATE_LIMIT_PER_MIN (Standard 10)
"""
from __future__ import annotations

import hashlib
import hmac
import os
import re
import sqlite3
import time
from collections import defaultdict, deque
from contextlib import asynccontextmanager, closing
from typing import Literal, Optional

from fastapi import FastAPI, Header, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, field_validator

CHARACTERS = {"ranger", "pyro", "rogue", "guardian", "cryo", "summoner", "storm", "bomber", "venom", "sniper"}
MODES = {"normal", "eternal_night"}
NAME_RE = re.compile(r"^[A-Za-z0-9ÄÖÜäöüß _\-.]{2,16}$")
PERIOD_SECONDS = {"day": 86400, "week": 7 * 86400, "month": 30 * 86400}


def db_path() -> str:
    return os.environ.get("LEADERBOARD_DB", "leaderboard.db")


def connect() -> sqlite3.Connection:
    con = sqlite3.connect(db_path())
    con.row_factory = sqlite3.Row
    return con


def init_db() -> None:
    with closing(connect()) as con:
        con.executescript("""
        CREATE TABLE IF NOT EXISTS scores (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            run_id TEXT NOT NULL UNIQUE,
            owner_hash TEXT NOT NULL,
            name TEXT NOT NULL,
            character TEXT NOT NULL,
            mode TEXT NOT NULL,
            score INTEGER NOT NULL,
            seconds INTEGER NOT NULL,
            wave INTEGER NOT NULL,
            kills INTEGER NOT NULL,
            level INTEGER NOT NULL,
            bosses INTEGER NOT NULL,
            difficulty REAL NOT NULL,
            swarm_seconds INTEGER NOT NULL,
            victory INTEGER NOT NULL,
            version TEXT NOT NULL,
            seed INTEGER,
            replay TEXT,
            verified INTEGER NOT NULL DEFAULT 0,
            created_at INTEGER NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_scores_rank ON scores (mode, character, score DESC, seconds ASC);
        CREATE INDEX IF NOT EXISTS idx_scores_owner ON scores (owner_hash);
        """)


class ScoreIn(BaseModel):
    run_id: str = Field(min_length=8, max_length=64, pattern=r"^[A-Za-z0-9\-]+$")
    client_token: str = Field(min_length=16, max_length=128)
    name: str
    character: str
    mode: Literal["normal", "eternal_night"] = "normal"
    score: int = Field(ge=0, le=100_000_000)
    seconds: int = Field(ge=1, le=7200)
    wave: int = Field(ge=1, le=300)
    kills: int = Field(ge=0, le=200_000)
    level: int = Field(ge=1, le=200)
    bosses: int = Field(ge=0, le=20)
    difficulty: float = Field(ge=1.0, le=10.0, description="Schwierigkeitsfaktor D (1.0 = Basis)")
    swarm_seconds: int = Field(ge=0, le=7200, default=0)
    victory: bool = False
    version: str = Field(min_length=1, max_length=20)
    seed: Optional[int] = None
    replay: Optional[str] = Field(default=None, max_length=200_000)

    @field_validator("name")
    @classmethod
    def _name(cls, v: str) -> str:
        v = v.strip()
        if not NAME_RE.match(v):
            raise ValueError("Name: 2 bis 16 Zeichen (Buchstaben, Ziffern, Leerzeichen, _ - .)")
        return v

    @field_validator("character")
    @classmethod
    def _char(cls, v: str) -> str:
        if v not in CHARACTERS:
            raise ValueError("unbekannter Charakter")
        return v


def max_plausible_score(s: ScoreIn) -> float:
    """Obergrenze aus der Punkteformel (siehe CONTENT.md): Zeit, Kills, Level, Bosse, Sieg, Flut, Schwierigkeit."""
    base = 2 * s.seconds + 5 * s.kills + 20 * s.level + 500 * s.bosses
    base += 20000 if s.victory else 0
    base += 1000 * (s.swarm_seconds / 10) * 8
    return base * (1 + 0.8 * (s.difficulty - 1)) * 1.02 + 50


def plausibility_error(s: ScoreIn) -> Optional[str]:
    if s.score > max_plausible_score(s):
        return "Punkte passen nicht zu Zeit, Kills und Level"
    if s.kills > s.seconds * 40:
        return "zu viele Kills fuer die Spielzeit"
    if abs(s.wave - (s.seconds // 30 + 1)) > 2 and s.swarm_seconds == 0:
        return "Welle passt nicht zur Spielzeit"
    if s.swarm_seconds > max(0, s.seconds - 1200 + 5):
        return "Flutzeit passt nicht zur Spielzeit"
    if s.bosses > 6 + (s.seconds // 900):
        return "zu viele Bosse"
    allowed = [v for v in os.environ.get("ALLOWED_VERSIONS", "").split(",") if v]
    if allowed and s.version not in allowed:
        return "Spielversion wird nicht mehr angenommen"
    return None


def owner_hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


_hits: dict[str, deque] = defaultdict(deque)


def rate_limited(key: str, limit: int, window: int = 60) -> bool:
    now = time.time()
    q = _hits[key]
    while q and now - q[0] > window:
        q.popleft()
    if len(q) >= limit:
        return True
    q.append(now)
    return False


@asynccontextmanager
async def lifespan(_app):
    init_db()
    yield


app = FastAPI(title="Last Bean Standing Bestenliste", version="0.1.0", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=os.environ.get("ALLOWED_ORIGINS", "*").split(","),
                   allow_methods=["GET", "POST", "DELETE"], allow_headers=["*"])


def _rank(con: sqlite3.Connection, score: int, seconds: int, mode: str, character: Optional[str]) -> int:
    q = "SELECT COUNT(*) FROM scores WHERE mode=? AND (score>? OR (score=? AND seconds<?))"
    args: list = [mode, score, score, seconds]
    if character:
        q += " AND character=?"; args.append(character)
    return con.execute(q, args).fetchone()[0] + 1


@app.get("/v1/health")
def health() -> dict:
    return {"ok": True}


@app.post("/v1/scores")
def submit(s: ScoreIn, request: Request) -> dict:
    ip = request.client.host if request.client else "?"
    if rate_limited("ip:" + ip, int(os.environ.get("RATE_LIMIT_PER_MIN", "10"))):
        raise HTTPException(429, "zu viele Anfragen")
    err = plausibility_error(s)
    if err:
        raise HTTPException(422, err)
    init_db()
    with closing(connect()) as con:
        row = con.execute("SELECT * FROM scores WHERE run_id=?", (s.run_id,)).fetchone()
        if row is None:
            con.execute("""INSERT INTO scores (run_id, owner_hash, name, character, mode, score, seconds, wave, kills, level, bosses,
                           difficulty, swarm_seconds, victory, version, seed, replay, created_at)
                           VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                        (s.run_id, owner_hash(s.client_token), s.name, s.character, s.mode, s.score, s.seconds, s.wave, s.kills, s.level,
                         s.bosses, s.difficulty, s.swarm_seconds, int(s.victory), s.version, s.seed, s.replay, int(time.time())))
            con.commit()
            row = con.execute("SELECT * FROM scores WHERE run_id=?", (s.run_id,)).fetchone()
        elif not hmac.compare_digest(row["owner_hash"], owner_hash(s.client_token)):
            raise HTTPException(409, "run_id gehoert einem anderen Spieler")
        return {"id": row["id"], "rank_overall": _rank(con, row["score"], row["seconds"], row["mode"], None),
                "rank_character": _rank(con, row["score"], row["seconds"], row["mode"], row["character"])}


@app.get("/v1/leaderboard")
def leaderboard(mode: str = "normal", character: Optional[str] = None, period: Literal["all", "day", "week", "month"] = "all",
                limit: int = Query(50, ge=1, le=100), offset: int = Query(0, ge=0, le=10_000)) -> dict:
    if mode not in MODES:
        raise HTTPException(422, "unbekannter Modus")
    if character is not None and character not in CHARACTERS:
        raise HTTPException(422, "unbekannter Charakter")
    init_db()
    q, args = "SELECT * FROM scores WHERE mode=?", [mode]
    if character:
        q += " AND character=?"; args.append(character)
    if period != "all":
        q += " AND created_at>=?"; args.append(int(time.time()) - PERIOD_SECONDS[period])
    q += " ORDER BY score DESC, seconds ASC, id ASC LIMIT ? OFFSET ?"
    args += [limit, offset]
    with closing(connect()) as con:
        rows = con.execute(q, args).fetchall()
    entries = [dict(rank=offset + i + 1, name=r["name"], character=r["character"], score=r["score"], seconds=r["seconds"], wave=r["wave"],
                    kills=r["kills"], level=r["level"], victory=bool(r["victory"]), swarm_seconds=r["swarm_seconds"],
                    difficulty=r["difficulty"], verified=bool(r["verified"]), created_at=r["created_at"]) for i, r in enumerate(rows)]
    return {"mode": mode, "character": character, "period": period, "entries": entries}


@app.delete("/v1/me")
def delete_me(x_client_token: str = Header(...)) -> dict:
    init_db()
    with closing(connect()) as con:
        n = con.execute("DELETE FROM scores WHERE owner_hash=?", (owner_hash(x_client_token),)).rowcount
        con.commit()
    return {"deleted": n}


@app.delete("/v1/scores/{score_id}")
def admin_delete(score_id: int, x_admin_token: str = Header(...)) -> dict:
    expected = os.environ.get("ADMIN_TOKEN", "")
    if not expected or not hmac.compare_digest(expected, x_admin_token):
        raise HTTPException(403, "kein Zugriff")
    init_db()
    with closing(connect()) as con:
        n = con.execute("DELETE FROM scores WHERE id=?", (score_id,)).rowcount
        con.commit()
    if not n:
        raise HTTPException(404, "nicht gefunden")
    return {"deleted": n}
