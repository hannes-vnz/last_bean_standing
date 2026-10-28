"""In-run upgrades: stat modifiers, derived player stats and level-up offers.

Upgrades are data: each effect `{"stat": key, "per_level": x}` adds `x * level` to that
key. `derive_stats` turns the sums into combat stats. New stat keys are added in
`SUPPORTED_STATS` plus one line in `derive_stats`, never as a special case per upgrade.
"""

from __future__ import annotations

from dataclasses import dataclass

from .entities import CharacterStats, Stats
from .rng import Rng

RARITIES = ("common", "uncommon", "rare", "epic", "legendary")

SUPPORTED_STATS = frozenset(
    {
        "damage_pct",
        "attack_speed_pct",
        "range_pct",
        "crit_chance_pct",
        "crit_mult_add_pct",
        "max_hp_flat",
        "damage_taken_pct",
        "move_speed_pct",
        "pickup_radius_pct",
        "extra_attacks",
        "pierce_add",
        "regen_per_s",
        # Paket C (items)
        "xp_gain_pct",
        "gold_gain_pct",
        "luck",
        "cooldown_pct",
        "elite_damage_pct",
        "standing_damage_pct",
        "thorns_flat",
        "heal_per_kill",
        "i_frames_pct",
        "explode_on_kill_pct",
    }
)


@dataclass(frozen=True, slots=True)
class UpgradeDef:
    id: str
    rarity: str
    max_level: int
    tags: tuple[str, ...]
    effects: tuple[tuple[str, float], ...]  # (stat, per_level)
    impl_phase: int
    unlocked_at_start: bool

    @classmethod
    def from_content(cls, u) -> UpgradeDef:
        effects = tuple((e["stat"], float(e["per_level"])) for e in u.effects if "stat" in e and "per_level" in e)
        return cls(u.id, u.rarity, u.max_level, u.tags, effects, u.impl_phase, u.unlocked_at_start)

    @property
    def supported(self) -> bool:
        return bool(self.effects) and all(stat in SUPPORTED_STATS for stat, _ in self.effects)


def modifier_sums(levels: dict[str, int], defs: dict[str, UpgradeDef], items: dict[str, int] | None = None,
                  item_defs: dict | None = None) -> dict[str, float]:  # fmt: skip
    """Stat sums from upgrade levels plus item stacks (an item counts once per copy)."""
    sums: dict[str, float] = {}
    for uid, level in levels.items():
        for stat, per_level in defs[uid].effects:
            sums[stat] = sums.get(stat, 0.0) + per_level * level
    for iid, count in (items or {}).items():
        for stat, value in item_defs[iid].effects:
            sums[stat] = sums.get(stat, 0.0) + value * count
    return sums


def derive_stats(base: CharacterStats, mods: dict[str, float]) -> Stats:
    """Same source adds up, different sources multiply (DESIGN.md section 4, `stat_model`).

    The character's passive ability counts as one more source of the same stat keys.
    """
    mods = dict(mods)
    far_pct, far_threshold = 0.0, 0.0
    for stat, value, threshold in base.passive:
        if stat == "damage_pct_far":
            far_pct, far_threshold = far_pct + value, threshold
        else:
            mods[stat] = mods.get(stat, 0.0) + value
    pct = lambda key: 1.0 + mods.get(key, 0.0) / 100.0  # noqa: E731
    return Stats(
        max_hp=base.hp + mods.get("max_hp_flat", 0.0),
        speed=base.speed * pct("move_speed_pct"),
        damage=base.damage * pct("damage_pct"),
        attack_rate=base.attack_rate * pct("attack_speed_pct"),
        range=base.range * pct("range_pct"),
        crit_chance_pct=min(100.0, base.crit_chance_pct + mods.get("crit_chance_pct", 0.0)),
        crit_mult=base.crit_mult + mods.get("crit_mult_add_pct", 0.0) / 100.0,
        pierce=base.pierce + int(mods.get("pierce_add", 0.0)),
        extra_attacks=int(mods.get("extra_attacks", 0.0)),
        pickup_radius=base.pickup_radius * pct("pickup_radius_pct"),
        regen_per_s=mods.get("regen_per_s", 0.0),
        damage_taken_mult=max(0.1, pct("damage_taken_pct")),
        far_damage_pct=far_pct,
        far_threshold=far_threshold,
        xp_mult=pct("xp_gain_pct"),
        gold_mult=pct("gold_gain_pct"),
        luck=mods.get("luck", 0.0),
        cooldown_mult=max(0.2, pct("cooldown_pct")),
        elite_damage_mult=pct("elite_damage_pct"),
        standing_damage_mult=pct("standing_damage_pct"),
        thorns=mods.get("thorns_flat", 0.0),
        heal_per_kill=mods.get("heal_per_kill", 0.0),
        i_frames_mult=pct("i_frames_pct"),
        explode_on_kill_pct=min(100.0, mods.get("explode_on_kill_pct", 0.0)),
    )


def roll_offer(
    rng: Rng,
    pool: list[UpgradeDef],
    levels: dict[str, int],
    rarity_weights: dict[str, float],
    choices: int,
    luck: float = 0.0,
    luck_shift: float = 0.0,
) -> tuple[str, ...]:
    """Pick up to `choices` different upgrades, weighted by rarity, skipping maxed ones.

    Luck moves weight towards rarer tiers: each point multiplies tier i's weight by
    (1 + luck * luck_shift * i). The exact luck curve is open until a luck upgrade exists.
    """
    candidates = [u for u in pool if levels.get(u.id, 0) < u.max_level]
    weights = [rarity_weights[u.rarity] * (1.0 + luck * luck_shift * RARITIES.index(u.rarity)) for u in candidates]
    picked: list[str] = []
    while candidates and len(picked) < choices:
        total = sum(weights)
        if total <= 0:
            break
        r = rng.random() * total
        i = 0
        while i < len(weights) - 1 and r >= weights[i]:
            r -= weights[i]
            i += 1
        picked.append(candidates.pop(i).id)
        weights.pop(i)
    return tuple(picked)
