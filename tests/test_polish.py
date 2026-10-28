"""Sprites, effects and sound: they load, react to events and never touch the simulation."""

import pytest

pygame = pytest.importorskip("pygame")


@pytest.fixture(autouse=True)
def headless(monkeypatch):
    monkeypatch.setenv("SDL_VIDEODRIVER", "dummy")
    monkeypatch.setenv("SDL_AUDIODRIVER", "dummy")
    pygame.init()
    pygame.display.set_mode((1, 1))


def test_sprites_for_every_mob_and_boss(content):
    from lastbean.render.sprites import SpriteBank

    bank = SpriteBank()
    for name in ["ranger", *(m.id for m in content.mobs), *(b.id for b in content.bosses)]:
        img = bank.get(name)
        assert img is not None and img.get_width() >= 10, name
    big = bank.get("mold", 1.35)
    assert big.get_width() == round(16 * 1.35)
    white = bank.get("mold", flash=True)
    xs = [white.get_at((x, y)) for x in range(16) for y in range(16)]
    assert all(c[:3] == (255, 255, 255) for c in xs if c[3] > 0)  # flash is a white silhouette
    assert bank.get("does_not_exist") is None


def test_effects_react_to_events_without_touching_the_world(content, make_config):
    from lastbean.bots import heuristic_input
    from lastbean.render.effects import Effects
    from lastbean.render.renderer import Renderer, effect_palette
    from lastbean.sim import World

    r = Renderer(content)
    fx = Effects(*effect_palette(r))
    with_fx = World(4, make_config())
    without = World(4, make_config())
    seen = False
    for _ in range(90 * 60):
        events = with_fx.step([heuristic_input(with_fx)])
        without.step([heuristic_input(without)])
        fx.handle(events, r.boss_names, {p.player_id: (p.x, p.y) for p in with_fx.players})
        fx.update()
        seen = seen or bool(fx.particles or fx.texts or fx.rings)
        if with_fx.tick % 600 == 0:
            r.draw(with_fx.snapshot(), effects=fx)
    assert with_fx.state_hash() == without.state_hash()  # effects never change the run
    assert seen  # (the run may already be over at the end)
    assert len(fx.particles) <= 2000


def test_effect_details(content):
    from lastbean.render.effects import Effects
    from lastbean.render.renderer import Renderer, effect_palette
    from lastbean.sim import BossSpawned, EnemyHit, EnemyKilled, LevelUp, PlayerHit

    fx = Effects(*effect_palette(Renderer(content)))
    fx.handle([EnemyHit(1, 0, 5, 100.0, 100.0, 18.0, True)])
    assert fx.flash[5] == 2 and fx.hitstop == 2 and fx.texts[0].big and fx.texts[0].text == "18"
    fx.handle([EnemyKilled(1, 0, 5, "slimeling", 100.0, 100.0), PlayerHit(1, 0, 5.0, 95.0)])
    assert fx.trauma > 0 and fx.shake(6) != (0, 0) or fx.trauma < 0.3
    fx.handle([LevelUp(1, 0, 2)], players={0: (10.0, 10.0)})
    assert fx.rings
    fx.handle([BossSpawned(1, None, 9, "ildra")], boss_names={"ildra": "Ildra"})
    assert fx.banner[0] == "Ildra erscheint!"
    for _ in range(200):
        fx.update()
    assert not fx.flash and fx.banner is None and fx.trauma == 0.0


def test_audio_synthesises_all_sounds():
    from lastbean.audio import Audio
    from lastbean.sim import ShotFired

    a = Audio()
    if not a.sounds:
        pytest.skip("no audio device in this environment")
    assert {"shoot", "hit", "kill", "hurt", "level", "chest", "boss", "explosion"} <= set(a.sounds)
    a.handle([ShotFired(1, 0, 0.0, 0.0, 1.0, 0.0)] * 10)  # rate-limited, must not raise
    a.muted = True
    a.play("boss")
