"""Shrines on the map (shrines.json): stand in the circle to charge them, once per shrine.

Gier-Schrein: raises the difficulty for more XP (and, through the difficulty factor, more points).
Mut-Schrein: raises the difficulty for a free card of at least rarity "rare".
"""

from __future__ import annotations

from dataclasses import dataclass

# Shrine kinds the simulation implements, and whether charging needs standing still.
SHRINE_KINDS = {"greed": True, "courage": False}


@dataclass(frozen=True, slots=True)
class ShrineRules:
    id: str
    name: str
    per_stage: int
    channel_s: float
    radius: float
    difficulty_add: float
    still: bool  # charging only while standing still

    @classmethod
    def from_content(cls, s, stage_count: int) -> ShrineRules:
        per_stage = max(1, round(s.count / max(1, stage_count)))
        return cls(s.id, s.name, per_stage, float(s.channel_s), float(s.radius_px), float(s.difficulty_add),
                   SHRINE_KINDS[s.id])  # fmt: skip


@dataclass(slots=True)
class Shrine:
    rules: ShrineRules
    x: float
    y: float
    charge: int = 0  # ticks charged so far
