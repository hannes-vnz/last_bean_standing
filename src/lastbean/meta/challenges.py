"""Challenges (challenges.json): progress over runs, completion at the end of a run, rewards.

Rewards: Funkelsteine (`stones`), titles, skins, locked upgrades and modes. Character unlocks are
recorded too; the six beans of phase 1 are playable from the start (decided with Paket H).
"""

from __future__ import annotations

from typing import Any

# Run statistics of the creative challenges (Paket K), straight from RunResult.stats.
CREATIVE_STATS = ("golden_snails", "gnomes", "ladybugs", "longest_still_s", "flawless_bosses", "distance_m",
                  "max_item_stack", "shrine_kinds", "max_kills_10s", "weapons_owned")  # fmt: skip
# Stats that a challenge wants below a value (op "<"), and where the run stores them.
LESS_THAN_STATS = {"stage2_reached_s": "stage2_s", "first_boss_s": "first_boss_s"}
# Lifetime sums kept in profile["lifetime"], from RunResult.stats / fields.
LIFETIME_FROM_STATS = {
    "crits": "crits_total",
    "poison_damage": "poison_damage_total",
    "low_hp_s": "low_hp_seconds_total",
}
REWARD_NAMES = {"title": "Titel", "unlock_skin": "Skin", "unlock_upgrade": "Upgrade", "unlock_character": "Bohne",
                "unlock_mode": "Modus"}  # fmt: skip


def _store(profile: dict[str, Any]) -> dict[str, Any]:
    life = profile.setdefault("lifetime", {})
    profile.setdefault("challenges_done", [])
    profile.setdefault("titles", [])
    profile.setdefault("skins", [])
    profile.setdefault("unlocked", {"upgrades": [], "characters": [], "modes": []})
    return life


def _cond(ch) -> dict[str, Any]:
    """The condition as one flat dict (type, stat, op, value and extras such as character, boss, biome, ids)."""
    c = ch.condition
    return {**c.extra, "type": c.type, "stat": c.stat, "op": c.op, "value": c.value}


def run_value(stat: str, cond: dict, result: dict[str, Any]) -> float:
    """A run statistic of one finished run (RunResult.to_dict())."""
    stats = result.get("stats") or {}
    if stat == "minutes_survived":
        return result["seconds"] / 60.0
    if cond.get("mode") and cond["mode"] != result.get("mode", "normal"):
        return 0.0
    if cond.get("op") == "<":  # "faster than": counts (as the full target) when the time was reached in time
        reached = stats.get(LESS_THAN_STATS.get(stat, stat))
        return cond["value"] if reached is not None and reached < cond["value"] else 0.0
    return float({
        "flawless_wave": stats.get("flawless_wave", 0.0),
        "level_reached": result["level"],
        "stage_reached": result.get("stage", 1),
        "kills_in_run": result["kills"],
        "swarm_seconds": result.get("swarm_seconds", 0),
        "shrines_activated": result.get("shrines", 0),
        "damage_taken_run": result.get("damage_taken", 0.0),
    }.get(stat, stats.get(stat, 0.0)))  # fmt: skip


def record_lifetime(profile: dict[str, Any], result: dict[str, Any]) -> None:
    """Add one run to the lifetime sums and keep the best value of each run statistic."""
    life = _store(profile)
    stats = result.get("stats") or {}
    for key, name in LIFETIME_FROM_STATS.items():
        life[name] = life.get(name, 0.0) + float(stats.get(key, 0.0))
    for key, value in stats.items():
        if key.startswith("kills_"):
            life[key] = life.get(key, 0.0) + value
    life["damage_taken_total"] = life.get("damage_taken_total", 0.0) + float(result.get("damage_taken", 0.0))
    life["elite_kills_total"] = life.get("elite_kills_total", 0.0) + int(result.get("elites", 0))
    bosses = life.setdefault("bosses", {})
    for b in result.get("boss_ids") or []:
        bosses[b] = bosses.get(b, 0) + 1
    best = life.setdefault("best", {})
    for stat in ("minutes_survived", "flawless_wave", "level_reached", "stage_reached", "kills_in_run",
                 "swarm_seconds", "shrines_activated", "damage_taken_run", *CREATIVE_STATS):  # fmt: skip
        best[stat] = max(best.get(stat, 0.0), run_value(stat, {}, result))
        char_best = best.setdefault("by_character", {}).setdefault(result["character"], {})
        char_best[stat] = max(char_best.get(stat, 0.0), run_value(stat, {}, result))


def profile_value(stat: str, cond: dict, profile: dict[str, Any], characters_playable: int) -> float:
    life = _store(profile)
    totals = profile.get("totals", {})
    bosses = life.get("bosses", {})
    if stat == "boss_defeated":
        return float(bosses.get(cond.get("boss"), 0))
    if stat == "kills_in_biome":
        return float(life.get(f"kills_{cond.get('biome')}", 0.0))
    return float({
        "kills_total": totals.get("kills", 0),
        "runs_total": totals.get("runs", 0),
        "boss_kills_total": sum(bosses.values()),
        "distinct_bosses_defeated": len(bosses),
        "characters_unlocked": characters_playable + len(profile["unlocked"]["characters"]),
    }.get(stat, life.get(stat, 0.0)))  # fmt: skip


def progress(ch, profile: dict[str, Any], characters_playable: int, result: dict | None = None) -> tuple[float, float]:
    """(current, target) of a challenge: profile sums, or the best run (or `result` for this run)."""
    cond = _cond(ch)
    target = float(cond.get("value") or len(cond.get("ids", ())) or 1)
    if cond["type"] == "profile_stat":
        return profile_value(cond["stat"], cond, profile, characters_playable), target
    if cond["type"] == "run_flag":
        owned = set((result or {}).get("owned") or [])
        return float(len(owned & set(cond["ids"]))), float(len(cond["ids"]))
    if result is not None:
        if cond.get("character") and cond["character"] != result["character"]:
            return 0.0, target
        return run_value(cond["stat"], cond, result), target
    best = _store(profile).get("best", {})
    if cond.get("character"):
        best = best.get("by_character", {}).get(cond["character"], {})
    if cond.get("op") == "<":
        return 0.0, target
    return float(best.get(cond["stat"], 0.0)), target


def evaluate(profile: dict[str, Any], result: dict[str, Any], challenges, characters_playable: int) -> list:
    """Complete every challenge this run reached (after record_run and record_lifetime); grant rewards.
    Returns the newly completed challenges."""
    _store(profile)
    done = set(profile["challenges_done"])
    new = []
    for ch in challenges:
        if ch.id in done:
            continue
        current, target = progress(ch, profile, characters_playable, result)
        if current >= target:
            new.append(ch)
            grant(profile, ch)
    return new


def evaluate_profile(profile: dict[str, Any], challenges, characters_playable: int) -> list:
    """Challenges that only depend on profile sums (e.g. squished menu slugs): checked outside a run."""
    _store(profile)
    done = set(profile["challenges_done"])
    new = []
    for ch in challenges:
        if ch.id in done or ch.condition.type != "profile_stat":
            continue
        current, target = progress(ch, profile, characters_playable)
        if current >= target:
            new.append(ch)
            grant(profile, ch)
    return new


def grant(profile: dict[str, Any], ch) -> None:
    _store(profile)
    profile["challenges_done"].append(ch.id)
    reward = ch.reward
    profile["sparkles"] = profile.get("sparkles", 0) + int(reward.stones or 0)
    kind, rid = reward.type, reward.id
    if kind == "title" and rid not in profile["titles"]:
        profile["titles"].append(rid)
    elif kind == "unlock_skin" and rid not in profile["skins"]:
        profile["skins"].append(rid)
    elif kind in ("unlock_upgrade", "unlock_character", "unlock_mode"):
        bucket = profile["unlocked"][kind.split("_", 1)[1] + "s"]
        if rid not in bucket:
            bucket.append(rid)


def reward_names(content) -> dict[str, str]:
    """Display names of everything a challenge can unlock."""
    names = {s.id: s.name for s in content.skins}
    names.update({c.id: c.name for c in content.characters})
    names.update({u.id: u.name for u in content.upgrades})
    names.update({m.id: m.name for m in content.modes})
    return names


def reward_text(ch, names: dict[str, str] | None = None) -> str:
    """'Titel „Glutfreund“ · 150 Funkelsteine' and the like."""
    reward = ch.reward
    kind, rid = reward.type, reward.id
    label = REWARD_NAMES.get(kind, kind)
    parts = [f"{label} „{(names or {}).get(rid, rid)}“"] if rid else []
    if reward.stones:
        parts.append(f"{reward.stones} Funkelsteine")
    return " · ".join(parts)
