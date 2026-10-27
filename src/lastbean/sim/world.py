"""Headless simulation. Never imports pygame (tests/test_sim_has_no_pygame.py).

M2 scope: stop-and-shoot (players fire only while standing), time-based wave budget,
enemy scaling over time, XP orbs, level-ups with a choice of upgrade cards.
M3 scope: static obstacles from the biome data (forest trees block movement and projectiles).
Only mobs with an implemented behaviour spawn (`IMPLEMENTED_BEHAVIORS`).

Determinism: only + - * / and sqrt (correctly rounded in IEEE 754), no trigonometry,
all randomness from `self.rng`, all iteration over lists in insertion order.
"""

from __future__ import annotations

import hashlib
import math
import struct
from dataclasses import dataclass, field
from typing import NamedTuple

from .arena import Obstacle, ObstacleMap, obstacles_from_content
from .entities import (
    PLAYER_RADIUS,
    PROJECTILE_RADIUS,
    CharacterStats,
    Enemy,
    MobStats,
    Player,
    Projectile,
    XpOrb,
)
from .events import (
    EnemyHit,
    EnemyKilled,
    EnemySpawned,
    Event,
    LevelUp,
    PlayerDied,
    PlayerHit,
    ProjectileBlocked,
    RunEnded,
    RunStarted,
    ShotFired,
    UpgradeChosen,
    UpgradeOffered,
    WaveStarted,
)
from .rng import Rng
from .spatial import SpatialHash
from .upgrades import UpgradeDef, derive_stats, modifier_sums, roll_offer
from .waves import BiomeArea, Scaling, biome_areas_from_content, biome_at

TICK_HZ = 60
DT = 1.0 / TICK_HZ
MAX_SPAWNS_PER_TICK = 8
GRID_CELL = 64.0
INV_SQRT2 = 1.0 / math.sqrt(2.0)
IMPLEMENTED_BEHAVIORS = frozenset({"chaser"})
MAX_TARGET_CHECKS = 8  # nearest enemies tested for a free line of fire
# Extra attacks: 60 % damage (balance.json stat_model), fanned out by a fixed angle.
EXTRA_ATTACK_DAMAGE = 0.6
SPREAD_COS, SPREAD_SIN = 0.9887710779360422, 0.14943813247359922  # cos/sin(0.15 rad) as literals
# XP orbs inside the pickup radius fly to the player at this speed (world units per second).
ORB_SPEED = 420.0


@dataclass(frozen=True, slots=True)
class PlayerInput:
    """Input of one player for one tick. move_x/move_y are each -1, 0 or 1.

    `choice` picks an offered upgrade card (0-based index); ignored when nothing is offered.
    """

    player_id: int
    move_x: int = 0
    move_y: int = 0
    choice: int | None = None


@dataclass(frozen=True, slots=True)
class WorldConfig:
    character: CharacterStats
    mobs: tuple[MobStats, ...]
    upgrades: tuple[UpgradeDef, ...]
    scaling: Scaling
    biomes: tuple[BiomeArea, ...] = ()
    obstacles: tuple[Obstacle, ...] = ()
    rarity_weights: dict[str, float] = field(default_factory=dict)
    level_up_choices: int = 3
    luck_shift: float = 0.0
    arena_w: float = 60 * 32.0
    arena_h: float = 60 * 32.0
    wave_interval_s: int = 30
    spawn_distance: tuple[float, float] = (520.0, 700.0)
    max_alive_enemies: int = 350
    difficulty: float = 1.0  # D, raised by shrines from phase 2 on
    enemy_target: int | None = None  # tests/benchmarks: keep exactly this many alive instead of the budget
    player_count: int = 1

    @classmethod
    def from_content(
        cls, content, character_id: str = "ranger", player_count: int = 1, max_phase: int = 1, **overrides
    ) -> WorldConfig:
        bal = content.balance
        lo, hi = bal.raw["spawn_distance_px"]
        mobs = tuple(
            MobStats.from_content(content, m.id)
            for m in content.mobs
            if m.impl_phase <= max_phase and m.behavior in IMPLEMENTED_BEHAVIORS
        )
        upgrades = tuple(
            d
            for d in (UpgradeDef.from_content(u) for u in content.upgrades)
            if d.impl_phase <= max_phase and d.unlocked_at_start and d.supported
        )
        values = dict(
            character=CharacterStats.from_content(content, character_id),
            mobs=mobs,
            upgrades=upgrades,
            scaling=Scaling.from_content(content),
            biomes=biome_areas_from_content(content),
            obstacles=obstacles_from_content(content, max_phase),
            rarity_weights={k: float(v) for k, v in bal.rarity_weights.items()},
            level_up_choices=bal.level_up_choices,
            luck_shift=float(bal.raw["luck_shift_per_point"]),
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
    level: int
    xp: float
    xp_needed: float
    offer: tuple[tuple[str, int], ...]  # (upgrade id, current level)
    upgrades: tuple[tuple[str, int], ...]


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


class OrbView(NamedTuple):
    x: float
    y: float
    value: float


@dataclass(slots=True)
class Snapshot:
    """Read-only view handed to the renderer."""

    tick: int
    time_s: float
    wave: int
    arena_w: float
    arena_h: float
    over: bool
    paused: bool
    difficulty: float
    players: tuple[PlayerView, ...]
    enemies: tuple[EnemyView, ...]
    projectiles: tuple[ProjectileView, ...]
    orbs: tuple[OrbView, ...]


@dataclass
class World:
    seed: int
    config: WorldConfig
    tick: int = 0
    wave: int = 0
    over: bool = False
    difficulty: float = field(init=False)
    players: list[Player] = field(default_factory=list)
    enemies: list[Enemy] = field(default_factory=list)
    projectiles: list[Projectile] = field(default_factory=list)
    orbs: list[XpOrb] = field(default_factory=list)
    rng: Rng = field(init=False)

    def __post_init__(self) -> None:
        cfg = self.config
        self.rng = Rng(self.seed)
        self.difficulty = cfg.difficulty
        self._next_eid = 0
        self._budget = 0.0
        self._pending_mob: MobStats | None = None
        self._grid = SpatialHash(GRID_CELL)
        self.obstacles = ObstacleMap(cfg.obstacles)
        self._upgrade_defs = {u.id: u for u in cfg.upgrades}
        self._max_mob_radius = max((m.radius for m in cfg.mobs), default=PLAYER_RADIUS)
        cx, cy = cfg.arena_w / 2, cfg.arena_h / 2
        if not self.players:
            # Players spawn next to each other in the central clearing.
            stats = derive_stats(cfg.character, {})
            self.players = [
                Player(pid, cx + (pid - (cfg.player_count - 1) / 2) * 32.0, cy, stats.max_hp, stats)
                for pid in range(cfg.player_count)
            ]
        self._pending: list[Event] = [RunStarted(0, None, self.seed)]

    @property
    def time_s(self) -> float:
        return self.tick / TICK_HZ

    @property
    def paused(self) -> bool:
        """Single player: an open upgrade choice pauses the game. Co-op will keep running (section 18)."""
        return self.config.player_count == 1 and any(p.offer for p in self.players if p.alive)

    @property
    def reward_mult(self) -> float:
        return 1.0 + 0.8 * (self.difficulty - 1.0)

    # ------------------------------------------------------------------ step

    def step(self, inputs: dict[int, PlayerInput] | list[PlayerInput] | None = None) -> list[Event]:
        """Advance one fixed tick. Missing inputs mean "stand still".

        While paused for an upgrade choice, only the choice is processed and time stands still.
        """
        if self.over:
            return []
        if isinstance(inputs, list):
            inputs = {i.player_id: i for i in inputs}
        inputs = inputs or {}
        events, self._pending = self._pending, []

        self._apply_choices(inputs, events)
        if self.paused:
            return events

        self._move_players(inputs)
        self._spawn(events)
        self._rebuild_grid()
        self._move_enemies()
        self._rebuild_grid()
        self._shoot(events)
        self._move_projectiles(events)
        self._contact_damage(events)
        self._collect_orbs(events)

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

    # ------------------------------------------------------------------ players

    def _apply_choices(self, inputs: dict[int, PlayerInput], events: list[Event]) -> None:
        for p in self.players:
            inp = inputs.get(p.player_id)
            if not p.offer or inp is None or inp.choice is None or not 0 <= inp.choice < len(p.offer):
                continue
            uid = p.offer[inp.choice]
            p.upgrades[uid] = p.upgrades.get(uid, 0) + 1
            old_max = p.stats.max_hp
            p.stats = derive_stats(self.config.character, modifier_sums(p.upgrades, self._upgrade_defs))
            # Max-HP gains also heal by the same amount ("heilt um 15").
            p.hp = min(p.stats.max_hp, p.hp + max(0.0, p.stats.max_hp - old_max))
            p.offer = ()
            p.pending_levels -= 1
            events.append(UpgradeChosen(self.tick, p.player_id, uid, p.upgrades[uid]))
            self._offer(p, events)

    def _offer(self, p: Player, events: list[Event]) -> None:
        cfg = self.config
        while p.pending_levels > 0 and not p.offer:
            p.offer = roll_offer(
                self.rng, list(cfg.upgrades), p.upgrades, cfg.rarity_weights, cfg.level_up_choices, 0.0, cfg.luck_shift
            )
            if p.offer:
                events.append(UpgradeOffered(self.tick, p.player_id, p.offer))
            else:
                p.pending_levels = 0  # everything maxed: nothing left to choose

    def _move_players(self, inputs: dict[int, PlayerInput]) -> None:
        cfg = self.config
        r = PLAYER_RADIUS
        for p in self.players:
            if not p.alive:
                continue
            inp = inputs.get(p.player_id)
            mx = _sign(inp.move_x) if inp else 0
            my = _sign(inp.move_y) if inp else 0
            speed = p.stats.speed
            k = speed * INV_SQRT2 if (mx and my) else speed
            p.vx, p.vy = mx * k, my * k
            p.standing = not (mx or my)
            x, y = self.obstacles.push_out(p.x + p.vx * DT, p.y + p.vy * DT, r)
            p.x = min(max(x, r), cfg.arena_w - r)
            p.y = min(max(y, r), cfg.arena_h - r)
            if p.i_frames > 0:
                p.i_frames = max(0.0, p.i_frames - DT)
            if p.stats.regen_per_s:
                p.hp = min(p.stats.max_hp, p.hp + p.stats.regen_per_s * DT)

    # ------------------------------------------------------------------ enemies

    def _spawn(self, events: list[Event]) -> None:
        cfg = self.config
        alive = [p for p in self.players if p.alive]
        if not alive or not cfg.mobs:
            return
        if cfg.enemy_target is not None:
            for _ in range(MAX_SPAWNS_PER_TICK):
                if len(self.enemies) >= min(cfg.enemy_target, cfg.max_alive_enemies):
                    return
                x, y = self._spawn_point(alive)
                self._spawn_enemy(cfg.mobs[0], x, y, events)
            return

        wave_ticks = cfg.wave_interval_s * TICK_HZ
        per_wave = cfg.scaling.wave_budget(self.wave, self.difficulty, cfg.player_count)
        # Unspent budget is capped at one wave, so a full arena does not cause a burst later.
        self._budget = min(self._budget + per_wave / wave_ticks, per_wave)
        for _ in range(MAX_SPAWNS_PER_TICK):
            if len(self.enemies) >= cfg.max_alive_enemies:
                return
            x, y = self._spawn_point(alive)
            mob = self._pending_mob or self._pick_mob(biome_at(cfg.biomes, x, y))
            if mob is None:
                return
            if self._budget < mob.cost:
                self._pending_mob = mob  # save up for it; position is rolled again when affordable
                return
            self._pending_mob = None
            self._budget -= mob.cost
            self._spawn_enemy(mob, x, y, events)

    def _pick_mob(self, biome: str | None) -> MobStats | None:
        t = self.time_s
        options = [(m, dict(m.biome_weights).get(biome, 0.0)) for m in self.config.mobs if m.min_time_s <= t]
        options = [(m, w) for m, w in options if w > 0]
        if not options:
            return None
        r = self.rng.random() * sum(w for _, w in options)
        for m, w in options:
            if r < w:
                return m
            r -= w
        return options[-1][0]

    def _spawn_point(self, alive: list[Player]) -> tuple[float, float]:
        cfg = self.config
        lo, hi = cfg.spawn_distance
        p = alive[self.rng.randint(0, len(alive) - 1)]
        dx, dy = self._random_direction()
        dist = self.rng.uniform(lo, hi)
        r = self._max_mob_radius
        return (
            min(max(p.x + dx * dist, r), cfg.arena_w - r),
            min(max(p.y + dy * dist, r), cfg.arena_h - r),
        )

    def _spawn_enemy(self, m: MobStats, x: float, y: float, events: list[Event]) -> None:
        sc, minutes = self.config.scaling, self.time_s / 60.0
        x, y = self.obstacles.push_out(x, y, m.radius)
        hp = m.hp * sc.hp_mult(minutes)
        dmg = m.damage * sc.damage_mult(minutes) * self.difficulty
        speed = m.speed * sc.speed_mult(minutes)
        self.enemies.append(Enemy(self._next_eid, m.id, x, y, hp, hp, speed, dmg, m.radius, m.xp))
        events.append(EnemySpawned(self.tick, None, self._next_eid, m.id, biome_at(self.config.biomes, x, y)))
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
            for o in g.query(e.x, e.y, e.radius + self._max_mob_radius):
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
        obstacles = self.obstacles
        for e in self.enemies:
            x, y = obstacles.push_out(e.x, e.y, e.radius)
            e.x = min(max(x, e.radius), cfg.arena_w - e.radius)
            e.y = min(max(y, e.radius), cfg.arena_h - e.radius)

    # ------------------------------------------------------------------ combat

    def _shoot(self, events: list[Event]) -> None:
        ch = self.config.character
        for p in self.players:
            if not p.alive:
                continue
            s = p.stats
            p.shot_cooldown -= DT
            if p.shot_cooldown > 0:
                continue
            # Stop-and-shoot: moving interrupts the attack; it fires as soon as you stand.
            target, best = self._pick_target(p) if p.standing else (None, 0.0)
            if target is None:
                p.shot_cooldown = 0.0
                continue
            p.shot_cooldown += 1.0 / s.attack_rate
            d = math.sqrt(best) or 1.0
            dx, dy = (target.x - p.x) / d, (target.y - p.y) / d
            life = max(1, int(s.range / ch.projectile_speed * TICK_HZ + 0.5))
            self._fire(p, dx, dy, s.damage, life, events)
            # Extra attacks fan out alternately left and right of the main shot.
            lx, ly, rx, ry = dx, dy, dx, dy
            for k in range(s.extra_attacks):
                if k % 2 == 0:
                    lx, ly = lx * SPREAD_COS - ly * SPREAD_SIN, lx * SPREAD_SIN + ly * SPREAD_COS
                    self._fire(p, lx, ly, s.damage * EXTRA_ATTACK_DAMAGE, life, events)
                else:
                    rx, ry = rx * SPREAD_COS + ry * SPREAD_SIN, -rx * SPREAD_SIN + ry * SPREAD_COS
                    self._fire(p, rx, ry, s.damage * EXTRA_ATTACK_DAMAGE, life, events)

    def _pick_target(self, p: Player) -> tuple[Enemy | None, float]:
        """Nearest enemy in range with a free line of fire (trees give cover)."""
        range2 = p.stats.range * p.stats.range
        in_range = []
        for e in self.enemies:
            d2 = (e.x - p.x) ** 2 + (e.y - p.y) ** 2
            if d2 <= range2:
                in_range.append((d2, e.eid, e))
        in_range.sort(key=lambda t: (t[0], t[1]))
        for d2, _, e in in_range[:MAX_TARGET_CHECKS]:
            if not self.obstacles.line_blocked(p.x, p.y, e.x, e.y, PROJECTILE_RADIUS):
                return e, d2
        return None, 0.0

    def _fire(self, p: Player, dx: float, dy: float, damage: float, life: int, events: list[Event]) -> None:
        s, speed = p.stats, self.config.character.projectile_speed
        crit = self.rng.random() * 100.0 < s.crit_chance_pct
        dmg = damage * (s.crit_mult if crit else 1.0)
        self.projectiles.append(
            Projectile(p.player_id, p.x, p.y, dx * speed, dy * speed, dmg, crit, life, s.pierce + 1)
        )
        events.append(ShotFired(self.tick, p.player_id, p.x, p.y, dx, dy))

    def _move_projectiles(self, events: list[Event]) -> None:
        g = self._grid
        reach = PROJECTILE_RADIUS + self._max_mob_radius
        survivors: list[Projectile] = []
        killed: set[int] = set()
        for pr in self.projectiles:
            pr.x += pr.vx * DT
            pr.y += pr.vy * DT
            pr.ticks_left -= 1
            if self.obstacles.blocks_point(pr.x, pr.y, PROJECTILE_RADIUS):
                events.append(ProjectileBlocked(self.tick, pr.owner, pr.x, pr.y))
                continue
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
                    if e.xp > 0:
                        self.orbs.append(XpOrb(e.x, e.y, e.xp * self.reward_mult))
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
        reach = PLAYER_RADIUS + self._max_mob_radius
        for p in self.players:
            if not p.alive or p.i_frames > 0:
                continue
            for e in g.query(p.x, p.y, reach):
                r = e.radius + PLAYER_RADIUS
                if (e.x - p.x) ** 2 + (e.y - p.y) ** 2 <= r * r:
                    dmg = e.damage * p.stats.damage_taken_mult
                    p.hp = max(0.0, p.hp - dmg)
                    p.i_frames = self.config.character.i_frames_s
                    events.append(PlayerHit(self.tick, p.player_id, dmg, p.hp))
                    if p.hp <= 0:
                        p.alive = False
                        p.offer, p.pending_levels = (), 0
                        events.append(PlayerDied(self.tick, p.player_id))
                    break

    def _collect_orbs(self, events: list[Event]) -> None:
        alive = [p for p in self.players if p.alive]
        if not alive or not self.orbs:
            return
        step = ORB_SPEED * DT
        remaining: list[XpOrb] = []
        for o in self.orbs:
            owner, best = None, math.inf
            for p in alive:
                d2 = (p.x - o.x) ** 2 + (p.y - o.y) ** 2
                if d2 <= p.stats.pickup_radius * p.stats.pickup_radius and d2 < best:
                    owner, best = p, d2
            if owner is None:
                remaining.append(o)
                continue
            d = math.sqrt(best)
            if d <= PLAYER_RADIUS + step:
                self._gain_xp(owner, o.value, events)
                continue
            o.x += (owner.x - o.x) / d * step
            o.y += (owner.y - o.y) / d * step
            remaining.append(o)
        self.orbs = remaining

    def _gain_xp(self, p: Player, value: float, events: list[Event]) -> None:
        p.xp += value
        sc = self.config.scaling
        while p.xp >= sc.xp_needed(p.level):
            p.xp -= sc.xp_needed(p.level)
            p.level += 1
            p.pending_levels += 1
            events.append(LevelUp(self.tick, p.player_id, p.level))
        self._offer(p, events)

    # ------------------------------------------------------------------ views

    def snapshot(self) -> Snapshot:
        sc = self.config.scaling
        return Snapshot(
            tick=self.tick,
            time_s=self.time_s,
            wave=self.wave,
            arena_w=self.config.arena_w,
            arena_h=self.config.arena_h,
            over=self.over,
            paused=self.paused,
            difficulty=self.difficulty,
            players=tuple(
                PlayerView(
                    p.player_id,
                    p.x,
                    p.y,
                    p.standing,
                    p.hp,
                    p.stats.max_hp,
                    p.alive,
                    p.i_frames > 0,
                    p.kills,
                    p.level,
                    p.xp,
                    sc.xp_needed(p.level),
                    tuple((uid, p.upgrades.get(uid, 0)) for uid in p.offer),
                    tuple(p.upgrades.items()),
                )
                for p in self.players
            ),
            enemies=tuple(EnemyView(e.eid, e.kind, e.x, e.y, e.radius, e.hp / e.max_hp) for e in self.enemies),
            projectiles=tuple(ProjectileView(pr.x, pr.y, pr.crit) for pr in self.projectiles),
            orbs=tuple(OrbView(o.x, o.y, o.value) for o in self.orbs),
        )

    def state_hash(self) -> str:
        """Hash over the full simulation state, for determinism tests and later desync detection."""
        h = hashlib.sha256()
        h.update(struct.pack("<qqq?qdd", self.seed, self.tick, self.wave, self.over, self._next_eid, self._budget,
                             self.difficulty))  # fmt: skip
        h.update(struct.pack("<4I", *self.rng.getstate()))
        h.update((self._pending_mob.id if self._pending_mob else "").encode())
        for p in self.players:
            h.update(
                struct.pack(
                    "<i7d?iidi", p.player_id, p.x, p.y, p.vx, p.vy, p.hp, p.shot_cooldown, p.i_frames, p.alive,
                    p.kills, p.level, p.xp, p.pending_levels,
                )
            )  # fmt: skip
            h.update(repr((sorted(p.upgrades.items()), p.offer)).encode())
        for e in self.enemies:
            h.update(struct.pack("<i3d", e.eid, e.x, e.y, e.hp))
        for pr in self.projectiles:
            h.update(struct.pack("<i4d2i", pr.owner, pr.x, pr.y, pr.vx, pr.vy, pr.ticks_left, pr.hits_left))
        for o in self.orbs:
            h.update(struct.pack("<3d", o.x, o.y, o.value))
        return h.hexdigest()


def _sign(v: int) -> int:
    return -1 if v < 0 else (1 if v > 0 else 0)
