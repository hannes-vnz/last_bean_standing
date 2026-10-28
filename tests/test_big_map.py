"""Paket B/F: a map per garden bed (120 x 120), chunked ground, boss near the player, minimap."""

import pytest

from lastbean.sim import TICK_HZ, World
from lastbean.sim import tuning as T

pygame = pytest.importorskip("pygame")


def test_map_size_and_start_in_the_middle(make_config):
    cfg = make_config()
    assert cfg.arena_w == cfg.arena_h == 120 * 32
    p = World(1, cfg).players[0]
    assert (p.x, p.y) == (cfg.arena_w / 2, cfg.arena_h / 2)


def test_boss_spawns_near_the_player(make_config):
    for seed in range(1, 6):
        w = World(seed, make_config(enemy_target=0, character={"attack_rate": 0.001, "hp": 10**6}))
        w.tick = w.stage_tick = 210 * TICK_HZ
        w.step()
        boss = next(e for e in w.enemies if e.boss)
        assert boss.boss == "snail_queen"
        p = w.players[0]
        d = ((boss.x - p.x) ** 2 + (boss.y - p.y) ** 2) ** 0.5
        assert T.BOSS_MIN_SPAWN_DISTANCE <= d <= 1.5 * w.config.spawn_distance[1]


@pytest.fixture
def renderer(monkeypatch, content):
    monkeypatch.setenv("SDL_VIDEODRIVER", "dummy")
    pygame.init()
    pygame.display.set_mode((1, 1))
    from lastbean.render.renderer import Renderer

    return Renderer(content, (300, 650))


def test_ground_chunks_are_bounded(renderer, make_config):
    from lastbean.render import renderer as rmod
    from lastbean.sim import PlayerInput

    w = World(2, make_config(enemy_target=0, character={"hp": 10**9, "speed": 2000.0}))
    for direction in [(1, 1), (-1, 0), (0, -1), (1, 0)]:  # race across the whole map
        for i in range(4 * TICK_HZ):
            w.step([PlayerInput(0, *direction)])
            if i % 10 == 0:
                renderer.draw(w.snapshot())
    assert 0 < len(renderer._chunks) <= rmod.MAX_CHUNKS


def test_minimap_and_menu_backdrop(renderer, make_config):
    from lastbean.meta.profile import new_profile
    from lastbean.ui import screens

    w = World(3, make_config(enemy_target=0, character={"attack_rate": 0.001, "hp": 10**6}))
    w.tick = w.stage_tick = 210 * TICK_HZ
    w.step()
    renderer.touch = True
    renderer.draw(w.snapshot())  # boss far away: arrow at the edge, dot on the minimap
    assert renderer.overview.get_size() == (120, 120)
    screens.draw_menu(renderer, new_profile(), web=True)
