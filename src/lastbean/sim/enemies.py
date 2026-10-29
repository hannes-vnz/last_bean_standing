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
    BEETLE_AIM_S,
    BEETLE_DASH_INTERVAL_S,
    BEETLE_DASH_S,
    BEETLE_DASH_SPEED,
    BEETLE_DAZE_S,
    BEETLE_FAN_DEG,
    BEETLE_FAN_INTERVAL_S,
    BEETLE_SUMMONS,
    CHARGE_START_DISTANCE,
    EXPLODER_FUSE_S,
    EXPLODER_TRIGGER,
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
    REAPER_DASH_INTERVAL_S,
    REAPER_RAIN_COUNT,
    REAPER_RAIN_DELAY_S,
    REAPER_RAIN_INTERVAL_S,
    REAPER_RAIN_RADIUS,
    REAPER_RAIN_SPREAD,
    REAPER_RING_INTERVAL_S,
    REAPER_RING_SHOTS,
    REAPER_SUMMONS,
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
from .weapons import TAU, cos_sin, fan_directions

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


def speed_of(e: Enemy) -> float:
    """Current speed: chilled enemies are slower (player hits with "Kälte")."""
    return e.speed * (1.0 - e.chill_pct / 100.0) if e.chill_t > 0 else e.speed


def chaser(w: World, e: Enemy, tx: float, ty: float, d: float, events: list[Event]) -> None:
    move_towards(e, tx, ty, d, speed_of(e))


def charger(w: World, e: Enemy, tx: float, ty: float, d: float, events: list[Event]) -> None:
    """Walk closer, aim (warning line), dash in a straight line, then stand dazed."""
    m = w.mob_stats(e.kind)
    if e.charge_state == 0:
        move_towards(e, tx, ty, d, speed_of(e))
        if d < CHARGE_START_DISTANCE and m is not None:
            start_aim(e, tx, ty, d, m.telegraph_s)
        return
    dash(e, tx, ty, d, m.charge_s, m.charge_speed, m.recovery_s)


def start_aim(e: Enemy, tx: float, ty: float, d: float, aim_s: float) -> None:
    e.charge_state, e.charge_t = 1, aim_s
    if d > 1e-9:
        e.cdx, e.cdy = (tx - e.x) / d, (ty - e.y) / d


def dash(e: Enemy, tx: float, ty: float, d: float, charge_s: float, speed: float, recovery_s: float) -> bool:
    """Advance an aim/dash/daze cycle. Returns True when the cycle is over (back to walking)."""
    e.charge_t -= DT
    if e.charge_state == 1:
        if d > 1e-9:  # keep tracking while aiming, the line follows the target until the dash starts
            e.cdx, e.cdy = (tx - e.x) / d, (ty - e.y) / d
        if e.charge_t <= 0:
            e.charge_state, e.charge_t = 2, charge_s
    elif e.charge_state == 2:
        e.x += e.cdx * speed * DT
        e.y += e.cdy * speed * DT
        if e.charge_t <= 0:
            e.charge_state, e.charge_t = 3, recovery_s
    elif e.charge_state == 3 and e.charge_t <= 0:
        e.charge_state = 0
        return True
    return False


def exploder(w: World, e: Enemy, tx: float, ty: float, d: float, events: list[Event]) -> None:
    """Rolls at the player; on contact it stops, warns briefly and bursts (no reward, it destroyed itself)."""
    m = w.mob_stats(e.kind)
    if e.charge_state == 0:
        move_towards(e, tx, ty, d, speed_of(e))
        if d <= e.radius + w.player_radius + EXPLODER_TRIGGER and m is not None:
            e.charge_state = 1
            spec = HazardSpec("explosion", m.explosion_radius, delay=EXPLODER_FUSE_S, burst=e.damage)
            w.add_hazard(spec, e.x, e.y, e.eid)
            w.despawn(e)


def ranged_direct(w: World, e: Enemy, tx: float, ty: float, d: float, events: list[Event]) -> None:
    """Keep `keep_distance` and shoot straight at the player (trees stop the shot)."""
    keep = e.keep_distance
    if d > keep:
        move_towards(e, tx, ty, d, speed_of(e))
    elif d < keep * RANGED_BACKOFF and d > 1e-9:
        move_towards(e, 2 * e.x - tx, 2 * e.y - ty, d, speed_of(e))
    e.timer -= DT
    if e.timer <= 0 and d <= keep * RANGED_FIRE_REACH and d > 1e-9:
        e.timer = e.shot_interval
        m = w.mob_stats(e.kind)
        speed = m.projectile_speed if m and m.projectile_speed else THORN_SPEED
        life = int(keep * RANGED_FIRE_REACH * 1.5 / speed * 60)
        w.enemy_shots.append(EnemyShot(e.x, e.y, (tx - e.x) / d * speed, (ty - e.y) / d * speed, e.damage, life, e.eid))
        events.append(EnemyShotFired(w.tick, None, e.eid, e.x, e.y, False))


def swarm(w: World, e: Enemy, tx: float, ty: float, d: float, events: list[Event]) -> None:
    """Forward plus a sideways triangle-wave flutter, each one with its own phase."""
    if d <= 1e-9:
        return
    fx, fy = (tx - e.x) / d, (ty - e.y) / d
    t = (w.tick + e.eid * 17) % 40
    wobble = (t / 10.0 - 1.0) if t < 20 else (3.0 - t / 10.0)
    step = speed_of(e) * DT
    e.x += (fx - fy * wobble * SWARM_WOBBLE) * step
    e.y += (fy + fx * wobble * SWARM_WOBBLE) * step


def ranged_lobbed(w: World, e: Enemy, tx: float, ty: float, d: float, events: list[Event]) -> None:
    """Keep `keep_distance` and lob a spore at the player that leaves a poison puddle."""
    keep = e.keep_distance
    if d > keep:
        move_towards(e, tx, ty, d, speed_of(e))
    elif d < keep * RANGED_BACKOFF and d > 1e-9:
        move_towards(e, 2 * e.x - tx, 2 * e.y - ty, d, speed_of(e))
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


def _boss_phase(w: World, e: Enemy, events: list[Event]) -> bool:
    """Update the phase from the HP share. Returns True when a new phase just began."""
    boss = w.boss_stats[e.boss]
    pct = 100.0 * e.hp / e.max_hp
    phase = sum(1 for th in boss.phase_thresholds[1:] if pct <= th)
    if phase > e.phase:
        e.phase = phase
        events.append(BossPhase(w.tick, None, e.eid, e.boss, phase))
        return True
    return False


def boss_snail_queen(w: World, e: Enemy, tx: float, ty: float, d: float, events: list[Event]) -> None:
    """Schleimrun. Phase 0: slime ring. Phase 1 (60 %): slowing slime trail and 3 snails.
    Phase 2 (30 %): ring twice as fast plus spore rain around the player."""
    move_towards(e, tx, ty, d, speed_of(e))
    if not e.timers:
        e.timers = [RING_INTERVAL_S, GRIP_DELAY_S, SPORE_RAIN_INTERVAL_S]
    if _boss_phase(w, e, events):
        if e.phase == 1:
            w.summon_around(e, w.boss_stats[e.boss].summon_mob, GRIP_SUMMONS, events)
        if e.phase == 2:
            e.timers[0] = min(e.timers[0], RING_INTERVAL_FAST_S)
    e.timers = [t - DT for t in e.timers]
    if e.timers[0] <= 0:
        e.timers[0] = RING_INTERVAL_FAST_S if e.phase >= 2 else RING_INTERVAL_S
        thorn_ring(w, e, RING_SHOTS, events)
    if e.phase >= 1 and e.timers[1] <= 0:
        e.timers[1] = GRIP_INTERVAL_S
        grip = HazardSpec("grip", GRIP_RADIUS, delay=GRIP_DELAY_S, duration=GRIP_DURATION_S, slow_pct=GRIP_SLOW_PCT)
        w.add_hazard(grip, tx, ty, e.eid)
    if e.phase >= 2 and e.timers[2] <= 0:
        e.timers[2] = SPORE_RAIN_INTERVAL_S
        for _ in range(SPORE_RAIN_COUNT):
            ox, oy = w.random_offset(SPORE_RAIN_SPREAD)
            lob_spore(w, e, tx + ox, ty + oy, events)


def boss_beetle_king(w: World, e: Enemy, tx: float, ty: float, d: float, events: list[Event]) -> None:
    """Knollgrimm. Thorn fan at the player and a dash after a warning line. Phase 1 (60 %): 4 beetles,
    wider fan. Phase 2 (30 %): two dashes in a row, fan twice as fast."""
    if not e.timers:
        e.timers = [BEETLE_FAN_INTERVAL_S, BEETLE_DASH_INTERVAL_S, 0.0]  # fan, next dash, dashes left
    if _boss_phase(w, e, events) and e.phase == 1:
        w.summon_around(e, w.boss_stats[e.boss].summon_mob, BEETLE_SUMMONS, events)
    e.timers[0] -= DT
    if e.timers[0] <= 0 and e.charge_state != 2:  # the fan keeps coming, except in the middle of a dash
        e.timers[0] = BEETLE_FAN_INTERVAL_S / (2.0 if e.phase >= 2 else 1.0)
        aimed_fan(w, e, tx, ty, d, 7 if e.phase >= 1 else 5, BEETLE_FAN_DEG, events)
    if e.charge_state:
        if dash(e, tx, ty, d, BEETLE_DASH_S, BEETLE_DASH_SPEED, BEETLE_DAZE_S) and e.timers[2] > 0:
            e.timers[2] -= 1
            start_aim(e, tx, ty, d, BEETLE_AIM_S * 0.6)
        return
    move_towards(e, tx, ty, d, speed_of(e))
    e.timers[1] -= DT
    if e.timers[1] <= 0:
        e.timers[1] = BEETLE_DASH_INTERVAL_S
        e.timers[2] = 1.0 if e.phase >= 2 else 0.0
        start_aim(e, tx, ty, d, BEETLE_AIM_S)


def boss_reaper(w: World, e: Enemy, tx: float, ty: float, d: float, events: list[Event]) -> None:
    """Der Schnitter. Scythe ring. Phase 1 (66 %): soul rain (warned impacts) and pest tomatoes.
    Phase 2 (33 %): faster ring and a dash after a warning line."""
    if not e.timers:
        e.timers = [REAPER_RING_INTERVAL_S, REAPER_RAIN_INTERVAL_S, REAPER_DASH_INTERVAL_S]
    if _boss_phase(w, e, events) and e.phase == 1:
        w.summon_around(e, w.boss_stats[e.boss].summon_mob, REAPER_SUMMONS, events)
    e.timers = [t - DT for t in e.timers]
    if e.timers[0] <= 0:
        e.timers[0] = REAPER_RING_INTERVAL_S / (1.625 if e.phase >= 2 else 1.0)  # (text) "alle 1,6 s"
        thorn_ring(w, e, REAPER_RING_SHOTS, events)
    if e.phase >= 1 and e.timers[1] <= 0:
        e.timers[1] = REAPER_RAIN_INTERVAL_S
        for _ in range(REAPER_RAIN_COUNT):
            ox, oy = w.random_offset(REAPER_RAIN_SPREAD)
            spec = HazardSpec("explosion", REAPER_RAIN_RADIUS, delay=REAPER_RAIN_DELAY_S, burst=e.damage)
            w.add_hazard(spec, tx + ox, ty + oy, e.eid)
    if e.charge_state:
        dash(e, tx, ty, d, BEETLE_DASH_S, BEETLE_DASH_SPEED, BEETLE_DAZE_S * 0.5)
        return
    move_towards(e, tx, ty, d, speed_of(e))
    if e.phase >= 2 and e.timers[2] <= 0:
        e.timers[2] = REAPER_DASH_INTERVAL_S
        start_aim(e, tx, ty, d, BEETLE_AIM_S)


def aimed_fan(w: World, e: Enemy, tx: float, ty: float, d: float, count: int, spread_deg: float,
              events: list[Event]) -> None:  # fmt: skip
    if d <= 1e-9:
        return
    life = int(THORN_RANGE / THORN_SPEED * 60)
    for dx, dy in fan_directions((tx - e.x) / d, (ty - e.y) / d, count, spread_deg):
        w.enemy_shots.append(EnemyShot(e.x, e.y, dx * THORN_SPEED, dy * THORN_SPEED, e.damage, life, e.eid))
    events.append(EnemyShotFired(w.tick, None, e.eid, e.x, e.y, False))


def thorn_ring(w: World, e: Enemy, shots: int, events: list[Event]) -> None:
    """`shots` thorns evenly around the boss; every second volley is turned by half a step."""
    offset = 0.5 * (e.volley % 2)
    e.volley += 1
    life = int(THORN_RANGE / THORN_SPEED * 60)
    for k in range(shots):
        dx, dy = cos_sin(TAU * (k + offset) / shots)
        w.enemy_shots.append(EnemyShot(e.x, e.y, dx * THORN_SPEED, dy * THORN_SPEED, e.damage, life, e.eid))
    events.append(EnemyShotFired(w.tick, None, e.eid, e.x, e.y, False))


BEHAVIORS = {
    "chaser": chaser,
    "chaser_tank": chaser,  # knockback does not exist yet, so the tank only differs by its numbers
    "swarm": swarm,
    "ranged_lobbed": ranged_lobbed,
    "ranged_direct": ranged_direct,
    "charger": charger,
    "exploder": exploder,
}
BOSS_BEHAVIORS = {"snail_queen": boss_snail_queen, "beetle_king": boss_beetle_king, "reaper": boss_reaper}


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
