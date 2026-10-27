import pytest

from lastbean.bots import heuristic_input
from lastbean.sim import TICK_HZ, EnemySpawned, WaveStarted, World
from lastbean.sim.waves import biome_at


def test_budget_formula_matches_content_model(make_config):
    sc = make_config().scaling
    # Values from the model table in docs/CONTENT.md (budget per wave).
    for wave, budget in [(2, 22), (10, 87), (20, 208), (30, 373), (40, 582)]:
        assert round(sc.wave_budget(wave)) == budget
    assert sc.wave_budget(10, difficulty=1.2) == pytest.approx(1.2 * sc.wave_budget(10))
    assert sc.wave_budget(10, player_count=2) == sc.wave_budget(10)  # co-op factor still open (0)


def test_scaling_curves(make_config):
    sc = make_config().scaling
    assert sc.hp_mult(0) == 1.0 and round(sc.hp_mult(5), 1) == 1.8 and round(sc.hp_mult(10), 1) == 3.2
    assert round(sc.damage_mult(10), 1) == 1.9
    assert sc.speed_mult(5) == pytest.approx(1.05) and sc.speed_mult(60) == 1.2
    assert sc.xp_needed(1) == 12 + 8 + 0.5


def spawned_costs(world: World, ticks: int) -> float:
    cost = {m.id: m.cost for m in world.config.mobs}
    total = 0.0
    for _ in range(ticks):
        world.players[0].hp = world.players[0].max_hp  # keep the run alive
        world.players[0].offer, world.players[0].pending_levels = (), 0
        total += sum(cost[e.kind] for e in world.step() if isinstance(e, EnemySpawned))
    return total


def test_wave_budget_is_spent_over_each_wave(make_config):
    w = World(1, make_config(character={"attack_rate": 0.001}))
    sc, ticks = w.config.scaling, w.config.wave_interval_s * TICK_HZ
    assert spawned_costs(w, ticks) == pytest.approx(sc.wave_budget(0), abs=1.0)
    assert spawned_costs(w, ticks) == pytest.approx(sc.wave_budget(1), abs=1.0)


def test_difficulty_raises_spawns(make_config):
    ticks = 60 * TICK_HZ
    normal = spawned_costs(World(1, make_config(character={"attack_rate": 0.001})), ticks)
    hard = spawned_costs(World(1, make_config(character={"attack_rate": 0.001}, difficulty=1.5)), ticks)
    assert hard > normal * 1.4


def test_enemies_scale_with_time(make_config):
    w = World(1, make_config(enemy_target=1, character={"attack_rate": 0.001, "hp": 10**9}))
    w.step()
    first = w.enemies[0]
    w.enemies.clear()
    w.tick = 10 * 60 * TICK_HZ  # jump to minute 10
    w.step()
    late = w.enemies[0]
    sc = w.config.scaling
    assert late.max_hp == pytest.approx(first.max_hp * sc.hp_mult(10.0), rel=1e-3)
    assert late.damage == pytest.approx(first.damage * sc.damage_mult(10.0), rel=1e-3)


def test_mob_pool_respects_phase_and_behaviour(make_config):
    ids = {m.id for m in make_config().mobs}
    assert ids == {"slimeling"}  # M2: only the chaser is implemented
    assert {m.id for m in make_config(max_phase=3).mobs} == {"slimeling"}


def test_biome_lookup_prefers_clearing(make_config):
    areas = make_config().biomes
    t = 32
    assert biome_at(areas, 30 * t, 30 * t) == "plaza"
    assert biome_at(areas, 5 * t, 5 * t) == "forest"
    assert biome_at(areas, 55 * t, 5 * t) == "desert"
    assert biome_at(areas, 5 * t, 55 * t) == "ice"
    assert biome_at(areas, 55 * t, 55 * t) == "lava"


def test_run_to_five_minutes(make_config):
    """Acceptance M2: a full run to 5:00 works (bot with infinite HP; real survival is measured in tools/balance.py)."""
    w = World(7, make_config(character={"hp": 10**9}))
    waves = []
    while w.time_s < 300 and not w.over:
        waves += [e.wave for e in w.step([heuristic_input(w)]) if isinstance(e, WaveStarted)]
    p = w.players[0]
    assert waves == list(range(1, 11)) and w.time_s == 300
    assert p.level >= 3 and p.kills > 100 and sum(p.upgrades.values()) == p.level - 1
