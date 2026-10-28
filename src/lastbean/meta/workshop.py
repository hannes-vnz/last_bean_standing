"""Funkelsteine and the workshop (shop.json): small permanent bonuses bought between runs.

Costs: round(base_cost x 1.5^(level-1)) for each level; selling refunds everything spent (100 %).
Payout per run: floor(points / 100 x reward factor) plus drops (shop.json currency.run_drops).
"""

from __future__ import annotations

import dataclasses
import math
from typing import Any

# Workshop stat names that the simulation calls differently.
STAT_ALIASES = {"xp_pct": "xp_gain_pct"}
# Run packs (shop.json run_packs): their effects are texts there; the numbers are copied from them.
PACK_EFFECTS = {
    "pack_provisions": ("heal_orb_chance_pct", 5.0),  # (text) "+5 % Heilkugel-Chance"
    "pack_clover": ("luck", 10.0),  # (text) "+10 Glück"
    "pack_map": ("show_shrines_on_map", 1.0),  # (text) "Schreine sind sichtbar"
    "pack_headstart": ("start_levels", 2.0),  # (text) "Start bei Level 3 (2 Gratis-Upgradewahlen)"
}


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


def buy_pack(profile: dict[str, Any], shop, pack_id: str) -> bool:
    """Put a run pack in the bag for the next run (at most run_packs_max_per_run, each once)."""
    pack = next((p for p in shop.run_packs if p["id"] == pack_id), None)
    bag = profile.setdefault("packs", [])
    if pack is None or pack_id in bag or len(bag) >= shop.run_packs_max_per_run:
        return False
    if profile.get("sparkles", 0) < pack["cost"]:
        return False
    profile["sparkles"] -= pack["cost"]
    bag.append(pack_id)
    return True


def return_pack(profile: dict[str, Any], shop, pack_id: str) -> None:
    """Take a pack out of the bag again before the run (full refund)."""
    bag = profile.setdefault("packs", [])
    pack = next((p for p in shop.run_packs if p["id"] == pack_id), None)
    if pack is not None and pack_id in bag:
        bag.remove(pack_id)
        profile["sparkles"] = profile.get("sparkles", 0) + pack["cost"]


def meta_mods(profile: dict[str, Any], shop, packs: tuple[str, ...] = ()) -> tuple[tuple[str, float], ...]:
    """Workshop bonuses (plus the given run packs) as (stat, total) for WorldConfig.meta_mods."""
    out: dict[str, float] = {}
    for pid in packs:
        if pid in PACK_EFFECTS:
            stat, value = PACK_EFFECTS[pid]
            out[stat] = max(out.get(stat, 0.0), value) if stat == "show_shrines_on_map" else out.get(stat, 0.0) + value
    for item in shop.workshop:
        lv = levels(profile).get(item.id, 0)
        if lv:
            stat = STAT_ALIASES.get(item.effect["stat"], item.effect["stat"])
            out[stat] = out.get(stat, 0.0) + float(item.effect["per_level"]) * lv
    return tuple(sorted(out.items()))


def payout(result: dict[str, Any], shop, final_boss_won: bool) -> dict[str, int]:
    """Funkelsteine for one finished run, itemised for the results screen: the share of the points and
    everything picked up in the run (pests, elites, bosses, chests), plus the victory bonus."""
    drops = shop.raw["currency"]["run_drops"]
    factor = 1.0 + 0.8 * (float(result["difficulty"]) - 1.0)
    parts = {
        "Punkte": math.floor(int(result["score"]) / 100 * factor),
        "Gefunden": int(result.get("sparkles", 0)),
    }
    if final_boss_won:
        parts["Sieg"] = drops["victory_bonus"]
    return {k: int(v) for k, v in parts.items() if v}


# ---------------------------------------------------------------------------- greenhouse (Paket K)


def greenhouse(profile: dict[str, Any]) -> dict[str, list[str]]:
    """What grows in the greenhouse: bought wonders and planted seeds (weapons)."""
    g = profile.setdefault("greenhouse", {})
    g.setdefault("wonders", [])
    g.setdefault("seeds", [])
    return g


def _wonder(shop, wid: str) -> dict | None:
    return next((w for w in shop.raw.get("wonders", []) if w["id"] == wid), None)


def _seed(shop, weapon: str) -> dict | None:
    return next((x for x in shop.raw.get("seeds", []) if x["weapon"] == weapon), None)


def buy_greenhouse(profile: dict[str, Any], shop, kind: str, item_id: str) -> bool:
    """kind "wonders" or "seeds": pay once, it stays (and can be sold back for the full price)."""
    item = _wonder(shop, item_id) if kind == "wonders" else _seed(shop, item_id)
    owned = greenhouse(profile)[kind]
    if item is None or item_id in owned or profile.get("sparkles", 0) < item["cost"]:
        return False
    profile["sparkles"] -= item["cost"]
    owned.append(item_id)
    return True


def sell_greenhouse(profile: dict[str, Any], shop, kind: str, item_id: str) -> None:
    item = _wonder(shop, item_id) if kind == "wonders" else _seed(shop, item_id)
    owned = greenhouse(profile)[kind]
    if item is not None and item_id in owned:
        owned.remove(item_id)
        profile["sparkles"] = profile.get("sparkles", 0) + item["cost"]


def wonder_effects(profile: dict[str, Any], shop) -> dict[str, float]:
    out: dict[str, float] = {}
    for wid in greenhouse(profile)["wonders"]:
        w = _wonder(shop, wid)
        for k, v in (w or {}).get("effect", {}).items():
            out[k] = out.get(k, 0.0) + float(v)
    return out


def apply_greenhouse(cfg, profile: dict[str, Any], shop):
    """The run's config with the wonders (cards, weapon slots, chest price) and only grown weapons."""
    fx = wonder_effects(profile, shop)
    locked = {x["weapon"] for x in shop.raw.get("seeds", [])} - set(greenhouse(profile)["seeds"])
    changes: dict[str, Any] = {"weapons": tuple(w for w in cfg.weapons if w.id not in locked)}
    if fx.get("level_up_choices_add"):
        changes["level_up_choices"] = cfg.level_up_choices + int(fx["level_up_choices_add"])
    if fx.get("weapon_slots_add"):
        changes["weapon_slots"] = cfg.weapon_slots + int(fx["weapon_slots_add"])
    if fx.get("chest_discount_pct") and cfg.economy is not None:
        price = cfg.economy.price_start * (1.0 - fx["chest_discount_pct"] / 100.0)
        changes["economy"] = dataclasses.replace(cfg.economy, price_start=price)
    extra = {k: v for k, v in fx.items() if k in ("revives", "start_weapon")}
    if extra:
        meta = dict(cfg.meta_mods)
        for k, v in extra.items():
            meta[k] = meta.get(k, 0.0) + v
        changes["meta_mods"] = tuple(sorted(meta.items()))
    return dataclasses.replace(cfg, **changes)
