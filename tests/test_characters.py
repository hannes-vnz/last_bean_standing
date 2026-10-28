"""Paket H: Mira, Kaz, Brun, Ysa and Vex play with their own weapon, passive and active ability."""

import pytest

from lastbean.sim import TICK_HZ, AbilityUsed, Enemy, PlayerInput, World, WorldConfig
from lastbean.sim import tuning as T
from lastbean.sim.events import EnemyHit, WeaponPulse, Zap

PLAYABLE = ["ranger", "pyro", "rogue", "guardian", "cryo", "storm"]


def world_for(content, cid: str, **overrides) -> World:
    cfg = WorldConfig.from_content(content, cid, enemy_target=0, bosses=(), **overrides)
    return World(1, cfg)


def dummy(w: World, dx: float, dy: float = 0.0, hp: float = 10_000.0, speed: float = 0.0) -> Enemy:
    p, m = w.players[0], w.config.mobs[0]
    e = Enemy(w._next_eid, m.id, p.x + dx, p.y + dy, hp, hp, speed, 1.0, m.radius)
    w._next_eid += 1
    w.enemies.append(e)
    return e


def run(w: World, seconds: float, inputs=None) -> list:
    return [ev for _ in range(int(seconds * TICK_HZ)) for ev in w.step(inputs)]


@pytest.mark.parametrize("cid", PLAYABLE)
def test_every_playable_character_hurts_enemies(content, cid):
    w = world_for(content, cid)
    e = dummy(w, 80.0)
    events = run(w, 3)
    assert e.hp < e.max_hp and any(isinstance(ev, EnemyHit) for ev in events), cid


@pytest.mark.parametrize("cid", PLAYABLE)
def test_every_active_ability_works(content, cid):
    w = world_for(content, cid)
    dummy(w, 120.0)
    events = run(w, 0.2, [PlayerInput(0, ability=True)])
    assert any(isinstance(ev, AbilityUsed) for ev in events), cid


def test_mira_fireball_bursts_and_burns(content):
    w = world_for(content, "pyro")
    a, b = dummy(w, 150.0), dummy(w, 170.0, 20.0)
    events = run(w, 1.5)
    assert any(isinstance(ev, WeaponPulse) and ev.weapon == "fireball" for ev in events)
    assert b.hp < b.max_hp and (a.burn_t > 0 or b.burn_t > 0)


def test_kaz_throws_three_knives_and_dashes(content):
    w = world_for(content, "rogue")
    dummy(w, 150.0)
    w.step()
    assert sum(1 for pr in w.projectiles) == 3
    p = w.players[0]
    x = p.x
    w.step([PlayerInput(0, 1, 0)])
    w.step([PlayerInput(0, 1, 0, ability=True)])
    assert p.x - x > T.DASH_DISTANCE * 0.9 and p.i_frames > 0


def test_brun_pushes_back_and_shields(content):
    w = world_for(content, "guardian")
    e = dummy(w, 60.0)
    x = e.x
    events = run(w, 1.2)
    assert any(isinstance(ev, WeaponPulse) and ev.weapon == "shockwave" for ev in events) and e.x > x
    p = w.players[0]
    w.step([PlayerInput(0, ability=True)])
    hp = p.hp
    w._hurt(p, 100.0, [])
    assert p.hp == hp and p.temp_shield > 0


def test_ysa_freezes_after_three_hits(content):
    w = world_for(content, "cryo")
    e = dummy(w, 120.0, speed=50.0)
    run(w, 2.5)
    assert e.chill_t > 0
    w2 = world_for(content, "cryo")
    f = dummy(w2, 500.0)
    w2.step([PlayerInput(0, ability=True)])
    assert f.chill_pct == 100.0 and f.chill_t > 1.5


def test_vex_chains_and_calls_lightning(content):
    w = world_for(content, "storm")
    for dx in (100.0, 160.0, 220.0):
        dummy(w, dx)
    events = run(w, 6)
    zaps = [ev for ev in events if isinstance(ev, Zap)]
    assert zaps and max(len(z.points) for z in zaps) >= 3
    assert any(len(z.points) == 2 and z.points[0][0] == z.points[1][0] for z in zaps)  # strike from above
