import dataclasses

from lastbean.sim import TICK_HZ, Enemy, PlayerInput, ProjectileBlocked, ShotFired, World
from lastbean.sim.arena import OBSTACLE_RADIUS, Obstacle, ObstacleMap, obstacles_from_content
from lastbean.sim.waves import biome_at


def test_forest_trees_from_data(content, make_config):
    trees = make_config().obstacles
    forest = content.biome("forest").extra["obstacles"]
    assert len(trees) == forest["count"] and {o.kind for o in trees} == {"tree"}
    areas = make_config().biomes
    assert all(biome_at(areas, o.x, o.y) == "forest" for o in trees)  # never in the clearing
    assert obstacles_from_content(content, 1) == trees  # fixed seed: same layout every run
    tile = content.balance.tile_px
    for i, a in enumerate(trees):
        for b in trees[i + 1 :]:
            assert max(abs(a.x - b.x), abs(a.y - b.y)) >= 2 * tile  # never adjacent, no walls of trees


def test_later_biomes_have_no_obstacles_yet(content):
    assert {o.kind for o in obstacles_from_content(content, 3)} == {"tree"}  # rocks etc. need their phase


def one_tree_config(make_config, **overrides):
    """Real config but with a single tree 100 units right of the start, so tests see only this one."""
    cfg = make_config(**overrides)
    tree = Obstacle("tree", cfg.arena_w / 2 + 100, cfg.arena_h / 2, OBSTACLE_RADIUS, True, True)
    return dataclasses.replace(cfg, obstacles=(tree,)), tree


def tree_world(make_config):
    cfg, tree = one_tree_config(make_config, enemy_target=0, mob={"speed": 0.0})
    w = World(1, cfg)
    p = w.players[0]
    p.x, p.y = tree.x - 150, tree.y
    return w, tree, p


def test_player_cannot_walk_through_tree(make_config):
    w, tree, p = tree_world(make_config)
    for _ in range(3 * TICK_HZ):
        w.step([PlayerInput(0, 1, 0)])
        assert (p.x - tree.x) ** 2 + (p.y - tree.y) ** 2 >= (tree.radius + 12) ** 2 - 1e-6
    assert p.x < tree.x


def test_tree_gives_cover_and_player_targets_visible_enemy(make_config):
    w, tree, p = tree_world(make_config)
    m = w.config.mobs[0]
    hidden = Enemy(0, m.id, tree.x + 60, tree.y, 1e9, 1e9, 0.0, m.damage, m.radius)
    visible = Enemy(1, m.id, p.x, p.y + 250, 1e9, 1e9, 0.0, m.damage, m.radius)
    w.enemies += [hidden, visible]
    w._next_eid = 2
    shots = [e for _ in range(30) for e in w.step() if isinstance(e, ShotFired)]
    assert shots and all(s.dy > 0.99 for s in shots)  # aims at the visible one, not into the tree


def test_projectile_stops_at_tree(make_config):
    w, tree, p = tree_world(make_config)
    m = w.config.mobs[0]
    w.enemies.append(Enemy(0, m.id, tree.x + 60, tree.y, 1e9, 1e9, 0.0, m.damage, m.radius))
    w._next_eid = 1
    w.obstacles.line_blocked = lambda *a, **k: False  # force a shot straight into the tree
    events = [e for _ in range(TICK_HZ) for e in w.step()]
    assert any(isinstance(e, ProjectileBlocked) for e in events)
    assert w.enemies[0].hp == w.enemies[0].max_hp


def test_enemies_walk_around_trees(make_config):
    cfg, tree = one_tree_config(make_config, enemy_target=0, character={"attack_rate": 0.001, "hp": 10**6})
    w = World(1, cfg)
    p = w.players[0]
    p.x, p.y = tree.x - 80, tree.y
    m = w.config.mobs[0]
    w.enemies.append(Enemy(0, m.id, tree.x + 80, tree.y + 1, 1e9, 1e9, m.speed, m.damage, m.radius))
    w._next_eid = 1
    for _ in range(6 * TICK_HZ):
        w.step()
        e = w.enemies[0]
        assert (e.x - tree.x) ** 2 + (e.y - tree.y) ** 2 >= (tree.radius + e.radius) ** 2 - 1e-6
    assert (e.x - p.x) ** 2 + (e.y - p.y) ** 2 < 60**2  # got past the tree to the player


def test_line_of_fire_geometry():
    om = ObstacleMap((Obstacle("tree", 100.0, 100.0, 14.0, True, True),))
    assert om.line_blocked(0, 100, 200, 100)
    assert not om.line_blocked(0, 130, 200, 130)
    assert om.line_blocked(0, 115, 200, 115, radius=4)
    assert not om.line_blocked(0, 100, 80, 100)  # ends before the tree
    assert om.push_out(100.0, 100.0, 10.0) == (124.0, 100.0)
