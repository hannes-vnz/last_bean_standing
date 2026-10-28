"""Funkelsteine and the workshop (shop.json): small permanent bonuses bought between runs.

Costs: round(base_cost x 1.5^(level-1)) for each level; selling refunds everything spent (100 %).
Payout per run: floor(points / 100 x reward factor) plus drops (shop.json currency.run_drops).
"""

from __future__ import annotations

import math
from typing import Any

# Workshop stat names that the simulation calls differently.
STAT_ALIASES = {"xp_pct": "xp_gain_pct"}


def level_cost(item, level: int) -> int:
    """Price of buying `level` (1 = first level)."""
    return round(item.base_cost * 1.5 ** (level - 1))


def spent_on(item, level: int) -> int:
    return sum(level_cost(item, n) for n in range(1, level + 1))


def levels(profile: dict[str, Any]) -> dict[str, int]:
    return profile.setdefault("workshop", {})


def buy(profile: dict[str, Any], item) -> bool:
    """One level more, if affordable and not maxed."""
    lv = levels(profile).get(item.id, 0)
    if lv >= item.max_level:
        return False
    cost = level_cost(item, lv + 1)
    if profile.get("sparkles", 0) < cost:
        return False
    profile["sparkles"] -= cost
    levels(profile)[item.id] = lv + 1
    return True


def refund(profile: dict[str, Any], item) -> int:
    """Sell all levels of one item; returns the Funkelsteine given back."""
    lv = levels(profile).pop(item.id, 0)
    back = spent_on(item, lv)
    profile["sparkles"] = profile.get("sparkles", 0) + back
    return back


def meta_mods(profile: dict[str, Any], shop) -> tuple[tuple[str, float], ...]:
    """Workshop bonuses as (stat, total) for WorldConfig.meta_mods."""
    out: dict[str, float] = {}
    for item in shop.workshop:
        lv = levels(profile).get(item.id, 0)
        if lv:
            stat = STAT_ALIASES.get(item.effect["stat"], item.effect["stat"])
            out[stat] = out.get(stat, 0.0) + float(item.effect["per_level"]) * lv
    return tuple(sorted(out.items()))


def payout(result: dict[str, Any], shop, final_boss_won: bool) -> dict[str, int]:
    """Funkelsteine for one finished run, itemised for the results screen.

    Kill drops use the expected value (kills x chance), so the payout does not need a random roll."""
    drops = shop.raw["currency"]["run_drops"]
    factor = 1.0 + 0.8 * (float(result["difficulty"]) - 1.0)
    bosses = int(result["bosses"])
    parts = {
        "Punkte": math.floor(int(result["score"]) / 100 * factor),
        "Gegner": math.floor(int(result["kills"]) * drops["normal_kill_chance_pct"] / 100),
        "Elite": int(result.get("elites", 0)) * drops["elite"],
        "Bosse": (bosses - (1 if final_boss_won else 0)) * drops["biome_boss"],
        "Truhen": int(result.get("chests", 0)) * drops["chest"],
    }
    if final_boss_won:
        parts["Schnitter"] = drops["final_boss"] + drops["victory_bonus"]
    return {k: int(v) for k, v in parts.items() if v}
