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
