import dataclasses

import pytest

from lastbean.data import load_content
from lastbean.sim import WorldConfig


@pytest.fixture(scope="session")
def content():
    return load_content()


@pytest.fixture
def make_config(content):
    """WorldConfig from the real content, with optional overrides (character stats, stats of every mob)."""

    def make(character: dict | None = None, mob: dict | None = None, **overrides) -> WorldConfig:
        cfg = WorldConfig.from_content(content, **overrides)
        if character:
            cfg = dataclasses.replace(cfg, character=dataclasses.replace(cfg.character, **character))
        if mob:
            cfg = dataclasses.replace(cfg, mobs=tuple(dataclasses.replace(m, **mob) for m in cfg.mobs))
        return cfg

    return make


def with_obstacles(cfg: WorldConfig, obstacles: tuple) -> WorldConfig:
    """The same config with the first garden bed's obstacles replaced (tests want an empty or tiny map)."""
    first = dataclasses.replace(cfg.stages[0], obstacles=obstacles)
    return dataclasses.replace(cfg, stages=(first, *cfg.stages[1:]))
