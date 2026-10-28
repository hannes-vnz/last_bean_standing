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
from .render.effects import Effects
from .render.renderer import CANVAS_H, CANVAS_W, Renderer, effect_palette
from .sim import DT, PlayerInput, World, WorldConfig
from .ui import screens

MAX_STEPS_PER_FRAME = 5  # avoid the spiral of death after a stall
WEB = sys.platform == "emscripten"
STRESS_ENEMIES = 200


def read_input(player_id: int = 0) -> PlayerInput:
    keys = pygame.key.get_pressed()
    mx = (keys[pygame.K_d] or keys[pygame.K_RIGHT]) - (keys[pygame.K_a] or keys[pygame.K_LEFT])
    my = (keys[pygame.K_s] or keys[pygame.K_DOWN]) - (keys[pygame.K_w] or keys[pygame.K_UP])
    return PlayerInput(player_id, int(mx), int(my))


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

    def new_run(self) -> None:
        self.seed = self.seed + 1 if self.fixed_seed is not None else secrets.randbelow(2**31)
        self.world = World(self.seed, self.config)
        self.state = "play"

    def finish_run(self) -> None:
        """Record the result once, when the run ends (stress-test runs are not recorded)."""
        self.result = self.world.result().to_dict()
        self.flags = {}
        if self.config is self.normal:
            self.flags = record_run(self.profile, self.result)
            self.save()
        self.state = "results"

    def save(self) -> None:
        try:
            self.store.save(self.profile)
        except Exception as exc:  # noqa: BLE001 - a full disk or blocked storage must not crash the game
            print("Spielstand konnte nicht gespeichert werden:", exc)

    def start_name_entry(self) -> None:
        self.name_buffer = self.profile.get("nickname") or ""
        self.state = "name"
        pygame.key.start_text_input()

    def handle_name_event(self, event) -> None:
        if event.type == pygame.TEXTINPUT:
            self.name_buffer = (self.name_buffer + event.text)[:16]
        elif event.type == pygame.KEYDOWN:
            if event.key == pygame.K_BACKSPACE:
                self.name_buffer = self.name_buffer[:-1]
            elif event.key in (pygame.K_RETURN, pygame.K_KP_ENTER) and valid_nickname(self.name_buffer):
                set_nickname(self.profile, self.name_buffer)
                self.save()
                self.first_name = False
                self.state = "menu"
                pygame.key.stop_text_input()
            elif event.key == pygame.K_ESCAPE and not self.first_name:
                self.state = "menu"
                pygame.key.stop_text_input()


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
    window = pygame.display.set_mode((CANVAS_W * 2, CANVAS_H * 2), 0 if WEB else pygame.RESIZABLE)
    renderer = Renderer(content)
    effects = Effects(*effect_palette(renderer))
    audio = Audio()
    game = Game(content, renderer, store or default_store(), seed, autostart)
    if game.state == "name":
        game.start_name_entry()
    renderer.set_arena(game.config)
    clock = pygame.time.Clock()
    timer, show_timings, bench_result = FrameTimer(), False, ""
    acc, frames, running, choice = 0.0, 0, True, None
    last = time.perf_counter()
    try:
        while running:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                elif game.state == "name":
                    game.handle_name_event(event)
                elif event.type != pygame.KEYDOWN:
                    continue
                elif event.key == pygame.K_m:
                    audio.muted = not audio.muted
                elif event.key == pygame.K_F3:
                    show_timings = not show_timings
                elif event.key == pygame.K_F5:
                    bench_result = benchmark(content, renderer)
                    print(bench_result)
                    show_timings, last = True, time.perf_counter()
                elif game.state == "menu":
                    if event.key in (pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_SPACE):
                        game.new_run()
                        effects.reset()
                        acc = 0.0
                    elif event.key == pygame.K_n:
                        game.start_name_entry()
                    elif event.key == pygame.K_ESCAPE and not WEB:
                        running = False
                elif game.state == "results":
                    if event.key == pygame.K_r:
                        game.new_run()
                        effects.reset()
                        acc = 0.0
                    elif event.key in (pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_ESCAPE):
                        game.state = "menu"
                elif event.key == pygame.K_ESCAPE:
                    game.state = "menu"  # abandon the run, it is not recorded
                elif event.key == pygame.K_F4:
                    game.config = game.normal if game.config is not game.normal else stress_config(game.normal)
                    game.new_run()
                    effects.reset()
                    acc = 0.0
                elif game.world.paused:
                    choice = card_choice(event.key, renderer)
            acc += min(clock.tick(60 if WEB else 120) / 1000.0, DT * MAX_STEPS_PER_FRAME)
            t0 = time.perf_counter()
            world = game.world
            frame_events: list = []
            if game.state == "play":
                if world.paused:
                    acc = 0.0
                    if choice is not None:
                        frame_events += world.step([PlayerInput(0, choice=choice)])
                        renderer.selected = 0
                    elif game.config is not game.normal:
                        frame_events += world.step([PlayerInput(0, choice=0)])  # stress test picks automatically
                elif effects.hitstop > 0:  # hit-stop: the picture holds for a few frames, the run just waits
                    effects.hitstop -= 1
                    acc = 0.0
                else:
                    inputs = [read_input(0)]
                    while acc >= DT and not world.paused and not world.over:
                        frame_events += world.step(inputs)
                        acc -= DT
                if frame_events:
                    positions = {p.player_id: (p.x, p.y) for p in world.players}
                    effects.handle(frame_events, renderer.boss_names, positions)
                audio.handle(frame_events)
                effects.update()
                if world.over:
                    game.finish_run()
            else:
                acc = 0.0
            choice = None
            t1 = time.perf_counter()
            if game.state in ("play", "results"):
                debug = f"{timer.text(world)}  {bench_result}" if show_timings else None
                renderer.draw(world.snapshot(), debug=debug, effects=effects)
                if game.state == "results":
                    screens.draw_results(renderer, game.result, game.flags, game.profile)
            elif game.state == "menu":
                screens.draw_menu(renderer, game.profile, WEB)
            else:
                screens.draw_name_entry(renderer, game.name_buffer, valid_nickname(game.name_buffer), game.first_name)
            renderer.present(window)
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
