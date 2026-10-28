"""Game window and main loop.

Fixed simulation step of 1/60 s with an accumulator; rendering runs once per frame.
The loop is async with `await asyncio.sleep(0)` so it also runs in the browser (pygbag).

Debug keys: F3 shows frame timings, F4 switches to a stress test (200 enemies, player cannot die),
F5 runs a synchronous benchmark (independent of the browser frame rate) and shows the result with F3.
"""

from __future__ import annotations

import asyncio
import dataclasses
import secrets
import sys
import time

import pygame

from .audio import Audio
from .data import load_content
from .meta.profile import ProfileStore, default_store, new_profile, record_run, set_nickname, valid_nickname
from .online.leaderboard import REFRESH_S, Leaderboard
from .render.effects import Effects
from .render.renderer import CANVAS_H, CANVAS_W, Renderer, effect_palette
from .sim import DT, PlayerInput, World, WorldConfig
from .ui import screens
from .ui.layout import is_compact, logical_size, zoom_step
from .ui.touch import TouchState

MAX_STEPS_PER_FRAME = 5  # avoid the spiral of death after a stall
WEB = sys.platform == "emscripten"
STRESS_ENEMIES = 200


def read_input(player_id: int = 0) -> PlayerInput:
    keys = pygame.key.get_pressed()
    mx = (keys[pygame.K_d] or keys[pygame.K_RIGHT]) - (keys[pygame.K_a] or keys[pygame.K_LEFT])
    my = (keys[pygame.K_s] or keys[pygame.K_DOWN]) - (keys[pygame.K_w] or keys[pygame.K_UP])
    ability = bool(keys[pygame.K_SPACE] or keys[pygame.K_e])
    return PlayerInput(player_id, int(mx), int(my), ability=ability)


def card_choice(key: int, renderer: Renderer) -> int | None:
    """Keys on the level-up screen: 1/2/3 pick directly, arrows move the selection, Enter/Space confirm."""
    if key in (pygame.K_1, pygame.K_2, pygame.K_3):
        return key - pygame.K_1
    if key in (pygame.K_LEFT, pygame.K_a):
        renderer.selected = max(0, renderer.selected - 1)
    elif key in (pygame.K_RIGHT, pygame.K_d):
        renderer.selected += 1  # clamped to the number of cards when drawn
    elif key in (pygame.K_RETURN, pygame.K_SPACE, pygame.K_KP_ENTER):
        return renderer.selected
    return None


def benchmark(content, renderer: Renderer, enemies: int = STRESS_ENEMIES, ticks: int = 600) -> str:
    """Simulate `ticks` steps with `enemies` alive and draw 120 frames; report ms per step and per frame."""
    world = World(1, stress_config(WorldConfig.from_content(content), enemies))
    for _ in range(180):  # fill the arena first
        world.step([PlayerInput(0, choice=0)])
    t0 = time.perf_counter()
    for i in range(ticks):
        world.step([PlayerInput(0, 1 if (i // 60) % 2 else -1, 0, choice=0)])
    sim = (time.perf_counter() - t0) / ticks
    t1 = time.perf_counter()
    for _ in range(120):
        renderer.draw(world.snapshot())
    draw = (time.perf_counter() - t1) / 120
    return f"Messlauf {len(world.enemies)} Gegner: sim {sim * 1000:.2f} ms/Schritt, Zeichnen {draw * 1000:.2f} ms/Bild"


def use_whole_page() -> None:
    """pygbag sizes the canvas to half the page until main.py returns, which a game loop never does."""
    try:
        import platform

        platform.window.config.gui_divider = 1
        platform.window.window_resize()
        splash = platform.document.getElementById("lbs-splash")
        if splash:
            splash.style.display = "none"  # the game's own start screen takes over
    except Exception as exc:  # noqa: BLE001 - layout tweak only, never stop the game
        print("Vollbreite nicht gesetzt:", exc)


def stress_config(config: WorldConfig, enemies: int = STRESS_ENEMIES) -> WorldConfig:
    immortal = dataclasses.replace(config.character, hp=10**9)
    return dataclasses.replace(config, character=immortal, enemy_target=enemies)


class FrameTimer:
    """Rolling averages of simulation time, drawing time and frame time, for the F3 overlay."""

    def __init__(self, n: int = 60) -> None:
        self.n = n
        self.samples: dict[str, list[float]] = {"sim": [], "draw": [], "frame": []}

    def add(self, **values: float) -> None:
        for key, v in values.items():
            lst = self.samples[key]
            lst.append(v)
            if len(lst) > self.n:
                lst.pop(0)

    def ms(self, key: str) -> float:
        lst = self.samples[key]
        return 1000 * sum(lst) / max(1, len(lst))

    def text(self, world: World) -> str:
        frame = self.ms("frame")
        fps = 1000 / frame if frame > 0 else 0
        return (
            f"FPS {fps:.0f}  sim {self.ms('sim'):.1f} ms  draw {self.ms('draw'):.1f} ms  "
            f"Gegner {len(world.enemies)}  Kugeln {len(world.orbs)}"
        )


class Game:
    """Screens and the running world. States: "name" -> "menu" -> "play" -> "results" -> "play"/"menu"."""

    def __init__(self, content, renderer: Renderer, store: ProfileStore, seed: int | None, autostart: bool) -> None:
        self.content, self.renderer, self.store = content, renderer, store
        try:
            self.profile = store.load()
        except Exception as exc:  # noqa: BLE001 - a broken store must not stop the game
            print("Spielstand konnte nicht geladen werden:", exc)
            self.profile = new_profile()
        self.normal = WorldConfig.from_content(content)
        self.config = self.normal
        self.fixed_seed = seed
        self.seed = seed if seed is not None else secrets.randbelow(2**31)
        self.world = World(self.seed, self.config)
        self.result: dict = {}
        self.flags: dict = {}
        self.name_buffer = ""
        self.state = "play" if autostart else ("menu" if self.profile.get("nickname") else "name")
        self.first_name = not self.profile.get("nickname")
        self.leaderboard = Leaderboard()
        self.online: tuple[str, int | None, int | None] = ("", None, None)
        self.board: dict = {"period": "all", "entries": None, "loading": False, "fetched_at": 0.0}
        self._tasks: dict[str, asyncio.Future] = {}

    def new_run(self) -> None:
        self.seed = self.seed + 1 if self.fixed_seed is not None else secrets.randbelow(2**31)
        self.world = World(self.seed, self.config)
        self.state = "play"

    def finish_run(self) -> None:
        """Record the result once, when the run ends (stress-test runs are not recorded)."""
        self.result = self.world.result().to_dict()
        self.flags = {}
        self.online = ("", None, None)
        if self.config is self.normal:
            self.flags = record_run(self.profile, self.result)
            if self.leaderboard.queue(self.profile, self.result):
                self.online = ("sending", None, None)
            self.save()
            self.start_sync()
        self.state = "results"

    # ------------------------------------------------------------------ online leaderboard

    def start_sync(self) -> None:
        """Send queued runs in the background (an asyncio task, no threads)."""
        if self.leaderboard.enabled and self.profile["pending_submissions"] and not self._busy("sync"):
            self._tasks["sync"] = asyncio.ensure_future(self._sync())

    async def _sync(self) -> None:
        report = await self.leaderboard.sync(self.profile)
        self.save()
        if report.last_rank:
            self.online = ("rank", report.last_rank, report.last_rank_character)
        elif report.offline and self.online[0] == "sending":
            self.online = ("offline", None, None)
        elif report.error and self.online[0] == "sending":
            self.online = (f"Nicht angenommen: {report.error}", None, None)

    def open_board(self) -> None:
        self.state = "board"
        self.refresh_board()

    def refresh_board(self) -> None:
        if self.leaderboard.enabled and not self._busy("board"):
            self.board["loading"] = True
            self._tasks["board"] = asyncio.ensure_future(self._fetch_board())

    async def _fetch_board(self) -> None:
        self.board["entries"] = await self.leaderboard.top(self.board["period"])
        self.board["loading"] = False
        self.board["fetched_at"] = time.monotonic()

    def switch_period(self, step: int) -> None:
        periods = list(screens.PERIOD_NAMES)
        i = periods.index(self.board["period"])
        self.board["period"] = periods[(i + step) % len(periods)]
        self.board["entries"] = None
        self.refresh_board()

    def _busy(self, name: str) -> bool:
        task = self._tasks.get(name)
        return task is not None and not task.done()

    def save(self) -> None:
        try:
            self.store.save(self.profile)
        except Exception as exc:  # noqa: BLE001 - a full disk or blocked storage must not crash the game
            print("Spielstand konnte nicht gespeichert werden:", exc)

    def start_name_entry(self) -> None:
        self.name_buffer = self.profile.get("nickname") or ""
        self.state = "name"
        if not WEB:
            pygame.key.start_text_input()

    def confirm_name(self) -> None:
        if valid_nickname(self.name_buffer):
            set_nickname(self.profile, self.name_buffer)
            self.save()
            self.first_name = False
            self.state = "menu"
            pygame.key.stop_text_input()

    def type_name(self) -> None:
        """Phones and tablets: the browser's own text dialog brings up the on-screen keyboard."""
        if not WEB:
            return
        answer = web_prompt("Wie heißt deine Bohne? (2 bis 16 Zeichen)", self.name_buffer)
        if answer is not None:
            self.name_buffer = answer.strip()[:16]
            self.confirm_name()

    def handle_name_event(self, event) -> None:
        if event.type == pygame.TEXTINPUT:
            self.name_buffer = (self.name_buffer + event.text)[:16]
        elif event.type == pygame.KEYDOWN:
            if event.key == pygame.K_BACKSPACE:
                self.name_buffer = self.name_buffer[:-1]
            elif event.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                self.confirm_name()
            elif event.key == pygame.K_ESCAPE and not self.first_name:
                self.state = "menu"
                pygame.key.stop_text_input()


def web_prompt(question: str, default: str) -> str | None:
    try:
        import platform

        answer = platform.window.prompt(question, default)
        return None if answer is None else str(answer)
    except Exception as exc:  # noqa: BLE001 - no dialog available: keep the current name
        print("Eingabedialog nicht verfügbar:", exc)
        return None


class Screen:
    """The browser page or desktop window, and the logical canvas size that fits it."""

    def __init__(self, renderer: Renderer, zoom: int | None = None) -> None:
        self.renderer = renderer
        self.window: pygame.Surface | None = None
        self._css = (0, 0)
        self.zoom = zoom  # short side of the canvas chosen by the player; None = device default
        self.fit()

    def change_zoom(self, steps: int) -> bool:
        """Zoom in (negative steps) or out. Returns True when the view changed."""
        current = self.zoom or min(self.renderer.w, self.renderer.h)
        new = zoom_step(current, steps)
        if new == current:
            return False
        self.zoom = new
        self.fit(force=True)
        return True

    def css_size(self) -> tuple[int, int]:
        import platform

        return int(platform.window.innerWidth), int(platform.window.innerHeight)

    def fit(self, force: bool = False) -> None:
        """Pick the canvas size for the current screen. On the web the page size is polled (rotation)."""
        if WEB:
            css = self.css_size()
            if css == self._css and not force:
                return
            self._css = css
            w, h = logical_size(*css, compact=is_compact(*css), short=self.zoom)
            self.window = pygame.display.set_mode((w * 2, h * 2))
            use_whole_page()
        else:
            if self.window is None:
                self.window = pygame.display.set_mode((CANVAS_W * 2, CANVAS_H * 2), pygame.RESIZABLE)
            w, h = logical_size(*self.window.get_size(), short=self.zoom)
        self.renderer.resize(w, h)

    def debug_requested(self) -> bool:
        """Web: `?debug` in the address shows touch diagnostics on screen (for testing on phones)."""
        if not WEB:
            return False
        try:
            import platform

            return "debug" in str(platform.window.location.search)
        except Exception:  # noqa: BLE001
            return False

    def to_canvas(self, event) -> tuple[int, int]:
        """Canvas position of a mouse or finger event (fingers come normalised to 0..1)."""
        if event.type in (pygame.FINGERDOWN, pygame.FINGERUP, pygame.FINGERMOTION):
            ww, wh = self.window.get_size()
            return self.renderer.window_to_canvas(event.x * ww, event.y * wh)
        return self.renderer.window_to_canvas(*event.pos)


async def run(
    seed: int | None = None,
    max_frames: int | None = None,
    store: ProfileStore | None = None,
    autostart: bool = False,
) -> World:
    """Open the window and play. `max_frames` stops after that many frames (smoke tests)."""
    content = load_content()
    pygame.init()
    pygame.display.set_caption("Last Bean Standing")
    renderer = Renderer(content)
    game = Game(content, renderer, store or default_store(), seed, autostart)
    screen = Screen(renderer, game.profile["settings"]["zoom"])
    effects = Effects(*effect_palette(renderer))
    audio = Audio()
    touch = TouchState()

    def zoom(steps: int) -> None:
        if screen.change_zoom(steps):
            game.profile["settings"]["zoom"] = screen.zoom
            game.save()

    if game.state == "name":
        game.start_name_entry()
    game.start_sync()  # runs queued while offline
    renderer.set_arena(game.config)
    clock = pygame.time.Clock()
    timer, show_timings, bench_result = FrameTimer(), False, ""
    acc, frames, running, choice = 0.0, 0, True, None
    buttons: list[screens.Button] = []
    touch_ability = False
    was_paused = False
    touch_debug = "" if screen.debug_requested() else None
    last = time.perf_counter()
    next_fit = 0.0

    def new_run() -> None:
        nonlocal acc
        game.new_run()
        effects.reset()
        touch.reset()
        acc = 0.0

    def do(action: str | None) -> None:
        """Button actions, shared by touch, mouse and keyboard."""
        nonlocal running, acc
        if action is None:
            return
        if action in ("play", "again"):
            new_run()
        elif action == "board":
            game.open_board()
        elif action == "name":
            game.start_name_entry()
            game.type_name()
        elif action == "type":
            game.type_name()
        elif action == "ok":
            game.confirm_name()
        elif action in ("cancel", "menu", "back"):
            game.state = "menu"
            pygame.key.stop_text_input()
        elif action == "resume":
            game.state, acc = "play", 0.0
        elif action == "mute":
            audio.muted = not audio.muted
        elif action == "quit":
            running = False
        elif action.startswith("period:"):
            game.board["period"], game.board["entries"] = action.split(":", 1)[1], None
            game.refresh_board()

    def tap(pos: tuple[int, int]) -> None:
        nonlocal choice, touch_ability
        if game.state == "play":
            if game.world.paused:
                for i, rect in enumerate(renderer.card_rects):
                    if rect.collidepoint(pos):
                        choice = i
            elif renderer.pause_rect.collidepoint(pos):
                game.state = "pause"
            elif renderer.ability_rect.collidepoint(pos):
                touch_ability = True
        else:
            do(screens.hit(buttons, pos))

    try:
        while running:
            if WEB and time.monotonic() >= next_fit:  # page resized or device rotated
                screen.fit()
                next_fit = time.monotonic() + 0.5
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                elif event.type == pygame.WINDOWFOCUSLOST and game.state == "play" and not game.world.paused:
                    game.state = "pause"  # switching tabs or apps must not cost the run
                    touch.reset()
                elif event.type == pygame.VIDEORESIZE and not WEB:
                    screen.fit()
                elif event.type == pygame.FINGERDOWN:
                    renderer.touch = True
                    pos = screen.to_canvas(event)
                    if touch_debug is not None:
                        ww, wh = screen.window.get_size()
                        touch_debug = (
                            f"tap {event.x:.2f},{event.y:.2f} -> {pos} {game.state}\n"
                            f"canvas {renderer.w}x{renderer.h} win {ww}x{wh} css {screen._css[0]}x{screen._css[1]}"
                        )
                    on_button = renderer.ability_rect.collidepoint(pos) or renderer.pause_rect.collidepoint(pos)
                    steer = game.state == "play" and not game.world.paused and not on_button
                    touch.down(event.finger_id, *pos, steer=steer)
                    if game.state == "play" and not game.world.paused and on_button:
                        tap(pos)  # buttons react on touch down, so a running thumb is never blocked
                elif event.type == pygame.FINGERMOTION:
                    touch.move(event.finger_id, *screen.to_canvas(event))
                    ratio = touch.pinch_ratio()  # two fingers: pinch to zoom
                    if ratio is not None and (ratio > 1.15 or ratio < 0.87):
                        zoom(-1 if ratio > 1 else 1)
                        touch.rebase_pinch()
                elif event.type == pygame.MOUSEWHEEL:
                    zoom(-1 if event.y > 0 else 1)
                elif event.type == pygame.FINGERUP:
                    pos = screen.to_canvas(event)
                    in_game = game.state == "play" and not game.world.paused
                    if touch.up(event.finger_id, *pos) and not in_game:
                        tap(pos)
                elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1 and not getattr(event, "touch", False):
                    tap(screen.to_canvas(event))
                elif game.state == "name":
                    game.handle_name_event(event)
                elif event.type != pygame.KEYDOWN:
                    continue
                elif event.key == pygame.K_m:
                    audio.muted = not audio.muted
                elif event.key in (pygame.K_PLUS, pygame.K_EQUALS, pygame.K_KP_PLUS):
                    zoom(-1)
                elif event.key in (pygame.K_MINUS, pygame.K_KP_MINUS):
                    zoom(1)
                elif event.key == pygame.K_F11 and not WEB:
                    pygame.display.toggle_fullscreen()
                elif event.key == pygame.K_F3:
                    show_timings = not show_timings
                elif event.key == pygame.K_F5:
                    bench_result = benchmark(content, renderer)
                    print(bench_result)
                    show_timings, last = True, time.perf_counter()
                elif game.state == "menu":
                    if event.key in (pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_SPACE):
                        do("play")
                    elif event.key == pygame.K_n:
                        game.start_name_entry()
                    elif event.key == pygame.K_l:
                        do("board")
                    elif event.key == pygame.K_ESCAPE and not WEB:
                        running = False
                elif game.state == "board":
                    if event.key in (pygame.K_LEFT, pygame.K_a):
                        game.switch_period(-1)
                    elif event.key in (pygame.K_RIGHT, pygame.K_d):
                        game.switch_period(1)
                    elif event.key in (pygame.K_ESCAPE, pygame.K_RETURN, pygame.K_KP_ENTER):
                        do("back")
                elif game.state == "results":
                    if event.key == pygame.K_r:
                        do("again")
                    elif event.key in (pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_ESCAPE):
                        do("menu")
                elif game.state == "pause":
                    if event.key in (pygame.K_ESCAPE, pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_SPACE, pygame.K_p):
                        do("resume")
                    elif event.key == pygame.K_r:
                        do("again")
                    elif event.key == pygame.K_q:
                        do("menu")  # abandon the run, it is not recorded
                elif event.key in (pygame.K_ESCAPE, pygame.K_p) and not game.world.paused:
                    game.state = "pause"
                elif event.key == pygame.K_F4:
                    game.config = game.normal if game.config is not game.normal else stress_config(game.normal)
                    new_run()
                elif game.world.paused:
                    choice = card_choice(event.key, renderer)
            acc += min(clock.tick(60 if WEB else 120) / 1000.0, DT * MAX_STEPS_PER_FRAME)
            t0 = time.perf_counter()
            world = game.world
            frame_events: list = []
            if game.state == "play":
                if world.paused:
                    acc = 0.0
                    if not was_paused:  # cards just opened: forget fingers that were steering, keep new taps
                        touch.reset()
                    if choice is not None:
                        frame_events += world.step([PlayerInput(0, choice=choice)])
                        renderer.selected = 0
                    elif game.config is not game.normal:
                        frame_events += world.step([PlayerInput(0, choice=0)])  # stress test picks automatically
                elif effects.hitstop > 0:  # hit-stop: the picture holds for a few frames, the run just waits
                    effects.hitstop -= 1
                    acc = 0.0
                else:
                    inputs = [combine_input(read_input(0), touch.direction(), touch_ability)]
                    while acc >= DT and not world.paused and not world.over:
                        frame_events += world.step(inputs)
                        acc -= DT
                        inputs = [dataclasses.replace(inputs[0], ability=False)]  # one press, one use
                    touch_ability = False
                if frame_events:
                    positions = {p.player_id: (p.x, p.y) for p in world.players}
                    effects.handle(frame_events, renderer.boss_names, positions)
                audio.handle(frame_events)
                effects.update()
                if world.over:
                    game.finish_run()
                    touch.reset()
            else:
                acc = 0.0
            choice = None
            was_paused = game.state == "play" and game.world.paused
            t1 = time.perf_counter()
            buttons = []
            if game.state in ("play", "results", "pause"):
                debug = f"{timer.text(world)}  {bench_result}" if show_timings else None
                renderer.draw(world.snapshot(), debug=debug, effects=effects)
                if game.state == "play" and touch.stick is not None:
                    renderer.draw_stick(touch.stick)
                if game.state == "pause":
                    buttons = screens.draw_pause(renderer, game.world.snapshot(), audio.muted)
                if game.state == "results":
                    line = screens.online_line(*game.online)
                    buttons = screens.draw_results(renderer, game.result, game.flags, game.profile, line)
            elif game.state == "menu":
                buttons = screens.draw_menu(renderer, game.profile, WEB)
            elif game.state == "board":
                if time.monotonic() - game.board["fetched_at"] > REFRESH_S:
                    game.refresh_board()
                buttons = screens.draw_board(renderer, game.board, game.profile, game.leaderboard.enabled)
            else:
                valid = valid_nickname(game.name_buffer)
                buttons = screens.draw_name_entry(renderer, game.name_buffer, valid, game.first_name)
            if touch_debug is not None:
                for i, line in enumerate((touch_debug or "Tippe irgendwo hin").split("\n")):
                    renderer.text(line, (4, renderer.h - 34 + i * 14))
                for b in buttons:
                    pygame.draw.rect(renderer.canvas, (255, 60, 60), b.rect, 1)
            renderer.present(screen.window)
            pygame.display.flip()
            t2 = time.perf_counter()
            timer.add(sim=t1 - t0, draw=t2 - t1, frame=t2 - last)
            last = t2
            frames += 1
            if max_frames is not None and frames >= max_frames:
                running = False
            await asyncio.sleep(0)
    finally:
        pygame.quit()
    return game.world


def combine_input(keys: PlayerInput, stick: tuple[int, int], touch_ability: bool) -> PlayerInput:
    """Keyboard and touch together: the stick wins when it is deflected."""
    mx, my = stick if stick != (0, 0) else (keys.move_x, keys.move_y)
    return PlayerInput(keys.player_id, mx, my, ability=keys.ability or touch_ability)
