"""Smoke test: the game opens a (dummy) window, renders and steps the simulation."""

import asyncio
import os

import pytest

pygame = pytest.importorskip("pygame")


def test_window_runs_a_few_frames(monkeypatch):
    monkeypatch.setenv("SDL_VIDEODRIVER", "dummy")
    monkeypatch.setenv("SDL_AUDIODRIVER", "dummy")
    from lastbean.app import run
    from lastbean.meta.profile import MemoryProfileStore

    world = asyncio.run(run(seed=3, max_frames=5, store=MemoryProfileStore(), autostart=True))
    assert world.tick >= 0
    assert os.environ["SDL_VIDEODRIVER"] == "dummy"


def test_integer_scale():
    from lastbean.render.renderer import integer_scale

    assert integer_scale(1280, 720) == 2
    assert integer_scale(1920, 1080) == 3
    assert integer_scale(1919, 1080) == 2
    assert integer_scale(300, 200) == 1


def test_screens_render(monkeypatch, content):
    """Menu, name entry and results draw without errors (smoke test of the UI layer)."""
    monkeypatch.setenv("SDL_VIDEODRIVER", "dummy")
    pygame.init()
    from lastbean.meta.profile import new_profile, record_run
    from lastbean.render.renderer import Renderer
    from lastbean.ui import screens

    r = Renderer(content)
    profile = new_profile()
    screens.draw_menu(r, profile, web=True)
    screens.draw_name_entry(r, "Bo", True, first_time=True)
    result = dict(score=1234, seconds=200, kills=150, level=6, bosses=0, wave=6, character="ranger", seed=1)
    flags = record_run(profile, result)
    screens.draw_results(r, result, flags, profile)
    screens.draw_menu(r, profile, web=False)
