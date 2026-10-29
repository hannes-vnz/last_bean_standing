import copy

import pytest

from lastbean.data import parse_content, read_raw
from lastbean.sim import (
    TICK_HZ,
    BossKilled,
    BossPhase,
    ChestDropped,
    Enemy,
    EnemyShot,
    EnemyShotFired,
    EnemySpawned,
    GateOpened,
    HazardActivated,
    HazardSpec,
    ItemGained,
    PlayerHit,
    PlayerInput,
    World,
    WorldConfig,
)
from lastbean.sim import tuning as T
from lastbean.sim.enemies import apply_affixes, damage_enemy


def quiet_world(make_config, **overrides) -> World:
    """No spawning, harmless player (fires never), so only what a test places acts."""
    overrides.setdefault("character", {"attack_rate": 0.001, "hp": 10**6})
    return World(1, make_config(enemy_target=0, bosses=(), **overrides))


def place(w: World, kind: str, dx: float, dy: float = 0.0, **fields) -> Enemy:
    m = next(m for m in w.config.mobs if m.id == kind)
    p = w.players[0]
    e = Enemy(w._next_eid, m.id, p.x + dx, p.y + dy, m.hp, m.hp, m.speed, m.damage, m.radius, m.xp, m.behavior)
    e.keep_distance, e.shot_interval, e.timer = m.keep_distance, m.shot_interval, m.shot_interval
    for k, v in fields.items():
        setattr(e, k, v)
    w._next_eid += 1
    w.enemies.append(e)
    w.players[0].shot_cooldown = 1e9
    return e


def run(w: World, seconds: float, inputs=None) -> list:
    return [ev for _ in range(int(seconds * TICK_HZ)) for ev in w.step(inputs)]


# ---------------------------------------------------------------------------- behaviours


def test_aphids_spawn_in_groups_and_pay_per_member(make_config):
    w = World(3, make_config(character={"attack_rate": 0.001, "hp": 10**6}, bosses=()))
    w.tick = w.stage_tick = 30 * TICK_HZ  # aphids need 20 s
    spawned = [e for e in run(w, 25) if isinstance(e, EnemySpawned)]  # (well below the enemy limit)
    bats = [e for e in spawned if e.kind == "aphid"]
    assert bats and len(bats) % 5 == 0
    groups = [bats[i : i + 5] for i in range(0, len(bats), 5)]
    assert all(len({b.tick for b in g}) == 1 for g in groups)  # a group appears in the same tick


def test_aphids_flutter_but_reach_the_player(make_config):
    w = quiet_world(make_config)
    bat = place(w, "aphid", 300)
    xs = []
    for _ in range(4 * TICK_HZ):
        w.step()
        xs.append(bat.y)
    assert max(xs) - min(xs) > 5  # sideways flutter
    p = w.players[0]
    assert (bat.x - p.x) ** 2 + (bat.y - p.y) ** 2 < 50**2


def test_mold_keeps_distance_and_poisons(make_config):
    w = quiet_world(make_config)
    s = place(w, "mold", 120)
    events = run(w, 3)
    p = w.players[0]
    d = ((s.x - p.x) ** 2 + (s.y - p.y) ** 2) ** 0.5
    assert d > 120 and any(isinstance(e, EnemyShotFired) and e.lobbed for e in events)
    events = run(w, 3)
    assert any(isinstance(e, HazardActivated) and e.kind == "poison" for e in events)
    assert p.hp < p.max_hp
    # Poison is damage over time: no hit events, no i-frames.
    assert not any(isinstance(e, PlayerHit) for e in events) and p.i_frames == 0


def test_poison_puddle_damage_matches_text(make_config):
    w = quiet_world(make_config)
    poison = HazardSpec("poison", T.POISON_RADIUS, duration=T.POISON_DURATION_S, dps=4.0)
    w.add_hazard(poison, w.players[0].x, w.players[0].y, 0)
    hp = w.players[0].hp
    run(w, 4)
    assert hp - w.players[0].hp == pytest.approx(4.0 * T.POISON_DURATION_S, abs=0.2)


def test_snail_is_slow_and_tough(make_config):
    cfg = make_config()
    m = {m.id: m for m in cfg.mobs}
    assert m["snail"].hp > 4 * m["slug"].hp and m["snail"].speed < m["slug"].speed


def test_carrot_aims_then_dashes(make_config):
    w = quiet_world(make_config)
    c = place(w, "toxic_carrot", 250)
    run(w, 0.2)
    assert c.charge_state == 1 and w.snapshot().enemies[0].aim is not None  # warning line first
    x = c.x
    run(w, 1.0)
    assert c.charge_state == 2 and x - c.x > 100  # then it rushes in a straight line
    run(w, 1.0)
    assert c.charge_state in (0, 3)


def test_pest_tomato_bursts_after_a_warning(make_config):
    w = quiet_world(make_config)
    place(w, "pest_tomato", 40)
    hp = w.players[0].hp
    run(w, 0.3)
    assert not w.enemies and w.hazards and w.hazards[0].delay > 0 and w.players[0].hp == hp  # gone, warning only
    events = run(w, 0.5)
    assert any(isinstance(e, HazardActivated) and e.kind == "explosion" for e in events)
    assert w.players[0].hp < hp


def test_cucumber_shoots_straight(make_config):
    w = quiet_world(make_config)
    place(w, "spray_cucumber", 280)
    events = run(w, 3)
    assert any(isinstance(e, EnemyShotFired) and not e.lobbed for e in events)
    assert w.players[0].hp < w.players[0].max_hp


# ---------------------------------------------------------------------------- elites


def test_elite_every_five_waves_with_scaled_stats(make_config):
    w = World(2, make_config(character={"attack_rate": 0.001, "hp": 10**6}, bosses=()))
    run(w, 151)
    elites = [e for e in w.enemies if e.elite]
    assert len(elites) == 1
    e = elites[0]
    base = next(m for m in w.config.mobs if m.id == e.kind)
    sc = w.config.scaling
    assert e.max_hp == pytest.approx(base.hp * sc.hp_mult(1.5) * 4, rel=1e-6)  # wave 5 = 1:30
    assert e.radius == pytest.approx(base.radius * 1.35) and len(e.affixes) == 1


def test_affixes(make_config):
    w = quiet_world(make_config)
    armored = place(w, "slug", 300, hp=100.0, max_hp=100.0, affixes=("armored",), elite=True)
    assert damage_enemy(armored, 10.0) == pytest.approx(7.0)
    shielded = place(w, "slug", 300, hp=100.0, max_hp=100.0, affixes=("shielded",), elite=True)
    apply_affixes(shielded)
    assert damage_enemy(shielded, 30.0) == 0.0 and shielded.shield == 20.0
    swift = place(w, "slug", 300, affixes=("swift",), elite=True)
    speed = swift.speed
    apply_affixes(swift)
    assert swift.speed == pytest.approx(speed * 1.4)
    regen = place(w, "slug", -300, hp=50.0, max_hp=100.0, affixes=("regenerating",), elite=True)
    run(w, 1)
    assert regen.hp == pytest.approx(53.0, abs=0.1)
    assert shielded.shield == 20.0  # recharges only after 8 s without hits
    run(w, 8)
    assert shielded.shield == 50.0


def test_volatile_elite_explodes_after_warning(make_config):
    w = quiet_world(make_config)
    e = place(w, "slug", 40, elite=True, affixes=("volatile",), hp=1.0, max_hp=1.0, speed=0.0)
    w._kill(e, 0, [])
    w.enemies.remove(e)
    hp = w.players[0].hp
    events = run(w, 0.5)
    assert w.players[0].hp == hp and w.hazards and not w.hazards[0].delay <= 0  # still a warning
    events = run(w, 0.5)
    assert any(isinstance(ev, HazardActivated) and ev.kind == "explosion" for ev in events)
    assert w.players[0].hp < hp


def test_vampiric_heals_on_contact(make_config):
    w = quiet_world(make_config)
    e = place(w, "slug", 0, elite=True, affixes=("vampiric",), hp=5.0, max_hp=20.0, damage=6.0)
    run(w, 0.1)
    assert e.hp == pytest.approx(11.0)


def test_elite_chest_gives_a_rare_item(make_config):
    """Since Paket C chests hold items (level-ups still give upgrade cards)."""
    w = quiet_world(make_config)
    p = w.players[0]
    w._drop_chest(p.x, p.y, "elite", [])
    events = run(w, 0.1)
    gained = [e for e in events if isinstance(e, ItemGained)]
    rarity = {i.id: i.rarity for i in w.config.items}
    assert len(gained) == 1 and rarity[gained[0].item_id] in ("rare", "epic", "legendary")
    assert sum(p.items.values()) == 1 and not w.chests and not w.paused


# ---------------------------------------------------------------------------- boss


def boss_world(make_config, stage: int = 0) -> tuple[World, Enemy]:
    w = World(1, make_config(enemy_target=0, character={"attack_rate": 0.001, "hp": 10**6}))
    if stage:
        w.stage = stage
        w._setup_stage()
    w.tick = w.stage_tick = int(w.boss_stats[w.stage_cfg.boss].spawn_time_s * TICK_HZ)
    w.step()
    boss = next(e for e in w.enemies if e.boss)
    return w, boss


def test_snail_queen_arrives_at_three_thirty(make_config):
    w, boss = boss_world(make_config)
    assert boss.boss == "snail_queen" and boss.max_hp == 4000
    p = w.players[0]
    assert (boss.x - p.x) ** 2 + (boss.y - p.y) ** 2 >= T.BOSS_MIN_SPAWN_DISTANCE**2


def test_snail_queen_ring_every_three_seconds(make_config):
    w, boss = boss_world(make_config)
    boss.speed = 0.0
    events = run(w, 6.1)
    rings = [e for e in events if isinstance(e, EnemyShotFired) and not e.lobbed]
    assert len(rings) == 2
    assert sum(1 for s in w.enemy_shots if not s.lobbed) <= 2 * T.RING_SHOTS


def test_snail_queen_phases(make_config):
    w, boss = boss_world(make_config)
    boss.speed = 0.0
    boss.hp = boss.max_hp * 0.59
    events = run(w, 0.1)
    assert any(isinstance(e, BossPhase) and e.phase == 1 for e in events)
    assert sum(1 for e in w.enemies if e.kind == "snail") == 3
    run(w, 1.5)
    assert any(h.spec.kind == "grip" for h in w.hazards)
    boss.hp = boss.max_hp * 0.29
    events = run(w, 4.1)
    assert any(isinstance(e, BossPhase) and e.phase == 2 for e in events)
    assert any(isinstance(e, EnemyShotFired) and e.lobbed for e in events)  # spore rain
    rings = [e for e in events if isinstance(e, EnemyShotFired) and not e.lobbed and e.enemy_id == boss.eid]
    assert len(rings) >= 2  # twice as fast


def test_root_grip_slows(make_config):
    w = quiet_world(make_config)
    p = w.players[0]
    w.add_hazard(HazardSpec("grip", 90, duration=2, slow_pct=40), p.x, p.y, 0)
    w.step()
    x = p.x
    run(w, 0.5, [PlayerInput(0, 1, 0)])
    assert p.x - x == pytest.approx(w.config.character.speed * 0.6 * 0.5, rel=0.05)


def test_boss_kill_drops_chest_and_opens_the_gate(make_config):
    w, boss = boss_world(make_config)
    events = []
    boss.hp = 0
    w._kill(boss, 0, events)
    assert any(isinstance(e, BossKilled) for e in events)
    assert [e.min_rarity for e in events if isinstance(e, ChestDropped)] == ["boss"]  # free, at least epic
    assert w.gate is not None and not w.victory


def test_beetle_king_fans_and_dashes(make_config):
    w, boss = boss_world(make_config, stage=1)
    assert boss.boss == "beetle_king"
    events = run(w, 7)
    assert sum(isinstance(e, EnemyShotFired) and e.enemy_id == boss.eid for e in events) >= 2
    assert boss.charge_state or any(isinstance(e, EnemyShotFired) for e in events)
    boss.hp = boss.max_hp * 0.59
    run(w, 0.1)
    assert sum(1 for e in w.enemies if e.kind == "potato_beetle") >= 4


def test_reaper_rains_and_wins_the_run(make_config):
    w, boss = boss_world(make_config, stage=2)
    assert boss.boss == "reaper"
    boss.hp = boss.max_hp * 0.6
    run(w, 4.2)
    assert any(h.spec.kind == "explosion" for h in w.hazards)  # soul rain with warning circles
    boss.hp = 0
    events = []
    w._kill(boss, 0, events)
    # the way home opens; the run goes on (flood for more points) until you walk through it
    assert not w.victory and w.gate is not None and w.snapshot().gate_exit
    assert [e.exit for e in events if isinstance(e, GateOpened)] == [True]
    p = w.players[0]
    w.enemies = []
    w._gate_ready_tick = w.tick
    p.x, p.y = w.gate
    w.step()
    assert p.gate_prompt and not w.over
    events = w.step([PlayerInput(0, gate=True)])
    assert w.over and w.result().victory and any(getattr(e, "victory", False) for e in events)


def test_thorns_are_blocked_by_trees(make_config):
    from conftest import with_obstacles

    from lastbean.sim.arena import OBSTACLE_RADIUS, Obstacle

    cfg = make_config(enemy_target=0, bosses=())
    tree = Obstacle("tree", cfg.arena_w / 2 + 60, cfg.arena_h / 2, OBSTACLE_RADIUS, True, True)
    w = World(1, with_obstacles(cfg, (tree,)))
    p = w.players[0]
    w.enemy_shots.append(EnemyShot(p.x + 150, p.y, -T.THORN_SPEED, 0.0, 10.0, 200, 0))
    run(w, 2)
    assert p.hp == p.max_hp and not w.enemy_shots


# ---------------------------------------------------------------------------- data driven


def test_new_mob_only_via_json(content):
    """Acceptance M4: a new mob is just a data entry."""
    raw = read_raw()
    clone = copy.deepcopy(next(m for m in raw["mobs"] if m["id"] == "slug"))
    clone.update(id="mossling", name="Moosling", hp=20, min_time_s=0)
    raw["mobs"].append(clone)
    cfg = WorldConfig.from_content(parse_content(raw))
    assert "mossling" in {m.id for m in cfg.mobs}
    w = World(5, cfg)
    kinds = {e.kind for e in run(w, 30) if isinstance(e, EnemySpawned)}
    assert "mossling" in kinds
