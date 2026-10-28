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
class PotBroken(Event):
    x: float
    y: float
    content: str


@dataclass(frozen=True, slots=True)
class SeedsCollected(Event):
    amount: int
