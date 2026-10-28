from conftest import with_obstacles

from lastbean.sim import TICK_HZ, Enemy, PlayerInput, ProjectileBlocked, ShotFired, World
from lastbean.sim.arena import (
    OBSTACLE_KINDS,
    OBSTACLE_RADIUS,
    START_CLEAR_TILES,
    Obstacle,
    ObstacleMap,
    obstacles_for_biome,
)


def test_every_bed_has_its_obstacles_from_data(content, make_config):
    cfg = make_config()
    tile = content.balance.tile_px
    cx, cy = cfg.arena_w / 2, cfg.arena_h / 2
    for st in cfg.stages:
        spec = content.biome(st.biome).extra["obstacles"]
        obs = st.obstacles
        assert len(obs) == spec["count"] and {o.kind for o in obs} == {spec["type"]} and spec["type"] in OBSTACLE_KINDS
        assert obstacles_for_biome(content, st.biome) == obs  # fixed seed: same layout every run
        half = START_CLEAR_TILES / 2 * tile
        assert all(abs(o.x - cx) >= half or abs(o.y - cy) >= half for o in obs)  # the start stays free
    stalks = cfg.stages[0].obstacles
    for i, a in enumerate(stalks[:200]):
        for b in stalks[i + 1 : 200]:
            assert max(abs(a.x - b.x), abs(a.y - b.y)) >= 2 * tile  # never adjacent, no walls of plants


def test_only_the_seedbed_plants_give_cover(make_config):
    kinds = {st.id: st.obstacles[0] for st in make_config().stages}
    assert kinds["seedbed"].blocks_projectiles and not kinds["veggiebed"].blocks_projectiles
    assert all(o.solid for o in kinds.values())


def one_tree_config(make_config, **overrides):
    """Real config but with a single tree 100 units right of the start, so tests see only this one."""
    cfg = make_config(**overrides)
    tree = Obstacle("tree", cfg.arena_w / 2 + 100, cfg.arena_h / 2, OBSTACLE_RADIUS, True, True)
    return with_obstacles(cfg, (tree,)), tree


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
