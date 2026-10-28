"""Paket F: card rarities, on-hit effects, conditions and defensive bonuses."""

import pytest

from lastbean.sim import TICK_HZ, Enemy, PlayerInput, World
from lastbean.sim import tuning as T
from lastbean.sim.events import EnemyHit, PlayerDodged, PlayerRevived, StageStarted, Zap


def quiet(make_config, **kw) -> World:
    kw.setdefault("character", {"attack_rate": 0.001, "hp": 1000})
    kw.setdefault("mob", {"speed": 0.0})
    return World(1, make_config(enemy_target=0, bosses=(), **kw))


def dummy(w: World, dx: float, dy: float = 0.0, hp: float = 1000.0) -> Enemy:
    p, m = w.players[0], w.config.mobs[0]
    e = Enemy(w._next_eid, m.id, p.x + dx, p.y + dy, hp, hp, 0.0, 10.0, m.radius)
    w._next_eid += 1
    w.enemies.append(e)
    return e


def give(w: World, uid: str, tier: str = "common") -> None:
    p = w.players[0]
    p.offer, p.offer_tiers, p.offer_source, p.pending_levels = (uid,), (tier,), "level", 1
    w.step([PlayerInput(0, choice=0)])


def test_rarer_cards_are_worth_more(make_config):
    common, legendary = quiet(make_config), quiet(make_config)
    give(common, "sharp_edges")
    give(legendary, "sharp_edges", "legendary")
    base = common.config.character.damage
    assert common.players[0].stats.damage == pytest.approx(base * 1.08)
    assert legendary.players[0].stats.damage == pytest.approx(base * (1 + 0.08 * 3.0))
    assert legendary.players[0].upgrades == {"sharp_edges": 1}  # still one level


def test_every_level_up_card_gets_a_rarity(make_config):
    w = quiet(make_config)
    p = w.players[0]
    seen = set()
    for _ in range(200):
        p.offer, p.offer_tiers, p.pending_levels = (), (), 1
        w._offer(p, [])
        assert len(p.offer_tiers) == len(p.offer)
        seen.update(p.offer_tiers)
    assert {"common", "uncommon", "rare"} <= seen
    view = w.snapshot().players[0].offer
    assert all(len(card) == 3 for card in view)


def test_reroll_card_grants_rerolls_at_once(make_config):
    w = quiet(make_config)
    before = w.players[0].rerolls
    give(w, "reroll", "rare")  # 1 x 1.7, rounded down, at least 1
    assert w.players[0].rerolls == before + 1


def test_poison_and_burn_hurt_over_time(make_config):
    w = quiet(make_config)
    e = dummy(w, 300)
    p = w.players[0]
    p.upgrades["toxin"] = 1
    p.upgrades["ignite"] = 10  # 100 % burn chance
    w._recompute(p)
    w._weapon_hit(p, 0, e, 10.0, False, set(), [])
    hp = e.hp
    assert e.poison_t > 0 and e.burn_t > 0
    hits = [ev for _ in range(TICK_HZ * 2) for ev in w.step() if isinstance(ev, EnemyHit)]
    assert e.hp < hp and 2 <= len(hits) <= 6  # pulses every 0.5 s, not every tick


def test_chill_slows_enemies(make_config):
    w = quiet(make_config, mob={"speed": 100.0})
    e = dummy(w, 300)
    e.speed = 100.0
    p = w.players[0]
    p.upgrades["chill"] = 4
    w._recompute(p)
    w._weapon_hit(p, 0, e, 1.0, False, set(), [])
    x = e.x
    w.step()
    assert x - e.x == pytest.approx(100.0 * (1 - 0.32) / TICK_HZ, rel=1e-3)


def test_shock_jumps_to_nearby_enemies(make_config):
    w = quiet(make_config)
    a, b, c = dummy(w, 300), dummy(w, 340), dummy(w, 380)
    p = w.players[0]
    p.items["thunder_cloud"] = 7  # 105 % chance
    w._recompute(p)
    w._rebuild_grid()
    events = []
    w._weapon_hit(p, 0, a, 100.0, False, set(), events)
    zaps = [e for e in events if isinstance(e, Zap)]
    assert zaps and len(zaps[0].points) == 3 and b.hp < b.max_hp and c.hp < c.max_hp


def test_explosive_hits_damage_neighbours_without_chains(make_config):
    w = quiet(make_config)
    a, b = dummy(w, 300), dummy(w, 330)
    p = w.players[0]
    p.upgrades["explosive_rounds"] = 1
    w._recompute(p)
    w._rebuild_grid()
    w._weapon_hit(p, 0, a, 100.0, False, set(), [])
    assert b.hp == pytest.approx(b.max_hp - 30.0)


def test_execute_lifesteal_and_low_hp(make_config):
    w = quiet(make_config)
    e = dummy(w, 300)
    e.hp = e.max_hp * 0.2
    p = w.players[0]
    p.upgrades.update(executioner=1, lifesteal=1, last_stand=1)
    w._recompute(p)
    p.hp = p.stats.max_hp * 0.2
    events = []
    w._weapon_hit(p, 0, e, 10.0, False, set(), events)
    assert events[0].damage == pytest.approx(13.0)  # +30 % on enemies under 30 % HP
    assert p.hp == pytest.approx(p.stats.max_hp * 0.2 + 13.0 * 0.02)
    assert w.damage_mult(p) == pytest.approx(p.stats.standing_damage_mult * 1.3)  # "Letztes Gefecht"


def test_dodge_armor_shield_and_revive(make_config):
    w = quiet(make_config)
    p = w.players[0]
    p.items.update(bird_bath=20)  # 60 % cap
    w._recompute(p)
    dodged = 0
    for _ in range(200):
        p.i_frames = 0.0
        events = []
        w._hurt(p, 1.0, events)
        dodged += any(isinstance(e, PlayerDodged) for e in events)
    assert 80 < dodged < 160
    w2 = quiet(make_config)
    p2 = w2.players[0]
    p2.upgrades.update(armor_plating=2, shield_burst=1, second_wind=1)
    w2._recompute(p2)
    w2.step()  # the shield fills at once
    assert p2.shield == 25.0
    w2._hurt(p2, 30.0, [])
    assert p2.hp == p2.stats.max_hp - (30.0 - 2.0 - 25.0)
    p2.i_frames = 0.0
    events = []
    w2._hurt(p2, 10_000.0, events)
    assert p2.alive and p2.hp == pytest.approx(p2.stats.max_hp * T.REVIVE_HP_SHARE)
    assert any(isinstance(e, PlayerRevived) for e in events)


def test_bloodlust_speeds_up_after_kills(make_config):
    w = quiet(make_config)
    p = w.players[0]
    p.upgrades["bloodlust"] = 1
    w._recompute(p)
    for _ in range(5):
        e = dummy(w, 300, hp=1.0)
        w._rebuild_grid()
        w._weapon_hit(p, 0, e, 5.0, False, set(), [])
    assert p.haste_pct == 10.0 and w.attack_rate(p) == pytest.approx(p.stats.attack_rate * 1.1)
    w.enemies = [e for e in w.enemies if e.hp > 0]  # the world removes its dead itself
    for _ in range(int(T.KILL_HASTE_S * TICK_HZ) + 2):
        w.step()
    assert p.haste_pct == 0.0


def test_gate_takes_the_build_to_the_next_bed(make_config):
    w = quiet(make_config)
    p = w.players[0]
    p.upgrades["sharp_edges"] = 2
    w._recompute(p)
    p.hp = 10.0
    w.gate = (p.x, p.y)
    w._gate_ready_tick = w.tick
    events = w.step()
    assert w.stage == 1 and any(isinstance(e, StageStarted) and e.stage == 2 for e in events)
    assert p.upgrades == {"sharp_edges": 2} and p.hp == p.stats.max_hp and w.gate is None
    assert w.snapshot().stage_name == "Gemüsebeet" and w.snapshot().obstacles == w.config.stages[1].obstacles
