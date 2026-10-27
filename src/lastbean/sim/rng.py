"""Deterministic random number generator for the simulation.

Pure integer arithmetic (xoshiro128**), so the sequence is bit-identical on every
platform and Python version. The simulation must never use the `random` module.
"""

from __future__ import annotations

_MASK = 0xFFFFFFFF


def _rotl(x: int, k: int) -> int:
    return ((x << k) | (x >> (32 - k))) & _MASK


def _splitmix32(seed: int):
    state = seed & 0xFFFFFFFFFFFFFFFF
    while True:
        state = (state + 0x9E3779B97F4A7C15) & 0xFFFFFFFFFFFFFFFF
        z = state
        z = ((z ^ (z >> 30)) * 0xBF58476D1CE4E5B9) & 0xFFFFFFFFFFFFFFFF
        z = ((z ^ (z >> 27)) * 0x94D049BB133111EB) & 0xFFFFFFFFFFFFFFFF
        yield (z ^ (z >> 31)) & _MASK


class Rng:
    """xoshiro128** seeded via splitmix64."""

    __slots__ = ("_s",)

    def __init__(self, seed: int) -> None:
        gen = _splitmix32(seed)
        self._s = [next(gen) for _ in range(4)]
        if not any(self._s):
            self._s[0] = 1

    def next_u32(self) -> int:
        s = self._s
        result = (_rotl((s[1] * 5) & _MASK, 7) * 9) & _MASK
        t = (s[1] << 9) & _MASK
        s[2] ^= s[0]
        s[3] ^= s[1]
        s[1] ^= s[2]
        s[0] ^= s[3]
        s[2] ^= t
        s[3] = _rotl(s[3], 11)
        return result

    def random(self) -> float:
        """Float in [0, 1) with 24 bits of precision (exact in binary)."""
        return (self.next_u32() >> 8) / 16777216.0

    def randint(self, lo: int, hi: int) -> int:
        """Integer in [lo, hi], inclusive, without modulo bias."""
        if hi < lo:
            raise ValueError("hi < lo")
        span = hi - lo + 1
        limit = (1 << 32) - ((1 << 32) % span)
        while True:
            x = self.next_u32()
            if x < limit:
                return lo + x % span

    def uniform(self, lo: float, hi: float) -> float:
        return lo + (hi - lo) * self.random()

    def choice(self, seq):
        return seq[self.randint(0, len(seq) - 1)]

    def getstate(self) -> tuple[int, int, int, int]:
        return tuple(self._s)  # type: ignore[return-value]

    def setstate(self, state: tuple[int, int, int, int]) -> None:
        self._s = list(state)
