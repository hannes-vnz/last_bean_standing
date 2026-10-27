"""Game window and main loop.

Fixed simulation step of 1/60 s with an accumulator; rendering runs once per frame.
The loop is async with `await asyncio.sleep(0)` so it can later run in the browser (pygbag).
"""

from __future__ import annotations

import asyncio

import pygame

from .data import load_content
from .render.renderer import CANVAS_H, CANVAS_W, Renderer
from .sim import DT, PlayerInput, World, WorldConfig

MAX_STEPS_PER_FRAME = 5  # avoid the spiral of death after a stall


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


async def run(seed: int = 1, max_frames: int | None = None) -> World:
    """Open the window and play. `max_frames` stops after that many frames (smoke tests)."""
    content = load_content()
    pygame.init()
    pygame.display.set_caption("Last Bean Standing")
    window = pygame.display.set_mode((CANVAS_W * 2, CANVAS_H * 2), pygame.RESIZABLE)
    renderer = Renderer(content)
    config = WorldConfig.from_content(content)
    world = World(seed, config)
    clock = pygame.time.Clock()
    acc, frames, running, choice = 0.0, 0, True, None
    try:
        while running:
            for event in pygame.event.get():
                if event.type == pygame.QUIT or (event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE):
                    running = False
                elif event.type == pygame.KEYDOWN and event.key == pygame.K_r and world.over:
                    seed += 1
                    world, acc = World(seed, config), 0.0
                elif event.type == pygame.KEYDOWN and world.paused:
                    choice = card_choice(event.key, renderer)
            acc += min(clock.tick(120) / 1000.0, DT * MAX_STEPS_PER_FRAME)
            if world.paused:
                acc = 0.0
                if choice is not None:
                    world.step([PlayerInput(0, choice=choice)])
                    renderer.selected = 0
            else:
                inputs = [read_input(0)]
                while acc >= DT and not world.paused:
                    world.step(inputs)
                    acc -= DT
            choice = None
            renderer.draw(world.snapshot())
            renderer.present(window)
            pygame.display.flip()
            frames += 1
            if max_frames is not None and frames >= max_frames:
                running = False
            await asyncio.sleep(0)
    finally:
        pygame.quit()
    return world
