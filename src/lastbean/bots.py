"""Scripted players for tests, balancing runs and as a baseline for the RL agent (M7). No pygame."""

from __future__ import annotations

from .sim import PlayerInput, World
from .sim.upgrades import RARITIES
from .sim.weapons import WEAPON_PREFIX

# How much the bot likes a card by its tags. Measured 28.10.2026 (tools/balance.py): the bot dies of the
# damage it takes, not for lack of damage, so survival comes first; extra weapons add +50-150 % damage
# per second (tools: weapon DPS probe), one of them is worth it, more levels of it less so.
TAG_VALUE = {"defense": 70, "damage": 50, "projectile": 45, "area": 45, "crit": 40, "elemental": 40, "pierce": 40,
             "bounce": 35, "speed": 35, "fire": 35, "frost": 35, "poison": 35, "lightning": 35, "range": 25,
             "thorns": 30, "stillness": 20, "control": 25, "movement": 25, "utility": 15}  # fmt: skip


def heuristic_input(w: World, player_id: int = 0) -> PlayerInput:
    """Walk into an open gate, flee when crowded, close in on a boss while healthy, collect XP when the coast
    is clear, otherwise stand and shoot.
    Cards: see pick_card (first_card=True in first_card_input for the old baseline)."""
    p = next(p for p in w.players if p.player_id == player_id)
    if p.offer:
        return PlayerInput(player_id, choice=pick_card(w, player_id))
    if w.gate is not None:  # boss beaten: on to the next garden bed
        return PlayerInput(player_id, _dir(w.gate[0] - p.x, 4), _dir(w.gate[1] - p.y, 4))
    d2 = [((e.x - p.x) ** 2 + (e.y - p.y) ** 2, e) for e in w.enemies]
    crowded = sum(1 for d, _ in d2 if d < 250**2) >= 6
    if crowded and p.ability_cooldown <= 0:
        return PlayerInput(player_id, ability=True)
    nearest = min((d for d, _ in d2), default=float("inf"))
    near = [e for d, e in d2 if d < 120**2]
    boss = next((e for e in w.enemies if e.boss), None)
    if boss is not None and p.hp > 0.4 * p.max_hp and len(near) < 4:
        # Auto-fire aims at the nearest enemy, so close in on the boss (but keep a little distance).
        bd = ((boss.x - p.x) ** 2 + (boss.y - p.y) ** 2) ** 0.5
        if bd > 180:
            return PlayerInput(player_id, _dir(boss.x - p.x, 8), _dir(boss.y - p.y, 8))
    if near:  # flee from the centre of mass of close enemies, away from walls
        cx, cy = sum(e.x for e in near) / len(near), sum(e.y for e in near) / len(near)
        mx, my = _dir(p.x - cx), _dir(p.y - cy)
        if p.x < 100 or p.x > w.config.arena_w - 100:
            mx = _dir(w.config.arena_w / 2 - p.x)
        if p.y < 100 or p.y > w.config.arena_h - 100:
            my = _dir(w.config.arena_h / 2 - p.y)
        return PlayerInput(player_id, mx, my)
    if nearest > 260**2:  # quiet moment: buy a chest we can afford, or smash a pot on the way
        target = None
        if w.config.economy is not None:
            price = w.config.economy.chest_price(w.chests_opened)
            options = [(c.x, c.y) for c in w.chests if c.kind != "map" or p.seeds >= price]
            options += [(pot.x, pot.y) for pot in w.pots]
            near_targets = [t for t in options if (t[0] - p.x) ** 2 + (t[1] - p.y) ** 2 < 500**2]
            if near_targets:
                target = min(near_targets, key=lambda t: (t[0] - p.x) ** 2 + (t[1] - p.y) ** 2)
        if target is not None:
            return PlayerInput(player_id, _dir(target[0] - p.x, 8), _dir(target[1] - p.y, 8))
    if w.orbs and nearest > 220**2:
        o = min(w.orbs, key=lambda o: (o.x - p.x) ** 2 + (o.y - p.y) ** 2)
        if (o.x - p.x) ** 2 + (o.y - p.y) ** 2 < 400**2:
            return PlayerInput(player_id, _dir(o.x - p.x, 8), _dir(o.y - p.y, 8))
    return PlayerInput(player_id)


def first_card_input(w: World, player_id: int = 0) -> PlayerInput:
    """The old baseline: like heuristic_input, but always takes the first card."""
    p = next(p for p in w.players if p.player_id == player_id)
    return PlayerInput(player_id, choice=0) if p.offer else heuristic_input(w, player_id)


def pick_card(w: World, player_id: int = 0) -> int:
    """A simple build plan: fill the weapon slots, then raise owned weapons and damage, rarer cards first."""
    p = next(p for p in w.players if p.player_id == player_id)
    defs = {u.id: u for u in w.config.upgrades}
    owned_weapons = {st.weapon for st in p.weapons}
    free_slot = len(p.weapons) < w.config.weapon_slots - 1

    def score(i: int) -> float:
        uid = p.offer[i]
        tier = p.offer_tiers[i] if i < len(p.offer_tiers) else "common"
        value = 15.0 * RARITIES.index(tier) if tier in RARITIES else 0.0
        if uid.startswith(WEAPON_PREFIX):
            wid = uid[len(WEAPON_PREFIX) :]
            if wid in owned_weapons:
                return value + 40.0
            return value + (100.0 if not owned_weapons else 30.0 if free_slot else 0.0)
        u = defs.get(uid)
        if u is None:
            return value
        base = max((TAG_VALUE.get(t, 10) for t in u.tags), default=10)
        return value + base + 5.0 * p.upgrades.get(uid, 0)  # stacking pays off

    return max(range(len(p.offer)), key=score)


def _dir(v: float, dead: float = 0.0) -> int:
    return 1 if v > dead else -1 if v < -dead else 0
