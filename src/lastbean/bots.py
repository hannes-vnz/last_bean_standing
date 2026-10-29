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
    """Walk into an open gate and go through, dodge hazards and shots, flee when crowded, circle a boss while healthy,
    collect XP when the coast is clear, otherwise stand and shoot.
    Cards: see pick_card (first_card=True in first_card_input for the old baseline)."""
    p = next(p for p in w.players if p.player_id == player_id)
    if p.offer:
        return PlayerInput(player_id, choice=pick_card(w, player_id))
    if p.gate_prompt:  # in the gate: through it (in the last bed: home, the run is won)
        return PlayerInput(player_id, gate=True)
    danger = _danger(w, p)
    if danger is not None:  # poison puddles, warning circles and incoming shots first, like a human would
        return PlayerInput(player_id, *danger)
    if w.gate is not None:  # boss beaten: on to the next garden bed
        return PlayerInput(player_id, _dir(w.gate[0] - p.x, 4), _dir(w.gate[1] - p.y, 4))
    d2 = [((e.x - p.x) ** 2 + (e.y - p.y) ** 2, e) for e in w.enemies]
    crowded = sum(1 for d, _ in d2 if d < 250**2) >= 6
    if crowded and p.ability_cooldown <= 0:
        return PlayerInput(player_id, ability=True)
    nearest = min((d for d, _ in d2), default=float("inf"))
    near = [e for d, e in d2 if d < 120**2]
    boss = next((e for e in w.enemies if e.boss), None)
    if boss is not None and p.hp > 0.35 * p.max_hp and len(near) < 8:
        # Auto-fire aims at the nearest enemy, so close in on the boss, then circle it at a short distance
        # (that also walks out of its rings and dashes), drifting away from the closest pests.
        bx, by = boss.x - p.x, boss.y - p.y
        bd = max(1.0, (bx * bx + by * by) ** 0.5)
        if bd > 170:
            return PlayerInput(player_id, _dir(bx, 8), _dir(by, 8))
        out = 0.6 if bd < 110 else 0.0  # too close: step outwards while circling
        tx, ty = -by / bd - out * bx / bd, bx / bd - out * by / bd
        for e in near:
            d = max(1.0, ((p.x - e.x) ** 2 + (p.y - e.y) ** 2) ** 0.5)
            tx, ty = tx + (p.x - e.x) / d * 0.5, ty + (p.y - e.y) / d * 0.5
        return PlayerInput(player_id, _dir(tx, 0.3), _dir(ty, 0.3))
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


def random_card_input(w: World, player_id: int = 0) -> PlayerInput:
    """A first-time player: moves like heuristic_input but picks cards at random (seeded by the tick)."""
    p = next(p for p in w.players if p.player_id == player_id)
    if p.offer:
        return PlayerInput(player_id, choice=(w.tick * 7 + len(p.upgrades) * 13 + p.level) % len(p.offer))
    return heuristic_input(w, player_id)


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


def _danger(w: World, p) -> tuple[int, int] | None:
    """Step out of hazards (and their warning circles) and sideways out of the path of enemy shots;
    None when nothing threatens. Close enemies and walls push too, so the way out is not into a crowd."""
    vx = vy = 0.0
    threat = False
    for h in w.hazards:
        dx, dy = p.x - h.x, p.y - h.y
        reach = h.spec.radius + 24.0
        d2 = dx * dx + dy * dy
        if d2 < reach * reach:
            d = max(1.0, d2**0.5)
            vx, vy, threat = vx + dx / d * 3, vy + dy / d * 3, True
    for s in w.enemy_shots:
        if s.lobbed:  # lobbed spores land on a marked spot: that spot becomes a hazard to avoid
            dx, dy = p.x - s.tx, p.y - s.ty
            if dx * dx + dy * dy < 60.0**2:
                d = max(1.0, (dx * dx + dy * dy) ** 0.5)
                vx, vy, threat = vx + dx / d * 2, vy + dy / d * 2, True
            continue
        dx, dy = p.x - s.x, p.y - s.y
        if dx * dx + dy * dy > 140.0**2 or dx * s.vx + dy * s.vy <= 0:
            continue  # far away or flying away
        speed2 = s.vx * s.vx + s.vy * s.vy or 1.0
        side = (dx * s.vy - dy * s.vx) / speed2**0.5  # distance of the player from the shot's line
        if abs(side) < 22.0:
            sign = 1.0 if side >= 0 else -1.0
            vx, vy, threat = vx + sign * s.vy / speed2**0.5 * 2, vy - sign * s.vx / speed2**0.5 * 2, True
    if not threat:
        return None
    boss = next((e for e in w.enemies if e.boss), None)
    if boss is not None and p.hp > 0.35 * p.max_hp:  # dodge, but do not lose the boss
        bx, by = boss.x - p.x, boss.y - p.y
        bd = max(1.0, (bx * bx + by * by) ** 0.5)
        if bd > 200:
            vx, vy = vx + bx / bd * 1.5, vy + by / bd * 1.5
    for e in w.enemies:
        dx, dy = p.x - e.x, p.y - e.y
        d2 = dx * dx + dy * dy
        if d2 < 90.0**2:
            d = max(1.0, d2**0.5)
            vx, vy = vx + dx / d, vy + dy / d
    if p.x < 80:
        vx += 2
    elif p.x > w.config.arena_w - 80:
        vx -= 2
    if p.y < 80:
        vy += 2
    elif p.y > w.config.arena_h - 80:
        vy -= 2
    return _dir(vx, 0.3), _dir(vy, 0.3)


def _dir(v: float, dead: float = 0.0) -> int:
    return 1 if v > dead else -1 if v < -dead else 0
