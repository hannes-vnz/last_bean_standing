from lastbean.sim import (
    TICK_HZ,
    Enemy,
    EnemyHit,
    EnemyKilled,
    PlayerDied,
    PlayerHit,
    PlayerInput,
    RunEnded,
    ShotFired,
    World,
)


def place(world: World, x: float, y: float, hp: float | None = None) -> Enemy:
    m = world.config.mob
    e = Enemy(world._next_eid, m.id, x, y, hp or m.hp, hp or m.hp, m.speed, m.damage, m.radius)
    world._next_eid += 1
    world.enemies.append(e)
    return e


def collect(world: World, ticks: int, inputs=None) -> list:
    return [ev for _ in range(ticks) for ev in world.step(inputs)]


def test_spawner_keeps_target_alive_at_spawn_distance(make_config):
    w = World(1, make_config(enemy_target=30, character={"attack_rate": 0.001}))
    w.step()
    for _ in range(20):
        w.step()
    assert len(w.enemies) == 30
    p = w.players[0]
    lo, hi = w.config.spawn_distance
    # Fresh spawns lie on the spawn ring (minus at most 20 ticks of walking towards the player).
    walked = w.config.mob.speed * 21 / TICK_HZ + 2 * w.config.mob.radius
    for e in w.enemies:
        d = ((e.x - p.x) ** 2 + (e.y - p.y) ** 2) ** 0.5
        assert lo - walked <= d <= hi + 1e-6


def test_player_shoots_nearest_enemy_in_range_and_kills_it(make_config):
    w = World(1, make_config(enemy_target=0, character={"crit_chance_pct": 0.0}))
    p = w.players[0]
    near = place(w, p.x + 150, p.y)
    place(w, p.x - 300, p.y)  # farther away, must not be the first target
    events = collect(w, 2 * TICK_HZ)
    shots = [e for e in events if isinstance(e, ShotFired)]
    assert shots and shots[0].dx > 0.99
    kills = [e for e in events if isinstance(e, EnemyKilled)]
    assert kills[0].enemy_id == near.eid and kills[0].player_id == 0
    assert w.players[0].kills >= 1


def test_no_shot_when_nothing_in_range(make_config):
    w = World(1, make_config(enemy_target=0))
    p = w.players[0]
    place(w, p.x + w.config.character.range + 100, p.y)
    assert not any(isinstance(e, ShotFired) for e in collect(w, 10))


def test_fire_rate_matches_attack_rate(make_config):
    w = World(1, make_config(enemy_target=0, mob={"speed": 0.0}))
    p = w.players[0]
    place(w, p.x + 200, p.y, hp=1e9)
    shots = sum(isinstance(e, ShotFired) for e in collect(w, 10 * TICK_HZ))
    assert abs(shots - 10 * w.config.character.attack_rate) <= 1


def test_pierce_hits_enemies_in_a_line(make_config):
    w = World(1, make_config(enemy_target=0, character={"pierce": 1}, mob={"speed": 0.0}))
    p = w.players[0]
    a, b, c = (place(w, p.x + d, p.y, hp=1e9) for d in (100, 140, 180))
    w.players[0].shot_cooldown = 0.0
    hits = [e for e in collect(w, 30) if isinstance(e, EnemyHit)]
    first_shot = {h.enemy_id for h in hits}
    assert {a.eid, b.eid} <= first_shot and c.eid not in first_shot


def test_contact_damage_respects_i_frames_and_kills(make_config):
    cfg = make_config(enemy_target=0, character={"attack_rate": 0.001, "hp": 12}, mob={"damage": 5.0})
    w = World(1, cfg)
    p = w.players[0]
    w.players[0].shot_cooldown = 1e9
    place(w, p.x, p.y)
    events = collect(w, int(0.5 * TICK_HZ))
    assert sum(isinstance(e, PlayerHit) for e in events) == 1  # i-frames 0.6 s
    events = collect(w, 3 * TICK_HZ)
    assert any(isinstance(e, PlayerDied) for e in events)
    assert any(isinstance(e, RunEnded) for e in events)
    assert w.over and w.players[0].hp == 0
    tick = w.tick
    assert w.step() == [] and w.tick == tick


def test_enemies_chase_and_do_not_stack(make_config):
    w = World(1, make_config(enemy_target=0, character={"attack_rate": 0.001, "hp": 10**6}))
    p = w.players[0]
    for i in range(20):
        place(w, p.x + 300 + (i % 5) * 3, p.y + (i // 5) * 3)
    collect(w, 8 * TICK_HZ)
    es = w.enemies
    min_gap = min(((a.x - b.x) ** 2 + (a.y - b.y) ** 2) ** 0.5 for i, a in enumerate(es) for b in es[i + 1 :])
    assert min_gap > es[0].radius  # separation keeps them apart
    nearest = min(((e.x - p.x) ** 2 + (e.y - p.y) ** 2) ** 0.5 for e in es)
    assert nearest < 60  # they reached the player


def test_dead_player_does_not_move_or_shoot(make_config):
    w = World(1, make_config(enemy_target=0, player_count=2))
    w.players[1].alive = False
    x = w.players[1].x
    events = collect(w, 30, [PlayerInput(1, 1, 0)])
    assert w.players[1].x == x and not any(e.player_id == 1 for e in events if isinstance(e, ShotFired))
    assert not w.over
