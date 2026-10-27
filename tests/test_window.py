"""Smoke test: the game opens a (dummy) window, renders and steps the simulation."""

import asyncio
import os

import pytest

pygame = pytest.importorskip("pygame")


def test_window_runs_a_few_frames(monkeypatch):
    monkeypatch.setenv("SDL_VIDEODRIVER", "dummy")
    monkeypatch.setenv("SDL_AUDIODRIVER", "dummy")
    from lastbean.app import run

    world = asyncio.run(run(seed=3, max_frames=5))
    assert world.tick >= 0
    assert os.environ["SDL_VIDEODRIVER"] == "dummy"


def test_integer_scale():
    from lastbean.render.renderer import integer_scale

    assert integer_scale(1280, 720) == 2
    assert integer_scale(1920, 1080) == 3
    assert integer_scale(1919, 1080) == 2
    assert integer_scale(300, 200) == 1
