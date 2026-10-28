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
    t.move(1, 90, 300)
    assert t.direction() == (1, 0)
    assert t.up(1, 90, 300) is False and t.direction() == (0, 0)  # a drag is no tap
    t.down(2, 200, 400, steer=False)
    assert t.up(2, 203, 401) is True  # short touch = tap


def test_two_fingers_pinch_instead_of_steering():
    t = TouchState()
    t.down(1, 100, 300, steer=True)
    t.down(2, 200, 300, steer=True)
    assert t.stick is None and t.pinching and t.pinch_ratio() == pytest.approx(1.0)
    t.move(2, 250, 300)
    assert t.pinch_ratio() == pytest.approx(1.5)  # fingers apart = zoom in
    t.rebase_pinch()
    assert t.pinch_ratio() == pytest.approx(1.0)
    assert t.up(2, 250, 300) is False and t.up(1, 100, 300) is False  # ending a pinch is no tap
    t.down(3, 60, 300, steer=True)
    assert t.stick is not None and not t.pinching  # next touch steers again


def test_zoom_steps_are_clamped():
    from lastbean.ui.layout import ZOOM_STEPS, zoom_step

    assert zoom_step(300, -1) == 270 and zoom_step(300, 1) == 330
    assert zoom_step(ZOOM_STEPS[0], -5) == ZOOM_STEPS[0] and zoom_step(ZOOM_STEPS[-1], 5) == ZOOM_STEPS[-1]
    assert zoom_step(365, 0) == 360  # snaps to the nearest step
    assert logical_size(390, 844, compact=True, short=240) == (240, 520)


def test_zoom_is_saved_in_profile():
    from lastbean.meta.profile import new_profile, normalize

    p = new_profile()
    assert p["settings"]["zoom"] is None
    p["settings"]["zoom"] = 270
    assert normalize(p)["settings"]["zoom"] == 270
    assert normalize({"settings": {"zoom": "gross"}})["settings"]["zoom"] is None


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
def test_screens_fit_and_have_buttons(renderer, size, content):
    from lastbean.meta.profile import new_profile, record_run, set_nickname
    from lastbean.ui import screens

    chars = [c for c in content.characters if c.impl_phase == 1]
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
        (screens.draw_name_entry(r, "Fenn", True, False, keyboard=True), {"ok", "cancel", "key:Q", "key:back"}),
        (screens.draw_results(r, result, flags, p, "Online-Rang #1"), {"again", "menu"}),
        (screens.draw_board(r, board, p, True), {"back", "period:all", "period:week", "period:month"}),
        (screens.draw_characters(r, chars, "ranger", {}), {"char:ranger", "char:storm", "menu"}),
    ]:
        assert needed <= {b.action for b in buttons}
        assert all(canvas.contains(b.rect) for b in buttons), [b for b in buttons if not canvas.contains(b.rect)]
    play = next(b for b in screens.draw_menu(r, p, web=True) if b.action == "play")
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


@pytest.mark.parametrize("size", [(300, 650), (640, 360)])
def test_prologue_fits(renderer, size):
    from lastbean.ui import screens

    r = renderer(size)
    buttons = screens.draw_prologue(r)
    assert [b.action for b in buttons] == ["prologue_done"]
    assert pygame.Rect(0, 0, *size).contains(buttons[0].rect)


def test_app_icon_and_manifest_for_the_home_screen():
    import json
    from pathlib import Path

    web = Path(__file__).resolve().parents[1] / "web"
    manifest = json.loads((web / "manifest.webmanifest").read_text(encoding="utf-8"))
    assert manifest["display"] == "fullscreen" and manifest["short_name"]
    for icon in manifest["icons"]:
        assert (web / icon["src"]).is_file(), icon["src"]
    page = (web / "template.tmpl").read_text(encoding="utf-8")
    assert 'rel="apple-touch-icon"' in page and (web / "icons" / "apple-touch-icon.png").is_file()
    assert 'rel="manifest"' in page
    img = pygame.image.load(str(web / "icons" / "apple-touch-icon.png"))
    assert img.get_size() == (180, 180)


def test_on_screen_keyboard_types_a_name(renderer, content):
    from lastbean.app import Game
    from lastbean.meta.profile import MemoryProfileStore
    from lastbean.ui import screens

    r = renderer((300, 650))
    r.touch = True
    game = Game(content, r, MemoryProfileStore(), seed=1, autostart=False)
    game.start_name_entry()
    for key in ("F", "e", "n", "n", " ", "B", "x", "back"):
        game.press_key(key)
    assert game.name_buffer == "Fenn B"
    buttons = screens.draw_name_entry(r, game.name_buffer, True, True, keyboard=True, upper=game.name_upper)
    labels = {b.action for b in buttons}
    assert "key:a" in labels and "key:ß" in labels and "key: " in labels  # small letters after the capital


@pytest.mark.parametrize("css,dpr", [((390, 844), 3.0), ((1024, 1366), 2.0), ((1920, 1080), 1.0), ((412, 915), 2.625)])
def test_every_canvas_pixel_is_a_whole_number_of_screen_pixels(css, dpr):
    from lastbean.ui.layout import pixel_perfect_size

    w, h, k = pixel_perfect_size(*css, dpr, 360)
    assert w * k <= css[0] * dpr + 1e-6 and h * k <= css[1] * dpr + 1e-6  # fits on the screen
    assert css[0] * dpr - w * k < k and css[1] * dpr - h * k < k  # and covers it up to less than one pixel
    assert 250 <= min(w, h) <= 520
