from collections import Counter

import pytest

from lastbean.sim import (
    TICK_HZ,
    Enemy,
    LevelUp,
    PlayerInput,
    Rng,
    ShotFired,
    UpgradeChosen,
    UpgradeOffered,
    World,
)
from lastbean.sim.upgrades import SUPPORTED_STATS, UpgradeDef, derive_stats, modifier_sums, roll_offer


def test_phase_one_pool_has_twelve_supported_upgrades(content, make_config):
    phase1 = [UpgradeDef.from_content(u) for u in content.upgrades if u.impl_phase == 1]
    assert len(phase1) == 12 and all(u.supported for u in phase1)
    assert {u.id for u in make_config().upgrades} == {u.id for u in phase1}


def test_every_upgrade_effect_changes_stats(make_config):
    cfg = make_config()
    base = derive_stats(cfg.character, {})
    for u in cfg.upgrades:
        for stat, _ in u.effects:
            assert stat in SUPPORTED_STATS
        changed = derive_stats(cfg.character, modifier_sums({u.id: 1}, {u.id: u}))
        assert changed != base, u.id


def test_stat_examples(make_config):
    cfg = make_config()
    defs = {u.id: u for u in cfg.upgrades}
    s = derive_stats(cfg.character, modifier_sums({"sharp_edges": 2, "brutal_crits": 1, "thick_skin": 4}, defs))
    assert s.damage == pytest.approx(cfg.character.damage * 1.16)
    assert s.crit_mult == pytest.approx(1.7)
    assert s.damage_taken_mult == pytest.approx(0.76)


def test_offer_is_distinct_weighted_and_skips_maxed(make_config):
    cfg = make_config()
    rng = Rng(5)
    counts: Counter = Counter()
    for _ in range(3000):
        offer = roll_offer(rng, list(cfg.upgrades), {}, cfg.rarity_weights, 3)
        assert len(offer) == 3 == len(set(offer))
        counts.update(offer)
    rarity = {u.id: u.rarity for u in cfg.upgrades}
    common = sum(c for uid, c in counts.items() if rarity[uid] == "common") / 8
    uncommon = sum(c for uid, c in counts.items() if rarity[uid] == "uncommon") / 4
    assert common > uncommon
    maxed = {u.id: u.max_level for u in cfg.upgrades if u.id != "magnet"}
    assert roll_offer(rng, list(cfg.upgrades), maxed, cfg.rarity_weights, 3) == ("magnet",)


def test_fires_while_moving(make_config):
    """Decided 28.10.2026: auto-fire also while walking (stop-and-shoot was dropped)."""
    w = World(1, make_config(enemy_target=0, mob={"speed": 0.0}))
    p = w.players[0]
    m = w.config.mobs[0]
    w.enemies.append(Enemy(0, m.id, p.x + 200, p.y, 1e9, 1e9, 0.0, m.damage, m.radius))
    w._next_eid = 1
    moving = [e for _ in range(2 * TICK_HZ) for e in w.step([PlayerInput(0, 0, 1)])]
    shots = sum(isinstance(e, ShotFired) for e in moving)
    assert abs(shots - 2 * w.config.character.attack_rate) <= 1


def test_level_up_pauses_and_choice_applies(make_config):
    w = World(3, make_config(enemy_target=0))
    p = w.players[0]
    events = []
    w._gain_xp(p, w.config.scaling.xp_needed(1) + 0.5, events)
    assert any(isinstance(e, LevelUp) for e in events) and p.level == 2
    assert w.paused and len(p.offer) == 3
    tick = w.tick
    w.step([PlayerInput(0, 1, 0)])
    assert w.tick == tick  # time stands still while choosing
    chosen = p.offer[1]
    events = w.step([PlayerInput(0, choice=1)])
    assert any(isinstance(e, UpgradeChosen) and e.upgrade_id == chosen for e in events)
    assert p.upgrades == {chosen: 1} and not w.paused
    assert w.tick == tick + 1  # the tick with the choice already runs again


def test_several_levels_at_once_queue_offers(make_config):
    w = World(3, make_config(enemy_target=0))
    p = w.players[0]
    events = []
    sc = w.config.scaling
    w._gain_xp(p, sc.xp_needed(1) + sc.xp_needed(2) + sc.xp_needed(3), events)
    assert p.level == 4 and p.pending_levels == 3
    for _ in range(3):
        assert w.paused
        evs = w.step([PlayerInput(0, choice=0)])
        assert any(isinstance(e, UpgradeChosen) for e in evs)
    assert not w.paused and sum(p.upgrades.values()) == 3
    assert sum(isinstance(e, UpgradeOffered) for e in events) == 1


def test_vitality_raises_and_heals(make_config):
    w = World(3, make_config(enemy_target=0))
    p = w.players[0]
    p.hp = 50.0
    p.offer, p.pending_levels = ("vitality",), 1
    w.step([PlayerInput(0, choice=0)])
    assert p.max_hp == w.config.character.hp + 15 and p.hp == 65.0


def test_extra_attacks_fire_more_projectiles(make_config):
    w = World(1, make_config(enemy_target=0, mob={"speed": 0.0}))
    p = w.players[0]
    p.upgrades = {"double_shot": 2}
    p.stats = derive_stats(w.config.character, modifier_sums(p.upgrades, {u.id: u for u in w.config.upgrades}))
    m = w.config.mobs[0]
    w.enemies.append(Enemy(0, m.id, p.x + 200, p.y, 1e9, 1e9, 0.0, m.damage, m.radius))
    shots = [e for e in w.step() if isinstance(e, ShotFired)]
    assert len(shots) == 3
    assert shots[1].dy * shots[2].dy < 0  # one to each side


def test_xp_orbs_fly_to_player_inside_pickup_radius(make_config):
    w = World(1, make_config(enemy_target=0))
    p = w.players[0]
    from lastbean.sim import XpOrb

    w.orbs = [XpOrb(p.x + 60, p.y, 1.0), XpOrb(p.x + 300, p.y, 1.0)]
    for _ in range(20):
        w.step()
    assert p.xp == 1.0 and len(w.orbs) == 1
