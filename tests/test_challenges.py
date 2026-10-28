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
    assert "pyro" in p["unlocked"]["characters"] and "Beetbefreier" in p["titles"]
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
