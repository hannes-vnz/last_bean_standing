"""Shrines on the map (shrines.json): stand in the circle to charge them, once per shrine.

Gier-Schrein: raises the difficulty for more XP (and, through the difficulty factor, more points).
Mut-Schrein: raises the difficulty for a free card of at least rarity "rare".
Fluchstein: raises the difficulty; the next bed boss comes once more, cursed bosses give a legendary card.
Elite-Schrein: raises the difficulty and calls 3 elites at once (each drops its elite chest).
"""

from __future__ import annotations

from dataclasses import dataclass

# Shrine kinds the simulation implements, and whether charging needs standing still.
SHRINE_KINDS = {"greed": True, "courage": False, "curse": True, "elite": True}


@dataclass(frozen=True, slots=True)
class ShrineRules:
    id: str
    name: str
    count: int  # per run, spread over the beds (earlier beds get the remainder)
    channel_s: float
    radius: float
    difficulty_add: float
    still: bool  # charging only while standing still

    @classmethod
    def from_content(cls, s, stage_count: int) -> ShrineRules:
        return cls(s.id, s.name, int(s.count), float(s.channel_s), float(s.radius_px), float(s.difficulty_add),
                   SHRINE_KINDS[s.id])  # fmt: skip

    def on_stage(self, stage: int, stage_count: int) -> int:
        """How many of this shrine lie in bed `stage` (0-based)."""
        n = max(1, stage_count)
        return self.count // n + (1 if stage < self.count % n else 0)


@dataclass(slots=True)
class Shrine:
    rules: ShrineRules
    x: float
    y: float
    charge: int = 0  # ticks charged so far
