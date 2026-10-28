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

# Shrines (shrines.json; counts there are per run, spread evenly over the beds)
GREED_XP_PCT = 10.0  # (text) Gier-Schrein: "+10 % XP-Gewinn ... je Aktivierung (stapelt)"
SHRINE_START_CLEARANCE = 300.0  # no shrine right at the start of a bed
START_SHIELD_S = 20.0  # (text) workshop "Startschild": "verfällt nach 20 s"
CURSE_MAX_COPIES = 3  # (text) Fluchstein: "höchstens +3 Kopien insgesamt"
CURSE_CARD_RARITY = "legendary"  # Fluchstein reward "eine Karte mehr, eine Stufe höher": boss chests are epic
ELITE_SHRINE_COUNT = 3  # (text) Elite-Schrein: "Ruft sofort 3 Elite-Gegner"
COURAGE_MIN_RARITY = "rare"  # (text) Mut-Schrein: "Gratis-Upgradewahl mit mindestens Seltenheit selten"

# Performance (28.10.2026, measured: cost grows with the enemy count)
RECYCLE_DISTANCE = 1100.0  # enemies farther than this from every player jump back to the spawn ring
RECYCLE_EVERY_TICKS = 30
SEPARATE_EVERY_TICKS = 2  # crowd separation every 2nd tick (the most expensive pass)

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

# Paket F pests (mobs.json texts give the dash/explosion numbers; these are the rest)
CHARGE_START_DISTANCE = 320.0  # chargers start aiming this close to the player
EXPLODER_TRIGGER = 6.0  # pest tomatoes burst when this close to touching
EXPLODER_FUSE_S = 0.4  # (text) "0,4 s Warnung"

# Knollgrimm, der Käferkönig (bosses.json phase texts)
BEETLE_FAN_INTERVAL_S = 3.0  # (text) "alle 3 s"
BEETLE_FAN_DEG = 50.0
BEETLE_DASH_INTERVAL_S = 5.0
BEETLE_AIM_S = 0.8
BEETLE_DASH_S = 0.7
BEETLE_DASH_SPEED = 380.0  # (text) "Tempo 380"
BEETLE_DAZE_S = 1.0
BEETLE_SUMMONS = 4  # (text) "ruft 4 Kartoffelkäfer"

# Der Schnitter (bosses.json phase texts)
REAPER_RING_SHOTS = 12  # (text)
REAPER_RING_INTERVAL_S = 3.5  # (text)
REAPER_RAIN_INTERVAL_S = 4.0
REAPER_RAIN_COUNT = 6  # (text)
REAPER_RAIN_RADIUS = 80.0  # (text)
REAPER_RAIN_SPREAD = 200.0
REAPER_RAIN_DELAY_S = 1.0
REAPER_DASH_INTERVAL_S = 4.0
REAPER_SUMMONS = 4

# Gartentor (Paket F)
GATE_OFFSET = 140.0  # below the spot where the boss fell, so its chest and the gate do not overlap
GATE_DELAY_S = 2.0  # the gate opens with an animation and lets you through after this

# Paket F bonuses (texts in upgrades.json / items.json; the rest are assumptions)
LOW_HP_SHARE = 0.35  # (text) "unter 35 % HP"
CHALLENGE_LOW_HP_SHARE = 0.2  # (text) challenge "unlock_up_last_stand": "unter 20 % HP"
EXECUTE_SHARE = 0.30  # (text) "unter 30 % HP"
OVERCHARGE_INTERVAL_S = 6.0  # (text) "alle 6 s"
SHIELD_INTERVAL_S = 12.0  # (text) "alle 12 s"
KILL_HASTE_PCT = 2.0  # (text) "+2 % Angriffstempo"
KILL_HASTE_S = 5.0  # (text) "für 5 s"
BURN_SHARE = 0.30  # (text) "30 % Schaden/s"
BURN_S = 3.0  # (text)
POISON_S = 3.0  # (text)
POISON_MAX_STACKS = 4  # (text) "stapelt bis 4x"
CHILL_S = 2.0  # (text)
SHOCK_DAMAGE = 0.6  # (text) "60 % Schaden"
SHOCK_JUMPS = 2  # (text) "springt auf 2 nahe Gegner"
SHOCK_RANGE = 160.0
EXPLOSIVE_HIT_RADIUS = 50.0  # (text)
AURA_RADIUS = 100.0  # (text)
DOT_PULSE_TICKS = 30  # poison, burn and aura hurt every 0.5 s
BOUNCE_RANGE = 250.0
BOUNCE_DAMAGE = 0.8
SHRAPNEL_PIECES = 6  # (text)
SHRAPNEL_DAMAGE = 0.5  # (text)
SHRAPNEL_SPEED = 420.0
SHRAPNEL_RANGE = 160.0
DODGE_I_FRAMES_S = 0.3
REVIVE_HP_SHARE = 0.5  # (text)
REVIVE_I_FRAMES_S = 2.0  # (text)

# Paket G weapons
HOMING_RANGE = 260.0  # homing shots look for targets this close

# Paket H characters (characters.json texts; the rest are assumptions)
KNIFE_FAN_DEG = 20.0  # Kaz: three knives
SHOCKWAVE_PUSH = 24.0  # Brun: pests are pushed back this far (bosses stay)
SKY_STRIKE_HEIGHT = 220.0  # lightning from above: start point of the drawn bolt
INFERNO_S = 4.0  # (text) "4 s"
INFERNO_RADIUS = 180.0  # (text) "Radius 180"
INFERNO_DPS_SHARE = 0.4  # (text) "40 % Schaden/s"
DASH_DISTANCE = 220.0  # (text) "Dash über 220 px"
DASH_I_FRAMES_S = 0.3  # (text) "0,3 s unverwundbar"
BULWARK_SHIELD = 150.0  # (text) "absorbiert 150 Schaden"
BULWARK_S = 3.0  # (text) "Schild für 3 s"
ICE_AGE_S = 2.0  # (text) "2 s"
ICE_AGE_REACH = 720.0  # (text) "alle Gegner im Bild": about the visible area around you
STORM_S = 6.0  # (text) "6 s lang"
STORM_STRIKES_PER_S = 4  # (text) "4 Blitze pro Sekunde"
STORM_DAMAGE = 1.0
STORM_REACH = 500.0
