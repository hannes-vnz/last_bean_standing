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
    HazardActivated,
    HazardSpec,
    PlayerHit,
    PlayerInput,
    UpgradeOffered,
    World,
    WorldConfig,
)
from lastbean.sim import tuning as T
from lastbean.sim.enemies import apply_affixes, damage_enemy
from lastbean.sim.waves import biome_at


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


def test_bats_spawn_in_groups_and_pay_per_member(make_config):
    w = World(3, make_config(character={"attack_rate": 0.001, "hp": 10**6}, bosses=()))
    w.tick = 70 * TICK_HZ  # bats need 60 s
    spawned = [e for e in run(w, 60) if isinstance(e, EnemySpawned)]
    bats = [e for e in spawned if e.kind == "batswarm"]
    assert bats and len(bats) % 4 == 0
    groups = [bats[i : i + 4] for i in range(0, len(bats), 4)]
    assert all(len({b.tick for b in g}) == 1 for g in groups)  # a group appears in the same tick


def test_bats_flutter_but_reach_the_player(make_config):
    w = quiet_world(make_config)
    bat = place(w, "batswarm", 300)
    xs = []
    for _ in range(4 * TICK_HZ):
        w.step()
        xs.append(bat.y)
    assert max(xs) - min(xs) > 5  # sideways flutter
    p = w.players[0]
    assert (bat.x - p.x) ** 2 + (bat.y - p.y) ** 2 < 50**2


def test_sporeshooter_keeps_distance_and_poisons(make_config):
    w = quiet_world(make_config)
    s = place(w, "sporeshooter", 120)
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


def test_rootguard_is_slow_and_tough(make_config):
    cfg = make_config()
    m = {m.id: m for m in cfg.mobs}
    assert m["rootguard"].hp > 4 * m["slimeling"].hp and m["rootguard"].speed < m["slimeling"].speed


# ---------------------------------------------------------------------------- elites


def test_elite_every_five_waves_with_scaled_stats(make_config):
    w = World(2, make_config(character={"attack_rate": 0.001, "hp": 10**6}, bosses=()))
    run(w, 151)
    elites = [e for e in w.enemies if e.elite]
    assert len(elites) == 1
    e = elites[0]
    base = next(m for m in w.config.mobs if m.id == e.kind)
    sc = w.config.scaling
    assert e.max_hp == pytest.approx(base.hp * sc.hp_mult(2.5) * 4, rel=1e-6)
    assert e.radius == pytest.approx(base.radius * 1.35) and len(e.affixes) == 1


def test_affixes(make_config):
    w = quiet_world(make_config)
    armored = place(w, "slimeling", 300, hp=100.0, max_hp=100.0, affixes=("armored",), elite=True)
    assert damage_enemy(armored, 10.0) == pytest.approx(7.0)
    shielded = place(w, "slimeling", 300, hp=100.0, max_hp=100.0, affixes=("shielded",), elite=True)
    apply_affixes(shielded)
    assert damage_enemy(shielded, 30.0) == 0.0 and shielded.shield == 20.0
    swift = place(w, "slimeling", 300, affixes=("swift",), elite=True)
    speed = swift.speed
    apply_affixes(swift)
    assert swift.speed == pytest.approx(speed * 1.4)
    regen = place(w, "slimeling", -300, hp=50.0, max_hp=100.0, affixes=("regenerating",), elite=True)
    run(w, 1)
    assert regen.hp == pytest.approx(53.0, abs=0.1)
    assert shielded.shield == 20.0  # recharges only after 8 s without hits
    run(w, 8)
    assert shielded.shield == 50.0


def test_volatile_elite_explodes_after_warning(make_config):
    w = quiet_world(make_config)
    e = place(w, "slimeling", 40, elite=True, affixes=("volatile",), hp=1.0, max_hp=1.0, speed=0.0)
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
    e = place(w, "slimeling", 0, elite=True, affixes=("vampiric",), hp=5.0, max_hp=20.0, damage=6.0)
    run(w, 0.1)
    assert e.hp == pytest.approx(11.0)


def test_elite_chest_offers_rarest_available(make_config):
    w = quiet_world(make_config)
    p = w.players[0]
    w._drop_chest(p.x, p.y, "rare", [])
    events = run(w, 0.1)
    offer = next(e for e in events if isinstance(e, UpgradeOffered)).upgrade_ids
    rarity = {u.id: u.rarity for u in w.config.upgrades}
    # Phase 1 has no rare upgrades yet, so the chest falls back to the rarest tier left (uncommon).
    assert {rarity[u] for u in offer} == {"uncommon"} and p.offer_source == "chest" and w.paused
    w.step([PlayerInput(0, choice=0)])
    assert sum(p.upgrades.values()) == 1 and p.level == 1 and not p.pending_chests


# ---------------------------------------------------------------------------- boss


def boss_world(make_config) -> tuple[World, Enemy]:
    w = World(1, make_config(enemy_target=0, character={"attack_rate": 0.001, "hp": 10**6}))
    w.tick = 300 * TICK_HZ
    w.step()
    boss = next(e for e in w.enemies if e.boss)
    return w, boss


def test_ildra_spawns_at_five_minutes_in_the_forest(make_config):
    w, boss = boss_world(make_config)
    assert boss.boss == "ildra" and boss.max_hp == 2500
    assert biome_at(w.config.biomes, boss.x, boss.y) == "forest"
    p = w.players[0]
    assert (boss.x - p.x) ** 2 + (boss.y - p.y) ** 2 >= T.BOSS_MIN_SPAWN_DISTANCE**2


def test_ildra_thorn_ring_every_four_seconds(make_config):
    w, boss = boss_world(make_config)
    boss.speed = 0.0
    events = run(w, 8.1)
    rings = [e for e in events if isinstance(e, EnemyShotFired) and not e.lobbed]
    assert len(rings) == 2
    assert sum(1 for s in w.enemy_shots if not s.lobbed) <= 16


def test_ildra_phases(make_config):
    w, boss = boss_world(make_config)
    boss.speed = 0.0
    boss.hp = boss.max_hp * 0.59
    events = run(w, 0.1)
    assert any(isinstance(e, BossPhase) and e.phase == 1 for e in events)
    assert sum(1 for e in w.enemies if e.kind == "rootguard") == 3
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


def test_boss_kill_drops_chest(make_config):
    w, boss = boss_world(make_config)
    events = []
    boss.hp = 0
    w._kill(boss, 0, events)
    assert any(isinstance(e, BossKilled) for e in events)
    assert [e.min_rarity for e in events if isinstance(e, ChestDropped)] == ["epic"]


def test_thorns_are_blocked_by_trees(make_config):
    import dataclasses

    from lastbean.sim.arena import OBSTACLE_RADIUS, Obstacle

    cfg = make_config(enemy_target=0, bosses=())
    tree = Obstacle("tree", cfg.arena_w / 2 + 60, cfg.arena_h / 2, OBSTACLE_RADIUS, True, True)
    w = World(1, dataclasses.replace(cfg, obstacles=(tree,)))
    p = w.players[0]
    w.enemy_shots.append(EnemyShot(p.x + 150, p.y, -T.THORN_SPEED, 0.0, 10.0, 200, 0))
    run(w, 2)
    assert p.hp == p.max_hp and not w.enemy_shots


# ---------------------------------------------------------------------------- data driven


def test_new_mob_only_via_json(content):
    """Acceptance M4: a new mob is just a data entry."""
    raw = read_raw()
    clone = copy.deepcopy(next(m for m in raw["mobs"] if m["id"] == "slimeling"))
    clone.update(id="mossling", name="Moosling", hp=20, min_time_s=0)
    raw["mobs"].append(clone)
    cfg = WorldConfig.from_content(parse_content(raw))
    assert "mossling" in {m.id for m in cfg.mobs}
    w = World(5, cfg)
    kinds = {e.kind for e in run(w, 30) if isinstance(e, EnemySpawned)}
    assert "mossling" in kinds
