"""Headless simulation. Never imports pygame (tests/test_sim_has_no_pygame.py).

M1 scope: players move and auto-fire at the nearest enemy, one chaser enemy type,
projectiles with pierce and crits, contact damage with i-frames, death and run end.
Enemies come from a placeholder spawner that keeps a fixed number alive; the
time-based wave budget replaces it in M2.

Determinism: only + - * / and sqrt (correctly rounded in IEEE 754), no trigonometry,
all randomness from `self.rng`, all iteration over lists in insertion order.
"""

from __future__ import annotations

import hashlib
import math
import struct
from dataclasses import dataclass, field
from typing import NamedTuple

from .entities import PLAYER_RADIUS, PROJECTILE_RADIUS, CharacterStats, Enemy, MobStats, Player, Projectile
from .events import (
    EnemyHit,
    EnemyKilled,
    Event,
    PlayerDied,
    PlayerHit,
    RunEnded,
    RunStarted,
    ShotFired,
    WaveStarted,
)
from .rng import Rng
from .spatial import SpatialHash

TICK_HZ = 60
DT = 1.0 / TICK_HZ
SPAWNS_PER_TICK = 2
GRID_CELL = 64.0
INV_SQRT2 = 1.0 / math.sqrt(2.0)


@dataclass(frozen=True, slots=True)
class PlayerInput:
    """Input of one player for one tick. move_x/move_y are each -1, 0 or 1."""

    player_id: int
    move_x: int = 0
    move_y: int = 0


@dataclass(frozen=True, slots=True)
class WorldConfig:
    character: CharacterStats
    mob: MobStats
    arena_w: float = 60 * 32.0
    arena_h: float = 60 * 32.0
    wave_interval_s: int = 30
    spawn_distance: tuple[float, float] = (520.0, 700.0)
    max_alive_enemies: int = 350
    enemy_target: int = 40  # M1 placeholder spawner: keep this many enemies alive
    player_count: int = 1

    @classmethod
    def from_content(
        cls, content, character_id: str = "ranger", mob_id: str = "slimeling", player_count: int = 1, **overrides
    ) -> WorldConfig:
        bal = content.balance
        lo, hi = bal.raw["spawn_distance_px"]
        values = dict(
            character=CharacterStats.from_content(content, character_id),
            mob=MobStats.from_content(content, mob_id),
            arena_w=float(bal.arena_tiles[0] * bal.tile_px),
            arena_h=float(bal.arena_tiles[1] * bal.tile_px),
            wave_interval_s=bal.wave_interval_s,
            spawn_distance=(float(lo), float(hi)),
            max_alive_enemies=bal.max_alive_enemies,
            player_count=player_count,
        )
        values.update(overrides)
        return cls(**values)


class PlayerView(NamedTuple):
    player_id: int
    x: float
    y: float
    standing: bool
    hp: float
    max_hp: float
    alive: bool
    invulnerable: bool
    kills: int


class EnemyView(NamedTuple):
    eid: int
    kind: str
    x: float
    y: float
    radius: float
    hp_frac: float


class ProjectileView(NamedTuple):
    x: float
    y: float
    crit: bool


@dataclass(slots=True)
class Snapshot:
    """Read-only view handed to the renderer."""

    tick: int
    time_s: float
    wave: int
    arena_w: float
    arena_h: float
    over: bool
    players: tuple[PlayerView, ...]
    enemies: tuple[EnemyView, ...]
    projectiles: tuple[ProjectileView, ...]


@dataclass
class World:
    seed: int
    config: WorldConfig
    tick: int = 0
    wave: int = 0
    over: bool = False
    players: list[Player] = field(default_factory=list)
    enemies: list[Enemy] = field(default_factory=list)
    projectiles: list[Projectile] = field(default_factory=list)
    rng: Rng = field(init=False)

    def __post_init__(self) -> None:
        self.rng = Rng(self.seed)
        self._next_eid = 0
        self._grid = SpatialHash(GRID_CELL)
        cfg = self.config
        cx, cy = cfg.arena_w / 2, cfg.arena_h / 2
        if not self.players:
            # Players spawn next to each other in the central clearing.
            hp = float(cfg.character.hp)
            self.players = [
                Player(pid, cx + (pid - (cfg.player_count - 1) / 2) * 32.0, cy, hp, hp)
                for pid in range(cfg.player_count)
            ]
        self._pending: list[Event] = [RunStarted(0, None, self.seed)]

    @property
    def time_s(self) -> float:
        return self.tick / TICK_HZ

    # ------------------------------------------------------------------ step

    def step(self, inputs: dict[int, PlayerInput] | list[PlayerInput] | None = None) -> list[Event]:
        """Advance one fixed tick. Missing inputs mean "stand still"."""
        if self.over:
            return []
        if isinstance(inputs, list):
            inputs = {i.player_id: i for i in inputs}
        events, self._pending = self._pending, []

        self._move_players(inputs or {})
        self._spawn()
        self._rebuild_grid()
        self._move_enemies()
        self._rebuild_grid()
        self._shoot(events)
        self._move_projectiles(events)
        self._contact_damage(events)

        self.tick += 1
        # Wave n starts at n * wave_interval_s: 0:00-0:30 is wave 0, boss wave 10 = 5:00 (decided, M0).
        wave = self.tick // (self.config.wave_interval_s * TICK_HZ)
        if wave != self.wave:
            self.wave = wave
            events.append(WaveStarted(self.tick, None, wave))
        if not any(p.alive for p in self.players):
            self.over = True
            events.append(RunEnded(self.tick, None, self.time_s))
        return events

    def _move_players(self, inputs: dict[int, PlayerInput]) -> None:
        cfg = self.config
        speed = cfg.character.speed
        r = PLAYER_RADIUS
        for p in self.players:
            if not p.alive:
                continue
            inp = inputs.get(p.player_id)
            mx = _sign(inp.move_x) if inp else 0
            my = _sign(inp.move_y) if inp else 0
            k = speed * INV_SQRT2 if (mx and my) else speed
            p.vx, p.vy = mx * k, my * k
            p.standing = not (mx or my)
            p.x = min(max(p.x + p.vx * DT, r), cfg.arena_w - r)
            p.y = min(max(p.y + p.vy * DT, r), cfg.arena_h - r)
            if p.i_frames > 0:
                p.i_frames = max(0.0, p.i_frames - DT)

    def _spawn(self) -> None:
        cfg = self.config
        alive = [p for p in self.players if p.alive]
        if not alive:
            return
        target = min(cfg.enemy_target, cfg.max_alive_enemies)
        lo, hi = cfg.spawn_distance
        m = cfg.mob
        for _ in range(SPAWNS_PER_TICK):
            if len(self.enemies) >= target:
                return
            p = alive[self.rng.randint(0, len(alive) - 1)]
            dx, dy = self._random_direction()
            dist = self.rng.uniform(lo, hi)
            x = min(max(p.x + dx * dist, m.radius), cfg.arena_w - m.radius)
            y = min(max(p.y + dy * dist, m.radius), cfg.arena_h - m.radius)
            self.enemies.append(Enemy(self._next_eid, m.id, x, y, m.hp, m.hp, m.speed, m.damage, m.radius))
            self._next_eid += 1

    def _random_direction(self) -> tuple[float, float]:
        """Uniform unit vector by rejection sampling (no trigonometry, so bit-identical everywhere)."""
        while True:
            x, y = self.rng.uniform(-1.0, 1.0), self.rng.uniform(-1.0, 1.0)
            d2 = x * x + y * y
            if 0.01 < d2 <= 1.0:
                d = math.sqrt(d2)
                return x / d, y / d

    def _rebuild_grid(self) -> None:
        g = self._grid
        g.clear()
        for e in self.enemies:
            g.insert(e, e.x, e.y)

    def _move_enemies(self) -> None:
        alive = [p for p in self.players if p.alive]
        if not alive:
            return
        cfg = self.config
        for e in self.enemies:
            # Chaser: straight towards the nearest living player.
            tx, ty, best = alive[0].x, alive[0].y, math.inf
            for p in alive:
                d2 = (p.x - e.x) ** 2 + (p.y - e.y) ** 2
                if d2 < best:
                    tx, ty, best = p.x, p.y, d2
            if best > 1e-9:
                d = math.sqrt(best)
                step = min(e.speed * DT, d)
                e.x += (tx - e.x) / d * step
                e.y += (ty - e.y) / d * step
        # Separation so enemies form a crowd instead of a single dot.
        g = self._grid
        for e in self.enemies:
            for o in g.query(e.x, e.y, e.radius * 2):
                if o.eid <= e.eid:
                    continue
                dx, dy = o.x - e.x, o.y - e.y
                d2 = dx * dx + dy * dy
                min_d = e.radius + o.radius
                if 1e-9 < d2 < min_d * min_d:
                    d = math.sqrt(d2)
                    push = (min_d - d) * 0.5 / d
                    e.x -= dx * push
                    e.y -= dy * push
                    o.x += dx * push
                    o.y += dy * push
        for e in self.enemies:
            e.x = min(max(e.x, e.radius), cfg.arena_w - e.radius)
            e.y = min(max(e.y, e.radius), cfg.arena_h - e.radius)

    def _shoot(self, events: list[Event]) -> None:
        ch = self.config.character
        interval = 1.0 / ch.attack_rate
        range2 = ch.range * ch.range
        for p in self.players:
            if not p.alive:
                continue
            p.shot_cooldown -= DT
            if p.shot_cooldown > 0:
                continue
            target, best = None, range2
            for e in self.enemies:
                d2 = (e.x - p.x) ** 2 + (e.y - p.y) ** 2
                if d2 <= best:
                    target, best = e, d2
            if target is None:
                p.shot_cooldown = 0.0  # ready the moment something enters range
                continue
            p.shot_cooldown += interval
            d = math.sqrt(best) or 1.0
            dx, dy = (target.x - p.x) / d, (target.y - p.y) / d
            crit = self.rng.random() * 100.0 < ch.crit_chance_pct
            dmg = ch.damage * (ch.crit_mult if crit else 1.0)
            life = max(1, int(ch.range / ch.projectile_speed * TICK_HZ + 0.5))
            self.projectiles.append(
                Projectile(
                    p.player_id,
                    p.x,
                    p.y,
                    dx * ch.projectile_speed,
                    dy * ch.projectile_speed,
                    dmg,
                    crit,
                    life,
                    ch.pierce + 1,
                )
            )
            events.append(ShotFired(self.tick, p.player_id, p.x, p.y, dx, dy))

    def _move_projectiles(self, events: list[Event]) -> None:
        g = self._grid
        reach = PROJECTILE_RADIUS + self.config.mob.radius
        survivors: list[Projectile] = []
        killed: set[int] = set()
        for pr in self.projectiles:
            pr.x += pr.vx * DT
            pr.y += pr.vy * DT
            pr.ticks_left -= 1
            for e in g.query(pr.x, pr.y, reach):
                if e.eid in pr.hit_ids or e.eid in killed:
                    continue
                r = e.radius + PROJECTILE_RADIUS
                if (e.x - pr.x) ** 2 + (e.y - pr.y) ** 2 > r * r:
                    continue
                pr.hit_ids.add(e.eid)
                e.hp -= pr.damage
                events.append(EnemyHit(self.tick, pr.owner, e.eid, e.x, e.y, pr.damage, pr.crit))
                if e.hp <= 0:
                    killed.add(e.eid)
                    events.append(EnemyKilled(self.tick, pr.owner, e.eid, e.kind, e.x, e.y))
                    for p in self.players:
                        if p.player_id == pr.owner:
                            p.kills += 1
                pr.hits_left -= 1
                if pr.hits_left <= 0:
                    break
            if pr.ticks_left > 0 and pr.hits_left > 0:
                survivors.append(pr)
        self.projectiles = survivors
        if killed:
            self.enemies = [e for e in self.enemies if e.eid not in killed]
            self._rebuild_grid()

    def _contact_damage(self, events: list[Event]) -> None:
        g = self._grid
        reach = PLAYER_RADIUS + self.config.mob.radius
        for p in self.players:
            if not p.alive or p.i_frames > 0:
                continue
            for e in g.query(p.x, p.y, reach):
                r = e.radius + PLAYER_RADIUS
                if (e.x - p.x) ** 2 + (e.y - p.y) ** 2 <= r * r:
                    p.hp = max(0.0, p.hp - e.damage)
                    p.i_frames = self.config.character.i_frames_s
                    events.append(PlayerHit(self.tick, p.player_id, e.damage, p.hp))
                    if p.hp <= 0:
                        p.alive = False
                        events.append(PlayerDied(self.tick, p.player_id))
                    break

    # ------------------------------------------------------------------ views

    def snapshot(self) -> Snapshot:
        return Snapshot(
            tick=self.tick,
            time_s=self.time_s,
            wave=self.wave,
            arena_w=self.config.arena_w,
            arena_h=self.config.arena_h,
            over=self.over,
            players=tuple(
                PlayerView(p.player_id, p.x, p.y, p.standing, p.hp, p.max_hp, p.alive, p.i_frames > 0, p.kills)
                for p in self.players
            ),
            enemies=tuple(EnemyView(e.eid, e.kind, e.x, e.y, e.radius, e.hp / e.max_hp) for e in self.enemies),
            projectiles=tuple(ProjectileView(pr.x, pr.y, pr.crit) for pr in self.projectiles),
        )

    def state_hash(self) -> str:
        """Hash over the full simulation state, for determinism tests and later desync detection."""
        h = hashlib.sha256()
        h.update(struct.pack("<qqq?q", self.seed, self.tick, self.wave, self.over, self._next_eid))
        h.update(struct.pack("<4I", *self.rng.getstate()))
        for p in self.players:
            h.update(
                struct.pack(
                    "<i7d?i", p.player_id, p.x, p.y, p.vx, p.vy, p.hp, p.shot_cooldown, p.i_frames, p.alive, p.kills
                )
            )
        for e in self.enemies:
            h.update(struct.pack("<i3d", e.eid, e.x, e.y, e.hp))
        for pr in self.projectiles:
            h.update(struct.pack("<i4d2i", pr.owner, pr.x, pr.y, pr.vx, pr.vy, pr.ticks_left, pr.hits_left))
        return h.hexdigest()


def _sign(v: int) -> int:
    return -1 if v < 0 else (1 if v > 0 else 0)
