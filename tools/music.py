"""Background music: one chiptune loop per garden bed and one for bosses and the flood (own work).

Pure Python synthesis (square lead, triangle bass, chord arpeggio, noise drums), written as WAV
and encoded to OGG Vorbis with ffmpeg (assets/music/*.ogg). The game only loads the OGG files.

    python tools/music.py
"""

from __future__ import annotations

import array
import math
import random
import subprocess
import tempfile
import wave
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "assets" / "music"
RATE = 22050

NOTE = {n: i for i, n in enumerate(["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"])}


def freq(name: str, octave: int) -> float:
    return 440.0 * 2 ** ((NOTE[name] + 12 * (octave - 4) - 9) / 12)


# Each track: tempo, scale (semitones over the root), chords (scale degrees), feel.
TRACKS = {
    "seedbed": dict(bpm=124, root="C", minor=False, chords=[0, 4, 5, 3], seed=11, lead_oct=5, swing=0.0, drums="light"),
    "veggiebed": dict(
        bpm=136, root="F", minor=False, chords=[0, 5, 3, 4], seed=23, lead_oct=5, swing=0.12, drums="bouncy"
    ),
    "compost": dict(bpm=128, root="A", minor=True, chords=[0, 5, 2, 6], seed=37, lead_oct=4, swing=0.0, drums="heavy"),
    "boss": dict(bpm=150, root="D", minor=True, chords=[0, 0, 5, 6], seed=41, lead_oct=5, swing=0.0, drums="drive"),
}
MAJOR = [0, 2, 4, 5, 7, 9, 11]
MINOR = [0, 2, 3, 5, 7, 8, 10]


def compose(spec: dict) -> list[tuple[float, float, float, str, float]]:
    """Notes as (start beat, length in beats, frequency, voice, volume) for a 16-bar loop."""
    rng = random.Random(spec["seed"])
    scale = MINOR if spec["minor"] else MAJOR
    root = NOTE[spec["root"]]

    def pitch(degree: int, octave: int) -> float:
        o, d = divmod(degree, 7)
        semis = root + scale[d] + 12 * (octave + o - 4) - 9
        return 440.0 * 2 ** (semis / 12)

    notes = []
    # Phrases: A A B A, each 4 bars, one chord per bar.
    phrase_a, phrase_b = _melody(rng), _melody(rng)
    for part, phrase in enumerate([phrase_a, phrase_a, phrase_b, phrase_a]):
        for bar in range(4):
            chord = spec["chords"][bar]
            start = (part * 4 + bar) * 4.0
            for k in range(8):  # bass: eighths on root and fifth
                deg = chord if k % 4 != 2 else chord + 4
                notes.append((start + k * 0.5, 0.45, pitch(deg, 2), "tri", 0.55))
            for k in range(16):  # soft arpeggio of the chord tones
                deg = chord + (0, 2, 4, 7)[k % 4]
                notes.append((start + k * 0.25, 0.2, pitch(deg, 4), "pulse", 0.10))
            for beat, length, step in phrase[bar]:  # lead
                if step is not None:
                    notes.append((start + beat, length, pitch(chord + step, spec["lead_oct"]), "square", 0.22))
    return notes


def _melody(rng: random.Random) -> list[list[tuple[float, float, int | None]]]:
    """Four bars of (beat, length, step above the chord root); steps favour chord tones."""
    bars = []
    rhythms = [
        [(0, 1), (1, 0.5), (1.5, 0.5), (2, 1), (3, 1)],
        [(0, 0.5), (0.5, 0.5), (1, 1), (2, 1.5), (3.5, 0.5)],
        [(0, 1.5), (1.5, 0.5), (2, 0.5), (2.5, 0.5), (3, 1)],
        [(0, 2), (2, 1), (3, 1)],
    ]
    step = 4
    for b in range(4):
        rhythm = rhythms[rng.randrange(len(rhythms))] if b < 3 else rhythms[3]
        notes = []
        for beat, length in rhythm:
            step = max(0, min(9, step + rng.choice([-2, -1, -1, 0, 1, 1, 2])))
            if rng.random() < 0.55:  # land on a chord tone
                step = min((0, 2, 4, 7, 9), key=lambda c: abs(c - step))
            notes.append((beat, length, None if rng.random() < 0.08 else step))
        bars.append(notes)
    return bars


def drums(kind: str, beats: int) -> list[tuple[float, str, float]]:
    """(beat, sound, volume): kick, snare, hat."""
    out = []
    for b in range(beats):
        bar_beat = b % 4
        if kind == "light":
            if bar_beat in (0, 2):
                out.append((b, "kick", 0.45))
            out.append((b + 0.5, "hat", 0.10))
            if bar_beat == 3:
                out.append((b, "snare", 0.25))
        elif kind == "bouncy":
            out.append((b, "kick", 0.4 if bar_beat in (0, 2) else 0.0))
            if bar_beat in (1, 3):
                out.append((b, "snare", 0.3))
            out += [(b + 0.5, "hat", 0.12), (b + 0.75, "hat", 0.06)]
        elif kind == "heavy":
            if bar_beat in (0, 2) or (bar_beat == 3 and b % 8 == 7):
                out.append((b, "kick", 0.55))
            if bar_beat in (1, 3):
                out.append((b, "snare", 0.32))
            out.append((b + 0.5, "hat", 0.08))
        else:  # drive
            out.append((b, "kick", 0.5))
            out.append((b + 0.5, "kick", 0.25))
            if bar_beat in (1, 3):
                out.append((b, "snare", 0.35))
            out += [(b + 0.25, "hat", 0.08), (b + 0.75, "hat", 0.08)]
    return [d for d in out if d[2] > 0]


def render(spec: dict) -> array.array:
    beat_s = 60.0 / spec["bpm"]
    beats = 64
    n = int(beats * beat_s * RATE)
    buf = [0.0] * n
    swing = spec["swing"]

    def at(beat: float) -> int:
        frac = beat % 1.0
        if swing and abs(frac - 0.5) < 1e-6:
            beat += swing / 2
        return int(beat * beat_s * RATE)

    for start, length, f, voice, vol in compose(spec):
        i0, count = at(start), int(length * beat_s * RATE)
        for i in range(count):
            t = i / RATE
            ph = (f * t) % 1.0
            if voice == "square":
                v = 1.0 if ph < 0.5 else -1.0
                env = min(1.0, t / 0.005) * max(0.0, 1.0 - t / (length * beat_s)) ** 0.6
                v *= 1.0 + 0.004 * math.sin(2 * math.pi * 5.5 * t)  # a little vibrato in the level
            elif voice == "pulse":
                v = 1.0 if ph < 0.25 else -1.0
                env = max(0.0, 1.0 - t / (length * beat_s)) ** 2
            else:  # triangle
                v = 4 * abs(ph - 0.5) - 1
                env = min(1.0, t / 0.004) * max(0.0, 1.0 - t / (length * beat_s)) ** 0.5
            j = (i0 + i) % n
            buf[j] += v * env * vol
    noise = random.Random(5)
    for beat, kind, vol in drums(spec["drums"], beats):
        i0 = at(beat)
        if kind == "kick":
            dur = 0.18
            for i in range(int(dur * RATE)):
                t = i / RATE
                f = 120 * (1 - t / dur) + 40
                buf[(i0 + i) % n] += math.sin(2 * math.pi * f * t) * (1 - t / dur) ** 2 * vol
        else:
            dur = 0.14 if kind == "snare" else 0.04
            low = 0.0
            for i in range(int(dur * RATE)):
                t = i / RATE
                raw = noise.uniform(-1, 1)
                low += (raw - low) * (0.5 if kind == "snare" else 0.9)
                buf[(i0 + i) % n] += low * (1 - t / dur) ** 2 * vol
    peak = max(1e-6, max(abs(x) for x in buf))
    gain = 0.8 / peak
    return array.array("h", (int(max(-1.0, min(1.0, x * gain)) * 32767) for x in buf))


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    for name, spec in TRACKS.items():
        pcm = render(spec)
        with tempfile.TemporaryDirectory() as tmp:
            wav = Path(tmp) / f"{name}.wav"
            with wave.open(str(wav), "wb") as w:
                w.setnchannels(1)
                w.setsampwidth(2)
                w.setframerate(RATE)
                w.writeframes(pcm.tobytes())
            ogg = OUT / f"{name}.ogg"
            subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(wav), "-c:a", "libvorbis", "-q:a", "3",
                            str(ogg)], check=True)  # fmt: skip
        print(f"{ogg.relative_to(ROOT)}: {len(pcm) / RATE:.1f} s, {ogg.stat().st_size // 1024} KB")


if __name__ == "__main__":
    main()
