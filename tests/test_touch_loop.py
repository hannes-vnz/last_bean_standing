"""Touch events through the real game loop (regression: tapping a level-up card did nothing on phones)."""

import asyncio

import pytest

pygame = pytest.importorskip("pygame")


def test_tapping_a_card_picks_it(monkeypatch):
    monkeypatch.setenv("SDL_VIDEODRIVER", "dummy")
    monkeypatch.setenv("SDL_AUDIODRIVER", "dummy")
    from lastbean import app
    from lastbean.meta.profile import MemoryProfileStore

    class LevelledWorld(app.World):
        """Starts with a level-up waiting, so the card choice is open from the first frame."""

        def __post_init__(self):
            super().__post_init__()
            self._gain_xp(self.players[0], self.config.scaling.xp_needed(1) + 0.1, [])

    renderers = []

    class SpyRenderer(app.Renderer):
        def __init__(self, *a, **kw):
            super().__init__(*a, **kw)
            renderers.append(self)

    monkeypatch.setattr(app, "World", LevelledWorld)
    monkeypatch.setattr(app, "Renderer", SpyRenderer)

    real_get = pygame.event.get
    frame = {"n": 0}

    def finger(kind, frac):
        return pygame.event.Event(kind, finger_id=1, touch_id=0, x=frac[0], y=frac[1], dx=0.0, dy=0.0, pressure=1.0)

    def scripted_get(*a, **kw):
        events = list(real_get(*a, **kw))
        frame["n"] += 1
        r = renderers[0] if renderers else None
        if r and r.card_rects and frame["n"] in (6, 8):
            # middle card centre, converted from canvas pixels to the 0..1 window fractions fingers use
            cx, cy = r.card_rects[1].center
            win_w, win_h = pygame.display.get_surface().get_size()
            fx = (r._dest[0] + (cx + 0.5) * r._scale) / win_w
            fy = (r._dest[1] + (cy + 0.5) * r._scale) / win_h
            events.append(finger(pygame.FINGERDOWN if frame["n"] == 6 else pygame.FINGERUP, (fx, fy)))
        return events

    monkeypatch.setattr(pygame.event, "get", scripted_get)
    world = asyncio.run(app.run(seed=3, max_frames=14, store=MemoryProfileStore(), autostart=True))
    p = world.players[0]
    assert sum(p.upgrades.values()) == 1, "the tapped card was not taken"
    assert not world.paused


def test_gate_asks_before_the_next_bed(monkeypatch):
    """Walking into the open gate shows the question in the real loop; only a tap on "Rein!" moves on."""
    monkeypatch.setenv("SDL_VIDEODRIVER", "dummy")
    monkeypatch.setenv("SDL_AUDIODRIVER", "dummy")
    from lastbean import app
    from lastbean.meta.profile import MemoryProfileStore

    class GateWorld(app.World):
        def __post_init__(self):
            super().__post_init__()
            p = self.players[0]
            self.gate, self._gate_ready_tick = (p.x, p.y), 0

    renderers, seen = [], {}

    class SpyRenderer(app.Renderer):
        def __init__(self, *a, **kw):
            super().__init__(*a, **kw)
            renderers.append(self)

    monkeypatch.setattr(app, "World", GateWorld)
    monkeypatch.setattr(app, "Renderer", SpyRenderer)
    real_get = pygame.event.get
    frame = {"n": 0}

    def scripted_get(*a, **kw):
        events = list(real_get(*a, **kw))
        frame["n"] += 1
        r = renderers[0] if renderers else None
        gate = [rect for rect, action in (r.offer_buttons if r else []) if action == "gate_yes"]
        if gate and frame["n"] in (20, 22):
            seen["stage_before"] = seen.get("stage_before", "asked")
            cx, cy = gate[0].center
            win_w, win_h = pygame.display.get_surface().get_size()
            fx = (r._dest[0] + (cx + 0.5) * r._scale) / win_w
            fy = (r._dest[1] + (cy + 0.5) * r._scale) / win_h
            kind = pygame.FINGERDOWN if frame["n"] == 20 else pygame.FINGERUP
            events.append(pygame.event.Event(kind, finger_id=1, touch_id=0, x=fx, y=fy, dx=0.0, dy=0.0, pressure=1.0))
        return events

    monkeypatch.setattr(pygame.event, "get", scripted_get)
    world = asyncio.run(app.run(seed=3, max_frames=26, store=MemoryProfileStore(), autostart=True))
    assert seen.get("stage_before") == "asked", "the gate question never showed up"
    assert world.stage == 1 and not world.paused


def test_ability_button_keeps_the_stick(monkeypatch):
    """A second finger on the ability button must not stop the walking thumb (it used to start a pinch zoom)."""
    from lastbean.ui.touch import TouchState

    t = TouchState()
    t.down(1, 100, 200, steer=True)
    t.move(1, 140, 200)
    t.down(2, 600, 330, steer=False, button=True)
    assert t.direction() == (1, 0)
    t.up(2, 600, 330)
    assert t.direction() == (1, 0)
