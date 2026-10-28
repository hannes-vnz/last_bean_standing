"""Visual feedback ("game feel"), driven only by simulation events (DESIGN.md section 16).

Particles, white hit flashes, damage numbers, rings, trauma-based screen shake and hit-stop.
Uses its own random generator, never the simulation's, so effects cannot change a run.
Positions are in world units; the renderer converts them.
"""

from __future__ import annotations

import random
from dataclasses import dataclass

from ..sim import events as ev

MAX_PARTICLES = 2000
FLASH_FRAMES = 2


@dataclass(slots=True)
class Particle:
    x: float
    y: float
    vx: float
    vy: float
    life: int
    max_life: int
    color: tuple[int, int, int]
    size: int


@dataclass(slots=True)
class FloatingText:
    x: float
    y: float
    text: str
    color: tuple[int, int, int]
    big: bool
    life: int


@dataclass(slots=True)
class Ring:
    x: float
    y: float
    radius: float
    grow: float
    life: int
    max_life: int
    color: tuple[int, int, int]


class Effects:
    def __init__(self, colors: dict[str, tuple[int, int, int]], kind_colors: dict[str, tuple[int, int, int]]) -> None:
        self.rng = random.Random(0xB0B)
        self.colors = colors
        self.kind_colors = kind_colors
        self.particles: list[Particle] = []
        self.texts: list[FloatingText] = []
        self.rings: list[Ring] = []
        self.flash: dict[int, int] = {}  # enemy id -> frames left
        self.trauma = 0.0
        self.hitstop = 0
        self.banner: tuple[str, int] | None = None

    def reset(self) -> None:
        self.particles.clear()
        self.texts.clear()
        self.rings.clear()
        self.flash.clear()
        self.trauma, self.hitstop, self.banner = 0.0, 0, None

    # ------------------------------------------------------------------ events

    def handle(
        self,
        events: list,
        boss_names: dict[str, str] | None = None,
        players: dict[int, tuple[float, float]] | None = None,
    ) -> None:
        """React to one frame's simulation events. `players` maps player_id to position (for level-ups)."""
        c = self.colors
        for e in events:
            if isinstance(e, ev.EnemyHit):
                self.flash[e.enemy_id] = FLASH_FRAMES
                color = c["crit"] if e.crit else c["white"]
                self.texts.append(FloatingText(e.x, e.y - 14, f"{e.damage:.0f}", color, e.crit, 36))
                self.burst(e.x, e.y, 3, c["shot_halo"], speed=60, life=10)
                if e.crit:
                    self.hitstop = max(self.hitstop, 2)
            elif isinstance(e, ev.EnemyKilled):
                self.burst(e.x, e.y, 8, self.kind_colors.get(e.kind, c["white"]), speed=110, life=22, size=2)
            elif isinstance(e, ev.EliteSpawned):
                self.trauma = min(1.0, self.trauma + 0.2)
            elif isinstance(e, ev.BossSpawned):
                self.trauma = min(1.0, self.trauma + 0.6)
                name = (boss_names or {}).get(e.boss, e.boss)
                self.banner = (f"{name} erscheint!", 150)
            elif isinstance(e, ev.BossKilled):
                self.hitstop = max(self.hitstop, 3)
                self.trauma = 1.0
                self.banner = ("Boss besiegt!", 150)
            elif isinstance(e, ev.PlayerHit):
                self.trauma = min(1.0, self.trauma + 0.35)
            elif isinstance(e, ev.ShotFired):
                self.burst(e.x + e.dx * 14, e.y + e.dy * 14, 2, c["shot_core"], speed=40, life=6)
            elif isinstance(e, ev.ProjectileBlocked):
                self.burst(e.x, e.y, 4, c["leaf"], speed=50, life=14)
            elif isinstance(e, ev.HazardActivated):
                if e.kind == "explosion":
                    self.rings.append(Ring(e.x, e.y, 10, e.radius / 12, 12, 12, c["telegraph"]))
                    self.burst(e.x, e.y, 20, c["telegraph"], speed=180, life=20, size=2)
                    self.trauma = min(1.0, self.trauma + 0.5)
                elif e.kind == "poison":
                    self.burst(e.x, e.y, 6, c["poison"], speed=40, life=18)
            elif isinstance(e, ev.LevelUp) and players and e.player_id in players:
                self.level_up(*players[e.player_id])
            elif isinstance(e, ev.ChestDropped):
                self.burst(e.x, e.y, 12, c["crit"], speed=90, life=26)

    def level_up(self, x: float, y: float) -> None:
        self.rings.append(Ring(x, y, 8, 5, 24, 24, self.colors["crit"]))
        self.burst(x, y, 24, self.colors["crit"], speed=140, life=30, size=2)

    def burst(self, x: float, y: float, n: int, color, speed: float = 80, life: int = 20, size: int = 1) -> None:
        r = self.rng
        for _ in range(n):
            if len(self.particles) >= MAX_PARTICLES:
                self.particles.pop(0)
            vx, vy = r.uniform(-1, 1) * speed, r.uniform(-1, 1) * speed
            lf = r.randint(life // 2, life)
            self.particles.append(Particle(x, y, vx, vy, lf, lf, color, size))

    # ------------------------------------------------------------------ per frame

    def update(self) -> None:
        dt = 1 / 60
        alive = []
        for p in self.particles:
            p.life -= 1
            if p.life > 0:
                p.x += p.vx * dt
                p.y += p.vy * dt
                p.vx *= 0.9
                p.vy *= 0.9
                alive.append(p)
        self.particles = alive
        texts = []
        for t in self.texts:
            t.life -= 1
            t.y -= 0.6
            if t.life > 0:
                texts.append(t)
        self.texts = texts
        rings = []
        for g in self.rings:
            g.life -= 1
            g.radius += g.grow
            if g.life > 0:
                rings.append(g)
        self.rings = rings
        self.flash = {k: v - 1 for k, v in self.flash.items() if v > 1}
        self.trauma = max(0.0, self.trauma - 1.5 / 60)
        if self.banner:
            text, frames = self.banner
            self.banner = (text, frames - 1) if frames > 1 else None

    def shake(self, max_px: int = 6) -> tuple[int, int]:
        """Screen offset from trauma: strength grows with trauma squared."""
        s = self.trauma * self.trauma * max_px
        if s < 0.5:
            return 0, 0
        return round(self.rng.uniform(-s, s)), round(self.rng.uniform(-s, s))
