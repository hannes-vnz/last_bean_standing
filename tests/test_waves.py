import re
from pathlib import Path

import pytest

from lastbean.bots import heuristic_input
from lastbean.sim import (
    TICK_HZ,
    BossKilled,
    BossSpawned,
    ChestOpened,
    EliteSpawned,
    EnemySpawned,
    FloodStarted,
    StageStarted,
    WaveStarted,
    World,
)


def test_budget_formula_matches_content_model(make_config):
    sc = make_config().scaling
    # The model table in docs/CONTENT.md (generated from the same data) lists the budget per wave.
    table = Path(__file__).resolve().parents[1].joinpath("docs", "CONTENT.md").read_text(encoding="utf-8")
    rows = re.findall(r"^\| \d+ \| (\d+) \| (\d+) \|", table, re.M)
    assert len(rows) >= 4
    for wave, budget in rows:
        assert round(sc.wave_budget(int(wave))) == int(budget)
    assert sc.wave_budget(10, difficulty=1.2) == pytest.approx(1.2 * sc.wave_budget(10))
    assert sc.wave_budget(10, player_count=2) == sc.wave_budget(10)  # co-op factor still open (0)


def test_scaling_curves(make_config):
    sc = make_config().scaling
    assert sc.hp_mult(0) == 1.0 and round(sc.hp_mult(5), 1) == 1.8 and round(sc.hp_mult(10), 1) == 3.2
    assert round(sc.damage_mult(10), 1) == 1.9
    assert sc.speed_mult(5) == pytest.approx(1.05) and sc.speed_mult(60) == 1.2
    assert sc.xp_needed(1) == pytest.approx(2 + 1.2 + 0.12)  # fast levels (Paket F)


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
    # a group (5 aphids) is bought as a whole, so up to one group's cost can move into the next wave
    assert spawned_costs(w, ticks) == pytest.approx(sc.wave_budget(0), abs=2.5)
    assert spawned_costs(w, ticks) == pytest.approx(sc.wave_budget(1), abs=2.5)


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
    w.tick = w.stage_tick = 4 * 60 * TICK_HZ  # jump to minute 4 of the first bed
    w.step()
    late = w.enemies[0]
    sc = w.config.scaling
    assert late.max_hp == pytest.approx(first.max_hp * sc.hp_mult(4.0), rel=1e-3)
    assert late.damage == pytest.approx(first.damage * sc.damage_mult(4.0), rel=1e-3)
    w.enemies.clear()
    w.stage, w.stage_tick = 1, 0  # second bed: its own multipliers on top
    w.step()
    st = w.config.stages[1]
    assert w.enemies[0].max_hp == pytest.approx(first.max_hp * st.hp_mult, rel=1e-3)


def test_flood_grows_every_ten_seconds(make_config):
    w = World(1, make_config(enemy_target=0))
    f = w.config.flood
    w.stage_tick = int(w.stage_cfg.duration_s * TICK_HZ)
    assert w._flood_factor(f.hp_growth) == 1.0
    w.stage_tick += 25 * TICK_HZ
    assert w._flood_factor(f.hp_growth) == pytest.approx((1 + f.hp_growth) ** 2 * (1 + f.hp_growth * 0.5))


def test_every_pest_is_in_the_pool_and_beds_pick_their_own(content, make_config):
    cfg = make_config()
    assert {m.id for m in cfg.mobs} == {m.id for m in content.mobs}
    w = World(1, cfg)
    w.stage_tick = 120 * TICK_HZ
    for i, st in enumerate(cfg.stages):
        w.stage = i
        picked = {w._pick_mob(st.biome).id for _ in range(300)}
        assert all(dict(m.biome_weights).get(st.biome, 0) > 0 for m in cfg.mobs if m.id in picked)
    assert "pest_tomato" not in {w._pick_mob("seedbed").id for _ in range(300)}


def test_full_run_through_three_beds(make_config):
    """Acceptance Paket F: bed 1 with its boss at 3:30, the gate, bed 2, bed 3; the bot has infinite HP.
    Real survival is measured in tools/balance.py."""
    w = World(7, make_config(character={"hp": 10**9}))
    events = []
    while w.stage < 1 or w.stage_time_s < 60:
        events += w.step([heuristic_input(w)])
        assert not w.over
    p = w.players[0]
    assert [e.stage for e in events if isinstance(e, StageStarted)] == [1, 2]
    bosses = [e.boss for e in events if isinstance(e, BossSpawned)]
    assert bosses == ["snail_queen"]
    first = next(e for e in events if isinstance(e, BossSpawned))
    assert first.tick // TICK_HZ == 210
    waves = [e.wave for e in events if isinstance(e, WaveStarted)]
    assert waves[:5] == [1, 2, 3, 4, 5]
    assert [e.tick // TICK_HZ for e in events if isinstance(e, EliteSpawned)][0] == 150
    kinds = {e.kind for e in events if isinstance(e, EnemySpawned)}
    assert {"slug", "aphid", "snail", "potato_beetle"} <= kinds
    assert any(isinstance(e, BossKilled) for e in events)
    assert not any(isinstance(e, FloodStarted) for e in events) or w.flood_ticks > 0
    # every level gave one card (upgrade or weapon level), chests give items
    assert p.kills > 50 and sum(p.upgrades.values()) + sum(st.level for st in p.weapons) == p.level - 1
    assert p.weapons and len(p.weapons) <= w.config.weapon_slots - 1
    assert sum(p.items.values()) == sum(isinstance(e, ChestOpened) for e in events)


def test_flood_rolls_in_waves_every_thirty_seconds(make_config):
    from lastbean.sim import FloodWave

    w = World(1, make_config(character={"hp": 10**9, "attack_rate": 0.001}, bosses=()))
    w.tick = w.stage_tick = int(w.stage_cfg.duration_s * TICK_HZ) - 1
    events = []
    for _ in range(int(61 * TICK_HZ)):
        w.players[0].offer, w.players[0].pending_levels = (), 0
        events += w.step()
    waves = [e for e in events if isinstance(e, FloodWave)]
    assert [e.wave for e in waves] == [1, 2, 3]
    assert waves[2].reward_mult > waves[1].reward_mult > 1.0
    assert w.snapshot().flood_wave == 3
    cfg = w.config.flood
    fast = w._spawn_enemy(w.config.mobs[0], 10.0, 10.0, [])
    base = w.config.mobs[0].speed * w.config.scaling.speed_mult(w.stage_time_s / 60)
    assert fast.speed == pytest.approx(base * (1 + cfg.speed_per_wave_pct / 100 * 2))
