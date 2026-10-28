"""The four beans unlocked by challenges: Thorn's ghosts, Orm's bombs and mines, Lilu's poison, Aya's stillness."""

import dataclasses

from lastbean.sim import PlayerInput, World, WorldConfig
from lastbean.sim.events import ShotFired, WeaponPulse, Zap


def _world(content, cid, seed=3):
    cfg = WorldConfig.from_content(content, cid)
    cfg = dataclasses.replace(cfg, character=dataclasses.replace(cfg.character, hp=10**9))
    return World(seed, cfg)


def _run(w, seconds, move=(0, 0), ability_at=None):
    events = []
    for t in range(int(seconds * 60)):
        p = w.players[0]
        ability = ability_at is not None and t == int(ability_at * 60)
        mx, my = move if (t // 120) % 2 == 0 else (-move[0], -move[1])
        events += w.step([PlayerInput(0, mx, my, 0 if p.offer else None, ability=ability)])
    return events


def test_thorn_ghosts_attack_and_totenruf_calls_more(content):
    w = _world(content, "summoner")
    assert w.minion_count(w.players[0]) == 2 and len(w.snapshot().minions) == 2
    events = _run(w, 20, ability_at=19)
    assert any(isinstance(e, Zap) for e in events)
    assert w.minion_count(w.players[0]) == 6


def test_orm_throws_bombs_and_lays_mines_while_walking(content):
    w = _world(content, "bomber")
    events = _run(w, 20, move=(1, 0), ability_at=15)
    assert any(isinstance(e, WeaponPulse) and e.weapon == "bomb" for e in events)
    assert any(isinstance(e, WeaponPulse) and e.weapon == "mega_bomb" for e in events)
    assert sum(1 for m in w.mines if m.weapon == "orm_mine") <= 6
    still = _world(content, "bomber")
    _run(still, 6)
    assert not any(m.weapon == "orm_mine" for m in still.mines)


def test_lilu_vials_leave_poison(content):
    w = _world(content, "venom")
    _run(w, 15, ability_at=14)
    assert any(z.weapon == "vial" for z in w.zones) or w.run_stats.get("poison_damage", 0) > 0
    assert w.run_stats.get("poison_damage", 0) > 0
    assert any(z.weapon == "cloud" for z in w.zones)


def test_aya_shoots_only_standing_unless_focused(content):
    w = _world(content, "sniper")
    walking = [e for e in _run(w, 6, move=(1, 0)) if isinstance(e, ShotFired)]
    assert not walking
    standing = [e for e in _run(w, 6) if isinstance(e, ShotFired)]
    assert standing
    focused = [e for e in _run(w, 3, move=(1, 0), ability_at=0) if isinstance(e, ShotFired)]
    assert focused
