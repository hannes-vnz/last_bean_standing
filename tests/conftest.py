import dataclasses

import pytest

from lastbean.data import load_content
from lastbean.sim import WorldConfig


@pytest.fixture(scope="session")
def content():
    return load_content()


@pytest.fixture
def make_config(content):
    """WorldConfig from the real content, with optional overrides (also for character/mob stats)."""

    def make(character: dict | None = None, mob: dict | None = None, **overrides) -> WorldConfig:
        cfg = WorldConfig.from_content(content, **overrides)
        if character:
            cfg = dataclasses.replace(cfg, character=dataclasses.replace(cfg.character, **character))
        if mob:
            cfg = dataclasses.replace(cfg, mob=dataclasses.replace(cfg.mob, **mob))
        return cfg

    return make
