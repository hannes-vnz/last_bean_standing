"""Gameplay numbers that are NOT in data/ yet (start values, to be confirmed and moved into the JSON).

Every value here is an assumption made while implementing; numbers that do appear in a data
text (e.g. "4 Schaden/s, 3 s") are copied from there and marked with "(text)".
"""

# Players and arena
PLAYER_RADIUS = 12.0  # sprite 16 px = 32 units
PROJECTILE_RADIUS = 4.0
ORB_SPEED = 420.0  # XP orbs inside the pickup radius fly to the player
CHEST_PICKUP_RADIUS = 22.0
POT_RADIUS = 10.0
KILL_EXPLOSION_RADIUS = 60.0  # (text) item "Samenbombe": radius 60
KILL_EXPLOSION_DAMAGE = 0.5  # (text) 50 % of the killing hit
EXTRA_ATTACK_DAMAGE = 0.6  # balance.json stat_model

# Pickups (Paket A: magnet; gold and healing follow with Paket C)
PICKUP_RADIUS = 22.0
MAGNET_DROP_PCT = 0.5  # chance per normal kill; elites always drop one
MAGNET_ORB_SPEED = 900.0  # orbs pulled by a magnet fly this fast, from anywhere on the map

# Active abilities (characters.json texts)
ARROW_STORM_SHOTS = 16  # (text) "16 Pfeile in alle Richtungen (je 60 % Schaden)"
ARROW_STORM_DAMAGE = 0.6  # (text)
SPREAD_COS, SPREAD_SIN = 0.9887710779360422, 0.14943813247359922  # cos/sin(0.15 rad) as literals

# Enemy projectiles and hazards
ENEMY_SHOT_RADIUS = 5.0
SPORE_SPEED = 180.0  # lobbed spores, units per second
POISON_RADIUS = 40.0
POISON_DURATION_S = 3.0  # (text) sporeshooter: "Giftpfütze (4 Schaden/s, 3 s)"

# Mob behaviours
SWARM_SPREAD = 22.0  # bats of one group spawn around the same point
SWARM_WOBBLE = 0.6  # sideways flutter relative to forward speed
RANGED_BACKOFF = 0.75  # ranged mobs back off below this share of keep_distance
RANGED_FIRE_REACH = 1.3  # ...and shoot up to this share of keep_distance

# Elite affixes (text in elite.json)
ARMORED_DAMAGE_MULT = 0.7  # (text) -30 % damage taken
SWIFT_SPEED_MULT = 1.4  # (text) +40 % speed
REGEN_PCT_PER_S = 3.0  # (text) 3 % max HP per second
VOLATILE_RADIUS = 100.0  # (text) explodes on death, radius 100
VOLATILE_DELAY_S = 0.8  # warning before the explosion
SHIELD_PCT = 50.0  # (text) shield of 50 % HP
SHIELD_RECHARGE_S = 8.0  # (text) recharges after 8 s without hits

# Boss Ildra (bosses.json phase texts)
BOSS_RADIUS = 28.0  # 32x32 sprite
BOSS_MIN_SPAWN_DISTANCE = 420.0
RING_SHOTS = 8  # (text) "Dornenring (8 Geschosse), alle 4 s"
RING_INTERVAL_S = 4.0  # (text)
RING_INTERVAL_FAST_S = 2.0  # (text) "doppelt so schnell"
THORN_SPEED = 150.0
THORN_RANGE = 520.0  # thorns vanish after this distance
GRIP_INTERVAL_S = 7.0
GRIP_RADIUS = 90.0
GRIP_DELAY_S = 1.0
GRIP_DURATION_S = 4.0
GRIP_SLOW_PCT = 40.0  # (text) "verlangsamt dich 40 %"
GRIP_SUMMONS = 3  # (text) "ruft 3 Wurzelwächter"
SPORE_RAIN_INTERVAL_S = 1.5
SPORE_RAIN_COUNT = 3
SPORE_RAIN_SPREAD = 160.0
