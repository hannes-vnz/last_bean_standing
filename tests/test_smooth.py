"""Render interpolation, tap mapping with letterboxing, far-enemy recycling (28.10.2026)."""

import pytest

from lastbean.app import contain_point
from lastbean.render.interp import interpolate
from lastbean.sim import TICK_HZ, Enemy, PlayerInput, World
from lastbean.sim.tuning import RECYCLE_DISTANCE


def test_interpolation_blends_between_ticks(make_config):
    w = World(1, make_config(enemy_target=0))
    prev = w.positions()
    w.step([PlayerInput(0, 1, 0)])
    snap = w.snapshot()
    half = interpolate(snap, prev, 0.5)
    x0, x1 = prev[0][0][0], snap.players[0].x
    assert half.players[0].x == pytest.approx((x0 + x1) / 2)
    assert interpolate(snap, prev, 1.0) is snap and interpolate(snap, None, 0.3) is snap


def test_contain_point_undoes_letterboxing():
    # buffer 360x640 (portrait) shown in a 1000x1000 element: picture 562.5 wide, centred
    assert contain_point(0.5, 0.5, (1000, 1000), (360, 640)) == pytest.approx((0.5, 0.5))
    left_edge = (1000 - 562.5) / 2 / 1000
    assert contain_point(left_edge, 0.0, (1000, 1000), (360, 640)) == pytest.approx((0.0, 0.0))
    assert contain_point(0.3, 0.7, (360, 640), (360, 640)) == pytest.approx((0.3, 0.7))


def test_far_enemies_are_recycled_near_the_player(make_config):
    w = World(1, make_config(enemy_target=0, mob={"speed": 0.0}))
    p, m = w.players[0], w.config.mobs[0]
    w.enemies.append(Enemy(0, m.id, p.x + RECYCLE_DISTANCE + 500, p.y, 10.0, 10.0, 0.0, 1.0, m.radius))
    w._next_eid = 1
    for _ in range(TICK_HZ):
        w.step([PlayerInput(0)])
    e = w.enemies[0]
    assert ((e.x - p.x) ** 2 + (e.y - p.y) ** 2) ** 0.5 < RECYCLE_DISTANCE and e.hp == 10.0
