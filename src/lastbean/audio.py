"""Sound effects, synthesised at start-up in pure Python (own work, no files, no licences).

Each sound is a short envelope over a few oscillators or noise, rendered to 16-bit PCM in the
mixer's format. Sounds react to simulation events; frequent ones are rate-limited.
If no audio device is available (CI, some browsers before a click) everything stays silent.
"""

from __future__ import annotations

import array
import math
import random

import pygame

from .sim import events as ev

VOLUME = 0.35


def _render(rate: int, channels: int, seconds: float, sample) -> bytes:
    """Mono sample function f(t) -> [-1, 1] rendered to interleaved signed 16-bit PCM."""
    n = int(rate * seconds)
    data = array.array("h")
    for i in range(n):
        v = max(-1.0, min(1.0, sample(i / rate)))
        s = int(v * 32767 * VOLUME)
        data.extend([s] * channels)
    return data.tobytes()


def _env(t: float, attack: float, length: float) -> float:
    if t < attack:
        return t / attack
    return max(0.0, 1.0 - (t - attack) / max(1e-6, length - attack)) ** 2


def _square(phase: float) -> float:
    return 1.0 if (phase % 1.0) < 0.5 else -1.0


def _definitions(rng: random.Random) -> dict:
    noise = [rng.uniform(-1, 1) for _ in range(4096)]

    def blip(f0, f1, length, wave="sine"):
        def s(t):
            f = f0 + (f1 - f0) * t / length
            phase = f * t
            osc = math.sin(2 * math.pi * phase) if wave == "sine" else 0.5 * _square(phase)
            return osc * _env(t, 0.003, length)

        return length, s

    def noise_burst(length, lowpass=0.3):
        state = [0.0]

        def s(t):
            raw = noise[int(t * 22050) % len(noise)]
            state[0] += (raw - state[0]) * lowpass
            return state[0] * 1.6 * _env(t, 0.002, length)

        return length, s

    def arpeggio(notes, step):
        length = step * len(notes)

        def s(t):
            k = min(len(notes) - 1, int(t / step))
            return 0.6 * math.sin(2 * math.pi * notes[k] * t) * _env(t - k * step, 0.003, step * 1.4)

        return length, s

    return {
        "shoot": blip(1300, 700, 0.06, "square"),
        "hit": blip(500, 300, 0.04),
        "kill": blip(700, 1400, 0.08),
        "hurt": blip(220, 90, 0.18, "square"),
        "level": arpeggio([523, 659, 784, 1046], 0.07),
        "chest": arpeggio([784, 988, 1175, 1568], 0.06),
        "boss": blip(110, 55, 0.7, "square"),
        "explosion": noise_burst(0.35, 0.25),
        "blocked": noise_burst(0.05, 0.6),
    }


# Minimum frames between two plays of the same sound, so crowds do not turn into noise.
COOLDOWN = {"shoot": 3, "hit": 3, "kill": 3, "blocked": 4, "explosion": 6}


class Audio:
    def __init__(self) -> None:
        self.sounds: dict[str, pygame.mixer.Sound] = {}
        self.muted = False
        self.volume = 1.0  # 0..1, from the settings
        self._last: dict[str, int] = {}
        self._frame = 0
        try:
            if not pygame.mixer.get_init():
                pygame.mixer.init()
            rate, _size, channels = pygame.mixer.get_init()
            for name, (length, sample) in _definitions(random.Random(7)).items():
                self.sounds[name] = pygame.mixer.Sound(buffer=_render(rate, channels, length, sample))
        except (pygame.error, TypeError, ValueError) as exc:
            print("Ton aus:", exc)
            self.sounds = {}

    def play(self, name: str) -> None:
        if self.muted or name not in self.sounds:
            return
        cd = COOLDOWN.get(name, 0)
        if cd and self._frame - self._last.get(name, -cd) < cd:
            return
        self._last[name] = self._frame
        sound = self.sounds[name]
        sound.set_volume(self.volume)
        sound.play()

    def handle(self, events: list) -> None:
        self._frame += 1
        for e in events:
            if isinstance(e, ev.ShotFired):
                self.play("shoot")
            elif isinstance(e, ev.EnemyKilled):
                self.play("kill")
            elif isinstance(e, ev.EnemyHit):
                self.play("hit")
            elif isinstance(e, ev.PlayerHit):
                self.play("hurt")
            elif isinstance(e, ev.LevelUp):
                self.play("level")
            elif isinstance(e, ev.ChestOpened):
                self.play("chest")
            elif isinstance(e, ev.PotBroken):
                self.play("blocked")
            elif isinstance(e, ev.BossSpawned):
                self.play("boss")
            elif isinstance(e, ev.WeaponPulse) or (isinstance(e, ev.HazardActivated) and e.kind == "explosion"):
                self.play("explosion")
            elif isinstance(e, ev.ProjectileBlocked):
                self.play("blocked")
