"""Scripted players for tests, balancing runs and as a baseline for the RL agent (M7). No pygame."""

from __future__ import annotations

from .sim import PlayerInput, World


def heuristic_input(w: World, player_id: int = 0) -> PlayerInput:
    """Flee when crowded, collect XP when the coast is clear, otherwise stand and shoot. Always takes card 0."""
    p = next(p for p in w.players if p.player_id == player_id)
    if p.offer:
        return PlayerInput(player_id, choice=0)
    d2 = [((e.x - p.x) ** 2 + (e.y - p.y) ** 2, e) for e in w.enemies]
    nearest = min((d for d, _ in d2), default=float("inf"))
    near = [e for d, e in d2 if d < 120**2]
    if near:  # flee from the centre of mass of close enemies, away from walls
        cx, cy = sum(e.x for e in near) / len(near), sum(e.y for e in near) / len(near)
        mx, my = _dir(p.x - cx), _dir(p.y - cy)
        if p.x < 100 or p.x > w.config.arena_w - 100:
            mx = _dir(w.config.arena_w / 2 - p.x)
        if p.y < 100 or p.y > w.config.arena_h - 100:
            my = _dir(w.config.arena_h / 2 - p.y)
        return PlayerInput(player_id, mx, my)
    if w.orbs and nearest > 220**2:
        o = min(w.orbs, key=lambda o: (o.x - p.x) ** 2 + (o.y - p.y) ** 2)
        if (o.x - p.x) ** 2 + (o.y - p.y) ** 2 < 400**2:
            return PlayerInput(player_id, _dir(o.x - p.x, 8), _dir(o.y - p.y, 8))
    return PlayerInput(player_id)


def _dir(v: float, dead: float = 0.0) -> int:
    return 1 if v > dead else -1 if v < -dead else 0
