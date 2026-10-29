"""Challenges (challenges.json): run statistics from the simulation, lifetime sums, completion, rewards."""

import dataclasses

from lastbean.meta import challenges
from lastbean.meta.profile import new_profile, normalize, record_run
from lastbean.sim import PlayerInput, World, WorldConfig


def _result(**kw):
    base = dict(character="ranger", seed=1, seconds=100, wave=3, kills=50, level=5, bosses=0, difficulty=1.0,
                victory=False, swarm_seconds=0, swarm_mult=1.0, damage_taken=10.0, score=500, stage=1)  # fmt: skip
    base.update(kw)
    return base


def _ch(content, cid):
    return next(c for c in content.challenges if c.id == cid)


def test_run_and_lifetime_challenges_complete_once_and_pay(content):
    p = new_profile()
    res = _result(seconds=320, kills=120, stage=2, boss_ids=["snail_queen"], stats={"kills_compost": 120})
    record_run(p, res)
    challenges.record_lifetime(p, res)
    new = {c.id for c in challenges.evaluate(p, res, content.challenges, 6)}
    assert {"unlock_pyro", "unlock_storm", "boss_snail_queen", "unlock_up_second_wind"} <= new
    assert "unlock_cryo" not in new  # 120 of 300 compost kills
    assert p["sparkles"] == sum(_ch(content, c).reward.stones for c in new)
    assert "pyro" in p["unlocked"]["characters"] and "second_wind" in p["unlocked"]["upgrades"]
    assert challenges.progress(_ch(content, "unlock_cryo"), p, 6) == (120.0, 300.0)
    assert challenges.evaluate(p, res, content.challenges, 6) == []  # never twice
    p2 = normalize(p)  # survives saving
    assert p2["challenges_done"] == p["challenges_done"] and p2["lifetime"]["kills_compost"] == 120


def test_skin_challenges_need_their_bean_and_unlock_the_skin(content):
    p = new_profile()
    res = _result(character="pyro", seconds=200, stage=2)
    challenges.record_lifetime(p, res)
    new = {c.id for c in challenges.evaluate(p, res, content.challenges, 6)}
    assert "skin_pyro_a" in new and "skin_ranger_a" not in new
    assert "pyro_a" in p["skins"]
    p["skin"] = {"pyro": "pyro_a", "ranger": "ranger_a"}
    assert normalize(p)["skin"] == {"pyro": "pyro_a"}  # only owned skins stay chosen


def test_owns_all_and_glass_cannon(content):
    p = new_profile()
    res = _result(owned=["ignite", "chill", "toxin", "shock"], stats={"stage2_s": 200.0})
    new = {c.id for c in challenges.evaluate(p, res, content.challenges, 6)}
    assert {"unlock_up_elemental_storm", "unlock_up_glass_cannon"} <= new
    slow = _result(stats={"stage2_s": 250.0})
    later = challenges.evaluate(new_profile(), slow, content.challenges, 6)
    assert "unlock_up_glass_cannon" not in {c.id for c in later}


def test_simulation_counts_challenge_statistics(content):
    cfg = WorldConfig.from_content(content)
    cfg = dataclasses.replace(cfg, character=dataclasses.replace(cfg.character, hp=10**9, crit_chance_pct=50.0))
    w = World(2, cfg)
    for _ in range(70 * 60):
        p = w.players[0]
        w.step([PlayerInput(0, 0.0, 0.0, 0 if p.offer else None)])
    r = w.result().to_dict()
    assert r["stats"]["crits"] > 0 and r["stats"]["kills_seedbed"] == r["kills"]
    assert "flawless_wave" in r["stats"] or r["damage_taken"] > 0


def test_eternal_night_mode(content):
    normal = World(4, WorldConfig.from_content(content))
    night = World(4, WorldConfig.from_content(content, mode="eternal_night"))
    assert night.config.mode_hp_mult == 1.5 and night.config.mode_score_mult == 1.5
    assert night.reward_mult == normal.reward_mult * 1.25
    mob = normal.config.mobs[0]
    a, b = normal._spawn_enemy(mob, 10.0, 10.0, []), night._spawn_enemy(mob, 10.0, 10.0, [])
    assert b.max_hp == a.max_hp * 1.5
    r = night.result().to_dict()
    assert r["mode"] == "eternal_night" and night.snapshot().mode == "eternal_night"


def test_garden_critters_and_creative_stats(content):
    from lastbean.sim import TICK_HZ
    from lastbean.sim.events import Critter

    cfg = WorldConfig.from_content(content)
    cfg = dataclasses.replace(cfg, character=dataclasses.replace(cfg.character, hp=10**9))
    w = World(6, cfg)
    gnome_bed = w._gnome_bed
    assert gnome_bed in (0, 1) and w._snail_tick > 0
    if gnome_bed == 0:
        gnome = next(e for e in w.enemies if e.critter == "gnome")
        killed = set()
        for _ in range(10):
            w._weapon_hit(w.players[0], 0, gnome, 999.0, True, killed, [])
        assert gnome.eid in killed and w.run_stats["gnomes"] == 1
    events = []
    snail_at = w._snail_tick
    while w.stage_tick < snail_at + 2:
        p = w.players[0]
        events += w.step([PlayerInput(0, 0, 0, 0 if p.offer else None)])
    assert any(isinstance(e, Critter) and e.kind == "golden_snail" and e.what == "appeared" for e in events)
    snail = next(e for e in w.enemies if e.critter == "golden_snail")
    snail.life = 1 / TICK_HZ
    events = w.step([PlayerInput(0, 0, 0, None)])
    assert any(isinstance(e, Critter) and e.what == "escaped" for e in events) or snail.hp <= 0
    r = w.result().to_dict()
    assert r["stats"]["longest_still_s"] > 20 and "max_kills_10s" in r["stats"]


def test_creative_challenges_complete(content):
    p = new_profile()
    stats = {"golden_snails": 1, "longest_still_s": 31, "first_boss_s": 140.0, "shrine_kinds": 4, "max_kills_10s": 70}
    res = _result(stage=2, mode="eternal_night", stats=stats)
    done = {c.id for c in challenges.evaluate(p, res, content.challenges, 1)}
    assert {"golden_snail_1", "still_life", "express_boss", "pilgrim", "chain_reaction", "night_owl"} <= done
    assert "golden_snail_3" not in done
    p["lifetime"]["menu_squished"] = 10
    assert [c.id for c in challenges.evaluate_profile(p, content.challenges, 1)] == ["menu_squish"]


def test_completed_challenges_unlock_upgrades_that_used_to_be_titles(content):
    """29.10.2026: 16 upgrades are locked; an old profile that completed their challenge keeps them."""
    from lastbean.meta.profile import new_profile

    locked = [u for u in content.upgrades if not u.unlocked_at_start and u.impl_phase == 1]
    assert len(locked) == 14  # (plus 2 that were locked before and 2 of phase 3)
    p = new_profile()
    p["challenges_done"] = ["unlock_up_lifesteal"]
    challenges.sync_unlocks(p, content.challenges)
    assert p["unlocked"]["upgrades"] == ["lifesteal"]
