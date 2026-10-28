"""Run result and score. Keep in sync with docs/CONTENT.md ("Punkte") and server/app.py (max_plausible_score).

Punkte = 2 x Sekunden + 5 x Kills + 20 x Level + 500 x Bosse (+ Sieg, + Schwarmflut),
times the reward factor 1 + 0.8 x (D - 1) of the shrine difficulty D.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field


@dataclass(frozen=True, slots=True)
class ScoreRules:
    per_second: float
    per_kill: float
    per_level: float
    per_boss: float
    victory_bonus: float
    swarm_per_10s: float

    @classmethod
    def from_content(cls, content) -> ScoreRules:
        s = content.balance.raw["score"]
        return cls(
            s["per_second"], s["per_kill"], s["per_level"], s["per_boss"], s["victory_bonus"], s["swarm_per_10s"]
        )


@dataclass(frozen=True, slots=True)
class RunResult:
    """What a finished run reports to the profile, the results screen and (M6b) the leaderboard."""

    character: str
    seed: int
    seconds: int
    wave: int  # 0-based as in the game (0:00-0:30 is wave 0)
    kills: int
    level: int
    bosses: int
    difficulty: float
    victory: bool
    swarm_seconds: int
    swarm_mult: float
    damage_taken: float
    score: int
    stage: int = 1  # garden bed reached (Paket F)
    elites: int = 0  # elites killed (Funkelstein drops)
    chests: int = 0  # chests opened
    shrines: int = 0  # shrines activated
    stats: dict = field(default_factory=dict)  # challenge statistics (World.run_stats)
    boss_ids: list = field(default_factory=list)  # bosses defeated, by id
    owned: list = field(default_factory=list)  # upgrade and item ids at the end

    def to_dict(self) -> dict:
        return asdict(self)


def compute_score(
    rules: ScoreRules,
    seconds: int,
    kills: int,
    level: int,
    bosses: int,
    difficulty: float = 1.0,
    victory: bool = False,
    swarm_seconds: int = 0,
    swarm_mult: float = 1.0,
) -> int:
    base = rules.per_second * seconds + rules.per_kill * kills + rules.per_level * level + rules.per_boss * bosses
    if victory:
        base += rules.victory_bonus
    base += rules.swarm_per_10s * (swarm_seconds // 10) * swarm_mult
    return int(base * (1.0 + 0.8 * (difficulty - 1.0)))
