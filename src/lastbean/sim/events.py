"""Events emitted by `World.step`. Effects, audio and challenges react to them.

Every event carries a `player_id` (None for global events) so co-op can route them later.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Event:
    tick: int
    player_id: int | None


@dataclass(frozen=True, slots=True)
class RunStarted(Event):
    seed: int


@dataclass(frozen=True, slots=True)
class WaveStarted(Event):
    wave: int


@dataclass(frozen=True, slots=True)
class ShotFired(Event):
    x: float
    y: float
    dx: float
    dy: float
    weapon: str = ""  # extra weapon id, "" for the character's own


@dataclass(frozen=True, slots=True)
class EnemyHit(Event):
    enemy_id: int
    x: float
    y: float
    damage: float
    crit: bool


@dataclass(frozen=True, slots=True)
class EnemyKilled(Event):
    enemy_id: int
    kind: str
    x: float
    y: float


@dataclass(frozen=True, slots=True)
class PlayerHit(Event):
    damage: float
    hp_left: float


@dataclass(frozen=True, slots=True)
class PlayerDied(Event):
    pass


@dataclass(frozen=True, slots=True)
class RunEnded(Event):
    time_s: float
    victory: bool = False


@dataclass(frozen=True, slots=True)
class LevelUp(Event):
    level: int


@dataclass(frozen=True, slots=True)
class UpgradeOffered(Event):
    upgrade_ids: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class UpgradeChosen(Event):
    upgrade_id: str
    level: int
    tier: str = "common"  # rarity rolled for the card (Paket F)


@dataclass(frozen=True, slots=True)
class EnemySpawned(Event):
    enemy_id: int
    kind: str
    biome: str | None


@dataclass(frozen=True, slots=True)
class ProjectileBlocked(Event):
    x: float
    y: float


@dataclass(frozen=True, slots=True)
class EliteSpawned(Event):
    enemy_id: int
    kind: str
    affixes: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class BossSpawned(Event):
    enemy_id: int
    boss: str


@dataclass(frozen=True, slots=True)
class BossPhase(Event):
    enemy_id: int
    boss: str
    phase: int


@dataclass(frozen=True, slots=True)
class BossKilled(Event):
    enemy_id: int
    boss: str
    time_s: float


@dataclass(frozen=True, slots=True)
class EnemyShotFired(Event):
    enemy_id: int
    x: float
    y: float
    lobbed: bool


@dataclass(frozen=True, slots=True)
class HazardActivated(Event):
    kind: str
    x: float
    y: float
    radius: float


@dataclass(frozen=True, slots=True)
class ChestDropped(Event):
    x: float
    y: float
    min_rarity: str


@dataclass(frozen=True, slots=True)
class ChestOpened(Event):
    min_rarity: str


@dataclass(frozen=True, slots=True)
class AbilityUsed(Event):
    ability: str
    x: float
    y: float


@dataclass(frozen=True, slots=True)
class PickupCollected(Event):
    kind: str
    x: float
    y: float


@dataclass(frozen=True, slots=True)
class ItemGained(Event):
    item_id: str
    count: int
    source: str  # chest kind


@dataclass(frozen=True, slots=True)
class ChestLocked(Event):
    """Touched a chest without enough seeds (the HUD shows the price)."""

    price: int


@dataclass(frozen=True, slots=True)
class ShrineActivated(Event):
    kind: str  # "greed" or "courage"
    name: str
    x: float
    y: float
    difficulty: float  # D after the activation


@dataclass(frozen=True, slots=True)
class PotBroken(Event):
    x: float
    y: float
    content: str


@dataclass(frozen=True, slots=True)
class SeedsCollected(Event):
    amount: int


@dataclass(frozen=True, slots=True)
class WeaponPulse(Event):
    """An area weapon went off: a nova ring around the player or a bursting bomb."""

    weapon: str
    x: float
    y: float
    radius: float


@dataclass(frozen=True, slots=True)
class StageStarted(Event):
    """A garden bed begins (also the first one at the start of the run)."""

    stage: int  # 1-based
    name: str


@dataclass(frozen=True, slots=True)
class FloodWarning(Event):
    stage: int


@dataclass(frozen=True, slots=True)
class FloodStarted(Event):
    stage: int


@dataclass(frozen=True, slots=True)
class FloodWave(Event):
    """Every flood_wave_s of Plagenflut a new wave rolls in (wave 1 starts with the flood)."""

    stage: int
    wave: int
    reward_mult: float


@dataclass(frozen=True, slots=True)
class GateOpened(Event):
    x: float
    y: float


@dataclass(frozen=True, slots=True)
class Zap(Event):
    """Lightning from the "Schock" effect: the points it jumped through."""

    points: tuple[tuple[float, float], ...]


@dataclass(frozen=True, slots=True)
class PlayerDodged(Event):
    x: float
    y: float


@dataclass(frozen=True, slots=True)
class PlayerRevived(Event):
    x: float
    y: float


@dataclass(frozen=True, slots=True)
class BeamFired(Event):
    """A light beam (weapon "Brennglasstrahl") from (x, y) to (x2, y2)."""

    weapon: str
    x: float
    y: float
    x2: float
    y2: float
    width: float


@dataclass(frozen=True, slots=True)
class SweepSwung(Event):
    """A melee sweep (weapon "Sichel"): arc around (dx, dy)."""

    weapon: str
    x: float
    y: float
    dx: float
    dy: float
    radius: float
    arc_deg: float
