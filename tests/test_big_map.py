"""Paket B: 200 x 200 map, chunked ground, boss near the player, minimap."""

import pytest

from lastbean.sim import TICK_HZ, World
from lastbean.sim import tuning as T
from lastbean.sim.waves import biome_at

pygame = pytest.importorskip("pygame")


def test_map_is_big(make_config):
    cfg = make_config()
    assert cfg.arena_w == cfg.arena_h == 200 * 32
    p = World(1, cfg).players[0]
    assert biome_at(cfg.biomes, p.x, p.y) == "plaza"  # start in the clearing in the middle


def test_boss_spawns_near_the_player_in_its_biome(make_config):
    for seed in range(1, 6):
        w = World(seed, make_config(enemy_target=0, character={"attack_rate": 0.001, "hp": 10**6}))
        w.tick = 300 * TICK_HZ
        w.step()
        boss = next(e for e in w.enemies if e.boss)
        p = w.players[0]
        d = ((boss.x - p.x) ** 2 + (boss.y - p.y) ** 2) ** 0.5
        assert T.BOSS_MIN_SPAWN_DISTANCE <= d <= 2.5 * w.config.spawn_distance[1]
        assert biome_at(w.config.biomes, boss.x, boss.y) == "forest"


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
    w.tick = 300 * TICK_HZ
    w.step()
    renderer.touch = True
    renderer.draw(w.snapshot())  # boss far away: arrow at the edge, dot on the minimap
    assert renderer.overview.get_size() == (200, 200)
    screens.draw_menu(renderer, new_profile(), web=True)
