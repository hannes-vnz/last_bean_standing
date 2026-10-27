"""Headless simulation. Never imports pygame (tests/test_sim_has_no_pygame.py).

M0 scope: players move inside the arena on a fixed 1/60 s tick, the wave clock runs.
Enemies, projectiles and stop-and-shoot follow in M1/M2.
"""

from __future__ import annotations

import hashlib
import math
import struct
from dataclasses import dataclass, field

from .events import Event, RunStarted, WaveStarted
from .rng import Rng

TICK_HZ = 60
DT = 1.0 / TICK_HZ


@dataclass(frozen=True, slots=True)
class PlayerInput:
    """Input of one player for one tick. move_x/move_y are each -1, 0 or 1."""

    player_id: int
    move_x: int = 0
    move_y: int = 0


@dataclass(frozen=True, slots=True)
class WorldConfig:
    arena_w: float = 60 * 32.0
    arena_h: float = 60 * 32.0
    wave_interval_s: int = 30
    player_speed: float = 100.0
    player_radius: float = 8.0
    player_count: int = 1

    @classmethod
    def from_content(cls, content, character_id: str = "ranger", player_count: int = 1) -> WorldConfig:
        bal = content.balance
        char = content.character(character_id)
        return cls(
            arena_w=float(bal.arena_tiles[0] * bal.tile_px),
            arena_h=float(bal.arena_tiles[1] * bal.tile_px),
            wave_interval_s=bal.wave_interval_s,
            player_speed=float(char.speed),
            player_count=player_count,
        )


@dataclass(slots=True)
class Player:
    player_id: int
    x: float
    y: float
    vx: float = 0.0
    vy: float = 0.0
    standing: bool = True


@dataclass(slots=True)
class Snapshot:
    """Read-only view handed to the renderer."""

    tick: int
    time_s: float
    wave: int
    arena_w: float
    arena_h: float
    players: tuple[tuple[int, float, float, bool], ...]


@dataclass
class World:
    seed: int
    config: WorldConfig = field(default_factory=WorldConfig)
    tick: int = 0
    wave: int = 0
    players: list[Player] = field(default_factory=list)
    rng: Rng = field(init=False)

    def __post_init__(self) -> None:
        self.rng = Rng(self.seed)
        cx, cy = self.config.arena_w / 2, self.config.arena_h / 2
        if not self.players:
            # Players spawn next to each other in the central clearing.
            self.players = [
                Player(pid, cx + (pid - (self.config.player_count - 1) / 2) * 24.0, cy)
                for pid in range(self.config.player_count)
            ]
        self._pending: list[Event] = [RunStarted(0, None, self.seed)]

    @property
    def time_s(self) -> float:
        return self.tick / TICK_HZ

    def step(self, inputs: dict[int, PlayerInput] | list[PlayerInput] | None = None) -> list[Event]:
        """Advance one fixed tick. Missing inputs mean "stand still"."""
        if isinstance(inputs, list):
            inputs = {i.player_id: i for i in inputs}
        inputs = inputs or {}
        events, self._pending = self._pending, []
        cfg = self.config

        for p in self.players:
            inp = inputs.get(p.player_id)
            mx = _clamp_unit(inp.move_x) if inp else 0
            my = _clamp_unit(inp.move_y) if inp else 0
            if mx and my:
                # sqrt is correctly rounded in IEEE 754, so this stays bit-identical across platforms.
                inv = 1.0 / math.sqrt(2.0)
                p.vx, p.vy = mx * cfg.player_speed * inv, my * cfg.player_speed * inv
            else:
                p.vx, p.vy = mx * cfg.player_speed, my * cfg.player_speed
            p.standing = not (mx or my)
            r = cfg.player_radius
            p.x = min(max(p.x + p.vx * DT, r), cfg.arena_w - r)
            p.y = min(max(p.y + p.vy * DT, r), cfg.arena_h - r)

        self.tick += 1
        wave = self.tick // (cfg.wave_interval_s * TICK_HZ)
        if wave != self.wave:
            self.wave = wave
            events.append(WaveStarted(self.tick, None, wave))
        return events

    def snapshot(self) -> Snapshot:
        return Snapshot(
            tick=self.tick,
            time_s=self.time_s,
            wave=self.wave,
            arena_w=self.config.arena_w,
            arena_h=self.config.arena_h,
            players=tuple((p.player_id, p.x, p.y, p.standing) for p in self.players),
        )

    def state_hash(self) -> str:
        """Hash over the full simulation state, for determinism tests and later desync detection."""
        h = hashlib.sha256()
        h.update(struct.pack("<qqq", self.seed, self.tick, self.wave))
        h.update(struct.pack("<4I", *self.rng.getstate()))
        for p in self.players:
            h.update(struct.pack("<i4d?", p.player_id, p.x, p.y, p.vx, p.vy, p.standing))
        return h.hexdigest()


def _clamp_unit(v: int) -> int:
    return -1 if v < 0 else (1 if v > 0 else 0)
