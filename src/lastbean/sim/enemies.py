"""Enemy behaviours, elite affixes and boss patterns.

`behavior` in mobs.json selects a movement/attack function here. A new mob that reuses an
existing behaviour needs only a JSON entry; a new behaviour needs one function plus an entry
in `BEHAVIORS`. Unspecified numbers live in `tuning.py`.
"""

from __future__ import annotations

import math
from typing import TYPE_CHECKING

from .entities import Enemy, EnemyShot, HazardSpec
from .events import BossPhase, EnemyShotFired, Event
from .tuning import (
    ARMORED_DAMAGE_MULT,
    GRIP_DELAY_S,
    GRIP_DURATION_S,
    GRIP_INTERVAL_S,
    GRIP_RADIUS,
    GRIP_SLOW_PCT,
    GRIP_SUMMONS,
    POISON_DURATION_S,
    POISON_RADIUS,
    RANGED_BACKOFF,
    RANGED_FIRE_REACH,
    REGEN_PCT_PER_S,
    RING_INTERVAL_FAST_S,
    RING_INTERVAL_S,
    RING_SHOTS,
    SHIELD_PCT,
    SHIELD_RECHARGE_S,
    SPORE_RAIN_COUNT,
    SPORE_RAIN_INTERVAL_S,
    SPORE_RAIN_SPREAD,
    SPORE_SPEED,
    SWARM_WOBBLE,
    SWIFT_SPEED_MULT,
    THORN_RANGE,
    THORN_SPEED,
)

if TYPE_CHECKING:
    from .world import World

DT = 1.0 / 60

# Unit vectors in 22.5 degree steps as literals (no trigonometry at runtime, bit-identical everywhere).
_C, _S, _H = 0.9238795325112867, 0.3826834323650898, 0.7071067811865476
COMPASS_16 = (
    (1.0, 0.0), (_C, _S), (_H, _H), (_S, _C), (0.0, 1.0), (-_S, _C), (-_H, _H), (-_C, _S),
    (-1.0, 0.0), (-_C, -_S), (-_H, -_H), (-_S, -_C), (0.0, -1.0), (_S, -_C), (_H, -_H), (_C, -_S),
)  # fmt: skip


def move_towards(e: Enemy, tx: float, ty: float, d: float, speed: float) -> None:
    if d > 1e-9:
        step = min(speed * DT, d)
        e.x += (tx - e.x) / d * step
        e.y += (ty - e.y) / d * step


def chaser(w: World, e: Enemy, tx: float, ty: float, d: float, events: list[Event]) -> None:
    move_towards(e, tx, ty, d, e.speed)


def swarm(w: World, e: Enemy, tx: float, ty: float, d: float, events: list[Event]) -> None:
    """Forward plus a sideways triangle-wave flutter, each bat with its own phase."""
    if d <= 1e-9:
        return
    fx, fy = (tx - e.x) / d, (ty - e.y) / d
    t = (w.tick + e.eid * 17) % 40
    wobble = (t / 10.0 - 1.0) if t < 20 else (3.0 - t / 10.0)
    step = e.speed * DT
    e.x += (fx - fy * wobble * SWARM_WOBBLE) * step
    e.y += (fy + fx * wobble * SWARM_WOBBLE) * step


def ranged_lobbed(w: World, e: Enemy, tx: float, ty: float, d: float, events: list[Event]) -> None:
    """Keep `keep_distance` and lob a spore at the player that leaves a poison puddle."""
    keep = e.keep_distance
    if d > keep:
        move_towards(e, tx, ty, d, e.speed)
    elif d < keep * RANGED_BACKOFF and d > 1e-9:
        move_towards(e, 2 * e.x - tx, 2 * e.y - ty, d, e.speed)
    e.timer -= DT
    if e.timer <= 0 and d <= keep * RANGED_FIRE_REACH:
        e.timer = e.shot_interval
        lob_spore(w, e, tx, ty, events)


def lob_spore(w: World, e: Enemy, tx: float, ty: float, events: list[Event]) -> None:
    dx, dy = tx - e.x, ty - e.y
    d = math.sqrt(dx * dx + dy * dy)
    ticks = max(1, int(d / SPORE_SPEED * 60 + 0.5))
    poison = HazardSpec("poison", POISON_RADIUS, duration=POISON_DURATION_S, dps=e.damage)
    w.enemy_shots.append(EnemyShot(e.x, e.y, dx / ticks * 60, dy / ticks * 60, 0.0, ticks, e.eid, True, tx, ty, poison))
    events.append(EnemyShotFired(w.tick, None, e.eid, e.x, e.y, True))


def boss_ildra(w: World, e: Enemy, tx: float, ty: float, d: float, events: list[Event]) -> None:
    """Thorn queen. Phase 0: rotating thorn ring. Phase 1 (60 %): root grip zones and 3 root guards.
    Phase 2 (30 %): ring twice as fast plus spore rain around the player."""
    move_towards(e, tx, ty, d, e.speed)
    boss = w.boss_stats[e.boss]
    pct = 100.0 * e.hp / e.max_hp
    phase = sum(1 for th in boss.phase_thresholds[1:] if pct <= th)
    if not e.timers:
        e.timers = [RING_INTERVAL_S, GRIP_DELAY_S, SPORE_RAIN_INTERVAL_S]
    if phase > e.phase:
        e.phase = phase
        events.append(BossPhase(w.tick, None, e.eid, e.boss, phase))
        if phase == 1:
            w.summon_around(e, "rootguard", GRIP_SUMMONS, events)
        if phase == 2:
            e.timers[0] = min(e.timers[0], RING_INTERVAL_FAST_S)
    e.timers = [t - DT for t in e.timers]
    if e.timers[0] <= 0:
        e.timers[0] = RING_INTERVAL_FAST_S if e.phase >= 2 else RING_INTERVAL_S
        thorn_ring(w, e, events)
    if e.phase >= 1 and e.timers[1] <= 0:
        e.timers[1] = GRIP_INTERVAL_S
        grip = HazardSpec("grip", GRIP_RADIUS, delay=GRIP_DELAY_S, duration=GRIP_DURATION_S, slow_pct=GRIP_SLOW_PCT)
        w.add_hazard(grip, tx, ty, e.eid)
    if e.phase >= 2 and e.timers[2] <= 0:
        e.timers[2] = SPORE_RAIN_INTERVAL_S
        for _ in range(SPORE_RAIN_COUNT):
            ox, oy = w.random_offset(SPORE_RAIN_SPREAD)
            lob_spore(w, e, tx + ox, ty + oy, events)


def thorn_ring(w: World, e: Enemy, events: list[Event]) -> None:
    """RING_SHOTS thorns evenly around the boss; every second volley is turned by half a step."""
    step = len(COMPASS_16) // RING_SHOTS
    offset = (step // 2) * (e.volley % 2)
    e.volley += 1
    life = int(THORN_RANGE / THORN_SPEED * 60)
    for k in range(RING_SHOTS):
        dx, dy = COMPASS_16[(k * step + offset) % len(COMPASS_16)]
        w.enemy_shots.append(EnemyShot(e.x, e.y, dx * THORN_SPEED, dy * THORN_SPEED, e.damage, life, e.eid))
    events.append(EnemyShotFired(w.tick, None, e.eid, e.x, e.y, False))


BEHAVIORS = {
    "chaser": chaser,
    "chaser_tank": chaser,  # knockback does not exist yet, so the tank only differs by its numbers
    "swarm": swarm,
    "ranged_lobbed": ranged_lobbed,
}
BOSS_BEHAVIORS = {"ildra": boss_ildra}


# ---------------------------------------------------------------------------- elite affixes


def apply_affixes(e: Enemy) -> None:
    """One-off effects at spawn (speed, shield). Ongoing ones run in `tick_affixes` / `damage_enemy`."""
    if "swift" in e.affixes:
        e.speed *= SWIFT_SPEED_MULT
    if "shielded" in e.affixes:
        e.shield = e.shield_max = e.max_hp * SHIELD_PCT / 100.0


def tick_affixes(e: Enemy) -> None:
    e.since_hit += DT
    if "regenerating" in e.affixes:
        e.hp = min(e.max_hp, e.hp + e.max_hp * REGEN_PCT_PER_S / 100.0 * DT)
    if e.shield_max and e.since_hit >= SHIELD_RECHARGE_S:
        e.shield = e.shield_max


def damage_enemy(e: Enemy, amount: float) -> float:
    """Apply damage through armour and shield. Returns the HP actually lost."""
    e.since_hit = 0.0
    if "armored" in e.affixes:
        amount *= ARMORED_DAMAGE_MULT
    if e.shield > 0:
        absorbed = min(e.shield, amount)
        e.shield -= absorbed
        amount -= absorbed
    e.hp -= amount
    return amount
