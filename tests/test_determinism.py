import pytest

from lastbean.sim import TICK_HZ, PlayerInput, Rng, WaveStarted, World

REFERENCE_U32 = [1096865841, 933661059, 3314798965]


def scripted_inputs(n: int, seed: int) -> list[list[PlayerInput]]:
    rng = Rng(seed ^ 0xABCDEF)
    return [[PlayerInput(0, rng.randint(-1, 1), rng.randint(-1, 1))] for _ in range(n)]


@pytest.fixture
def run(make_config):
    def run(seed: int, inputs, **overrides) -> World:
        w = World(seed, make_config(**overrides))
        for inp in inputs:
            w.step(inp)
        return w

    return run


def test_same_seed_and_inputs_give_same_state(run):
    # 60 s with a crowd of enemies, shooting, hits, kills and contact damage.
    inputs = scripted_inputs(60 * TICK_HZ, 1)
    a, b = run(42, inputs, enemy_target=120), run(42, inputs, enemy_target=120)
    assert a.state_hash() == b.state_hash()
    assert a.players[0].kills > 0 and a.players[0].hp < a.players[0].max_hp


def test_different_seed_gives_different_state(run):
    inputs = scripted_inputs(10, 1)
    assert run(1, inputs).state_hash() != run(2, inputs).state_hash()


def test_different_inputs_give_different_state(run):
    assert run(1, scripted_inputs(600, 1)).state_hash() != run(1, scripted_inputs(600, 2)).state_hash()


def test_rng_reference_values_are_stable():
    # Pinned values: changing the generator would silently break replays and the leaderboard.
    r = Rng(12345)
    assert [r.next_u32() for _ in range(3)] == REFERENCE_U32
    r = Rng(0)
    assert {r.randint(-3, 3) for _ in range(500)} == set(range(-3, 4))
    assert all(0.0 <= r.random() < 1.0 for _ in range(500))


def test_rng_state_roundtrip():
    a = Rng(9)
    a.next_u32()
    b = Rng(0)
    b.setstate(a.getstate())
    assert [a.next_u32() for _ in range(5)] == [b.next_u32() for _ in range(5)]


def test_player_stays_inside_arena(make_config):
    cfg = make_config(arena_w=200.0, arena_h=100.0, enemy_target=0, character={"speed": 500.0})
    w = World(1, cfg)
    for _ in range(300):
        w.step([PlayerInput(0, 1, 1)])
    p = w.players[0]
    assert p.x == 200 - 12 and p.y == 100 - 12


def test_diagonal_is_not_faster(make_config):
    w = World(1, make_config(enemy_target=0, character={"speed": 60.0}))
    start = w.players[0].x, w.players[0].y
    for _ in range(TICK_HZ):
        w.step([PlayerInput(0, 1, 1)])
    dx, dy = w.players[0].x - start[0], w.players[0].y - start[1]
    assert abs((dx * dx + dy * dy) ** 0.5 - 60) < 1e-9


def test_waves_advance_every_interval(make_config):
    w = World(1, make_config(enemy_target=0, wave_interval_s=30))
    waves = [e.wave for _ in range(TICK_HZ * 65) for e in w.step() if isinstance(e, WaveStarted)]
    assert waves == [1, 2] and w.wave == 2


def test_world_supports_several_players(make_config):
    w = World(1, make_config(enemy_target=0, player_count=3))
    w.step([PlayerInput(2, 1, 0)])
    assert [p.player_id for p in w.players] == [0, 1, 2]
    assert w.players[2].x > w.players[1].x + 32 - 1e-9 and w.players[0].standing and not w.players[2].standing
