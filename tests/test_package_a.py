"""Paket A (28.10.2026): magnet pickup, Fenn's passive "Weitblick" and active "Pfeilhagel"."""

import pytest

from lastbean.sim import TICK_HZ, AbilityUsed, Enemy, Pickup, PickupCollected, PlayerInput, ShotFired, World, XpOrb
from lastbean.sim import tuning as T


def quiet(make_config, **kw) -> World:
    kw.setdefault("character", {"attack_rate": 0.001})
    return World(1, make_config(enemy_target=0, bosses=(), **kw))


def test_new_values_from_data(make_config):
    cfg = make_config()
    assert cfg.character.speed == 225 and cfg.character.attack_rate == 2.0 and cfg.character.pickup_radius == 220
    assert dict(next(m for m in cfg.mobs if m.id == "slug").biome_weights)["seedbed"] == 1


def test_magnet_pulls_every_orb_on_the_map(make_config):
    w = quiet(make_config)
    p = w.players[0]
    far = [XpOrb(p.x + 800, p.y + 600, 1.0), XpOrb(p.x - 900, p.y - 700, 2.0)]
    w.orbs = list(far)
    w.pickups.append(Pickup("magnet", p.x + 10, p.y))
    events = [e for _ in range(3 * TICK_HZ) for e in w.step()]
    assert any(isinstance(e, PickupCollected) and e.kind == "magnet" for e in events)
    assert not w.orbs and (p.xp == 3.0 or p.level > 1)


def test_elites_always_drop_a_magnet(make_config):
    w = quiet(make_config)
    m = w.config.mobs[0]
    e = Enemy(0, m.id, 500.0, 500.0, 1.0, 1.0, 0.0, 1.0, m.radius, 1.0, elite=True)
    w._kill(e, 0, [])
    assert [k.kind for k in w.pickups] == ["magnet"]


def test_magnet_drop_rate_is_small(make_config):
    w = quiet(make_config)
    m = w.config.mobs[0]
    for i in range(4000):
        w._kill(Enemy(i, m.id, 0.0, 0.0, 1.0, 1.0, 0.0, 1.0, m.radius, 1.0), 0, [])
    magnets = [k for k in w.pickups if k.kind == "magnet"]
    assert 0.2 < 100 * len(magnets) / 4000 < 1.0  # about MAGNET_DROP_PCT (ladybugs are counted apart)


def test_weitblick_passive(make_config):
    w = quiet(make_config, character={"attack_rate": 2.0, "crit_chance_pct": 0.0}, mob={"speed": 0.0})
    s = w.players[0].stats
    assert s.range == pytest.approx(w.config.character.range * 1.12)  # +12 % range
    assert s.far_damage_pct == 8 and s.far_threshold == 250
    p = w.players[0]
    m = w.config.mobs[0]
    w.enemies.append(Enemy(0, m.id, p.x + 300, p.y, 1e9, 1e9, 0.0, 1.0, m.radius))
    w._next_eid = 1
    w.step()
    assert w.projectiles[0].damage == pytest.approx(s.damage * 1.08)  # target farther than 250


def test_pfeilhagel(make_config):
    w = quiet(make_config)
    p = w.players[0]
    events = w.step([PlayerInput(0, ability=True)])
    shots = [e for e in events if isinstance(e, ShotFired)]
    assert len(shots) == T.ARROW_STORM_SHOTS and any(isinstance(e, AbilityUsed) for e in events)
    assert w.projectiles[0].damage == pytest.approx(p.stats.damage * T.ARROW_STORM_DAMAGE)
    assert not any(isinstance(e, AbilityUsed) for e in w.step([PlayerInput(0, ability=True)]))  # cooldown
    for _ in range(int(w.config.character.active_cooldown_s * TICK_HZ)):
        w.step()
    assert any(isinstance(e, AbilityUsed) for e in w.step([PlayerInput(0, ability=True)]))
    assert w.snapshot().players[0].ability_ready == pytest.approx(0.0)


def test_progression_is_faster(make_config):
    """Acceptance for the new values: the bot reaches a clearly higher level by 5:00 than before (2 to 4)."""
    from lastbean.bots import heuristic_input

    w = World(7, make_config(character={"hp": 10**9}))
    while w.time_s < 300:
        w.step([heuristic_input(w)])
    assert w.players[0].level >= 12  # variant C: about level 14 to 16 by 5:00
