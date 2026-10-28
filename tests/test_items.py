"""Paket C: seeds, seed chests with rising prices, pots, items and their effects, reroll and banish."""

import dataclasses
from collections import Counter

import pytest

from lastbean.sim import (
    TICK_HZ,
    ChestLocked,
    Enemy,
    ItemGained,
    MapChest,
    PlayerInput,
    Pot,
    PotBroken,
    Rng,
    ShotFired,
    UpgradeOffered,
    World,
    XpOrb,
)
from lastbean.sim.economy import roll_item
from lastbean.sim.upgrades import SUPPORTED_STATS, derive_stats, modifier_sums


def quiet(make_config, **kw) -> World:
    kw.setdefault("character", {"attack_rate": 0.001, "hp": 10**6})
    return World(1, make_config(enemy_target=0, bosses=(), **kw))


def run(w, seconds, inputs=None):
    return [e for _ in range(int(seconds * TICK_HZ)) for e in w.step(inputs)]


def test_all_items_supported(make_config):
    cfg = make_config()
    assert len(cfg.items) == 46  # 30 from Paket C, 16 with triggers and conditions from Paket F
    assert Counter(i.rarity for i in cfg.items) == {"common": 12, "uncommon": 16, "rare": 10, "epic": 6, "legendary": 2}
    base = derive_stats(cfg.character, {})
    defs = {i.id: i for i in cfg.items}
    for item in cfg.items:
        assert all(stat in SUPPORTED_STATS for stat, _ in item.effects), item.id
        assert derive_stats(cfg.character, modifier_sums({}, {}, {item.id: 1}, defs)) != base, item.id


def test_map_is_full_of_chests_and_pots(make_config):
    w = World(3, make_config())
    eco = w.config.economy
    assert len(w.chests) == eco.chest_count and len(w.pots) == eco.pot_count
    assert all(c.kind == "map" for c in w.chests)
    p = w.players[0]
    assert all((c.x - p.x) ** 2 + (c.y - p.y) ** 2 >= 220**2 for c in w.chests)
    other = World(4, make_config())
    assert [(c.x, c.y) for c in other.chests] != [(c.x, c.y) for c in w.chests]  # new layout every run


def test_chest_costs_seeds_and_gets_pricier(make_config):
    w = quiet(make_config)
    p = w.players[0]
    eco = w.config.economy
    w.chests = [MapChest(p.x + 10, p.y, "map")]
    events = run(w, 0.2)
    assert any(isinstance(e, ChestLocked) and e.price == eco.price_start for e in events) and w.chests
    p.seeds = 100
    events = run(w, 0.1)
    assert any(isinstance(e, ItemGained) for e in events) and not w.chests
    assert p.seeds == 100 - eco.price_start
    assert w.snapshot().chest_price == eco.chest_price(1) == round(eco.price_start * 1.4)


def test_seeds_drop_and_are_collected(make_config):
    w = quiet(make_config)
    p = w.players[0]
    m = w.config.mobs[0]
    for i in range(400):
        w._kill(Enemy(i, m.id, p.x + 30, p.y, 1.0, 1.0, 0.0, 1.0, m.radius, 1.0), 0, [])
    seeds = [o for o in w.orbs if o.kind == "seeds"]
    assert 0.25 < len(seeds) / 400 < 0.45  # about 35 % (items.json)
    run(w, 1)
    assert p.seeds == len(seeds)


def test_pots_break_into_loot(make_config):
    w = quiet(make_config)
    p = w.players[0]
    w.pots = [Pot(p.x + 5, p.y) for _ in range(50)]
    events = run(w, 0.1)
    contents = Counter(e.content for e in events if isinstance(e, PotBroken))
    assert sum(contents.values()) == 50 and contents["seeds"] > contents["heal"] > 0


def test_heal_orb(make_config):
    w = quiet(make_config)
    p = w.players[0]
    p.hp = 50.0
    w.orbs = [XpOrb(p.x + 20, p.y, 15.0, kind="heal")]
    run(w, 0.5)
    assert p.hp == pytest.approx(65.0, abs=0.1)


def test_items_stack(make_config):
    w = quiet(make_config)
    p = w.players[0]
    base = p.stats.damage
    p.items = {"garden_gloves": 3}
    w._recompute(p)
    assert p.stats.damage == pytest.approx(base * 1.24)


def test_luck_shifts_item_rarity(make_config):
    cfg = make_config()
    rng = Rng(9)

    def rare_share(luck):
        rolls = [roll_item(rng, cfg.items, cfg.rarity_weights, "common", luck, cfg.luck_shift) for _ in range(3000)]
        return sum(r.rarity != "common" for r in rolls) / len(rolls)

    assert rare_share(5) > rare_share(0) + 0.05


def item_world(make_config, items):
    w = quiet(make_config, character={"attack_rate": 2.0, "crit_chance_pct": 0.0}, mob={"speed": 0.0})
    p = w.players[0]
    p.items = dict(items)
    w._recompute(p)
    return w, p


def place(w, dx, hp=1e9, **kw):
    m = w.config.mobs[0]
    p = w.players[0]
    e = Enemy(w._next_eid, m.id, p.x + dx, p.y, hp, hp, 0.0, m.damage, m.radius, **kw)
    w._next_eid += 1
    w.enemies.append(e)
    return e


def test_standing_and_elite_damage(make_config):
    w, p = item_world(make_config, {"deep_roots": 1, "scarecrow": 1})
    elite = place(w, 120, elite=True)
    w.step()
    shot = w.projectiles[0]
    assert shot.damage == pytest.approx(p.stats.damage * 1.2)  # standing bonus
    run(w, 0.3)
    assert elite.max_hp - elite.hp == pytest.approx(p.stats.damage * 1.2 * 1.2)  # + elite bonus on hit


def test_thorns_and_heal_per_kill(make_config):
    w, p = item_world(make_config, {"nettle": 1, "honey_pot": 1})
    p.shot_cooldown = 1e9
    e = place(w, 0, hp=8.0)
    p.hp = 50.0
    run(w, 0.1)
    assert e not in w.enemies and p.kills == 1  # touched me, the nettle killed it
    assert p.hp == pytest.approx(50.0 - e.damage + 0.3)


def test_seed_bomb_explodes(make_config):
    w, p = item_world(make_config, {"seed_bomb": 20})  # 160 % chance: always explodes
    target = place(w, 120, hp=1.0)
    neighbour = place(w, 150, hp=1.0)
    run(w, 0.5)
    assert target not in w.enemies and neighbour not in w.enemies


def test_cooldown_and_xp_items(make_config):
    w, p = item_world(make_config, {"sundial": 2, "earthworm": 1})
    events = w.step([PlayerInput(0, ability=True)])
    assert any(isinstance(e, ShotFired) for e in events)
    assert p.ability_cooldown == pytest.approx(w.config.character.active_cooldown_s * 0.8, abs=0.02)
    w._gain_xp(p, 0, [])
    w.orbs = [XpOrb(p.x + 10, p.y, 10.0)]
    run(w, 0.2)
    assert p.xp == pytest.approx(11.0) or p.level > 1


def test_reroll_and_banish(make_config):
    w = quiet(make_config)
    p = w.players[0]
    w._gain_xp(p, w.config.scaling.xp_needed(1) + 0.1, [])
    first = p.offer
    events = w.step([PlayerInput(0, reroll=True)])
    assert any(isinstance(e, UpgradeOffered) for e in events) and p.rerolls == 1 and w.paused
    banned = p.offer[0]
    w.step([PlayerInput(0, banish=0)])
    assert banned in p.banished and p.banishes == 1 and banned not in p.offer
    for _ in range(40):  # the banished upgrade never shows up again
        p.offer = ()
        p.pending_levels = 1
        w._offer(p, [])
        assert banned not in p.offer
    assert first  # offers existed throughout
    p.rerolls = 0
    before = p.offer
    w.step([PlayerInput(0, reroll=True)])
    assert p.offer == before  # no rerolls left


def test_determinism_with_economy(make_config):
    from lastbean.bots import heuristic_input

    def play():
        w = World(11, dataclasses.replace(make_config(), max_alive_enemies=120))
        while w.time_s < 120 and not w.over:
            w.step([heuristic_input(w)])
        return w

    a, b = play(), play()
    assert a.state_hash() == b.state_hash()
    assert a.players[0].seeds > 0 or a.players[0].items
