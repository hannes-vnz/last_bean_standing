"""Paket C2: extra weapons from level-up cards (sim/weapons.py and World integration)."""

import math

import pytest

from lastbean.sim import TICK_HZ, WEAPON_PREFIX, Enemy, PlayerInput, UpgradeChosen, World
from lastbean.sim.events import EnemyHit, ShotFired, WeaponPulse
from lastbean.sim.weapons import WeaponState, cos_sin, fan_directions


def _world(make_config, seed=1):
    w = World(seed, make_config(enemy_target=0, mob={"speed": 0.0}))
    w.players[0].shot_cooldown = 1e9  # silence the start weapon, so only the extra weapon hits
    return w


def _dummy(w, dx, dy, hp=1e9):
    p, m = w.players[0], w.config.mobs[0]
    e = Enemy(w._next_eid, m.id, p.x + dx, p.y + dy, hp, hp, 0.0, 0.0, m.radius)
    w.enemies.append(e)
    w._next_eid += 1
    return e


def _give(w, wid, level=1):
    w.players[0].weapons.append(WeaponState(wid, level))


def _run(w, seconds):
    return [e for _ in range(int(seconds * TICK_HZ)) for e in w.step([PlayerInput(0)])]


def test_content_has_six_weapons_and_four_slots(content, make_config):
    cfg = make_config()
    assert len(cfg.weapons) == 6 and cfg.weapon_slots == 4
    assert {w.kind for w in cfg.weapons} == {"fan", "nova", "aura", "orbit", "lobbed"}
    for w in content.weapons:
        assert w.name and w.text and w.level_text


def test_cos_sin_matches_math_and_is_exact_at_zero():
    assert cos_sin(0.0) == (1.0, 0.0)
    for k in range(-40, 41):
        a = k * 0.37
        c, s = cos_sin(a)
        assert c == pytest.approx(math.cos(a), abs=1e-12) and s == pytest.approx(math.sin(a), abs=1e-12)


def test_fan_directions_are_spread_evenly():
    dirs = fan_directions(1.0, 0.0, 3, 30.0)
    assert dirs[1] == pytest.approx((1.0, 0.0))
    assert math.atan2(dirs[2][1], dirs[2][0]) == pytest.approx(math.radians(15))
    ring = fan_directions(0.0, 1.0, 8, 360.0)
    assert len({(round(x, 6), round(y, 6)) for x, y in ring}) == 8
    assert all(math.hypot(x, y) == pytest.approx(1.0) for x, y in ring)


def test_levels_add_per_level_values(make_config):
    bees = next(w for w in make_config().weapons if w.id == "bees")
    assert bees.at(1)["count"] == 2 and bees.at(3)["count"] == 4 and bees.at(3)["damage"] == 16


@pytest.mark.parametrize("wid", ["thorn_twig", "dandelion", "pollen_cloud", "bees", "sun_pulse", "pumpkin_bomb"])
def test_every_weapon_damages_an_enemy_next_to_the_player(make_config, wid):
    w = _world(make_config)
    _give(w, wid)
    e = _dummy(w, 60.0, 0.0)
    events = _run(w, 4)
    assert e.hp < e.max_hp, wid
    assert any(isinstance(ev, EnemyHit) and ev.enemy_id == e.eid for ev in events)


def test_weapons_stay_quiet_without_enemies(make_config):
    w = _world(make_config)
    for wid in ("thorn_twig", "sun_pulse", "pumpkin_bomb"):
        _give(w, wid)
    events = _run(w, 3)
    assert not any(isinstance(e, (ShotFired, WeaponPulse)) for e in events) and not w.bombs


def test_fan_fires_count_projectiles(make_config):
    w = _world(make_config)
    _give(w, "thorn_twig", level=3)  # 3 + 0.5 * 2 = 4 thorns
    _dummy(w, 150.0, 0.0)
    events = w.step([PlayerInput(0)])
    assert sum(isinstance(e, ShotFired) and e.weapon == "thorn_twig" for e in events) == 4


def test_pumpkin_bursts_after_its_flight(make_config):
    w = _world(make_config)
    _give(w, "pumpkin_bomb")
    e = _dummy(w, 200.0, 0.0)
    w.step([PlayerInput(0)])
    assert len(w.bombs) == 1 and e.hp == e.max_hp
    assert w.snapshot().bombs[0].tx == pytest.approx(e.x)
    events = _run(w, 1.0)
    assert any(isinstance(ev, WeaponPulse) and ev.weapon == "pumpkin_bomb" for ev in events) and e.hp < e.max_hp


def test_bees_sting_each_enemy_once_per_cooldown(make_config):
    w = _world(make_config)
    _give(w, "bees")
    p = w.players[0]
    e = _dummy(w, 64.0, 0.0)
    hits = [ev for ev in _run(w, 3) if isinstance(ev, EnemyHit) and ev.enemy_id == e.eid]
    ticks = [ev.tick for ev in hits]
    assert hits and all(b - a >= 0.5 * TICK_HZ - 1 for a, b in zip(ticks, ticks[1:], strict=False))
    snap = w.snapshot()
    assert len(snap.orbiters) == 2
    assert all(math.hypot(x - p.x, y - p.y) == pytest.approx(64.0) for _, x, y in snap.orbiters)


def test_damage_bonus_scales_weapons(make_config):
    hits = []
    for bonus in (0, 2):
        w = _world(make_config)
        if bonus:
            w.players[0].upgrades["sharp_edges"] = bonus
            w._recompute(w.players[0])
        w.players[0].stats.crit_chance_pct = 0.0
        _give(w, "sun_pulse")
        _dummy(w, 50.0, 0.0)
        hits.append(next(e.damage for e in w.step([PlayerInput(0)]) if isinstance(e, EnemyHit)))
    assert hits[1] > hits[0]


def test_weapon_cards_offer_new_weapons_only_while_a_slot_is_free(make_config):
    w = _world(make_config)
    p = w.players[0]
    pool = {c.id for c in w._weapon_pool(p)}
    assert pool == {WEAPON_PREFIX + wd.id for wd in w.config.weapons}
    for wid in ("bees", "sun_pulse", "pollen_cloud"):  # 3 extra + start weapon = 4 slots
        _give(w, wid)
    assert {c.id for c in w._weapon_pool(p)} == {WEAPON_PREFIX + x for x in ("bees", "sun_pulse", "pollen_cloud")}
    p.weapons[0].level = 5  # maxed: its card is never offered again
    for _ in range(40):
        p.offer, p.pending_levels = (), 1
        w._offer(p, [])
        assert WEAPON_PREFIX + "bees" not in p.offer


def test_choosing_a_weapon_card_adds_then_levels_it(make_config):
    w = _world(make_config)
    p = w.players[0]
    card = WEAPON_PREFIX + "bees"
    for expected in (1, 2):
        p.offer, p.offer_source, p.pending_levels = (card,), "level", 1
        events = w.step([PlayerInput(0, choice=0)])
        assert any(isinstance(e, UpgradeChosen) and e.upgrade_id == card and e.level == expected for e in events)
    assert [(st.weapon, st.level) for st in p.weapons] == [("bees", 2)] and not p.upgrades
    assert w.snapshot().players[0].weapons == (("bees", 2),)


def test_level_up_offers_contain_weapon_cards(make_config):
    w = World(5, make_config(enemy_target=0))
    p = w.players[0]
    seen = set()
    for _ in range(40):
        p.offer, p.pending_levels = (), 1
        w._offer(p, [])
        seen.update(p.offer)
    assert any(uid.startswith(WEAPON_PREFIX) for uid in seen)


def test_weapons_are_deterministic(make_config):
    def run():
        w = World(11, make_config(character={"hp": 10**9}))
        for wid in ("bees", "pumpkin_bomb", "dandelion"):
            w.players[0].weapons.append(WeaponState(wid, 2))
        for _ in range(40 * TICK_HZ):
            w.step([PlayerInput(0, 1 if (w.tick // 90) % 2 else -1, 0)])
        return w.state_hash(), w.players[0].kills

    a, b = run(), run()
    assert a == b and a[1] > 0
