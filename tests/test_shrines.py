"""Shrines (shrines.json): placed per bed, charged by standing in the circle, once each."""

import dataclasses

from lastbean.data import load_content
from lastbean.sim import PlayerInput, World, WorldConfig
from lastbean.sim.events import ShrineActivated
from lastbean.sim.tuning import GREED_XP_PCT


def _world(seed: int = 4) -> World:
    cfg = WorldConfig.from_content(load_content())
    cfg = dataclasses.replace(cfg, character=dataclasses.replace(cfg.character, hp=10**9))
    return World(seed, cfg)


def _stand_on(w: World, kind: str, ticks: int, move: bool = False) -> list:
    sh = next(s for s in w.shrines if s.rules.id == kind)
    p = w.players[0]
    events = []
    for t in range(ticks):
        p.x, p.y = sh.x + (1.0 if move and t % 2 else 0.0), sh.y
        mx = (1.0 if t % 2 else -1.0) if move else 0.0
        events += w.step([PlayerInput(0, mx, 0.0, 0 if p.offer else None)])
    return events


def test_shrines_are_placed_per_bed_and_deterministic():
    a, b = _world(), _world()
    kinds = sorted(s.rules.id for s in a.shrines)
    assert kinds == ["courage", "greed", "greed"]
    assert [(s.x, s.y) for s in a.shrines] == [(s.x, s.y) for s in b.shrines]
    assert [(s.x, s.y) for s in _world(5).shrines] != [(s.x, s.y) for s in a.shrines]


def test_greed_shrine_needs_standing_still_and_pays_xp_for_difficulty():
    w = _world()
    rules = next(s.rules for s in w.shrines if s.rules.id == "greed")
    assert not any(isinstance(e, ShrineActivated) for e in _stand_on(w, "greed", 200, move=True))
    events = _stand_on(w, "greed", round(rules.channel_s * 60) + 5)
    hits = [e for e in events if isinstance(e, ShrineActivated)]
    assert len(hits) == 1 and hits[0].kind == "greed"
    assert abs(w.difficulty - (1.0 + rules.difficulty_add)) < 1e-9
    assert w.players[0].shrine_mods["xp_gain_pct"] == GREED_XP_PCT
    assert sum(1 for s in w.shrines if s.rules.id == "greed") == 1  # used up


def test_courage_shrine_grants_a_rare_card():
    w = _world()
    rules = next(s.rules for s in w.shrines if s.rules.id == "courage")
    sh = next(s for s in w.shrines if s.rules.id == "courage")
    p = w.players[0]
    activated = False
    for _ in range(round(rules.channel_s * 60) + 5):
        p.x, p.y = sh.x, sh.y
        evs = w.step([PlayerInput(0, 0.0, 0.0, 0 if p.offer else None)])
        if any(isinstance(e, ShrineActivated) for e in evs):
            activated = True
            break
    assert activated
    # The free card waits behind any open level-up, then comes as a chest offer of at least "rare".
    assert p.offer_source == "chest" or "rare" in p.pending_chests
