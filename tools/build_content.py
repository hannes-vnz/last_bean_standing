#!/usr/bin/env python3
"""Erzeugt data/*.json und docs/CONTENT.md aus den Inhaltstabellen und prueft sie.

Alle Spielinhalte stehen hier an einer Stelle. Zahlen sind STARTWERTE: Sie stammen aus einer
Modellrechnung, nicht aus gespielten Runs. Feinjustierung erfolgt spaeter mit einer Headless-Simulation.
Aufruf: python tools/build_content.py   (aus dem Repo-Wurzelordner)
"""
import json, math, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA, DOCS = ROOT / "data", ROOT / "docs"

# ---------------------------------------------------------------------------- Balance
BALANCE = {
    "tick_hz": 60, "wave_interval_s": 30, "max_wave": 40, "swarm_time_s": 1200, "max_alive_enemies": 350,
    "budget": {"base": 10, "linear": 5.5, "quadratic": 0.22},           # je Welle w: base + linear*w + quadratic*w^2
    "hp_mult": {"linear": 0.10, "quadratic": 0.012},                     # 1 + a*m + b*m^2, m = Minuten
    "damage_mult": {"linear": 0.05, "quadratic": 0.004},
    "speed_mult": {"linear": 0.01, "cap": 1.2},
    "xp_to_next": {"base": 8, "linear": 5, "quadratic": 0.4},            # Level L -> L+1 (flacher seit 28.10.2026)
    "elite_every_n_waves": 5, "boss_waves": {"10": "ildra", "15": "skarra", "20": "kalthorn", "30": "ignarok"},
    "spawn_distance_px": [520, 700], "arena_tiles": [60, 60], "tile_px": 32,
    "player_base": {"hp": 100, "pickup_radius_px": 130, "i_frames_s": 0.6},
    "score": {"per_second": 2, "per_kill": 5, "per_level": 20, "per_boss": 500, "victory_bonus": 20000, "swarm_per_10s": 1000},
    "rarity_weights": {"common": 60, "uncommon": 25, "rare": 10, "epic": 4, "legendary": 1},
    "luck_shift_per_point": 0.4, "level_up_choices": 3, "elite_chest_min_rarity": "rare",
    "target_median_death_minutes": {"beginner": [3, 5], "skilled": [8, 12], "expert": [14, 18], "swarm_reached": "extrem selten"},
}

BALANCE.update({
    "mini_boss_times_s": [120, 750],
    "final_boss": {"id": "reaper", "summon": "altar", "altar_unlock_s": 600, "base_hp": 30000, "hp_scaling": "base_hp * hp_mult(minute_at_summon)",
                   "enrage_after_s": 90, "enrage_damage_pct_per_20s": 10},
    "difficulty": {"formula": "D = 1 + Summe(difficulty_add der aktivierten Schreine)", "applies_to": ["budget", "spawn_rate", "enemy_damage"],
                   "reward_mult": "1 + 0.8 * (D - 1)", "reward_applies_to": ["xp", "score"], "shown_in_hud": True},
    "stat_model": {"damage": "base * (1 + Summe(damage_pct)/100) * Produkt(Spezialmultiplikatoren)", "crit": "erwartet 1 + crit_chance * (crit_mult - 1)",
                   "dps": "damage * attack_rate * crit * (1 + extra_attacks * 0.6)", "rule": "gleiche Quelle addiert sich, verschiedene Quellen multiplizieren sich"},
})

# ---------------------------------------------------------------------------- Charaktere
def ch(id, name, title, arch, hp, speed, dmg, rate, rng, crit, weapon, passive, active, tags, unlock, phase, skins):
    return dict(id=id, name=name, title=title, archetype=arch, hp=hp, speed=speed, damage=dmg, attack_rate=rate,
                range=rng, crit_chance=crit, crit_mult=1.5, weapon=weapon, passive=passive, active=active,
                tags=tags, unlock_challenge=unlock, impl_phase=phase, skins=skins)

CHARACTERS = [
 ch("ranger", "Fenn", "der Falkenauge", "Jäger: ausgewogen, durchschlagende Pfeile", 100, 180, 12, 2.0, 380, 5,
    dict(type="projectile", pattern="single", projectile_speed=640, pierce=1, aoe_radius=0, text="Ein Pfeil, durchschlägt 1 Gegner."),
    dict(id="far_sight", name="Weitblick", text="+12 % Reichweite. +8 % Schaden auf Ziele über 250 px.", effects=[dict(stat="range_pct", value=12), dict(stat="damage_pct_far", value=8, threshold_px=250)]),
    dict(id="arrow_storm", name="Pfeilhagel", cooldown_s=18, text="16 Pfeile in alle Richtungen (je 60 % Schaden)."),
    ["projectile", "pierce", "range"], None, 1, ["ranger_a", "ranger_b"]),
 ch("pyro", "Mira", "Aschenglut", "Pyromantin: Flächenschaden und Brand", 80, 140, 14, 1.1, 320, 5,
    dict(type="projectile", pattern="single_explosive", projectile_speed=420, pierce=0, aoe_radius=64, text="Feuerball explodiert (Radius 64) und entzündet (3 s, 20 % Schaden/s)."),
    dict(id="heat_wave", name="Hitzewelle", text="Brennende Gegner erleiden +20 % Schaden.", effects=[dict(stat="damage_pct_vs_burning", value=20)]),
    dict(id="inferno", name="Inferno", cooldown_s=22, text="Feuerring (Radius 180) um dich, 4 s, 40 % Schaden/s."),
    ["fire", "area", "burn"], "unlock_pyro", 2, ["pyro_a", "pyro_b"]),
 ch("rogue", "Kaz", "Nachtmesser", "Schurke: schnell, kritisch, kurze Reichweite", 85, 190, 7, 2.2, 210, 20,
    dict(type="projectile", pattern="fan3", projectile_speed=700, pierce=0, aoe_radius=0, text="Fächer aus 3 Wurfmessern."),
    dict(id="thrill", name="Nervenkitzel", text="+15 % Lauftempo. +6 % Schaden je Gegner im Umkreis 150 px (max. 5).", effects=[dict(stat="move_speed_pct", value=15), dict(stat="damage_pct_per_nearby", value=6, radius_px=150, max_stacks=5)]),
    dict(id="shadow_step", name="Schattenschritt", cooldown_s=5, text="Dash über 220 px, 0,3 s unverwundbar."),
    ["crit", "movement", "close"], "unlock_rogue", 2, ["rogue_a", "rogue_b"]),
 ch("guardian", "Brun", "Eisenschulter", "Wächter: Nahkampf-Tank mit Dornen", 160, 120, 20, 0.9, 110, 0,
    dict(type="nova", pattern="shockwave", projectile_speed=0, pierce=99, aoe_radius=110, text="Schockwelle um dich (Radius 110) mit Rückstoß."),
    dict(id="iron_skin", name="Eisenhaut", text="-15 % erlittener Schaden. Reflektiert 25 % des Nahkampfschadens.", effects=[dict(stat="damage_taken_pct", value=-15), dict(stat="thorns_pct", value=25)]),
    dict(id="bulwark", name="Bollwerk", cooldown_s=25, text="Schild für 3 s, absorbiert 150 Schaden."),
    ["defense", "thorns", "area", "melee"], "unlock_guardian", 2, ["guardian_a", "guardian_b"]),
 ch("cryo", "Ysa", "Winterhauch", "Frostmagierin: Kontrolle und Verlangsamung", 90, 145, 10, 1.3, 340, 5,
    dict(type="projectile", pattern="single", projectile_speed=520, pierce=0, aoe_radius=0, text="Frostgeschoss verlangsamt um 30 % (2 s). 3 Kältestapel frieren 1,2 s ein."),
    dict(id="frost_aura", name="Frostaura", text="Gegner im Umkreis von 140 px sind 15 % langsamer.", effects=[dict(stat="aura_slow_pct", value=15, radius_px=140)]),
    dict(id="ice_age", name="Eiszeit", cooldown_s=24, text="Friert alle Gegner im Bild 2 s ein."),
    ["frost", "control", "ranged"], "unlock_cryo", 2, ["cryo_a", "cryo_b"]),
 ch("summoner", "Thorn", "Geisterruf", "Beschwörer: Begleiter kämpfen für ihn", 90, 140, 6, 1.0, 300, 5,
    dict(type="projectile_plus_minions", pattern="single", projectile_speed=480, pierce=0, aoe_radius=0, minions=2, text="Schwacher Geisterbolzen. 2 Geister-Begleiter greifen selbstständig an (8 Schaden, 1,5/s)."),
    dict(id="soul_bond", name="Seelenband", text="Geister erhalten 50 % deiner Schadensboni.", effects=[dict(stat="minion_inherit_damage_pct", value=50)]),
    dict(id="raise_dead", name="Totenruf", cooldown_s=30, text="4 zusätzliche Geister für 10 s."),
    ["summon", "minion"], "unlock_summoner", 3, ["summoner_a", "summoner_b"]),
 ch("storm", "Vex", "Donnerhall", "Sturmrufer: Kettenblitze, hohe Schussrate", 80, 160, 8, 2.4, 300, 5,
    dict(type="chain", pattern="chain_lightning", projectile_speed=0, pierce=0, aoe_radius=0, chain_jumps=2, chain_radius=160, chain_falloff=0.8, text="Kettenblitz springt 2-mal (160 px, je 80 % Schaden)."),
    dict(id="static_charge", name="Statische Ladung", text="Jeder 10. Schuss ruft einen Blitzschlag (200 % Schaden) auf einen zufälligen Gegner.", effects=[dict(stat="bonus_strike_every_n_shots", value=10, damage_pct=200)]),
    dict(id="thunderstorm", name="Gewittersturm", cooldown_s=28, text="6 s lang 4 Blitze pro Sekunde auf zufällige Gegner."),
    ["chain", "lightning", "speed"], "unlock_storm", 3, ["storm_a", "storm_b"]),
 ch("bomber", "Orm", "Zündfunke", "Sprengmeister: Bomben im Stand, Minen im Lauf", 110, 150, 26, 0.7, 300, 5,
    dict(type="lobbed", pattern="bomb", projectile_speed=300, pierce=0, aoe_radius=90, fuse_s=0.6, text="Bombe im Bogen, explodiert nach 0,6 s (Radius 90)."),
    dict(id="mine_layer", name="Minenleger", text="Legt beim Laufen alle 1,5 s eine Mine (60 % Schaden, Radius 70, max. 6).", effects=[dict(stat="mine_interval_s", value=1.5, damage_pct=60, radius_px=70, max_mines=6)]),
    dict(id="mega_bomb", name="Megabombe", cooldown_s=20, text="Große Bombe (Radius 200, 500 % Schaden)."),
    ["bomb", "area", "mine"], "unlock_bomber", 3, ["bomber_a", "bomber_b"]),
 ch("venom", "Lilu", "Schierling", "Giftmischerin: Giftpfützen und Seuche", 85, 150, 5, 1.4, 330, 5,
    dict(type="lobbed", pattern="vial", projectile_speed=360, pierce=0, aoe_radius=55, text="Giftphiole: Pfütze (Radius 55, 3 s, 12 Gift/s, stapelt bis 4x)."),
    dict(id="plague", name="Seuche", text="Vergiftete Gegner verbreiten beim Tod Gift (Radius 80).", effects=[dict(stat="poison_spread_on_death_radius_px", value=80)]),
    dict(id="toxic_cloud", name="Giftnebel", cooldown_s=26, text="Wolke (Radius 160) für 8 s, 35 % Schaden/s, verlangsamt 20 %."),
    ["poison", "area", "dot"], "unlock_venom", 3, ["venom_a", "venom_b"]),
 ch("sniper", "Aya", "Stillstand", "Scharfschützin: je länger sie steht, desto härter", 75, 130, 40, 0.45, 600, 10,
    dict(type="projectile", pattern="charged", projectile_speed=1100, pierce=3, aoe_radius=0, charge_bonus_per_s_pct=10, charge_max_pct=100, text="Durchschlag-Schuss (3). +10 % Schaden je Sekunde Stillstand (max. +100 %)."),
    dict(id="calm_before", name="Ruhe vor dem Schuss", text="Nach 2 s Stillstand ist der nächste Schuss ein garantierter Krit (x2,5).", effects=[dict(stat="guaranteed_crit_after_still_s", value=2, crit_mult=2.5)]),
    dict(id="focus", name="Fokus", cooldown_s=20, text="4 s lang: schießt auch im Lauf, doppelte Schussrate."),
    ["crit", "pierce", "stillness"], "unlock_sniper", 3, ["sniper_a", "sniper_b"]),
]


# ---------------------------------------------------------------------------- Optik: Effekte je Charakter (Pixel-Art)
VFX = {
 "ranger": dict(projectile="Pfeil (3 px lang, helle Spitze) mit Schweif aus 3 verblassenden Pixeln", impact="4 Funken und 2 Frames weißes Aufblitzen am Gegner", ability="Pfeilhagel: Mündungsring, 16 Pfeile in alle Richtungen"),
 "pyro": dict(projectile="Feuerball (6 px, 3-Frame-Flackern) mit Glutschweif (orange, rot, dunkelrot)", impact="expandierender Explosionsring (4 Frames), Glutpartikel; brennende Gegner tragen kleine Flammen", ability="Inferno: rotierender Flammenring um den Spieler"),
 "rogue": dict(projectile="drehendes Messer (4 Frames) mit blaugrauen Nachbildern", impact="weißer Diagonal-Schnitt (3 Frames)", ability="Schattenschritt: Schatten-Nachbilder und kleiner Rauchpuff"),
 "guardian": dict(projectile="Schockwelle: Ring mit 2 px Kante expandiert, Staubpartikel am Boden", impact="Rückstoß mit Staub, leichtes Bildschirmwackeln", ability="Bollwerk: schimmernder Sechseck-Schild"),
 "cryo": dict(projectile="Eiskristall (5 px) mit Glitzerpixeln", impact="6 Eisscherben und blaues Aufblitzen; eingefrorene Gegner bläulich mit Kristallhülle", ability="Eiszeit: weiß-blauer Ring über den ganzen Bildschirm"),
 "summoner": dict(projectile="grüner Wisp mit Schweif", impact="Seelenfunken steigen auf", ability="Totenruf: Rune am Boden, Geister steigen auf; Begleiter (8 px) schweben sinusförmig"),
 "storm": dict(projectile="Kettenblitz: gezackte 1-px-Linie, 3-Frame-Flackern, Funken an den Knoten", impact="Blitzschlag von oben (senkrechter Strahl) mit Bodenfunken", ability="Gewittersturm: dunkle Pixelwolke über dem Spieler, Blitze im Takt"),
 "bomber": dict(projectile="Bombe im Bogen mit Bodenschatten und funkensprühender Lunte", impact="großer Feuerball, Rauchring und Bildschirmwackeln; Minen blinken rot", ability="Megabombe: roter Warnkreis, dann Einschlag"),
 "venom": dict(projectile="Phiole dreht sich im Bogen", impact="grüner Platscher mit Tropfen; Pfütze mit blubbernden Blasen", ability="Giftnebel: wabernde Partikelwolke"),
 "sniper": dict(projectile="Aufladen: wachsender heller Punkt am Lauf und feine Zielline", impact="langer heller Strahl (1 px, 2 Frames) mit Mündungsblitz; Krit: goldener Ring plus Hit-Stop", ability="Fokus: leichte Entsättigung des Bildes während der 4 s"),
}
VFX_GLOBAL = ["Stil freundlich-pastellig: jede spielrelevante Figur hat eine dunkle Kontur (#4a3358), eigene Geschosse sind warmgelb, gegnerische violett mit Kontur", "Treffer-Aufblitzen: 2 Frames weiß", "Hit-Stop von 2 bis 3 Frames bei Krit, Elite- und Bosstod", "Bildschirmwackeln nach Trauma-Prinzip (Explosionen, Bosse)", "Schadenszahlen in Pixelschrift, Krit größer und gelb",
              "Todes-Pop: 8 Partikel in der Gegnerfarbe", "XP-Kugeln glitzern und fliegen zum Spieler", "Level-up: Ring und Funkenregen", "Boss-Warnungen: rote Linien und Kreise, 2 Hz Blinken",
              "Biom-Partikel: Blätter (Wald), Sandwind (Wüste), Schnee (Eis), Glut (Lava)", "Skins als Paletten-Tausch der Charakterfarben"]

# ---------------------------------------------------------------------------- Upgrades
def up(id, name, rar, maxlv, tags, text, effects, unlocked, phase, unlock_ch=None):
    return dict(id=id, name=name, rarity=rar, max_level=maxlv, tags=tags, text=text, effects=effects,
                unlocked_at_start=unlocked, unlock_challenge=unlock_ch, impl_phase=phase)
S = lambda stat, v: dict(stat=stat, per_level=v)
UPGRADES = [
 # --- gewöhnlich (18)
 up("sharp_edges", "Geschärfte Spitzen", "common", 5, ["damage"], "+8 % Schaden je Stufe.", [S("damage_pct", 8)], True, 1),
 up("quick_hands", "Flinke Hände", "common", 5, ["speed"], "+7 % Angriffstempo je Stufe.", [S("attack_speed_pct", 7)], True, 1),
 up("long_reach", "Weitsicht", "common", 4, ["range"], "+10 % Reichweite je Stufe.", [S("range_pct", 10)], True, 1),
 up("keen_eye", "Scharfblick", "common", 5, ["crit"], "+4 % Krit-Chance je Stufe.", [S("crit_chance_pct", 4)], True, 1),
 up("vitality", "Lebenskraft", "common", 5, ["defense"], "+15 Max-HP je Stufe (heilt um 15).", [S("max_hp_flat", 15)], True, 1),
 up("thick_skin", "Dicke Haut", "common", 4, ["defense"], "-6 % erlittener Schaden je Stufe.", [S("damage_taken_pct", -6)], True, 1),
 up("swift_feet", "Flinke Füße", "common", 5, ["movement"], "+6 % Lauftempo je Stufe.", [S("move_speed_pct", 6)], True, 1),
 up("magnet", "XP-Magnet", "common", 4, ["utility"], "+30 % Aufsammelradius je Stufe.", [S("pickup_radius_pct", 30)], True, 1),
 up("quick_learner", "Schnelle Auffassung", "common", 4, ["utility"], "+8 % XP je Stufe.", [S("xp_pct", 8)], True, 2),
 up("heal_orbs", "Heilkugeln", "common", 3, ["defense", "utility"], "Gegner lassen mit 3 % je Stufe Heilkugeln fallen (5 HP).", [S("heal_orb_chance_pct", 3)], True, 2),
 up("wide_blast", "Breite Wirkung", "common", 4, ["area"], "+10 % Flächenradius je Stufe.", [S("area_pct", 10)], True, 2),
 up("thorns", "Dornenpanzer", "common", 4, ["defense", "thorns"], "Reflektiert 20 % des erlittenen Nahkampfschadens je Stufe.", [S("thorns_pct", 20)], True, 2),
 up("big_shots", "Schwere Geschosse", "common", 3, ["projectile"], "+12 % Geschossgröße je Stufe (trifft leichter).", [S("projectile_size_pct", 12)], True, 2),
 up("fast_shots", "Schnelle Geschosse", "common", 3, ["projectile"], "+12 % Geschossgeschwindigkeit je Stufe.", [S("projectile_speed_pct", 12)], True, 2),
 up("dodge", "Ausweichen", "common", 5, ["defense"], "3 % Chance je Stufe, einem Treffer zu entgehen.", [S("dodge_chance_pct", 3)], True, 2),
 up("armor_plating", "Panzerplatten", "common", 4, ["defense"], "-1 Schaden je Treffer und Stufe (mindestens 1).", [S("flat_damage_reduction", 1)], True, 2),
 up("lucky_charm", "Glücksklee", "common", 4, ["utility"], "+5 Glück je Stufe: seltenere Upgrades werden wahrscheinlicher.", [S("luck", 5)], True, 2),
 up("bounty_hunter", "Kopfgeldjäger", "common", 4, ["damage"], "+6 % Schaden gegen Elite und Bosse je Stufe.", [S("damage_pct_vs_elite_boss", 6)], True, 2),
 # --- ungewöhnlich (14)
 up("brutal_crits", "Brutale Treffer", "uncommon", 4, ["crit"], "+20 % Krit-Schaden je Stufe (Basis 150 %).", [S("crit_mult_add_pct", 20)], True, 1),
 up("double_shot", "Mehrfachangriff", "uncommon", 3, ["projectile"], "+1 zusätzlicher Angriff je Stufe (60 % Schaden, leichte Streuung).", [S("extra_attacks", 1)], True, 1),
 up("piercing", "Durchschlag", "uncommon", 3, ["pierce", "projectile"], "Geschosse durchbohren +1 Gegner je Stufe.", [S("pierce_add", 1)], True, 1),
 up("heavy_hitter", "Schwergewicht", "uncommon", 3, ["damage"], "+25 % Schaden, -10 % Angriffstempo je Stufe.", [S("damage_pct", 25), S("attack_speed_pct", -10)], True, 2),
 up("regeneration", "Regeneration", "uncommon", 4, ["defense"], "+0,6 HP pro Sekunde je Stufe.", [S("regen_per_s", 0.6)], True, 1),
 up("reroll", "Neuwurf", "uncommon", 3, ["utility"], "+1 Neuwurf der Upgrade-Auswahl je Stufe (pro Run).", [S("rerolls", 1)], True, 2),
 up("banish", "Verbannung", "uncommon", 3, ["utility"], "+1 Verbannen je Stufe: entfernt ein Upgrade aus dem Pool dieses Runs.", [S("banishes", 1)], True, 2),
 up("stillness", "Meditation", "uncommon", 3, ["stillness", "damage"], "Nach 1 s Stillstand +12 % Schaden je Stufe.", [S("damage_pct_standing", 12)], False, 2, "unlock_up_stillness"),
 up("ignite", "Entzünden", "uncommon", 4, ["fire", "elemental"], "12 % Chance je Stufe zu entzünden (3 s, 30 % Schaden/s).", [S("ignite_chance_pct", 12)], True, 2),
 up("chill", "Kälte", "uncommon", 4, ["frost", "elemental"], "Treffer verlangsamen um 8 % je Stufe (max. 32 %).", [S("chill_slow_pct", 8)], True, 2),
 up("toxin", "Toxin", "uncommon", 4, ["poison", "elemental"], "Treffer vergiften (15 % Schaden/s je Stufe, 3 s, stapelt 4x).", [S("poison_pct_per_s", 15)], True, 2),
 up("shock", "Schock", "uncommon", 3, ["lightning", "elemental"], "15 % Chance je Stufe auf einen Blitz (60 % Schaden) auf einen nahen Gegner.", [S("shock_chance_pct", 15)], True, 2),
 up("minion_horde", "Gefolgschaft", "uncommon", 3, ["summon"], "+1 Begleiter je Stufe (ohne Beschwörer: Irrlicht mit 50 % Schaden).", [S("minions_add", 1)], False, 3, "unlock_up_minion_horde"),
 up("orbiting_blades", "Kreisende Klingen", "uncommon", 4, ["area", "melee"], "Eine zusätzliche Klinge je Stufe umkreist dich (6 Schaden).", [S("orbit_blades", 1)], False, 3, "unlock_up_orbiting_blades"),
 # --- selten (9)
 up("ricochet", "Rückprall", "rare", 3, ["bounce", "projectile"], "Geschosse springen +1-mal je Stufe auf einen nahen Gegner (70 % Schaden).", [S("bounce_add", 1)], True, 2),
 up("executioner", "Henker", "rare", 3, ["damage"], "+30 % Schaden gegen Gegner unter 30 % HP je Stufe.", [S("damage_pct_vs_low_hp", 30)], False, 2, "unlock_up_executioner"),
 up("lifesteal", "Aderlass", "rare", 3, ["defense", "damage"], "Heilt 2 % des verursachten Schadens je Stufe.", [S("lifesteal_pct", 2)], False, 2, "unlock_up_lifesteal"),
 up("shield_burst", "Notschild", "rare", 3, ["defense"], "Schild (40 HP) alle 20 s, -2 s je Stufe.", [dict(special="periodic_shield", hp=40, interval_s=20, interval_per_level_s=-2)], False, 2, "unlock_up_shield_burst"),
 up("last_stand", "Letztes Gefecht", "rare", 3, ["defense", "damage"], "Unter 30 % HP: +30 % Schaden und +20 % Tempo je Stufe.", [dict(special="low_hp_bonus", hp_threshold_pct=30, damage_pct=30, speed_pct=20)], False, 2, "unlock_up_last_stand"),
 up("overcharge", "Überladung", "rare", 3, ["damage"], "Alle 15 s (-2 s je Stufe) trifft der nächste Angriff mit 300 % Schaden.", [dict(special="overcharge", interval_s=15, interval_per_level_s=-2, damage_pct=300)], False, 2, "unlock_up_overcharge"),
 up("explosive_rounds", "Sprengmunition", "rare", 3, ["area", "projectile"], "Treffer lösen eine kleine Explosion aus (Radius 50, 40 % Schaden je Stufe).", [dict(special="explosive_hits", radius_px=50, damage_pct_per_level=40)], False, 2, "unlock_up_explosive_rounds"),
 up("aura_of_pain", "Aura des Schmerzes", "rare", 4, ["area", "melee"], "Gegner im Umkreis von 100 px erleiden 4 Schaden/s je Stufe.", [dict(special="damage_aura", radius_px=100, dps_per_level=4)], True, 2),
 up("elemental_mastery", "Elementarmeister", "rare", 3, ["elemental"], "+20 % Schaden aller Elementareffekte (Brand, Frost, Gift, Schock) je Stufe.", [S("elemental_damage_pct", 20)], True, 2),
 # --- episch (6)
 up("second_wind", "Zweiter Atem", "epic", 2, ["defense"], "Stufe 1: einmal pro Run mit 40 % HP wiederbeleben. Stufe 2: 60 % HP und 2 s unverwundbar.", [dict(special="revive", hp_pct=[40, 60], i_frames_s=[0, 2])], False, 3, "unlock_up_second_wind"),
 up("gravity_well", "Schwerkraftbrunnen", "epic", 2, ["control", "area"], "Alle 12 s zieht ein Sog alle Gegner im Radius 200 zusammen (Stufe 2: Radius 280, alle 9 s).", [dict(special="gravity_pull", radius_px=[200, 280], interval_s=[12, 9])], False, 3, "unlock_up_gravity_well"),
 up("bloodlust", "Blutrausch", "epic", 3, ["speed"], "Jeder Kill: +2 % Angriffstempo für 5 s, stapelt bis 20 % / 30 % / 40 %.", [dict(special="kill_haste", per_kill_pct=2, duration_s=5, max_pct=[20, 30, 40])], False, 3, "unlock_up_bloodlust"),
 up("time_warp", "Zeitdehnung", "epic", 2, ["control", "stillness"], "Im Stand sind alle Gegner im Radius 250 um 12 % / 20 % langsamer.", [dict(special="standing_slow", radius_px=250, slow_pct=[12, 20])], False, 3, "unlock_up_time_warp"),
 up("shrapnel", "Splitterhagel", "epic", 3, ["area", "projectile"], "Sterbende Gegner lösen mit 20 % Chance 6 Splitter aus (50 % Schaden), +10 % je Stufe.", [dict(special="death_shrapnel", chance_pct=[20, 30, 40], pieces=6, damage_pct=50)], False, 3, "unlock_up_shrapnel"),
 up("titan_heart", "Titanenherz", "epic", 3, ["defense"], "+30 % Max-HP je Stufe. +1 % Schaden je 10 Max-HP.", [S("max_hp_pct", 30), dict(special="damage_per_hp", damage_pct_per_10_hp=1)], False, 3, "unlock_up_titan_heart"),
 # --- legendär (3)
 up("glass_cannon", "Glaskanone", "legendary", 1, ["damage"], "+100 % Schaden, -40 % Max-HP.", [dict(stat="damage_pct", value=100), dict(stat="max_hp_pct", value=-40)], False, 3, "unlock_up_glass_cannon"),
 up("reaper_pact", "Pakt der Sense", "legendary", 1, ["damage", "defense"], "Jeder Kill heilt 1 HP. Alle 25 Kills ein Todesschlag (Radius 250, 500 % Schaden).", [dict(special="reaper_pact", heal_per_kill=1, strike_every_kills=25, radius_px=250, damage_pct=500)], False, 3, "unlock_up_reaper_pact"),
 up("elemental_storm", "Elementarsturm", "legendary", 1, ["elemental"], "Alle Elementareffekte (Brand, Frost, Gift, Schock) können auf jeden Treffer wirken, +50 % Elementarschaden.", [dict(special="all_elements", elemental_damage_pct=50)], False, 3, "unlock_up_elemental_storm"),
]

# ---------------------------------------------------------------------------- Mobs, Elite, Bosse, Biome
def mob(id, name, beh, hp, speed, dmg, cost, xp, min_t, biomes, text, phase, **extra):
    return dict(id=id, name=name, behavior=beh, hp=hp, speed=speed, damage=dmg, cost=cost, xp=xp, min_time_s=min_t,
                biome_weights=biomes, text=text, impl_phase=phase, **extra)
ALL = dict(forest=1, desert=1, ice=1, lava=1, plaza=1)
MOBS = [
 mob("slimeling", "Schleimling", "chaser", 12, 62, 5, 1, 1, 0, ALL, "Läuft geradeaus auf dich zu. Der Standardgegner.", 1, radius=12),
 mob("batswarm", "Fledermaus", "swarm", 5, 120, 3, 0.5, 0.5, 60, {b: 0.5 for b in ALL}, "Kommt in Gruppen zu 4, flattert unregelmäßig, sehr schnell.", 1, radius=9, group_size=4),
 mob("rootguard", "Wurzelwächter", "chaser_tank", 55, 38, 10, 4, 4, 90, dict(forest=1, plaza=0.3, desert=0.2, ice=0.2, lava=0.2), "Langsam und zäh, kaum Rückstoß.", 1, radius=18, knockback_resist=0.8),
 mob("sporeshooter", "Sporenschütze", "ranged_lobbed", 16, 45, 4, 3, 3, 120, dict(forest=1, plaza=0.3, desert=0.2, ice=0.2, lava=0.2), "Hält 260 px Abstand und wirft Sporen, die eine Giftpfütze (4 Schaden/s, 3 s) hinterlassen.", 1, radius=12, keep_distance_px=260, shot_interval_s=2.4),
 mob("sandspitter", "Sandspeier", "ranged_direct", 14, 55, 7, 2, 2, 100, dict(desert=1, plaza=0.3, forest=0.2, ice=0.2, lava=0.2), "Hält 300 px Abstand und schießt gerade Sandgeschosse (Tempo 260).", 2, radius=12, keep_distance_px=300, shot_interval_s=1.8, projectile_speed=260),
 mob("dunescorpion", "Dünenskorpion", "charger", 30, 50, 12, 3, 3, 150, dict(desert=1, plaza=0.3, forest=0.2, ice=0.2, lava=0.2), "Markiert 0,8 s eine Linie, stürmt dann 0,6 s mit Tempo 260 los und ist 1,2 s erschöpft.", 2, radius=14, telegraph_s=0.8, charge_s=0.6, charge_speed=260, recovery_s=1.2),
 mob("frostwolf", "Frostwolf", "chaser_pack", 20, 105, 7, 2, 2, 180, dict(ice=1, plaza=0.3, forest=0.2, desert=0.2, lava=0.2), "Schneller Läufer, kommt im Rudel zu 3.", 2, radius=13, group_size=3),
 mob("icegolem", "Eisgolem", "chaser_tank", 90, 32, 14, 7, 7, 240, dict(ice=1, plaza=0.2, forest=0.1, desert=0.1, lava=0.1), "Sehr zäh und langsam. Zerplatzt beim Tod in 8 Eissplitter (6 Schaden).", 2, radius=22, on_death=dict(type="shards", count=8, damage=6), knockback_resist=0.9),
 mob("emberimp", "Glutimp", "ranged_lobbed", 18, 58, 9, 3, 3, 210, dict(lava=1, plaza=0.3, forest=0.2, desert=0.2, ice=0.2), "Hält 280 px Abstand und wirft Feuerbälle (Radius 50), die 3 s Feuer am Boden hinterlassen.", 3, radius=12, keep_distance_px=280, shot_interval_s=2.2, aoe_radius=50),
 mob("lavabug", "Lavakäfer", "exploder", 10, 95, 18, 2, 2, 270, dict(lava=1, plaza=0.3, forest=0.2, desert=0.2, ice=0.2), "Rennt auf dich zu und explodiert bei Berührung (Radius 70, 18 Schaden), auch beim Tod (50 %).", 3, radius=11, explosion_radius=70, death_explosion_pct=50),
]
ELITE_AFFIXES = [
 dict(id="armored", name="Gepanzert", text="-30 % erlittener Schaden."),
 dict(id="swift", name="Flink", text="+40 % Tempo."),
 dict(id="regenerating", name="Regenerierend", text="Heilt 3 % Max-HP pro Sekunde."),
 dict(id="volatile", name="Explosiv", text="Explodiert beim Tod (Radius 100)."),
 dict(id="vampiric", name="Vampirisch", text="Heilt sich um 100 % des verursachten Schadens."),
 dict(id="shielded", name="Schildträger", text="Schild in Höhe von 50 % der HP, lädt nach 8 s ohne Treffer neu."),
]
ELITE = dict(hp_mult=4, damage_mult=1.5, xp_mult=5, size_mult=1.35, affixes_per_elite_by_minute={"0": 1, "10": 2, "15": 3}, drops="elite_chest")
CURRENCY = dict(
    id="sparkles", name="Funkelsteine",
    payout="Am Laufende: floor(Punkte / 100 x Belohnungsfaktor). Der Belohnungsfaktor ist 1 + 0,8 x (D - 1), also steigt die Auszahlung mit der Schwierigkeit (Schreine). Nichts geht beim Sterben verloren.",
    run_drops=dict(normal_kill_chance_pct=1.5, elite=2, mini_boss=8, biome_boss=20, final_boss=100, victory_bonus=100, chest=3),
    estimates="Ein 5-Minuten-Lauf bringt etwa 40 bis 50, ein starker 15-Minuten-Lauf etwa 200 Funkelsteine (Modellrechnung, nicht gemessen).",
    shown_at_run_end="Aufschlüsselung: Zeit, Kills, Level, Bosse, Schwierigkeitsbonus, Drops, Challenges.",
    never_lost=True)
WORKSHOP_RULES = dict(cost="round(base_cost x 1.5^(Stufe-1))", refund_pct=100,
    note="Jederzeit zu 100 % erstattbar, damit niemand etwas bereut. Die Boni sind klein und begrenzt, damit der Lauf selbst entscheidet und nicht der Grind.")
def ws(id, name, per, unit, mx, base, text): return dict(id=id, name=name, effect=dict(stat=per, per_level=unit), max_level=mx, base_cost=base, text=text)
WORKSHOP = [
 ws("ws_hp", "Zähigkeit", "max_hp_pct", 3, 5, 50, "+3 % Max-HP je Stufe."),
 ws("ws_damage", "Kraft", "damage_pct", 2, 5, 60, "+2 % Schaden je Stufe."),
 ws("ws_attack", "Eifer", "attack_speed_pct", 2, 5, 60, "+2 % Angriffstempo je Stufe."),
 ws("ws_move", "Beinarbeit", "move_speed_pct", 2, 5, 40, "+2 % Lauftempo je Stufe."),
 ws("ws_magnet", "Sammelfreude", "pickup_radius_pct", 8, 5, 30, "+8 % Aufsammelradius je Stufe."),
 ws("ws_xp", "Wissensdurst", "xp_pct", 3, 5, 50, "+3 % XP je Stufe."),
 ws("ws_luck", "Kleeblatt", "luck", 2, 5, 70, "+2 Glück je Stufe."),
 ws("ws_range", "Weitblick", "range_pct", 2, 5, 40, "+2 % Reichweite je Stufe."),
 ws("ws_reroll", "Neuwurf-Vorrat", "rerolls", 1, 2, 150, "+1 Neuwurf je Stufe (pro Lauf)."),
 ws("ws_banish", "Verbannungs-Vorrat", "banishes", 1, 2, 150, "+1 Verbannen je Stufe (pro Lauf)."),
 ws("ws_shield", "Startschild", "start_shield_hp", 20, 3, 80, "+20 Schild-HP zu Beginn, verfällt nach 20 s."),
 ws("ws_radar", "Schrein-Radar", "show_shrines_on_map", 1, 1, 300, "Schreine sind auf der Karte sichtbar."),
]
RUN_PACKS = dict(max_per_run=2, items=[
 dict(id="pack_provisions", name="Proviant", cost=25, effect="+5 % Heilkugel-Chance in diesem Lauf."),
 dict(id="pack_clover", name="Glücksbringer", cost=40, effect="+10 Glück in diesem Lauf."),
 dict(id="pack_map", name="Schatzkarte", cost=30, effect="Schreine sind in diesem Lauf auf der Karte sichtbar."),
 dict(id="pack_headstart", name="Frühstart", cost=60, effect="Start bei Level 3 (2 Gratis-Upgradewahlen)."),
])
COSMETICS = dict(id="color_pots", name="Farbtöpfe", cost_each=150, per_character=3,
    variants=[dict(name="Zuckerwatte", hue_shift=40), dict(name="Minze", hue_shift=160), dict(name="Sonnenuntergang", hue_shift=-60)],
    text="Rein kosmetische Zusatzfarben für jeden Charakter (Paletten-Tausch der Ramp-Farben).")
MINI_BOSS = dict(times_s=[120, 750], hp_mult=12, damage_mult=2, xp_mult=15, size_mult=1.8, has_hp_bar=True, drops="boss_chest_rare",
                 pick="eine zufällige, schon freigeschaltete Mob-Art der Zone, in der der Spieler steht")
SHRINES = [
 dict(id="greed", name="Gier-Schrein", count=6, channel_s=1.5, radius_px=60, difficulty_add=0.05, impl_phase=2,
      effect="Dauerhaft +5 % Schwierigkeit.", reward="+10 % XP-Gewinn und +5 % Punktemultiplikator je Aktivierung (stapelt)."),
 dict(id="courage", name="Mut-Schrein", count=3, channel_s=20, radius_px=120, difficulty_add=0.08, impl_phase=3,
      effect="Dauerhaft +8 %. 20 s im markierten Kreis stehen, währenddessen 1,5x Spawnrate in der Nähe (Fortschritt pausiert außerhalb).", reward="Eine Gratis-Upgradewahl mit mindestens Seltenheit \"selten\"."),
 dict(id="curse", name="Fluchstein", count=2, channel_s=1.5, radius_px=60, difficulty_add=0.05, impl_phase=3,
      effect="Dauerhaft +5 %. Der nächste Biom-Boss erscheint einmal mehr (höchstens +3 Kopien insgesamt).", reward="Bosstruhen bieten eine Karte mehr und eine Seltenheitsstufe höher."),
 dict(id="elite", name="Elite-Schrein", count=2, channel_s=1.5, radius_px=60, difficulty_add=0.03, impl_phase=3,
      effect="Dauerhaft +3 %. Ruft sofort 3 Elite-Gegner mit Affixen.", reward="Jeder Elite lässt eine Elitetruhe fallen (mindestens \"selten\")."),
]
SHRINE_RULES = ("Pro Lauf liegen die Schreine mit festem Seed in den Zonen (jede Zone mindestens einen, nicht in der Lichtung). Aktiviert wird durch Stillstehen im Radius "
                "(passt zu Stop-and-Shoot: du schießt dabei weiter). Jeder Schrein ist einmal nutzbar. Die Schwierigkeit zeigt das HUD als Prozentwert.")
SWARM = dict(start_s=1200, entity="floodwisp", name="Flutgeist", hp=6, speed=75, damage=6, flying=True, ignores_obstacles=True,
             burst_every_s=3, burst_size_base=40, burst_growth_pct_per_min=10, speed_gain_pct_per_min=8,
             score_mult_start=1, score_mult_gain_per_45s=1, score_mult_cap=8, hp_damage_scaling="wie normale Gegner (hp_mult, damage_mult), setzt sich unbegrenzt fort",
             text="Ab 20:00 beginnt die Schwarmflut: fliegende Flutgeister in Schüben, die nie aufhört und immer schneller wird. Sie ist der Endlos-Modus für den Highscore.")
BOSSES = [
 dict(id="ildra", name="Ildra, die Dornenkönigin", spawn_wave=10, spawn_time_s=300, hp=2500, speed=45, damage=14, biome="forest", impl_phase=1,
      phases=[dict(at_hp_pct=100, pattern="Rotierender Dornenring (8 Geschosse), alle 4 s"), dict(at_hp_pct=60, pattern="Wurzelgriff: verlangsamt dich 40 % in einem Kreis, ruft 3 Wurzelwächter"), dict(at_hp_pct=30, pattern="Dornenring doppelt so schnell, Spore-Regen")],
      reward="boss_chest_epic", first_kill_challenge="boss_ildra"),
 dict(id="skarra", name="Skarra, die Sandkönigin", spawn_wave=15, spawn_time_s=450, hp=5000, speed=60, damage=17, biome="desert", impl_phase=2,
      phases=[dict(at_hp_pct=100, pattern="Stachelfächer (5 Sandstacheln, alle 3 s) und Sturmangriff nach Warnlinie (Tempo 300)"), dict(at_hp_pct=60, pattern="Eingraben: verschwindet, bricht nach 1,5 s Warnkreis (Radius 120) unter dir hervor, ruft Dünenskorpione"), dict(at_hp_pct=30, pattern="Sandwirbel über Teilen des Bildes (halbtransparent, Gegner und Geschosse bleiben sichtbar), Stachelfächer doppelt so schnell")],
      reward="boss_chest_epic", first_kill_challenge="boss_skarra"),
 dict(id="kalthorn", name="Kalthorn, der Eiswurm", spawn_wave=20, spawn_time_s=600, hp=9000, speed=70, damage=20, biome="ice", impl_phase=2,
      phases=[dict(at_hp_pct=100, pattern="Frostbahn: Linie markieren, dann Sturm (Tempo 320)"), dict(at_hp_pct=60, pattern="Eisnova (Radius 260), ruft Frostwolf-Rudel"), dict(at_hp_pct=30, pattern="Eisnova alle 5 s, Boden wird rutschig")],
      reward="boss_chest_epic", first_kill_challenge="boss_kalthorn"),
 dict(id="ignarok", name="Ignarok, der Glutkoloss", spawn_wave=30, spawn_time_s=900, hp=24000, speed=40, damage=28, biome="lava", impl_phase=3,
      phases=[dict(at_hp_pct=100, pattern="Meteorregen (6 Einschläge, 1,2 s Vorwarnung)"), dict(at_hp_pct=60, pattern="Stampfen: Schockwelle (Radius 300), Lavapfützen"), dict(at_hp_pct=30, pattern="Meteore doppelt, ruft Lavakäfer")],
      reward="boss_chest_legendary", first_kill_challenge="boss_ignarok"),
 dict(id="reaper", name="Der Schnitter", summon="altar", altar_unlock_s=600, spawn_time_s=None, hp_base=30000, hp_scaled=True, speed=55, damage=40, biome=None, impl_phase=3,
      enrage_after_s=90, enrage_damage_pct_per_20s=10,
      phases=[dict(at_hp_pct=100, pattern="Sensenwirbel: rotierender Kegel mit 1 s Warnfläche, alle 5 s"), dict(at_hp_pct=66, pattern="Seelenregen: 8 Einschläge mit Warnkreis (Radius 90) in Wellen, ruft Flutgeister"), dict(at_hp_pct=33, pattern="Zeitriss: du bist 3 s lang 30 % langsamer, er stürmt dreimal; danach 25 % mehr Tempo")],
      reward="victory", first_kill_challenge="boss_reaper"),
]
BIOMES = [
 dict(id="plaza", name="Lichtung (Start)", effect="Keine, enthält den Boss-Altar (ab 10:00 aktivierbar, ruft den Schnitter)", rect_tiles=[22, 22, 16, 16], text="Neutrale Startzone in der Mitte.", objects=[dict(type="boss_altar", pos_tiles=[30, 30], unlock_s=600)]),
 dict(id="forest", name="Wald", effect="Bäume blockieren Geschosse (Deckung für beide Seiten)", rect_tiles=[0, 0, 30, 30], obstacles=dict(type="tree", count=70, seed=11), impl_phase=1),
 dict(id="desert", name="Wüste", effect="Du bist 15 % langsamer", rect_tiles=[30, 0, 30, 30], obstacles=dict(type="rock", count=25, seed=12), player_speed_pct=-15, impl_phase=2),
 dict(id="ice", name="Eis", effect="Rutschen: träge Beschleunigung und Bremsen", rect_tiles=[0, 30, 30, 30], obstacles=dict(type="ice_block", count=30, seed=13), friction=0.15, impl_phase=2),
 dict(id="lava", name="Lava", effect="4 Schaden pro Sekunde in Lavapfützen, dafür +25 % XP in der Zone", rect_tiles=[30, 30, 30, 30], obstacles=dict(type="lava_pool", count=18, seed=14), dot_per_s=4, xp_bonus_pct=25, impl_phase=3),
]
PALETTES = {
 "plaza":  dict(ground="#b9e08f", detail="#9fcf72", hazard=None),
 "forest": dict(ground="#a6dd82", detail="#83c564", hazard=None, tree="#5aa05a", trunk="#8a6a4a"),
 "desert": dict(ground="#f6dfa8", detail="#e8c47a", hazard="#e0b862", rock="#c9a46a"),
 "ice":    dict(ground="#d6ecff", detail="#b4d6f5", hazard="#ffffff", block="#bfe0ff"),
 "lava":   dict(ground="#ffc9b0", detail="#ff9f86", hazard="#ff6b6b", bubble="#ffd45e"),
}
STYLE = dict(
 name="Freundlich, pastell", ink="#4a3358",
 player=dict(hair="#ffb04a", skin="#ffe0c8", body="#6ec6ff"),
 enemy=dict(slime="#ff8fb8", bat="#7a5cc0"),
 player_projectile=dict(core="#fff7a8", halo="#ffd45e"),
 enemy_projectile=dict(core="#8a4fff", outline="#4a3358"),
 xp_orb="#5ee6b8", heal_orb="#ff7aa8", telegraph="#ff6b6b", crit_text="#ffd45e", reaper="#2a1d3d",
 flowers=["#ffffff", "#ff9fc0", "#ffd45e"],
)
MODES = [dict(id="eternal_night", name="Ewige Nacht", text="Gegner-HP x1,5, XP x1,25, Punkte x1,5.", hp_mult=1.5, xp_mult=1.25, score_mult=1.5, unlock_challenge="reach_swarm")]

# ---------------------------------------------------------------------------- Challenges und Skins
CHALLENGES, SKINS = [], []
STONES_BY_REWARD = {"unlock_character": 100, "unlock_skin": 50, "unlock_upgrade": 40, "title": 150, "unlock_mode": 300}
def chal(id, text, cond, reward):
    CHALLENGES.append(dict(id=id, text=text, condition=cond, reward=dict(reward, stones=STONES_BY_REWARD[reward["type"]])))
RS = lambda stat, v, **kw: dict(type="run_stat", stat=stat, op=">=", value=v, **kw)
PS = lambda stat, v, **kw: dict(type="profile_stat", stat=stat, op=">=", value=v, **kw)
UC = lambda i: dict(type="unlock_character", id=i)
UU = lambda i: dict(type="unlock_upgrade", id=i)
chal("unlock_pyro", "Erreiche Minute 5 mit beliebigem Charakter.", RS("minutes_survived", 5), UC("pyro"))
chal("unlock_rogue", "Räume eine Welle ab Welle 5, ohne Schaden zu nehmen.", RS("flawless_wave", 5), UC("rogue"))
chal("unlock_guardian", "Erleide insgesamt 5000 Schaden.", PS("damage_taken_total", 5000), UC("guardian"))
chal("unlock_cryo", "Besiege 300 Gegner im Eisbiom.", PS("kills_in_biome", 300, biome="ice"), UC("cryo"))
chal("unlock_summoner", "Erreiche Level 15 in einem Run.", RS("level_reached", 15), UC("summoner"))
chal("unlock_storm", "Erreiche Minute 8.", RS("minutes_survived", 8), UC("storm"))
chal("unlock_bomber", "Besiege insgesamt 2000 Gegner.", PS("kills_total", 2000), UC("bomber"))
chal("unlock_venom", "Verursache insgesamt 10000 Giftschaden.", PS("poison_damage_total", 10000), UC("venom"))
chal("unlock_sniper", "Besiege alle vier Biom-Bosse (Ildra, Skarra, Kalthorn, Ignarok).", PS("distinct_bosses_defeated", 4), UC("sniper"))
UP_UNLOCKS = {
 "unlock_up_stillness": ("Schließe 10 Runs ab.", PS("runs_total", 10), "stillness"),
 "unlock_up_minion_horde": ("Schalte 3 Charaktere frei.", PS("characters_unlocked", 3), "minion_horde"),
 "unlock_up_orbiting_blades": ("Erreiche Level 20 in einem Run.", RS("level_reached", 20), "orbiting_blades"),
 "unlock_up_executioner": ("Besiege 25 Elite-Gegner.", PS("elite_kills_total", 25), "executioner"),
 "unlock_up_lifesteal": ("Besiege insgesamt 1000 Gegner.", PS("kills_total", 1000), "lifesteal"),
 "unlock_up_shield_burst": ("Räume eine Welle ab Welle 8, ohne Schaden zu nehmen.", RS("flawless_wave", 8), "shield_burst"),
 "unlock_up_last_stand": ("Verbringe insgesamt 60 s mit unter 20 % HP.", PS("low_hp_seconds_total", 60), "last_stand"),
 "unlock_up_overcharge": ("Lande insgesamt 3000 kritische Treffer.", PS("crits_total", 3000), "overcharge"),
 "unlock_up_explosive_rounds": ("Besiege insgesamt 3000 Gegner.", PS("kills_total", 3000), "explosive_rounds"),
 "unlock_up_second_wind": ("Besiege den ersten Boss.", PS("boss_kills_total", 1), "second_wind"),
 "unlock_up_gravity_well": ("Erreiche Minute 10.", RS("minutes_survived", 10), "gravity_well"),
 "unlock_up_bloodlust": ("Besiege 800 Gegner in einem Run.", RS("kills_in_run", 800), "bloodlust"),
 "unlock_up_time_warp": ("Erreiche Minute 12.", RS("minutes_survived", 12), "time_warp"),
 "unlock_up_shrapnel": ("Besiege insgesamt 10000 Gegner.", PS("kills_total", 10000), "shrapnel"),
 "unlock_up_titan_heart": ("Erleide 1500 Schaden in einem Run.", RS("damage_taken_run", 1500), "titan_heart"),
 "unlock_up_glass_cannon": ("Erreiche Minute 15.", RS("minutes_survived", 15), "glass_cannon"),
 "unlock_up_reaper_pact": ("Besiege insgesamt 10 Bosse.", PS("boss_kills_total", 10), "reaper_pact"),
 "unlock_up_elemental_storm": ("Besitze Entzünden, Kälte, Toxin und Schock in einem Run.", dict(type="run_flag", flag="owns_all", ids=["ignite", "chill", "toxin", "shock"]), "elemental_storm"),
}
for cid, (text, cond, upid) in UP_UNLOCKS.items():
    chal(cid, text, cond, UU(upid))
SKIN_NAMES = {"ranger": ("Waldläufer", "Goldjäger"), "pyro": ("Glutrot", "Weißglut"), "rogue": ("Mitternacht", "Schattenfürst"),
              "guardian": ("Stahlgrau", "Goldplatte"), "cryo": ("Gletscher", "Polarlicht"), "summoner": ("Nekrogrün", "Seelenlicht"),
              "storm": ("Gewitterblau", "Himmelsgold"), "bomber": ("Zunderorange", "Funkenweiß"), "venom": ("Giftgrün", "Schierlingsviolett"),
              "sniper": ("Wüstentarn", "Schneetarn")}
SKIN_TINTS = {"ranger": ([90, 170, 90], [255, 210, 80]), "pyro": ([230, 80, 40], [255, 245, 200]), "rogue": ([50, 60, 140], [120, 60, 160]),
              "guardian": ([150, 160, 170], [230, 190, 70]), "cryo": ([120, 200, 240], [140, 255, 220]), "summoner": ([80, 160, 110], [200, 230, 255]),
              "storm": ([70, 110, 220], [255, 220, 120]), "bomber": ([240, 140, 40], [250, 250, 240]), "venom": ([110, 200, 60], [150, 70, 180]),
              "sniper": ([190, 160, 100], [235, 240, 245])}
for c in CHARACTERS:
    for i, minute in enumerate((10, 15)):
        sid = f"{c['id']}_{'ab'[i]}"
        cid = f"skin_{sid}"
        chal(cid, f"Erreiche Minute {minute} mit {c['name']}.", RS("minutes_survived", minute, character=c["id"]), dict(type="unlock_skin", id=sid))
        SKINS.append(dict(id=sid, character=c["id"], name=SKIN_NAMES[c["id"]][i], tint=SKIN_TINTS[c["id"]][i], unlock_challenge=cid))
chal("boss_ildra", "Besiege Ildra.", PS("boss_defeated", 1, boss="ildra"), dict(type="title", id="Dornenbrecher"))
chal("boss_skarra", "Besiege Skarra.", PS("boss_defeated", 1, boss="skarra"), dict(type="title", id="Sandbezwinger"))
chal("boss_kalthorn", "Besiege Kalthorn.", PS("boss_defeated", 1, boss="kalthorn"), dict(type="title", id="Eisbrecher"))
chal("boss_ignarok", "Besiege Ignarok.", PS("boss_defeated", 1, boss="ignarok"), dict(type="title", id="Glutlöscher"))
chal("reach_swarm", "Erreiche 20:00 (Beginn der Schwarmflut).", RS("minutes_survived", 20), dict(type="unlock_mode", id="eternal_night"))
chal("boss_reaper", "Besiege den Schnitter.", PS("boss_defeated", 1, boss="reaper"), dict(type="title", id="Sensenmeister"))
chal("shrines_5", "Aktiviere 5 Schreine in einem Run.", RS("shrines_activated", 5), dict(type="title", id="Wagemutig"))
chal("swarm_5min", "Überlebe 5 Minuten der Schwarmflut.", RS("swarm_seconds", 300), dict(type="title", id="Flutreiter"))

# ---------------------------------------------------------------------------- Pruefung
def validate():
    errs = []
    ids = lambda L: [x["id"] for x in L]
    for name, L in [("characters", CHARACTERS), ("upgrades", UPGRADES), ("mobs", MOBS), ("challenges", CHALLENGES), ("skins", SKINS), ("bosses", BOSSES), ("biomes", BIOMES)]:
        if len(set(ids(L))) != len(L): errs.append(f"doppelte IDs in {name}")
    if len(WORKSHOP) != 12 or any(w["max_level"] < 1 or w["base_cost"] <= 0 for w in WORKSHOP): errs.append("Werkstatt: 12 Einträge mit gültigen Werten erwartet")
    if len(SHRINES) != 4: errs.append("Schreine: 4 Arten erwartet")
    if "reaper" not in ids(BOSSES): errs.append("Endboss fehlt")
    if not all(str(k) in ("10", "15", "20", "30") and v in ids(BOSSES) for k, v in BALANCE["boss_waves"].items()): errs.append("boss_waves verweist auf unbekannten Boss")
    if len(CHARACTERS) != 10: errs.append(f"Charaktere: {len(CHARACTERS)} statt 10")
    if set(PALETTES) != set(ids(BIOMES)): errs.append("Paletten: jedes Biom braucht eine")
    if set(VFX) != set(ids(CHARACTERS)): errs.append("VFX: jeder Charakter braucht eine Beschreibung")
    if len(UPGRADES) != 50: errs.append(f"Upgrades: {len(UPGRADES)} statt 50")
    if len(MOBS) != 10: errs.append(f"Mobs: {len(MOBS)} statt 10")
    rar = {}
    for u in UPGRADES: rar[u["rarity"]] = rar.get(u["rarity"], 0) + 1
    if rar != {"common": 18, "uncommon": 14, "rare": 9, "epic": 6, "legendary": 3}: errs.append(f"Seltenheiten: {rar}")
    ch_ids = set(ids(CHALLENGES))
    for c in CHARACTERS:
        if c["unlock_challenge"] and c["unlock_challenge"] not in ch_ids: errs.append(f"Charakter {c['id']}: Challenge fehlt")
        for s in c["skins"]:
            if s not in ids(SKINS): errs.append(f"Skin {s} fehlt")
    for u in UPGRADES:
        if (not u["unlocked_at_start"]) != bool(u["unlock_challenge"]): errs.append(f"Upgrade {u['id']}: Start-Freischaltung und Challenge passen nicht")
        if u["unlock_challenge"] and u["unlock_challenge"] not in ch_ids: errs.append(f"Upgrade {u['id']}: Challenge fehlt")
    for ch_ in CHALLENGES:
        r = ch_["reward"]
        if r["type"] == "unlock_character" and r["id"] not in ids(CHARACTERS): errs.append(f"{ch_['id']}: Charakter {r['id']} unbekannt")
        if r["type"] == "unlock_upgrade" and r["id"] not in ids(UPGRADES): errs.append(f"{ch_['id']}: Upgrade {r['id']} unbekannt")
        if r["type"] == "unlock_skin" and r["id"] not in ids(SKINS): errs.append(f"{ch_['id']}: Skin {r['id']} unbekannt")
        for i in ch_["condition"].get("ids", []):
            if i not in ids(UPGRADES): errs.append(f"{ch_['id']}: Upgrade {i} unbekannt")
    biomes = set(ids(BIOMES))
    for m in MOBS:
        if set(m["biome_weights"]) - biomes: errs.append(f"Mob {m['id']}: unbekanntes Biom")
    for u in UPGRADES:
        if u["rarity"] in ("epic", "legendary") and u["unlocked_at_start"]: errs.append(f"{u['id']}: epische/legendäre Upgrades müssen gesperrt starten")
    return errs

# ---------------------------------------------------------------------------- Balance-Modell
def budget(w): b = BALANCE["budget"]; return b["base"] + b["linear"] * w + b["quadratic"] * w * w
def hp_mult(m): b = BALANCE["hp_mult"]; return 1 + b["linear"] * m + b["quadratic"] * m * m
def dmg_mult(m): b = BALANCE["damage_mult"]; return 1 + b["linear"] * m + b["quadratic"] * m * m
def xp_next(L): x = BALANCE["xp_to_next"]; return x["base"] + x["linear"] * L + x["quadratic"] * L * L
def balance_rows():
    hp_per_cost = sum(m["hp"] / m["cost"] for m in MOBS) / len(MOBS)
    rows, cum_xp, level, spent = [], 0.0, 1, 0.0
    for w in range(1, BALANCE["max_wave"] + 1):
        cum_xp += budget(w)                       # XP je Welle entspricht dem Budget (xp = cost)
        while cum_xp - spent >= xp_next(level): spent += xp_next(level); level += 1
        if w % 2 == 0:
            m = w * BALANCE["wave_interval_s"] / 60
            rows.append(dict(minute=m, wave=w, budget=budget(w), hp_mult=hp_mult(m), dmg_mult=dmg_mult(m),
                             spawn_hp_per_s=budget(w) / BALANCE["wave_interval_s"] * hp_per_cost * hp_mult(m), level=level, cum_xp=cum_xp))
    return rows, hp_per_cost

# ---------------------------------------------------------------------------- Ausgabe
def write_json():
    DATA.mkdir(exist_ok=True)
    files = {"balance.json": BALANCE, "characters.json": [dict(c, vfx=VFX[c["id"]]) for c in CHARACTERS], "upgrades.json": UPGRADES, "mobs.json": MOBS,
             "elite.json": dict(ELITE, affixes=ELITE_AFFIXES, mini_boss=MINI_BOSS), "shrines.json": dict(shrines=SHRINES, rules=SHRINE_RULES), "shop.json": dict(currency=CURRENCY, workshop_rules=WORKSHOP_RULES, workshop=WORKSHOP, run_packs=RUN_PACKS, cosmetics=COSMETICS), "swarm.json": SWARM, "bosses.json": BOSSES, "biomes.json": [dict(b, palette=PALETTES[b["id"]]) for b in BIOMES], "style.json": STYLE,
             "challenges.json": CHALLENGES, "skins.json": SKINS, "modes.json": MODES}
    for n, d in files.items():
        (DATA / n).write_text(json.dumps(d, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")

def md():
    L = []
    P = L.append
    P("# CONTENT: festes Inhaltskonzept\n")
    P("Alle Zahlen sind **Startwerte aus einer Modellrechnung**, nicht aus gespielten Runs. Sie werden später mit einer Headless-Simulation (Bot-Läufe) justiert. Diese Datei wird von `tools/build_content.py` erzeugt, die Quelle der Wahrheit sind die JSON-Dateien in `data/`. IDs nie ohne Rückfrage ändern.\n")
    P("## Lauf und Schwierigkeit\n")
    P("""- **Eine Arena, keine Portale, keine Stufenwechsel.** Die Arena wächst über die Zeit: neue Mob-Arten, Biom-Bosse, später die Schwarmflut. Das Vorbild beim Schwierigkeitsaufbau ist Megabonk (ohne dessen Portale und Stufen).
- Welle alle **30 s**, ohne Pause. Level-ups pausieren das Spiel.
- **Schwierigkeit = Zeit x Entscheidungen.** Zeit: Budget je Welle `w` = `10 + 5,5*w + 0,22*w²`, Gegner-HP `x (1 + 0,10*m + 0,012*m²)`, Schaden `x (1 + 0,05*m + 0,004*m²)`, Tempo `x (1 + 0,01*m)` bis 1,2 (m = Minuten). Entscheidungen: Schreine erhöhen einen Schwierigkeitsfaktor `D` dauerhaft. `D` wirkt auf Gegnerzahl, Spawnrate und Gegnerschaden. Dafür steigen XP und Punkte um `1 + 0,8*(D-1)`. Die Schwierigkeit steht als Prozentwert im HUD. Höchstens 350 Gegner gleichzeitig.
- **Mehrfach-Skalierung wie bei Megabonk:** Gleiche Quellen addieren sich, verschiedene multiplizieren sich (Schaden x Krit x Angriffstempo). So entsteht die steile Kurve, in der Builds den Unterschied machen.
- **Bossplan:** Mini-Boss mit eigener Lebensleiste bei **2:00** und **12:30**. Biom-Bosse: **5:00** Ildra (Wald), **7:30** Skarra (Wüste), **10:00** Kalthorn (Eis), **15:00** Ignarok (Lava), jeder in seiner Zone. Elite alle 5 Wellen (2:30, 5:00 ...). Der Fluchstein verdoppelt Bossauftritte.
- **Endboss per Altar:** Ab **10:00** kann der Boss-Altar in der Lichtung aktiviert werden. Er ruft **Den Schnitter** (HP `30000 x HP-Faktor zur Beschwörungszeit`, nach 90 s Wutphase). Früher rufen heißt weniger Upgrades, aber schwächerer Boss, später heißt stärker und stärkerer Boss. Sieg beendet den Lauf (+20000 Punkte), danach optional weiterspielen.
- **Schwarmflut ab 20:00** (wenn der Schnitter nicht schon besiegt ist): fliegende Flutgeister in Schüben alle 3 s, Schubgröße +10 % pro Minute, Tempo +8 % pro Minute, Punktemultiplikator von x1 bis x8 (+1 je 45 s). Die Skalierung endet nie: Es bleibt möglich, wird aber immer schwerer.
- **Machbarkeitsregeln:** glatte Kurve ohne Sprünge, jeder gefährliche Angriff hat eine Vorwarnung, jeder Boss hat ein klares Muster, nichts ist unverwundbar außer kurzen Phasen.
- **Zielkurve (Ziel, nicht gemessen):** Einsteiger sterben bei 3 bis 5 min, Geübte bei 8 bis 12, Experten bei 14 bis 18, 20:00 erreicht kaum jemand.
""")
    rows, hpc = balance_rows()
    P(f"### Modellrechnung (Ø {hpc:.1f} HP je Budgetpunkt, alles wird getötet)\n")
    P("| Minute | Welle | Budget | HP x | Schaden x | nötige HP/s | Level (ca.) | XP gesamt |\n|---|---|---|---|---|---|---|---|")
    for r in rows:
        if r["minute"] in (1, 2.5, 5, 7.5, 10, 12.5, 15, 17.5, 20):
            P(f"| {r['minute']:g} | {r['wave']} | {r['budget']:.0f} | {r['hp_mult']:.1f} | {r['dmg_mult']:.1f} | {r['spawn_hp_per_s']:.0f} | {r['level']} | {r['cum_xp']:.0f} |")
    P("\nDie Spalte „nötige HP/s“ ist die Leistung, die du brauchst, um alles Erscheinende zu töten. Ein Start-Jäger macht rund 19 Schaden pro Sekunde auf ein Ziel. Das Spiel soll so gebaut sein, dass starke Builds (Flächenschaden, Durchschlag, Ketten) diese Kurve bis etwa Minute 14 bis 18 halten können.\n")
    P("## Charaktere (10)\n")
    P("| Name | Spielstil | HP | Tempo | Schaden | Schuss/s | Reichweite | Krit | Waffe | Passiv | Fertigkeit | Freischaltung | Phase |\n|---|---|---|---|---|---|---|---|---|---|---|---|---|")
    chal_text = {c["id"]: c["text"] for c in CHALLENGES}
    for c in CHARACTERS:
        P(f"| **{c['name']} {c['title']}** (`{c['id']}`) | {c['archetype']} | {c['hp']} | {c['speed']} | {c['damage']} | {c['attack_rate']} | {c['range']} | {c['crit_chance']} % | {c['weapon']['text']} | **{c['passive']['name']}**: {c['passive']['text']} | **{c['active']['name']}** ({c['active']['cooldown_s']} s): {c['active']['text']} | {chal_text[c['unlock_challenge']] if c['unlock_challenge'] else 'von Anfang an'} | {c['impl_phase']} |")
    P("\nZwei Skins je Charakter (reine Farbvarianten, Freischaltung: Minute 10 bzw. 15 mit diesem Charakter): " + "; ".join(f"{c['name']}: {SKIN_NAMES[c['id']][0]} / {SKIN_NAMES[c['id']][1]}" for c in CHARACTERS) + ".\n")
    P("## Optik und Effekte (Pixel-Art)\n")
    P("Stil: Pixel-Art, begrenzte Palette, **Effekte sind das Aushängeschild** (siehe `DESIGN.md` Abschnitt 16 für Auflösung und Regeln).\n")
    P("| Charakter | Projektil | Treffer | Fertigkeit |\n|---|---|---|---|")
    for c in CHARACTERS:
        v = VFX[c["id"]]
        P(f"| {c['name']} | {v['projectile']} | {v['impact']} | {v['ability']} |")
    P("\nAllgemein: " + "; ".join(VFX_GLOBAL) + ".\n")
    P("## Upgrades (50)\n")
    P("Auswahl: Gewichte gewöhnlich 60, ungewöhnlich 25, selten 10, episch 4, legendär 1. Jeder Punkt Glück verschiebt 0,4 % Gewicht von den unteren zu den oberen Stufen. Bei Level-up 3 Karten, Elitetruhen bieten mindestens „selten“, Bosstruhen „episch“ oder „legendär“. Upgrades haben Stufen (Stapel bis `max_level`). Gewichtung nach Charakter-Tags.\n")
    names = {"common": "Gewöhnlich", "uncommon": "Ungewöhnlich", "rare": "Selten", "epic": "Episch", "legendary": "Legendär"}
    for r in ("common", "uncommon", "rare", "epic", "legendary"):
        P(f"### {names[r]}\n")
        P("| ID | Name | Max. Stufe | Effekt | Tags | Freischaltung | Phase |\n|---|---|---|---|---|---|---|")
        for u in [u for u in UPGRADES if u["rarity"] == r]:
            P(f"| `{u['id']}` | {u['name']} | {u['max_level']} | {u['text']} | {', '.join(u['tags'])} | {'von Anfang an' if u['unlocked_at_start'] else chal_text[u['unlock_challenge']]} | {u['impl_phase']} |")
        P("")
    P("## Mob-Typen (10)\n")
    P("| ID | Name | Verhalten | HP | Tempo | Schaden | Kosten | XP | ab Sek. | Biom | Beschreibung | Phase |\n|---|---|---|---|---|---|---|---|---|---|---|---|")
    for m in MOBS:
        main = max(m["biome_weights"], key=m["biome_weights"].get) if m["biome_weights"].get("forest", 1) != 1 or m["id"] not in ("slimeling", "batswarm") else "alle"
        P(f"| `{m['id']}` | {m['name']} | {m['behavior']} | {m['hp']} | {m['speed']} | {m['damage']} | {m['cost']} | {m['xp']} | {m['min_time_s']} | {main} | {m['text']} | {m['impl_phase']} |")
    P("\nSpawn: Position bestimmt das Biom, dort gewichtet `biome_weights` die Mob-Auswahl (nur Mobs mit `min_time_s` erreicht). Gruppen (`group_size`) kosten ihr Budget einmal je Gegner.\n")
    P("### Elite-Gegner\n")
    P(f"HP x{ELITE['hp_mult']}, Schaden x{ELITE['damage_mult']}, XP x{ELITE['xp_mult']}, Größe x{ELITE['size_mult']}, lässt eine Elitetruhe fallen. Affixe (1 ab Start, 2 ab Minute 10, 3 ab Minute 15): " + "; ".join(f"**{a['name']}** ({a['text']})" for a in ELITE_AFFIXES) + ".\n")
    P(f"### Mini-Boss\n\nBei {MINI_BOSS['times_s'][0] // 60}:{MINI_BOSS['times_s'][0] % 60:02d} und {MINI_BOSS['times_s'][1] // 60}:{MINI_BOSS['times_s'][1] % 60:02d}: {MINI_BOSS['pick']}, HP x{MINI_BOSS['hp_mult']}, Schaden x{MINI_BOSS['damage_mult']}, XP x{MINI_BOSS['xp_mult']}, Größe x{MINI_BOSS['size_mult']}, eigene Lebensleiste, lässt eine Boss-Truhe (mindestens \"selten\") fallen.\n")
    P("### Schreine (Risiko gegen Belohnung)\n")
    P("| Schrein | Anzahl | Aktivierung | Schwierigkeit | Effekt | Belohnung | Phase |\n|---|---|---|---|---|---|---|")
    for sh in SHRINES:
        P(f"| **{sh['name']}** (`{sh['id']}`) | {sh['count']} | {sh['channel_s']} s im Radius {sh['radius_px']} px | +{sh['difficulty_add'] * 100:g} % | {sh['effect']} | {sh['reward']} | {sh['impl_phase']} |")
    P("\n" + SHRINE_RULES + "\n")
    P("### Schwarmflut (ab 20:00)\n")
    P(f"{SWARM['text']} Flutgeist: HP {SWARM['hp']}, Tempo {SWARM['speed']}, Schaden {SWARM['damage']}, fliegt und ignoriert Hindernisse. Schub alle {SWARM['burst_every_s']} s mit {SWARM['burst_size_base']} Gegnern (+{SWARM['burst_growth_pct_per_min']} % je Minute), Tempo +{SWARM['speed_gain_pct_per_min']} % je Minute. Punktemultiplikator x{SWARM['score_mult_start']}, +{SWARM['score_mult_gain_per_45s']} je 45 s, höchstens x{SWARM['score_mult_cap']}. HP und Schaden skalieren weiter wie bei normalen Gegnern.\n")
    P("### Bosse\n")
    for b in BOSSES:
        tm = f"{b['spawn_time_s'] // 60}:{b['spawn_time_s'] % 60:02d}" if b.get("spawn_time_s") else f"per Altar ab {b['altar_unlock_s'] // 60}:{b['altar_unlock_s'] % 60:02d}"
        hp = f"HP {b['hp']}, " if b.get("hp") else (f"HP {b['hp_base']} x HP-Faktor, Wutphase nach {b['enrage_after_s']} s, " if b.get("hp_base") else "")
        P(f"- **{b['name']}** (`{b['id']}`, {tm}, Phase {b['impl_phase']}): " + hp + "; ".join(f"ab {p['at_hp_pct']} % HP: {p['pattern']}" for p in b["phases"]) + ".")
    P("\n## Arena und Biome (60 x 60 Felder à 32 px)\n")
    P("| ID | Name | Bereich (x, y, Breite, Höhe in Feldern) | Effekt | Phase |\n|---|---|---|---|---|")
    for b in BIOMES:
        P(f"| `{b['id']}` | {b['name']} | {b['rect_tiles']} | {b['effect']} | {b.get('impl_phase', 1)} |")
    P("\nLayout: Lichtung in der Mitte (16 x 16, überlagert die Quadranten), Wald oben links, Wüste oben rechts, Eis unten links, Lava unten rechts. Hindernisse sind pro Biom mit festem Seed verteilt.\n")
    P("Biom-Farben (Pastell): " + "; ".join(f"{b['name']}: Boden {PALETTES[b['id']]['ground']}, Details {PALETTES[b['id']]['detail']}" for b in BIOMES) + ". Gefahren (Lava, Sand, Eisglanz) heben sich über die Farbe `hazard` ab.\n")
    P("## Punkte\n")
    P("`Punkte = 2 x Sekunden + 5 x Kills + 20 x Level + 500 x Bosse` (Sieg über den Schnitter +20000; in der Schwarmflut +1000 je 10 s mal Flut-Multiplikator, der Schwierigkeitsfaktor erhöht die Punkte). Highscore je Charakter und gesamt, lokal gespeichert. Modus „Ewige Nacht“ (nach Challenge „Erreiche 20:00“): Gegner-HP x1,5, XP x1,25, Punkte x1,5.\n")
    P("## Funkelsteine, Werkstatt und Startpakete (Meta-Währung)\n")
    P(f"**{CURRENCY['name']}** (`{CURRENCY['id']}`): {CURRENCY['payout']} Drops im Lauf: normale Gegner {CURRENCY['run_drops']['normal_kill_chance_pct']} % Chance auf 1, Elite {CURRENCY['run_drops']['elite']}, Mini-Boss {CURRENCY['run_drops']['mini_boss']}, Biom-Boss {CURRENCY['run_drops']['biome_boss']}, Schnitter {CURRENCY['run_drops']['final_boss']}, Sieg +{CURRENCY['run_drops']['victory_bonus']}, Truhen {CURRENCY['run_drops']['chest']}. Challenges zahlen zusätzlich aus (Feld `reward.stones`). {CURRENCY['estimates']} {CURRENCY['shown_at_run_end']}\n")
    P("### Werkstatt (dauerhafte Mini-Verbesserungen)\n")
    P(f"Kosten je Stufe: `{WORKSHOP_RULES['cost']}`. {WORKSHOP_RULES['note']}\n")
    P("| ID | Name | Effekt | Max. Stufe | Grundpreis | Gesamtpreis |\n|---|---|---|---|---|---|")
    tot = 0
    for w_ in WORKSHOP:
        cost = sum(round(w_["base_cost"] * 1.5 ** (l - 1)) for l in range(1, w_["max_level"] + 1)); tot += cost
        P(f"| `{w_['id']}` | {w_['name']} | {w_['text']} | {w_['max_level']} | {w_['base_cost']} | {cost} |")
    P(f"\nAlle Werkstatt-Stufen zusammen kosten {tot} Funkelsteine. Bei etwa 60 Funkelsteinen je Lauf sind das rund {round(tot / 60)} Läufe, also ein langes, aber freiwilliges Ziel.\n")
    P("### Startpakete (vor dem Lauf, verbrauchen sich)\n")
    P(f"Höchstens {RUN_PACKS['max_per_run']} je Lauf. " + "; ".join(f"**{x['name']}** ({x['cost']}): {x['effect']}" for x in RUN_PACKS["items"]) + ".\n")
    P(f"### Farbtöpfe (Kosmetik)\n\n{COSMETICS['text']} {COSMETICS['per_character']} Varianten je Charakter ({', '.join(v['name'] for v in COSMETICS['variants'])}) für je {COSMETICS['cost_each']} Funkelsteine, zusammen {COSMETICS['cost_each'] * COSMETICS['per_character'] * 10}.\n")
    P(f"## Challenges ({len(CHALLENGES)})\n")
    P("| ID | Aufgabe | Belohnung |\n|---|---|---|")
    for c in CHALLENGES:
        r = c["reward"]
        P(f"| `{c['id']}` | {c['text']} | {r['type']}: {r['id']} |")
    P("\n## Umsetzungsphasen (Vertical Slice zuerst)\n")
    P("- **Phase 1:** Jäger, 12 Upgrades (Phase 1), Mobs Schleimling, Fledermaus, Wurzelwächter, Sporenschütze, Biom Wald plus Lichtung, Boss Ildra. Spielbar von 0 bis 5:00.\n- **Phase 2:** Pyro, Schurke, Wächter, Frost; restliche gewöhnliche/ungewöhnliche/seltene Upgrades; Wüste und Eis; Skarra, Kalthorn; Mini-Boss, Gier-Schreine, Schwarmflut; Profil, Challenges, Skins.\n- **Phase 3:** Beschwörer, Sturm, Sprengmeister, Gift, Scharfschütze; epische und legendäre Upgrades; Lava; Ignarok; Boss-Altar mit dem Schnitter, Mut-Schrein, Fluchstein, Elite-Schrein; RL-Umgebung.\n")
    return "\n".join(L) + "\n"

if __name__ == "__main__":
    errs = validate()
    if errs:
        print("FEHLER:"); [print(" -", e) for e in errs]; sys.exit(1)
    write_json(); DOCS.mkdir(exist_ok=True); (DOCS / "CONTENT.md").write_text(md(), encoding="utf-8")
    ph = lambda L: {p: sum(1 for x in L if x["impl_phase"] == p) for p in (1, 2, 3)}
    print("OK: 10 Charaktere, 50 Upgrades (18/14/9/6/3), 10 Mobs,", len(BOSSES), "Bosse, 5 Biome,", len(CHALLENGES), "Challenges,", len(SKINS), "Skins")
    print("Phasen  Charaktere:", ph(CHARACTERS), " Upgrades:", ph(UPGRADES), " Mobs:", ph(MOBS))
    print("Start freigeschaltet: Upgrades", sum(u["unlocked_at_start"] for u in UPGRADES), "von 50")
