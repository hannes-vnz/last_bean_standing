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

SUPPORTED_SPECIALS = frozenset({"gravity_pull", "standing_slow"})  # handled in World._upgrade_specials
SUPPORTED_STATS = frozenset(
    {
        "minions_add",
        "orbit_blades",
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
        # Paket F (procs, conditions, status effects)
        "max_hp_pct",
        "heal_orb_chance_pct",
        "area_pct",
        "thorns_pct",
        "projectile_size_pct",
        "projectile_speed_pct",
        "dodge_chance_pct",
        "flat_damage_reduction",
        "rerolls",
        "banishes",
        "ignite_chance_pct",
        "chill_slow_pct",
        "poison_pct_per_s",
        "shock_chance_pct",
        "bounce_add",
        "execute_damage_pct",
        "lifesteal_pct",
        "shield_flat",
        "low_hp_damage_pct",
        "overcharge_pct",
        "explosive_hit_pct",
        "aura_dps",
        "elemental_damage_pct",
        "revives",
        "kill_haste_max_pct",
        "shrapnel_chance_pct",
    }
)
INSTANT_STATS = frozenset({"rerolls", "banishes"})  # granted once when the card is taken
# Character passives with extra numbers (radius, stacks, damage): handled by name in derive_stats.
PASSIVE_SPECIAL = frozenset(
    {"damage_pct_vs_burning", "damage_pct_per_nearby", "aura_slow_pct", "bonus_strike_every_n_shots"}
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
    # Effects without a stat (Paket J): (name, numbers by key; lists hold one value per level)
    specials: tuple[tuple[str, tuple[tuple[str, tuple[float, ...]], ...]], ...] = ()

    @classmethod
    def from_content(cls, u) -> UpgradeDef:
        effects = tuple((e["stat"], float(e["per_level"])) for e in u.effects if "stat" in e and "per_level" in e)
        specials = tuple(
            (
                e["special"],
                tuple(
                    (k, tuple(float(x) for x in (v if isinstance(v, list) else [v])))
                    for k, v in e.items()
                    if k != "special" and isinstance(v, (int, float, list))
                ),
            )
            for e in u.effects
            if "special" in e
        )
        return cls(u.id, u.rarity, u.max_level, u.tags, effects, u.impl_phase, u.unlocked_at_start, specials)

    @property
    def supported(self) -> bool:
        return (
            (bool(self.effects) or bool(self.specials))
            and all(stat in SUPPORTED_STATS for stat, _ in self.effects)
            and all(name in SUPPORTED_SPECIALS for name, _ in self.specials)
        )


def modifier_sums(levels: dict[str, float], defs: dict[str, UpgradeDef], items: dict[str, int] | None = None,
                  item_defs: dict | None = None) -> dict[str, float]:  # fmt: skip
    """Stat sums from upgrade power plus item stacks (an item counts once per copy).

    `levels` is the summed card power per upgrade: 1 per common card, more for rarer cards (card_tier_mult)."""
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
    special: dict[str, tuple[float, float, float]] = {}
    for stat, value, a, b in base.passive:
        if stat == "damage_pct_far":
            far_pct, far_threshold = far_pct + value, a
        elif stat in PASSIVE_SPECIAL:
            special[stat] = (value, a, b)
        else:
            mods[stat] = mods.get(stat, 0.0) + value
    pct = lambda key: 1.0 + mods.get(key, 0.0) / 100.0  # noqa: E731
    return Stats(
        max_hp=max(1.0, (base.hp + mods.get("max_hp_flat", 0.0)) * pct("max_hp_pct")),
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
        heal_orb_chance_pct=mods.get("heal_orb_chance_pct", 0.0),
        area_mult=max(0.2, pct("area_pct")),
        thorns_pct=mods.get("thorns_pct", 0.0),
        projectile_size_mult=max(0.2, pct("projectile_size_pct")),
        projectile_speed_mult=max(0.2, pct("projectile_speed_pct")),
        dodge_chance_pct=min(60.0, mods.get("dodge_chance_pct", 0.0)),
        armor=mods.get("flat_damage_reduction", 0.0),
        ignite_chance_pct=min(100.0, mods.get("ignite_chance_pct", 0.0)),
        chill_slow_pct=min(60.0, mods.get("chill_slow_pct", 0.0)),
        poison_pct_per_s=mods.get("poison_pct_per_s", 0.0),
        shock_chance_pct=min(100.0, mods.get("shock_chance_pct", 0.0)),
        bounces=int(mods.get("bounce_add", 0.0)),
        execute_damage_pct=mods.get("execute_damage_pct", 0.0),
        lifesteal_pct=mods.get("lifesteal_pct", 0.0),
        shield=mods.get("shield_flat", 0.0),
        low_hp_damage_pct=mods.get("low_hp_damage_pct", 0.0),
        overcharge_pct=mods.get("overcharge_pct", 0.0),
        explosive_hit_pct=mods.get("explosive_hit_pct", 0.0),
        aura_dps=mods.get("aura_dps", 0.0),
        elemental_mult=pct("elemental_damage_pct"),
        revives=int(mods.get("revives", 0.0)),
        kill_haste_max_pct=mods.get("kill_haste_max_pct", 0.0),
        shrapnel_chance_pct=min(100.0, mods.get("shrapnel_chance_pct", 0.0)),
        minions_add=int(mods.get("minions_add", 0.0)),
        orbit_blades=int(mods.get("orbit_blades", 0.0)),
        burning_damage_mult=1.0 + special.get("damage_pct_vs_burning", (0.0, 0, 0))[0] / 100.0,
        nearby_damage_pct=special.get("damage_pct_per_nearby", (0.0, 0, 0))[0],
        nearby_radius=special.get("damage_pct_per_nearby", (0, 0.0, 0))[1],
        nearby_max=int(special.get("damage_pct_per_nearby", (0, 0, 0.0))[2]),
        aura_slow_pct=special.get("aura_slow_pct", (0.0, 0, 0))[0],
        aura_slow_radius=special.get("aura_slow_pct", (0, 0.0, 0))[1],
        strike_every=int(special.get("bonus_strike_every_n_shots", (0.0, 0, 0))[0]),
        strike_damage_pct=special.get("bonus_strike_every_n_shots", (0, 0, 0.0))[2],
    )


def roll_tier(rng: Rng, rarity_weights: dict[str, float], luck: float = 0.0, luck_shift: float = 0.0) -> str:
    """Rarity of one level-up card (Paket F). Luck moves weight to rarer tiers like in `roll_offer`."""
    weights = [rarity_weights[r] * (1.0 + luck * luck_shift * i) for i, r in enumerate(RARITIES)]
    r = rng.random() * sum(weights)
    for tier, w in zip(RARITIES, weights, strict=True):
        if r < w:
            return tier
        r -= w
    return RARITIES[-1]


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
