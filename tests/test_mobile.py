"""Phone and tablet support: canvas size per screen, touch joystick, tappable buttons."""

import pytest

from lastbean.ui.layout import is_compact, logical_size
from lastbean.ui.touch import Joystick, TouchState

pygame = pytest.importorskip("pygame")


@pytest.mark.parametrize(
    "css, expected",
    [
        ((390, 844), (300, 650)),  # iPhone portrait: zoomed in a little
        ((844, 390), (650, 300)),  # iPhone landscape
        ((820, 1180), (360, 518)),  # iPad portrait
        ((1180, 820), (518, 360)),  # iPad landscape
        ((1920, 1080), (640, 360)),  # desktop 16:9 as before
        ((3000, 600), (864, 360)),  # extremely wide: capped aspect
    ],
)
def test_logical_size(css, expected):
    assert logical_size(*css, compact=is_compact(*css)) == expected


@pytest.mark.parametrize(
    "dx, dy, direction",
    [(0, 0, (0, 0)), (5, 3, (0, 0)), (30, 0, (1, 0)), (-30, 2, (-1, 0)), (0, 30, (0, 1)), (25, 25, (1, 1)),
     (-25, -22, (-1, -1)), (30, 8, (1, 0)), (30, 14, (1, 1))],
)  # fmt: skip
def test_joystick_eight_directions(dx, dy, direction):
    assert Joystick(0, 100, 100, 100 + dx, 100 + dy).direction() == direction


def test_knob_is_clamped():
    kx, ky = Joystick(0, 0, 0, 300, 0).knob()
    assert kx == pytest.approx(36) and ky == 0


def test_touch_state_steering_and_taps():
    t = TouchState()
    t.down(1, 50, 300, steer=True)
    t.down(2, 280, 600, steer=True)  # second finger does not take over the stick
    t.move(1, 90, 300)
    assert t.direction() == (1, 0)
    assert t.up(2, 282, 601) is True  # short touch = tap
    assert t.up(1, 90, 300) is False and t.direction() == (0, 0)


def test_combine_input_prefers_stick():
    from lastbean.app import combine_input
    from lastbean.sim import PlayerInput

    keys = PlayerInput(0, -1, 0)
    assert combine_input(keys, (0, 1), False) == PlayerInput(0, 0, 1)
    assert combine_input(keys, (0, 0), True) == PlayerInput(0, -1, 0, ability=True)


@pytest.fixture
def renderer(monkeypatch, content):
    monkeypatch.setenv("SDL_VIDEODRIVER", "dummy")
    pygame.init()
    pygame.display.set_mode((1, 1))
    from lastbean.render.renderer import Renderer

    return lambda size: Renderer(content, size)


@pytest.mark.parametrize("size", [(300, 650), (518, 360), (640, 360), (360, 780)])
def test_screens_fit_and_have_buttons(renderer, size):
    from lastbean.meta.profile import new_profile, record_run, set_nickname
    from lastbean.ui import screens

    r = renderer(size)
    r.touch = True
    p = new_profile()
    set_nickname(p, "Fenn")
    result = dict(score=500, seconds=90, kills=60, level=4, bosses=0, wave=3, character="ranger", seed=1)
    flags = record_run(p, result)
    board = {"period": "all", "entries": [dict(rank=1, name="Fenn", seconds=90, kills=60, score=500)] * 10}
    canvas = pygame.Rect(0, 0, *size)
    for buttons, needed in [
        (screens.draw_menu(r, p, web=True), {"play", "board", "name"}),
        (screens.draw_name_entry(r, "Fenn", True, first_time=False), {"ok", "type", "cancel"}),
        (screens.draw_results(r, result, flags, p, "Online-Rang #1"), {"again", "menu"}),
        (screens.draw_board(r, board, p, True), {"back", "period:all", "period:week", "period:month"}),
    ]:
        assert needed <= {b.action for b in buttons}
        assert all(canvas.contains(b.rect) for b in buttons), [b for b in buttons if not canvas.contains(b.rect)]
    play = screens.draw_menu(r, p, web=True)[0]
    assert screens.hit([play], play.rect.center) == "play"


@pytest.mark.parametrize("size", [(300, 650), (518, 360), (640, 360)])
def test_cards_and_hud_buttons_fit(renderer, size, make_config):
    from lastbean.bots import heuristic_input
    from lastbean.sim import World
    from lastbean.ui import screens

    r = renderer(size)
    r.touch = True
    w = World(5, make_config())
    while not w.paused:
        w.step([heuristic_input(w)])
    snap = w.snapshot()
    r.draw(snap)
    canvas = pygame.Rect(0, 0, *size)
    assert len(r.card_rects) == 3 and all(canvas.contains(c) for c in r.card_rects)
    assert canvas.contains(r.ability_rect) and canvas.contains(r.pause_rect) and r.ability_rect.w >= 40
    assert all(canvas.contains(b.rect) for b in screens.draw_pause(r, snap, muted=False))


def test_window_to_canvas(renderer):
    r = renderer((300, 650))
    window = pygame.Surface((600, 1300))
    r.present(window)
    assert r.window_to_canvas(300, 650) == (150, 325)
