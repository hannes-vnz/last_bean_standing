"""Visual feedback ("game feel"), driven only by simulation events (DESIGN.md section 16).

Particles, white hit flashes, damage numbers, rings, trauma-based screen shake and hit-stop.
Uses its own random generator, never the simulation's, so effects cannot change a run.
Positions are in world units; the renderer converts them.
"""

from __future__ import annotations

import random
from dataclasses import dataclass

from ..sim import events as ev
from ..sim.tuning import GREED_XP_PCT

MAX_PARTICLES = 2000
FLASH_FRAMES = 2
HURT_FRAMES = 6  # enemy squashes and is pushed back a pixel
CORPSE_FRAMES = 14  # dying enemy pops, flattens and fades
MAX_CORPSES = 80
INTRO_FRAMES = 110  # boss entrance: the camera swings over, the name slides in
HINT_FRAMES = 330  # a first-run tip stays 5.5 s


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


@dataclass(slots=True)
class Bolt:
    points: tuple[tuple[float, float], ...]
    life: int


@dataclass(slots=True)
class Reel:
    """Chest opening ("lucky draw"): a strip of item icons spins, slows down and lands on the item."""

    item_id: str
    rarity: str
    strip: list[str]  # item ids on the strip; the found item sits at index `land`
    land: int
    frame: int = 0

    SPIN = 70  # frames until it stops
    SHOW = 50  # frames the result stays

    @property
    def done(self) -> bool:
        return self.frame >= self.SPIN + self.SHOW

    @property
    def landed(self) -> bool:
        return self.frame >= self.SPIN

    def position(self) -> float:
        """Strip offset in icons: fast at first, easing out onto `land`."""
        t = min(1.0, self.frame / self.SPIN)
        return self.land * (1.0 - (1.0 - t) ** 3)


class Effects:
    def __init__(self, colors: dict[str, tuple[int, int, int]], kind_colors: dict[str, tuple[int, int, int]]) -> None:
        self.rng = random.Random(0xB0B)
        self.colors = colors
        self.kind_colors = kind_colors
        self.particles: list[Particle] = []
        self.texts: list[FloatingText] = []
        self.rings: list[Ring] = []
        self.flash: dict[int, int] = {}  # enemy id -> frames left
        self.hurt: dict[int, int] = {}  # enemy id -> frames left of the hit squash
        self.corpses: list[list] = []  # [kind, x, y, frames left, scale]
        self._step = 0  # footstep dust counter
        self.trauma = 0.0
        self.hitstop = 0
        self.banner: tuple[str, int] | None = None
        self.toast: tuple[str, int] | None = None  # small message, e.g. the item just found
        self.item_info: dict[str, tuple[str, str]] = {}  # item id -> (name, text), set by the app
        self.item_rarity: dict[str, str] = {}  # item id -> rarity, set by the app (for the chest reel)
        self.taglines: dict[int, str] = {}  # garden bed number -> tagline, set by the app
        self.bolts: list[Bolt] = []
        self.beams: list[list] = []  # [x, y, x2, y2, width, frames left]
        self.sweeps: list[list] = []  # [x, y, dx, dy, radius, arc_deg, frames left]
        self.reel: Reel | None = None
        self.subtitle: tuple[str, int] | None = None  # second banner line (tagline of a garden bed)
        self.show_numbers = True  # settings: damage numbers
        self.shake_on = True  # settings: screen shake
        self.hints: list[str] = []  # first run: tips shown one after another
        self.boss_phases: dict[str, list[str]] = {}  # boss id -> pattern text per phase, set by the app
        self.intro: list | None = None  # [boss id, name, frames left] while a boss makes its entrance
        self.hint: tuple[str, int] | None = None

    def reset(self) -> None:
        self.particles.clear()
        self.texts.clear()
        self.rings.clear()
        self.flash.clear()
        self.hurt.clear()
        self.corpses.clear()
        self.trauma, self.hitstop, self.banner, self.toast = 0.0, 0, None, None
        self.bolts.clear()
        self.beams.clear()
        self.sweeps.clear()
        self.reel, self.subtitle = None, None
        self.hints, self.hint = [], None
        self.intro = None

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
                self.hurt[e.enemy_id] = HURT_FRAMES
                color = c["crit"] if e.crit else c["white"]
                if self.show_numbers:
                    self.texts.append(FloatingText(e.x, e.y - 14, f"{e.damage:.0f}", color, e.crit, 36))
                self.burst(e.x, e.y, 3, c["shot_halo"], speed=60, life=10)
                if e.crit:
                    self.hitstop = max(self.hitstop, 2)
            elif isinstance(e, ev.EnemyKilled):
                self.burst(e.x, e.y, 8, self.kind_colors.get(e.kind, c["white"]), speed=110, life=22, size=2)
                if len(self.corpses) >= MAX_CORPSES:
                    self.corpses.pop(0)
                self.corpses.append([e.kind, e.x, e.y, CORPSE_FRAMES, 1.0])
                self.hurt.pop(e.enemy_id, None)
            elif isinstance(e, ev.EliteSpawned):
                self.trauma = min(1.0, self.trauma + 0.2)
            elif isinstance(e, ev.BossSpawned):
                self.trauma = min(1.0, self.trauma + 0.6)
                name = (boss_names or {}).get(e.boss, e.boss)
                self.intro = [e.boss, name, INTRO_FRAMES]  # the run waits while the boss is shown
            elif isinstance(e, ev.BossPhase):  # new attack pattern: say what is coming, so it can be learnt
                patterns = self.boss_phases.get(e.boss, [])
                self.banner = (f"Phase {e.phase + 1}!", 120)
                if e.phase < len(patterns):
                    self.subtitle = (patterns[e.phase], 150)
                self.trauma = min(1.0, self.trauma + 0.4)
                self.hitstop = max(self.hitstop, 4)
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
            elif isinstance(e, ev.ItemGained):
                name, text = self.item_info.get(e.item_id, (e.item_id, ""))
                stack = f" x{e.count}" if e.count > 1 else ""
                self.toast = (f"{name}{stack}: {text}", 180)
                self.start_reel(e.item_id)
                if players and e.player_id in players:
                    self.level_up(*players[e.player_id])
            elif isinstance(e, ev.BeamFired):
                self.beams.append([e.x, e.y, e.x2, e.y2, e.width, 10])
            elif isinstance(e, ev.SweepSwung):
                self.sweeps.append([e.x, e.y, e.dx, e.dy, e.radius, e.arc_deg, 8])
            elif isinstance(e, ev.Zap):
                self.bolts.append(Bolt(e.points, 8))
                for x, y in e.points[1:]:
                    self.burst(x, y, 4, c.get("shot_core", c["white"]), speed=70, life=10)
            elif isinstance(e, ev.PlayerDodged):
                self.texts.append(FloatingText(e.x, e.y - 30, "Ausgewichen!", c["white"], False, 40))
            elif isinstance(e, ev.PlayerRevived):
                self.banner = ("Zweiter Atem!", 120)
                self.level_up(e.x, e.y)
                self.trauma = min(1.0, self.trauma + 0.5)
            elif isinstance(e, ev.StageStarted):
                self.banner = (f"Beet {e.stage}: {e.name}", 170)
                self.subtitle = (self.taglines.get(e.stage, ""), 170)
            elif isinstance(e, ev.FloodWarning):
                self.banner = ("Die Plagenflut kommt!", 150)
            elif isinstance(e, ev.FloodStarted):
                self.banner = ("PLAGENFLUT!", 150)
                self.subtitle = ("Sie hört nicht auf. Ins Tor oder durchhalten!", 150)
                self.trauma = min(1.0, self.trauma + 0.6)
            elif isinstance(e, ev.FloodWave) and e.wave > 1:
                self.banner = (f"Flutwelle {e.wave}!", 120)
                self.subtitle = (f"Belohnung x{e.reward_mult:.2f}".replace(".", ","), 120)
                self.trauma = min(1.0, self.trauma + 0.4)
            elif isinstance(e, ev.GateOpened):
                self.banner = ("Das Gartentor ist offen!", 150)
                self.rings.append(Ring(e.x, e.y, 10, 6, 30, 30, c.get("gate", c["crit"])))
                self.burst(e.x, e.y, 30, c.get("gate", c["crit"]), speed=160, life=30, size=2)
            elif isinstance(e, ev.RunEnded) and e.victory:
                self.banner = ("Die Saat ist gerettet!", 240)
                self.trauma = 1.0
            elif isinstance(e, ev.ChestLocked):
                if players and e.player_id in players:
                    x, y = players[e.player_id]
                    self.texts.append(FloatingText(x, y - 40, f"{e.price} Samen nötig", c["white"], False, 60))
            elif isinstance(e, ev.WeaponPulse):  # own area weapons: warm ring, a bomb also bursts
                bomb = e.weapon == "pumpkin_bomb"
                color = c.get("pumpkin", c["crit"]) if bomb else c["crit"]
                self.rings.append(Ring(e.x, e.y, e.radius * 0.3, e.radius * 0.7 / 10, 10, 10, color))
                if bomb:
                    self.burst(e.x, e.y, 14, color, speed=150, life=18, size=2)
                    self.trauma = min(1.0, self.trauma + 0.15)
            elif isinstance(e, ev.ShrineActivated):
                self.trauma = min(1.0, self.trauma + 0.3)
                gold = c["crit"] if e.kind == "greed" else c.get("gate", c["crit"])
                self.rings.append(Ring(e.x, e.y, 10, 7, 30, 30, gold))
                self.burst(e.x, e.y, 30, gold, speed=160, life=34, size=2)
                self.banner = (f"{e.name}!", 110)
                reward = {
                    "greed": f"+{GREED_XP_PCT:.0f} % XP",
                    "courage": "Gratis-Karte (mind. selten)",
                    "curse": "Der nächste Boss kommt doppelt, Bonus-Karte (legendär)",
                    "elite": "3 Elite-Gegner! Jeder lässt eine Truhe fallen",
                }.get(e.kind, "")
                self.subtitle = (f"{reward} · Schwierigkeit {round(e.difficulty * 100)} %", 110)
            elif isinstance(e, ev.Critter):
                self._critter(e)
            elif isinstance(e, ev.SparklesCollected) and players and e.player_id in players:
                x, y = players[e.player_id]
                self.texts.append(FloatingText(x, y - 30, f"+{e.amount} Funkel", (255, 159, 192), e.amount > 1, 50))
            elif isinstance(e, ev.PotBroken):
                self.burst(e.x, e.y, 10, (226, 150, 120), speed=90, life=18, size=2)

    def start_reel(self, item_id: str) -> None:
        """Lucky draw: a strip of random item icons that lands on the found one."""
        pool = list(self.item_rarity) or [item_id]
        land = 18 + self.rng.randint(0, 4)
        strip = [pool[self.rng.randrange(len(pool))] for _ in range(land + 4)]
        strip[land] = item_id
        self.reel = Reel(item_id, self.item_rarity.get(item_id, "common"), strip, land)

    def skip_reel(self) -> None:
        """A tap skips the spin; a second tap (or time) closes it."""
        if self.reel is None:
            return
        if self.reel.landed:
            self.reel = None
        else:
            self.reel.frame = Reel.SPIN

    def level_up(self, x: float, y: float) -> None:
        self.rings.append(Ring(x, y, 8, 5, 24, 24, self.colors["crit"]))
        self.burst(x, y, 24, self.colors["crit"], speed=140, life=30, size=2)

    def _critter(self, e) -> None:
        """Announcements for the garden critters (balance.json critters)."""
        gold = self.colors["crit"]
        if e.kind == "golden_snail" and e.what == "appeared":
            self.banner = ("Eine Goldschnecke!", 110)
            self.subtitle = ("Schnapp sie, bevor sie sich eingräbt!", 110)
        elif e.kind == "golden_snail" and e.what == "caught":
            self.banner = ("Goldschnecke gefangen!", 100)
            self.burst(e.x, e.y, 40, gold, speed=180, life=40, size=2)
            self.trauma = min(1.0, self.trauma + 0.3)
        elif e.kind == "golden_snail":
            self.toast = ("Die Goldschnecke ist entwischt.", 150)
        elif e.kind == "gnome":
            self.banner = ("Der Gartenzwerg ist frei!", 110)
            self.subtitle = ("Zum Dank: eine Truhe.", 110)
            self.burst(e.x, e.y, 30, (230, 70, 70), speed=140, life=34, size=2)
        elif e.kind == "ladybug":
            self.toast = ("Glückskäfer! Eine Weile mehr Schaden.", 150)
            self.burst(e.x, e.y, 16, (230, 60, 60), speed=100, life=24, size=2)

    def footstep(self, x: float, y: float, moving: bool) -> None:
        """Small dust puffs at the feet while walking (called by the renderer once per frame)."""
        if not moving:
            self._step = 0
            return
        self._step += 1
        if self._step % 9 == 1:
            r = self.rng
            for _ in range(2):
                self.particles.append(
                    Particle(
                        x + r.uniform(-6, 6),
                        y,
                        r.uniform(-20, 20),
                        r.uniform(-25, -5),
                        12,
                        12,
                        self.colors.get("dust", (214, 196, 170)),
                        2,
                    )
                )

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
        self.hurt = {k: v - 1 for k, v in self.hurt.items() if v > 1}
        for cp in self.corpses:
            cp[3] -= 1
        self.corpses = [cp for cp in self.corpses if cp[3] > 0]
        for lst in (self.beams, self.sweeps):
            for item in lst:
                item[-1] -= 1
        self.beams = [b for b in self.beams if b[-1] > 0]
        self.sweeps = [w for w in self.sweeps if w[-1] > 0]
        for b in self.bolts:
            b.life -= 1
        self.bolts = [b for b in self.bolts if b.life > 0]
        if self.intro is not None:
            self.intro[2] -= 1
            if self.intro[2] <= 0:
                self.intro = None
                self.trauma = min(1.0, self.trauma + 0.5)
        if self.reel is not None:
            self.reel.frame += 1
            if self.reel.frame == Reel.SPIN:  # landing pop
                self.trauma = min(1.0, self.trauma + 0.25)
            if self.reel.done:
                self.reel = None
        if self.subtitle:
            text, frames = self.subtitle
            self.subtitle = (text, frames - 1) if frames > 1 else None
        self.trauma = max(0.0, self.trauma - 1.5 / 60)
        if self.banner:
            text, frames = self.banner
            self.banner = (text, frames - 1) if frames > 1 else None
        if self.hint:
            text, frames = self.hint
            self.hint = (text, frames - 1) if frames > 1 else None
        elif self.hints:
            self.hint = (self.hints.pop(0), HINT_FRAMES)
        if self.toast:
            text, frames = self.toast
            self.toast = (text, frames - 1) if frames > 1 else None

    def shake(self, max_px: int = 6) -> tuple[int, int]:
        """Screen offset from trauma: strength grows with trauma squared."""
        s = self.trauma * self.trauma * max_px if self.shake_on else 0.0
        if s < 0.5:
            return 0, 0
        return round(self.rng.uniform(-s, s)), round(self.rng.uniform(-s, s))
