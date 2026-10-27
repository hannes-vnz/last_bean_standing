"""Game window and main loop.

Fixed simulation step of 1/60 s with an accumulator; rendering runs once per frame.
The loop is async with `await asyncio.sleep(0)` so it also runs in the browser (pygbag).

Debug keys: F3 shows frame timings, F4 switches to a stress test (200 enemies, player cannot die),
F5 runs a synchronous benchmark (independent of the browser frame rate) and shows the result with F3.
"""

from __future__ import annotations

import asyncio
import dataclasses
import sys
import time

import pygame

from .data import load_content
from .render.renderer import CANVAS_H, CANVAS_W, Renderer
from .sim import DT, PlayerInput, World, WorldConfig

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


async def run(seed: int = 1, max_frames: int | None = None) -> World:
    """Open the window and play. `max_frames` stops after that many frames (smoke tests)."""
    content = load_content()
    pygame.init()
    pygame.display.set_caption("Last Bean Standing")
    window = pygame.display.set_mode((CANVAS_W * 2, CANVAS_H * 2), 0 if WEB else pygame.RESIZABLE)
    renderer = Renderer(content)
    normal = WorldConfig.from_content(content)
    config = normal
    world = World(seed, config)
    clock = pygame.time.Clock()
    timer, show_timings, bench_result = FrameTimer(), False, ""
    acc, frames, running, choice = 0.0, 0, True, None
    last = time.perf_counter()
    try:
        while running:
            for event in pygame.event.get():
                if event.type == pygame.QUIT or (
                    not WEB and event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE
                ):
                    running = False
                elif event.type != pygame.KEYDOWN:
                    continue
                elif event.key == pygame.K_F3:
                    show_timings = not show_timings
                elif event.key == pygame.K_F5:
                    bench_result = benchmark(content, renderer)
                    print(bench_result)
                    show_timings, last = True, time.perf_counter()
                elif event.key == pygame.K_F4:
                    config = normal if config is not normal else stress_config(normal)
                    world, acc = World(seed, config), 0.0
                elif event.key == pygame.K_r and world.over:
                    seed += 1
                    world, acc = World(seed, config), 0.0
                elif world.paused:
                    choice = card_choice(event.key, renderer)
            acc += min(clock.tick(60 if WEB else 120) / 1000.0, DT * MAX_STEPS_PER_FRAME)
            t0 = time.perf_counter()
            if world.paused:
                acc = 0.0
                if choice is not None:
                    world.step([PlayerInput(0, choice=choice)])
                    renderer.selected = 0
                elif config is not normal:
                    world.step([PlayerInput(0, choice=0)])  # stress test picks automatically
            else:
                inputs = [read_input(0)]
                while acc >= DT and not world.paused:
                    world.step(inputs)
                    acc -= DT
            choice = None
            t1 = time.perf_counter()
            debug = f"{timer.text(world)}  {bench_result}" if show_timings else None
            renderer.draw(world.snapshot(), debug=debug)
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
    return world
