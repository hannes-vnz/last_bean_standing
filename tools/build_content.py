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
    "tick_hz": 60, "wave_interval_s": 18, "max_wave": 40, "swarm_time_s": 300, "max_alive_enemies": 350,
    "budget": {"base": 40, "linear": 7.0, "quadratic": 0.22},           # je Welle w: base + linear*w + quadratic*w^2 (mehr Gegner früh, seit 28.10.2026)
    "hp_mult": {"linear": 0.17, "quadratic": 0.033},                     # 1 + a*m + b*m^2, m = Minuten (28.10.2026: Beete 3:00, Tempo x5/3)
    "damage_mult": {"linear": 0.085, "quadratic": 0.011},
    "speed_mult": {"linear": 0.017, "cap": 1.2},
    "xp_to_next": {"base": 2, "linear": 1.2, "quadratic": 0.12},        # Level L -> L+1 (Paket F: noch schnellere Level)
    "elite_every_n_waves": 5, "boss_waves": {},                         # Bosse kommen seit Paket F je Beet (stages.json)
    "spawn_distance_px": [520, 700], "arena_tiles": [120, 120], "tile_px": 32,
    "player_base": {"hp": 100, "pickup_radius_px": 220, "i_frames_s": 0.6},
    "score": {"per_second": 2, "per_kill": 5, "per_level": 20, "per_boss": 500, "victory_bonus": 20000, "swarm_per_10s": 1000},
    "rarity_weights": {"common": 60, "uncommon": 25, "rare": 10, "epic": 4, "legendary": 1},
    "luck_shift_per_point": 0.4, "level_up_choices": 3, "elite_chest_min_rarity": "rare",
    # Paket F: jede Karte beim Level-up bekommt eine eigene Seltenheit; sie vervielfacht den Wert (wie Megabonk-Bücher).
    "card_tier_mult": {"common": 1.0, "uncommon": 1.3, "rare": 1.7, "epic": 2.2, "legendary": 3.0},
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
# 28.10.2026 (Hannes: "Monster und Hero schneller"): Lauftempo aller Charaktere und Mobs x1,25.
def ch(id, name, title, arch, hp, speed, dmg, rate, rng, crit, weapon, passive, active, tags, unlock, phase, skins):
    return dict(id=id, name=name, title=title, archetype=arch, hp=hp, speed=speed, damage=dmg, attack_rate=rate,
                range=rng, crit_chance=crit, crit_mult=1.5, weapon=weapon, passive=passive, active=active,
                tags=tags, unlock_challenge=unlock, impl_phase=phase, skins=skins)

CHARACTERS = [
 ch("ranger", "Fenn", "der Falkenauge", "Jäger: ausgewogen, durchschlagende Pfeile", 100, 225, 12, 2.0, 380, 5,
    dict(type="projectile", pattern="single", projectile_speed=640, pierce=1, aoe_radius=0, text="Ein Pfeil, durchschlägt 1 Gegner."),
    dict(id="far_sight", name="Weitblick", text="+12 % Reichweite. +8 % Schaden auf Ziele über 250 px.", effects=[dict(stat="range_pct", value=12), dict(stat="damage_pct_far", value=8, threshold_px=250)]),
    dict(id="arrow_storm", name="Pfeilhagel", cooldown_s=18, text="16 Pfeile in alle Richtungen (je 60 % Schaden)."),
    ["projectile", "pierce", "range"], None, 1, ["ranger_a", "ranger_b"]),
 ch("pyro", "Mira", "Aschenglut", "Pyromantin: Flächenschaden und Brand", 80, 175, 14, 1.1, 320, 5,
    dict(type="projectile", pattern="single_explosive", projectile_speed=420, pierce=0, aoe_radius=64, text="Feuerball explodiert (Radius 64) und entzündet (3 s, 20 % Schaden/s)."),
    dict(id="heat_wave", name="Hitzewelle", text="Brennende Gegner erleiden +20 % Schaden.", effects=[dict(stat="damage_pct_vs_burning", value=20)]),
    dict(id="inferno", name="Inferno", cooldown_s=22, text="Feuerring (Radius 180) um dich, 4 s, 40 % Schaden/s."),
    ["fire", "area", "burn"], "unlock_pyro", 2, ["pyro_a", "pyro_b"]),
 ch("rogue", "Kaz", "Nachtmesser", "Schurke: schnell, kritisch, kurze Reichweite", 85, 238, 7, 2.2, 210, 20,
    dict(type="projectile", pattern="fan3", projectile_speed=700, pierce=0, aoe_radius=0, text="Fächer aus 3 Wurfmessern."),
    dict(id="thrill", name="Nervenkitzel", text="+15 % Lauftempo. +6 % Schaden je Gegner im Umkreis 150 px (max. 5).", effects=[dict(stat="move_speed_pct", value=15), dict(stat="damage_pct_per_nearby", value=6, radius_px=150, max_stacks=5)]),
    dict(id="shadow_step", name="Schattenschritt", cooldown_s=5, text="Dash über 220 px, 0,3 s unverwundbar."),
    ["crit", "movement", "close"], "unlock_rogue", 2, ["rogue_a", "rogue_b"]),
 ch("guardian", "Brun", "Eisenschulter", "Wächter: Nahkampf-Tank mit Dornen", 160, 150, 20, 0.9, 110, 0,
    dict(type="nova", pattern="shockwave", projectile_speed=0, pierce=99, aoe_radius=110, text="Schockwelle um dich (Radius 110) mit Rückstoß."),
    dict(id="iron_skin", name="Eisenhaut", text="-15 % erlittener Schaden. Reflektiert 25 % des Nahkampfschadens.", effects=[dict(stat="damage_taken_pct", value=-15), dict(stat="thorns_pct", value=25)]),
    dict(id="bulwark", name="Bollwerk", cooldown_s=25, text="Schild für 3 s, absorbiert 150 Schaden."),
    ["defense", "thorns", "area", "melee"], "unlock_guardian", 2, ["guardian_a", "guardian_b"]),
 ch("cryo", "Ysa", "Winterhauch", "Frostmagierin: Kontrolle und Verlangsamung", 90, 181, 10, 1.3, 340, 5,
    dict(type="projectile", pattern="single", projectile_speed=520, pierce=0, aoe_radius=0, text="Frostgeschoss verlangsamt um 30 % (2 s). 3 Kältestapel frieren 1,2 s ein."),
    dict(id="frost_aura", name="Frostaura", text="Gegner im Umkreis von 140 px sind 15 % langsamer.", effects=[dict(stat="aura_slow_pct", value=15, radius_px=140)]),
    dict(id="ice_age", name="Eiszeit", cooldown_s=24, text="Friert alle Gegner im Bild 2 s ein."),
    ["frost", "control", "ranged"], "unlock_cryo", 2, ["cryo_a", "cryo_b"]),
 ch("summoner", "Thorn", "Geisterruf", "Beschwörer: Begleiter kämpfen für ihn", 90, 175, 6, 1.0, 300, 5,
    dict(type="projectile_plus_minions", pattern="single", projectile_speed=480, pierce=0, aoe_radius=0, minions=2, text="Schwacher Geisterbolzen. 2 Geister-Begleiter greifen selbstständig an (8 Schaden, 1,5/s)."),
    dict(id="soul_bond", name="Seelenband", text="Geister erhalten 50 % deiner Schadensboni.", effects=[dict(stat="minion_inherit_damage_pct", value=50)]),
    dict(id="raise_dead", name="Totenruf", cooldown_s=30, text="4 zusätzliche Geister für 10 s."),
    ["summon", "minion"], "unlock_summoner", 3, ["summoner_a", "summoner_b"]),
 ch("storm", "Vex", "Donnerhall", "Sturmrufer: Kettenblitze, hohe Schussrate", 80, 200, 8, 2.4, 300, 5,
    dict(type="chain", pattern="chain_lightning", projectile_speed=0, pierce=0, aoe_radius=0, chain_jumps=2, chain_radius=160, chain_falloff=0.8, text="Kettenblitz springt 2-mal (160 px, je 80 % Schaden)."),
    dict(id="static_charge", name="Statische Ladung", text="Jeder 10. Schuss ruft einen Blitzschlag (200 % Schaden) auf einen zufälligen Gegner.", effects=[dict(stat="bonus_strike_every_n_shots", value=10, damage_pct=200)]),
    dict(id="thunderstorm", name="Gewittersturm", cooldown_s=28, text="6 s lang 4 Blitze pro Sekunde auf zufällige Gegner."),
    ["chain", "lightning", "speed"], "unlock_storm", 3, ["storm_a", "storm_b"]),
 ch("bomber", "Orm", "Zündfunke", "Sprengmeister: Bomben im Stand, Minen im Lauf", 110, 188, 26, 0.7, 300, 5,
    dict(type="lobbed", pattern="bomb", projectile_speed=300, pierce=0, aoe_radius=90, fuse_s=0.6, text="Bombe im Bogen, explodiert nach 0,6 s (Radius 90)."),
    dict(id="mine_layer", name="Minenleger", text="Legt beim Laufen alle 1,5 s eine Mine (60 % Schaden, Radius 70, max. 6).", effects=[dict(stat="mine_interval_s", value=1.5, damage_pct=60, radius_px=70, max_mines=6)]),
    dict(id="mega_bomb", name="Megabombe", cooldown_s=20, text="Große Bombe (Radius 200, 500 % Schaden)."),
    ["bomb", "area", "mine"], "unlock_bomber", 3, ["bomber_a", "bomber_b"]),
 ch("venom", "Lilu", "Schierling", "Giftmischerin: Giftpfützen und Seuche", 85, 188, 5, 1.4, 330, 5,
    dict(type="lobbed", pattern="vial", projectile_speed=360, pierce=0, aoe_radius=55, text="Giftphiole: Pfütze (Radius 55, 3 s, 12 Gift/s, stapelt bis 4x)."),
    dict(id="plague", name="Seuche", text="Vergiftete Gegner verbreiten beim Tod Gift (Radius 80).", effects=[dict(stat="poison_spread_on_death_radius_px", value=80)]),
    dict(id="toxic_cloud", name="Giftnebel", cooldown_s=26, text="Wolke (Radius 160) für 8 s, 35 % Schaden/s, verlangsamt 20 %."),
    ["poison", "area", "dot"], "unlock_venom", 3, ["venom_a", "venom_b"]),
 ch("sniper", "Aya", "Stillstand", "Scharfschützin: je länger sie steht, desto härter", 75, 162, 40, 0.45, 600, 10,
    dict(type="projectile", pattern="charged", projectile_speed=1100, pierce=3, aoe_radius=0, charge_bonus_per_s_pct=10, charge_max_pct=100, text="Durchschlag-Schuss (3). +10 % Schaden je Sekunde Stillstand (max. +100 %)."),
    dict(id="calm_before", name="Ruhe vor dem Schuss", text="Nach 2 s Stillstand ist der nächste Schuss ein garantierter Krit (x2,5).", effects=[dict(stat="guaranteed_crit_after_still_s", value=2, crit_mult=2.5)]),
    dict(id="focus", name="Fokus", cooldown_s=20, text="4 s lang: schießt auch im Lauf, doppelte Schussrate."),
    ["crit", "pierce", "stillness"], "unlock_sniper", 3, ["sniper_a", "sniper_b"]),
]


# Paket H (28.10.2026, Hannes: "5 weitere Charaktere mit ganz unterschiedlichen Skillsets"): Mira, Kaz, Brun, Ysa
# und Vex sind spielbar und von Anfang an frei (die Freischalt-Challenges geben dafür Titel).
PLAYABLE_H = {"pyro": "Glutfreund", "rogue": "Schattenläufer", "guardian": "Schildbohne", "cryo": "Frostherz", "storm": "Donnerbohne"}
for _c in CHARACTERS:
    if _c["id"] in PLAYABLE_H:
        _c["impl_phase"], _c["unlock_challenge"] = 1, None
next(c for c in CHARACTERS if c["id"] == "pyro")["weapon"].update(ignite_s=3, ignite_pct=20)
next(c for c in CHARACTERS if c["id"] == "cryo")["weapon"].update(slow_pct=30, slow_s=2, freeze_stacks=3, freeze_s=1.2)

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
 # Paket F (28.10.2026): alle umgesetzten Boni wirken über Stat-Schlüssel und sind von Anfang an im Pool.
 # Werte gelten für eine gewöhnliche Karte; die Kartenseltenheit vervielfacht sie (card_tier_mult).
 # --- gewöhnlich (18)
 up("sharp_edges", "Geschärfte Spitzen", "common", 5, ["damage"], "+8 % Schaden je Stufe.", [S("damage_pct", 8)], True, 1),
 up("quick_hands", "Flinke Hände", "common", 5, ["speed"], "+7 % Angriffstempo je Stufe.", [S("attack_speed_pct", 7)], True, 1),
 up("long_reach", "Weitsicht", "common", 4, ["range"], "+10 % Reichweite je Stufe.", [S("range_pct", 10)], True, 1),
 up("keen_eye", "Scharfblick", "common", 5, ["crit"], "+4 % Krit-Chance je Stufe.", [S("crit_chance_pct", 4)], True, 1),
 up("vitality", "Lebenskraft", "common", 5, ["defense"], "+15 Max-HP je Stufe (heilt um 15).", [S("max_hp_flat", 15)], True, 1),
 up("thick_skin", "Dicke Haut", "common", 4, ["defense"], "-6 % erlittener Schaden je Stufe.", [S("damage_taken_pct", -6)], True, 1),
 up("swift_feet", "Flinke Füße", "common", 5, ["movement"], "+6 % Lauftempo je Stufe.", [S("move_speed_pct", 6)], True, 1),
 up("magnet", "XP-Magnet", "common", 4, ["utility"], "+30 % Aufsammelradius je Stufe.", [S("pickup_radius_pct", 30)], True, 1),
 up("quick_learner", "Schnelle Auffassung", "common", 4, ["utility"], "+10 % XP je Stufe.", [S("xp_gain_pct", 10)], True, 1),
 up("heal_orbs", "Heilkugeln", "common", 3, ["defense", "utility"], "Gegner lassen mit 3 % je Stufe Heilkugeln fallen (15 HP).", [S("heal_orb_chance_pct", 3)], True, 1),
 up("wide_blast", "Breite Wirkung", "common", 4, ["area"], "+12 % Flächenradius je Stufe (Waffen, Explosionen, Aura).", [S("area_pct", 12)], True, 1),
 up("thorns", "Dornenpanzer", "common", 4, ["defense", "thorns"], "Reflektiert 40 % des erlittenen Nahkampfschadens je Stufe.", [S("thorns_pct", 40)], True, 1),
 up("big_shots", "Schwere Geschosse", "common", 3, ["projectile"], "+25 % Geschossgröße je Stufe (trifft leichter).", [S("projectile_size_pct", 25)], True, 1),
 up("fast_shots", "Schnelle Geschosse", "common", 3, ["projectile"], "+15 % Geschosstempo und +5 % Schaden je Stufe.", [S("projectile_speed_pct", 15), S("damage_pct", 5)], True, 1),
 up("dodge", "Ausweichen", "common", 5, ["defense"], "4 % Chance je Stufe, einem Treffer zu entgehen.", [S("dodge_chance_pct", 4)], True, 1),
 up("armor_plating", "Panzerplatten", "common", 4, ["defense"], "-1 Schaden je Treffer und Stufe (mindestens 1).", [S("flat_damage_reduction", 1)], True, 1),
 up("lucky_charm", "Glücksklee", "common", 4, ["utility"], "+1 Glück je Stufe: seltenere Karten, Items und Krits.", [S("luck", 1)], True, 1),
 up("bounty_hunter", "Kopfgeldjäger", "common", 4, ["damage"], "+12 % Schaden gegen Elites und Bosse je Stufe.", [S("elite_damage_pct", 12)], True, 1),
 # --- ungewöhnlich (14)
 up("brutal_crits", "Brutale Treffer", "uncommon", 4, ["crit"], "+20 % Krit-Schaden je Stufe (Basis 150 %).", [S("crit_mult_add_pct", 20)], True, 1),
 up("double_shot", "Mehrfachangriff", "uncommon", 3, ["projectile"], "+1 zusätzlicher Angriff je Stufe (60 % Schaden, leichte Streuung).", [S("extra_attacks", 1)], True, 1),
 up("piercing", "Durchschlag", "uncommon", 3, ["pierce", "projectile"], "Geschosse durchbohren +1 Gegner je Stufe.", [S("pierce_add", 1)], True, 1),
 up("heavy_hitter", "Schwergewicht", "uncommon", 3, ["damage"], "+25 % Schaden, -10 % Angriffstempo je Stufe.", [S("damage_pct", 25), S("attack_speed_pct", -10)], True, 1),
 up("regeneration", "Regeneration", "uncommon", 4, ["defense"], "+0,6 HP pro Sekunde je Stufe.", [S("regen_per_s", 0.6)], True, 1),
 up("reroll", "Neuwurf", "uncommon", 3, ["utility"], "+1 Neu würfeln je Stufe (sofort).", [S("rerolls", 1)], True, 1),
 up("banish", "Verbannung", "uncommon", 3, ["utility"], "+1 Verbannen je Stufe (sofort).", [S("banishes", 1)], True, 1),
 up("stillness", "Meditation", "uncommon", 3, ["stillness", "damage"], "+15 % Schaden im Stand je Stufe.", [S("standing_damage_pct", 15)], True, 1),
 up("ignite", "Entzünden", "uncommon", 4, ["fire", "elemental"], "10 % Chance je Stufe zu entzünden (3 s, 30 % Schaden/s).", [S("ignite_chance_pct", 10)], True, 1),
 up("chill", "Kälte", "uncommon", 4, ["frost", "elemental"], "Treffer verlangsamen um 8 % je Stufe für 2 s (max. 60 %).", [S("chill_slow_pct", 8)], True, 1),
 up("toxin", "Toxin", "uncommon", 4, ["poison", "elemental"], "Treffer vergiften (12 % Schaden/s je Stufe, 3 s, stapelt bis 4x).", [S("poison_pct_per_s", 12)], True, 1),
 up("shock", "Schock", "uncommon", 3, ["lightning", "elemental"], "12 % Chance je Stufe auf einen Blitz (60 % Schaden), der auf 2 nahe Gegner springt.", [S("shock_chance_pct", 12)], True, 1),
 up("minion_horde", "Gefolgschaft", "uncommon", 3, ["summon"], "+1 Begleiter je Stufe (ohne Beschwörer: Irrlicht mit 50 % Schaden).", [S("minions_add", 1)], False, 3, "unlock_up_minion_horde"),
 up("orbiting_blades", "Kreisende Klingen", "uncommon", 4, ["area", "melee"], "Eine zusätzliche Klinge je Stufe umkreist dich (6 Schaden).", [S("orbit_blades", 1)], False, 3, "unlock_up_orbiting_blades"),
 # --- selten (9)
 up("ricochet", "Rückprall", "rare", 3, ["bounce", "projectile"], "Geschosse springen +1-mal je Stufe auf einen nahen Gegner.", [S("bounce_add", 1)], True, 1),
 up("executioner", "Henker", "rare", 3, ["damage"], "+30 % Schaden gegen Gegner unter 30 % HP je Stufe.", [S("execute_damage_pct", 30)], True, 1),
 up("lifesteal", "Aderlass", "rare", 3, ["defense", "damage"], "Heilt 2 % des verursachten Schadens je Stufe.", [S("lifesteal_pct", 2)], True, 1),
 up("shield_burst", "Notschild", "rare", 3, ["defense"], "Alle 12 s ein Schild, der 25 Schaden je Stufe abfängt.", [S("shield_flat", 25)], True, 1),
 up("last_stand", "Letztes Gefecht", "rare", 3, ["defense", "damage"], "Unter 35 % HP: +30 % Schaden und +15 % Tempo je Stufe.", [S("low_hp_damage_pct", 30)], True, 1),
 up("overcharge", "Überladung", "rare", 3, ["damage"], "Alle 6 s trifft der nächste Schuss mit +200 % Schaden je Stufe.", [S("overcharge_pct", 200)], True, 1),
 up("explosive_rounds", "Sprengmunition", "rare", 3, ["area", "projectile"], "Treffer explodieren (Radius 50, 30 % Schaden je Stufe).", [S("explosive_hit_pct", 30)], True, 1),
 up("aura_of_pain", "Brennnesselkranz", "rare", 4, ["area", "melee"], "Gegner im Umkreis von 100 px erleiden 6 Schaden/s je Stufe.", [S("aura_dps", 6)], True, 1),
 up("elemental_mastery", "Elementarmeister", "rare", 3, ["elemental"], "+25 % Schaden von Brand, Gift und Blitz je Stufe.", [S("elemental_damage_pct", 25)], True, 1),
 # --- episch (6)
 up("second_wind", "Zweiter Atem", "epic", 2, ["defense"], "Einmal wiederbeleben je Stufe (mit 50 % HP, 2 s unverwundbar).", [S("revives", 1)], True, 1),
 up("gravity_well", "Schwerkraftbrunnen", "epic", 2, ["control", "area"], "Alle 12 s zieht ein Sog alle Gegner im Radius 200 zusammen (Stufe 2: Radius 280, alle 9 s).", [dict(special="gravity_pull", radius_px=[200, 280], interval_s=[12, 9])], False, 3, "unlock_up_gravity_well"),
 up("bloodlust", "Blutrausch", "epic", 3, ["speed"], "Jeder Kill: +2 % Angriffstempo für 5 s, stapelt bis +20 % je Stufe.", [S("kill_haste_max_pct", 20)], True, 1),
 up("time_warp", "Zeitdehnung", "epic", 2, ["control", "stillness"], "Im Stand sind alle Gegner im Radius 250 um 12 % / 20 % langsamer.", [dict(special="standing_slow", radius_px=250, slow_pct=[12, 20])], False, 3, "unlock_up_time_warp"),
 up("shrapnel", "Splitterhagel", "epic", 3, ["area", "projectile"], "Sterbende Gegner verschießen mit 20 % Chance je Stufe 6 Splitter (50 % Schaden).", [S("shrapnel_chance_pct", 20)], True, 1),
 up("titan_heart", "Titanenherz", "epic", 3, ["defense"], "+30 % Max-HP und +10 % Schaden je Stufe.", [S("max_hp_pct", 30), S("damage_pct", 10)], True, 1),
 # --- legendär (3)
 up("glass_cannon", "Glaskanone", "legendary", 1, ["damage"], "+100 % Schaden, -40 % Max-HP.", [S("damage_pct", 100), S("max_hp_pct", -40)], True, 1),
 up("reaper_pact", "Pakt der Sense", "legendary", 1, ["damage", "defense"], "Jeder Kill heilt 1 HP, 25 % Chance auf eine Explosion beim Kill.", [S("heal_per_kill", 1), S("explode_on_kill_pct", 25)], True, 1),
 up("elemental_storm", "Elementarsturm", "legendary", 1, ["elemental"], "Je 15 % Chance auf Brand und Blitz, Gift und Kälte bei jedem Treffer, +50 % Elementarschaden.", [S("ignite_chance_pct", 15), S("shock_chance_pct", 15), S("poison_pct_per_s", 10), S("chill_slow_pct", 10), S("elemental_damage_pct", 50)], True, 1),
]

# ---------------------------------------------------------------------------- Mobs, Elite, Bosse, Biome
def mob(id, name, beh, hp, speed, dmg, cost, xp, min_t, biomes, text, phase, **extra):
    return dict(id=id, name=name, behavior=beh, hp=hp, speed=speed, damage=dmg, cost=cost, xp=xp, min_time_s=min_t,
                biome_weights=biomes, text=text, impl_phase=phase, **extra)
# Paket F (28.10.2026): Gartenplagen und verpestetes Gemüse, je Beet eigene Gewichte. min_time_s zählt ab Beginn des Beets.
MOBS = [
 mob("slug", "Nacktschnecke", "chaser", 12, 80, 5, 1, 1, 0, dict(seedbed=1, veggiebed=0.5, compost=0.3), "Kriecht stur auf dich zu. Die häufigste Plage.", 1, radius=12),
 mob("aphid", "Blattlaus", "swarm", 4, 160, 3, 0.4, 0.4, 12, dict(seedbed=0.8, veggiebed=0.6, compost=0.4), "Kommt in Schwärmen zu 5, wuselt schnell und unregelmäßig.", 1, radius=8, group_size=5),
 mob("snail", "Gartenschnecke", "chaser_tank", 50, 52, 10, 4, 4, 36, dict(seedbed=0.6, veggiebed=0.4, compost=0.3), "Langsam, aber das Haus hält viel aus.", 1, radius=17),
 mob("mold", "Schimmelpilz", "ranged_lobbed", 16, 60, 4, 3, 3, 54, dict(seedbed=0.5, veggiebed=0.3, compost=0.5), "Hält 260 px Abstand und wirft Sporen, die eine Schimmelpfütze (4 Schaden/s, 3 s) hinterlassen.", 1, radius=12, keep_distance_px=260, shot_interval_s=2.4),
 mob("potato_beetle", "Kartoffelkäfer", "chaser", 18, 130, 7, 2, 2, 0, dict(veggiebed=1, compost=0.4), "Flinker Käfer, kommt im Trupp zu 3.", 1, radius=12, group_size=3),
 mob("toxic_carrot", "Giftmöhre", "charger", 30, 70, 12, 3, 3, 18, dict(veggiebed=1, compost=0.5), "Zielt 0,8 s (Warnlinie), stürmt dann 0,6 s mit Tempo 340 los und ist 1 s benommen.", 1, radius=13, telegraph_s=0.8, charge_s=0.6, charge_speed=340, recovery_s=1.0),
 mob("spray_cucumber", "Spritzgurke", "ranged_direct", 14, 70, 7, 2, 2, 36, dict(veggiebed=0.8, compost=0.6), "Hält 300 px Abstand und spritzt gerade Giftstrahlen (Tempo 280).", 1, radius=12, keep_distance_px=300, shot_interval_s=1.8, projectile_speed=280),
 mob("pest_tomato", "Pestizid-Tomate", "exploder", 10, 140, 18, 2, 2, 0, dict(compost=1, veggiebed=0.2), "Rollt auf dich zu und platzt bei Berührung (Radius 70, 18 Schaden, 0,4 s Warnung).", 1, radius=11, explosion_radius=70),
 mob("vole", "Wühlmaus", "chaser_tank", 90, 58, 14, 7, 7, 36, dict(compost=0.6, veggiebed=0.2), "Zäh und bissig, frisst sich durch alles.", 1, radius=20),
 mob("spray_shroom", "Sprühpilz", "ranged_lobbed", 18, 64, 7, 3, 3, 18, dict(compost=0.8), "Hält 280 px Abstand und sprüht Giftwolken (Radius 50, 3 s).", 1, radius=12, keep_distance_px=280, shot_interval_s=2.2),
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
SWARM = dict(start_s=300, entity="floodwisp", name="Flutgeist", hp=6, speed=75, damage=6, flying=True, ignores_obstacles=True,
             burst_every_s=3, burst_size_base=40, burst_growth_pct_per_min=10, speed_gain_pct_per_min=8,
             score_mult_start=1, score_mult_gain_per_45s=1, score_mult_cap=8, hp_damage_scaling="wie normale Gegner (hp_mult, damage_mult), setzt sich unbegrenzt fort",
             text="Seit Paket F ersetzt die Plagenflut am Ende jedes Beets (stages.json, flood) die Schwarmflut; diese Werte sind für spätere Flutgeister vorgemerkt.")
BOSSES = [
 dict(id="snail_queen", name="Schleimrun, die Schneckenkönigin", spawn_wave=7, spawn_time_s=126, hp=2400, speed=50, damage=14, biome="seedbed", impl_phase=1, summon_mob="snail",
      phases=[dict(at_hp_pct=100, pattern="Schleimring (8 Tropfen), alle 4 s"), dict(at_hp_pct=60, pattern="Schleimspur: verlangsamt dich 40 % in einem Kreis, ruft 3 Gartenschnecken"), dict(at_hp_pct=30, pattern="Schleimring doppelt so schnell, Sporenregen")],
      reward="boss_chest_epic", first_kill_challenge="boss_snail_queen"),
 dict(id="beetle_king", name="Knollgrimm, der Käferkönig", spawn_wave=7, spawn_time_s=126, hp=6000, speed=60, damage=18, biome="veggiebed", impl_phase=1, summon_mob="potato_beetle",
      phases=[dict(at_hp_pct=100, pattern="Stachelfächer (5 Geschosse, alle 3 s) und Sturmangriff nach Warnlinie (Tempo 380)"), dict(at_hp_pct=60, pattern="ruft 4 Kartoffelkäfer, Fächer mit 7 Geschossen"), dict(at_hp_pct=30, pattern="stürmt zweimal hintereinander, Fächer doppelt so schnell")],
      reward="boss_chest_epic", first_kill_challenge="boss_beetle_king"),
 dict(id="reaper", name="Der Schnitter", spawn_wave=7, spawn_time_s=126, hp=14000, speed=60, damage=24, biome="compost", impl_phase=1, summon_mob="pest_tomato",
      phases=[dict(at_hp_pct=100, pattern="Sensenring (12 Geschosse), alle 3,5 s"), dict(at_hp_pct=66, pattern="Seelenregen: 6 Einschläge mit Warnkreis (Radius 80), ruft Pestizid-Tomaten"), dict(at_hp_pct=33, pattern="Sensenring alle 2 s, stürmt nach Warnlinie")],
      reward="victory", first_kill_challenge="boss_reaper"),
]
# Paket F: drei Beete statt vier Biome. Jedes Beet ist eine eigene Karte (arena_tiles), die Startfläche bleibt frei.
BIOMES = [
 dict(id="seedbed", name="Saatbeet", effect="Hohe Stauden blockieren Geschosse (Deckung für beide Seiten)", rect_tiles=[0, 0, 120, 120], obstacles=dict(type="stalk", count=520, seed=11), impl_phase=1),
 dict(id="veggiebed", name="Gemüsebeet", effect="Kohlköpfe versperren den Weg, Geschosse fliegen darüber", rect_tiles=[0, 0, 120, 120], obstacles=dict(type="cabbage", count=380, seed=12), impl_phase=1),
 dict(id="compost", name="Komposthaufen", effect="Giftige Komposthügel versperren den Weg", rect_tiles=[0, 0, 120, 120], obstacles=dict(type="heap", count=300, seed=13), impl_phase=1),
]
PALETTES = {
 "seedbed":   dict(ground="#b98a62", detail="#a37552", hazard=None, stalk="#7ccf6a", soil="#8f6446", sprout="#9be27f"),
 "veggiebed": dict(ground="#a8d887", detail="#8fc46f", hazard=None, cabbage="#b7e39a", soil="#9a6d4c", sprout="#ffb35c"),
 "compost":   dict(ground="#8c7a6a", detail="#77665a", hazard="#b6e05a", heap="#6f5b49", soil="#5f4c3d", sprout="#c8f06a"),
}
# Ablauf eines Laufs: drei Beete à 3:00 (seit 28.10.2026, vorher 5:00). Der Boss kommt bei 2:06 des Beets; ist er besiegt, öffnet sich das Gartentor
# zum nächsten Beet (der Build bleibt). Läuft die Zeit ab, beginnt die Plagenflut: endlos, immer dichter und härter.
# Nach dem Schnitter im dritten Beet ist der Lauf gewonnen. Gegnerwerte: Grundwert x Beet-Faktor x Zeitfaktor im Beet.
STAGES = [
 dict(id="seedbed", index=1, name="Saatbeet", biome="seedbed", duration_s=180, boss="snail_queen", hp_mult=1.0, damage_mult=1.0, budget_mult=1.0, head_start_s=0,
      tagline="Die Keimlinge brauchen dich!"),
 dict(id="veggiebed", index=2, name="Gemüsebeet", biome="veggiebed", duration_s=180, boss="beetle_king", hp_mult=2.6, damage_mult=1.7, budget_mult=1.35, head_start_s=90,
      tagline="Das Gemüse ist vergiftet. Halte durch!"),
 dict(id="compost", index=3, name="Komposthaufen", biome="compost", duration_s=180, boss="reaper", hp_mult=6.0, damage_mult=2.6, budget_mult=1.7, head_start_s=108,
      tagline="Der Schnitter wartet im Kompost."),
]
# head_start_s (Paket G): spätere Beete beginnen mit so viel Wellen-Vorsprung (Gegnermenge und -arten), sonst laufen sie zu langsam an.
FLOOD = dict(name="Plagenflut", warning_s=10, budget_growth_per_10s=0.4, hp_growth_per_10s=0.15, damage_growth_per_10s=0.08, reward_growth_per_10s=0.25,
             wave_s=30, burst_base=12, burst_per_wave=8, speed_per_wave_pct=8,
             text="Läuft die Zeit eines Beets ab, beginnt die Plagenflut: alle 10 s +40 % Gegner, +15 % Gegner-HP und +8 % Schaden, ohne Ende. Dafür steigen XP und Samenkörner um +25 % je 10 s und die Flutzeit zählt Punkte: Wer zockt, wird stärker und reicher. Alle 30 s rollt eine neue Flutwelle heran: ein Ring aus 12 + 8 je Welle Gegnern direkt um dich, und alle neuen Gegner sind je Welle 8 % schneller. Das Gartentor bleibt offen, sobald der Boss besiegt ist.")
GATE = dict(radius_px=40, text="Gartentor: erscheint, wenn der Boss des Beets besiegt ist. Hineinlaufen bringt dich ins nächste Beet (volle Heilung).")

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
UC = lambda i: dict(type="title", id=PLAYABLE_H[i]) if i in PLAYABLE_H else dict(type="unlock_character", id=i)
UU = lambda i: dict(type="unlock_upgrade", id=i)
chal("unlock_pyro", "Erreiche Minute 5 mit beliebigem Charakter.", RS("minutes_survived", 5), UC("pyro"))
chal("unlock_rogue", "Räume eine Welle ab Welle 5, ohne Schaden zu nehmen.", RS("flawless_wave", 5), UC("rogue"))
chal("unlock_guardian", "Erleide insgesamt 5000 Schaden.", PS("damage_taken_total", 5000), UC("guardian"))
chal("unlock_cryo", "Besiege 300 Gegner im Komposthaufen.", PS("kills_in_biome", 300, biome="compost"), UC("cryo"))
chal("unlock_summoner", "Erreiche Level 15 in einem Run.", RS("level_reached", 15), UC("summoner"))
chal("unlock_storm", "Erreiche das zweite Beet.", RS("stage_reached", 2), UC("storm"))
chal("unlock_bomber", "Besiege insgesamt 2000 Gegner.", PS("kills_total", 2000), UC("bomber"))
chal("unlock_venom", "Verursache insgesamt 10000 Giftschaden.", PS("poison_damage_total", 10000), UC("venom"))
chal("unlock_sniper", "Besiege alle drei Beet-Bosse (Schleimrun, Knollgrimm, den Schnitter).", PS("distinct_bosses_defeated", 3), UC("sniper"))
UP_UNLOCKS = {
 "unlock_up_stillness": ("Schließe 10 Runs ab.", PS("runs_total", 10), "Ausdauernd"),
 "unlock_up_minion_horde": ("Schalte 3 Charaktere frei.", PS("characters_unlocked", 3), "minion_horde"),
 "unlock_up_orbiting_blades": ("Erreiche Level 20 in einem Run.", RS("level_reached", 20), "orbiting_blades"),
 "unlock_up_executioner": ("Besiege 25 Elite-Gegner.", PS("elite_kills_total", 25), "Elitejäger"),
 "unlock_up_lifesteal": ("Besiege insgesamt 1000 Gegner.", PS("kills_total", 1000), "Plagenschreck"),
 "unlock_up_shield_burst": ("Räume eine Welle ab Welle 8, ohne Schaden zu nehmen.", RS("flawless_wave", 8), "Unberührt"),
 "unlock_up_last_stand": ("Verbringe insgesamt 60 s mit unter 20 % HP.", PS("low_hp_seconds_total", 60), "Zähe Bohne"),
 "unlock_up_overcharge": ("Lande insgesamt 3000 kritische Treffer.", PS("crits_total", 3000), "Volltreffer"),
 "unlock_up_explosive_rounds": ("Besiege insgesamt 3000 Gegner.", PS("kills_total", 3000), "Gärtnermeister"),
 "unlock_up_second_wind": ("Besiege den ersten Boss.", PS("boss_kills_total", 1), "Beetbefreier"),
 "unlock_up_gravity_well": ("Erreiche das dritte Beet.", RS("stage_reached", 3), "gravity_well"),
 "unlock_up_bloodlust": ("Besiege 800 Gegner in einem Run.", RS("kills_in_run", 800), "Blutrausch"),
 "unlock_up_time_warp": ("Überlebe 2 Minuten Plagenflut.", RS("swarm_seconds", 120), "time_warp"),
 "unlock_up_shrapnel": ("Besiege insgesamt 10000 Gegner.", PS("kills_total", 10000), "Erntehelfer"),
 "unlock_up_titan_heart": ("Erleide 1500 Schaden in einem Run.", RS("damage_taken_run", 1500), "Dickhaut"),
 "unlock_up_glass_cannon": ("Erreiche das zweite Beet in unter 4 Minuten.", RS("stage2_before_s", 240), "Eilig"),
 "unlock_up_reaper_pact": ("Besiege insgesamt 10 Bosse.", PS("boss_kills_total", 10), "Bossbrecher"),
 "unlock_up_elemental_storm": ("Besitze Entzünden, Kälte, Toxin und Schock in einem Run.", dict(type="run_flag", flag="owns_all", ids=["ignite", "chill", "toxin", "shock"]), "Elementar"),
}
LOCKED_UPGRADES = {u["id"] for u in UPGRADES if not u["unlocked_at_start"]}
for cid, (text, cond, target) in UP_UNLOCKS.items():
    chal(cid, text, cond, UU(target) if target in LOCKED_UPGRADES else dict(type="title", id=target))
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
chal("boss_snail_queen", "Besiege Schleimrun.", PS("boss_defeated", 1, boss="snail_queen"), dict(type="title", id="Schneckenschreck"))
chal("boss_beetle_king", "Besiege Knollgrimm.", PS("boss_defeated", 1, boss="beetle_king"), dict(type="title", id="Käferknacker"))
chal("reach_swarm", "Überlebe 30 s Plagenflut.", RS("swarm_seconds", 30), dict(type="unlock_mode", id="eternal_night"))
chal("boss_reaper", "Besiege den Schnitter.", PS("boss_defeated", 1, boss="reaper"), dict(type="title", id="Sensenmeister"))
chal("shrines_5", "Aktiviere 5 Schreine in einem Run.", RS("shrines_activated", 5), dict(type="title", id="Wagemutig"))
chal("swarm_5min", "Überlebe 3 Minuten Plagenflut.", RS("swarm_seconds", 180), dict(type="title", id="Flutreiter"))

# ---------------------------------------------------------------------------- Pruefung
def validate():
    errs = []
    ids = lambda L: [x["id"] for x in L]
    for name, L in [("characters", CHARACTERS), ("upgrades", UPGRADES), ("mobs", MOBS), ("challenges", CHALLENGES), ("skins", SKINS), ("bosses", BOSSES), ("biomes", BIOMES)]:
        if len(set(ids(L))) != len(L): errs.append(f"doppelte IDs in {name}")
    if len(WORKSHOP) != 12 or any(w["max_level"] < 1 or w["base_cost"] <= 0 for w in WORKSHOP): errs.append("Werkstatt: 12 Einträge mit gültigen Werten erwartet")
    if len(SHRINES) != 4: errs.append("Schreine: 4 Arten erwartet")
    if "reaper" not in ids(BOSSES): errs.append("Endboss fehlt")
    if BALANCE["boss_waves"]: errs.append("boss_waves: Bosse stehen seit Paket F in stages.json")
    if len(STAGES) != 3: errs.append("Beete: 3 erwartet")
    for st in STAGES:
        if st["boss"] not in ids(BOSSES): errs.append(f"Beet {st['id']}: Boss unbekannt")
        if st["biome"] not in ids(BIOMES): errs.append(f"Beet {st['id']}: Biom unbekannt")
    if set(BALANCE["card_tier_mult"]) != set(BALANCE["rarity_weights"]): errs.append("card_tier_mult: jede Seltenheit braucht einen Faktor")
    for k in STAT_LABELS:
        if "{v}" not in STAT_LABELS[k]: errs.append(f"Stat-Text {k}: Platzhalter {{v}} fehlt")
    for L, what in ((UPGRADES, "per_level"), (ITEMS, "value")):
        for x in L:
            for eff in x["effects"]:
                if "stat" in eff and eff["stat"] not in STAT_LABELS and x.get("impl_phase", 1) == 1: errs.append(f"{x['id']}: kein Text für Stat {eff['stat']}")
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
    item_ids = ids(ITEMS)
    if len(set(item_ids)) != len(item_ids): errs.append("doppelte IDs in items")
    if set(i["rarity"] for i in ITEMS) - set(BALANCE["rarity_weights"]): errs.append("Items: unbekannte Seltenheit")
    if len(set(ids(WEAPONS))) != len(WEAPONS): errs.append("doppelte IDs in weapons")
    for w_ in WEAPONS:
        if w_["kind"] not in WEAPON_KINDS: errs.append(f"Waffe {w_['id']}: unbekannte Art")
        if w_["rarity"] not in BALANCE["rarity_weights"]: errs.append(f"Waffe {w_['id']}: unbekannte Seltenheit")
        if set(w_["per_level"]) - set(w_["base"]): errs.append(f"Waffe {w_['id']}: per_level ohne Grundwert")
        if "damage" not in w_["base"] or w_["base"].get("cooldown_s", 0) <= 0: errs.append(f"Waffe {w_['id']}: Schaden und Abklingzeit nötig")
        lv = w_["base"]["cooldown_s"] + w_["per_level"].get("cooldown_s", 0) * (WEAPON_RULES["max_level"] - 1)
        if lv <= 0: errs.append(f"Waffe {w_['id']}: Abklingzeit auf Höchststufe <= 0")
    return errs


# ---------------------------------------------------------------------------- Items und Laufwirtschaft (Paket C, 28.10.2026)
# Story "Die große Ernte" (docs/STORY.md): Items sind Gartenwerkzeug und Gärtnerkram aus Saatkisten,
# Gold heißt Samenkörner. Items wirken über dieselben Stat-Schlüssel wie Upgrades und stapeln sich.
def item(id, name, rar, text, **effects):
    return dict(id=id, name=name, rarity=rar, text=text, effects=[dict(stat=k, value=v) for k, v in effects.items()])
ITEMS = [
 item("watering_can", "Gießkanne", "common", "+8 % Angriffstempo.", attack_speed_pct=8),
 item("compost", "Kompost", "common", "+12 Max-HP.", max_hp_flat=12),
 item("garden_gloves", "Gartenhandschuhe", "common", "+8 % Schaden.", damage_pct=8),
 item("straw_hat", "Strohhut", "common", "-5 % erlittener Schaden.", damage_taken_pct=-5),
 item("seed_pouch", "Samenbeutel", "common", "+15 % Samenkörner.", gold_gain_pct=15),
 item("rake", "Rechen", "common", "+20 % Aufsammelradius.", pickup_radius_pct=20),
 item("snail_shell", "Schneckenhaus", "common", "+0,4 HP pro Sekunde.", regen_per_s=0.4),
 item("sprout_boots", "Keimstiefel", "common", "+6 % Lauftempo.", move_speed_pct=6),
 item("magnifier", "Lupe", "common", "+5 % Krit-Chance.", crit_chance_pct=5),
 item("sundial", "Sonnenuhr", "common", "-10 % Abklingzeit der Fähigkeit.", cooldown_pct=-10),
 item("earthworm", "Regenwurm", "common", "+10 % XP.", xp_gain_pct=10),
 item("garden_twine", "Gartenschnur", "common", "+8 % Reichweite.", range_pct=8),
 item("clover", "Kleeblatt", "uncommon", "+1 Glück: seltenere Karten und Items.", luck=1),
 item("trellis", "Rankhilfe", "uncommon", "Geschosse durchbohren +1 Gegner.", pierce_add=1),
 item("pruning_shears", "Gartenschere", "uncommon", "+25 % Krit-Schaden.", crit_mult_add_pct=25),
 item("scarecrow", "Vogelscheuche", "uncommon", "+20 % Schaden gegen Elites und Bosse.", elite_damage_pct=20),
 item("deep_roots", "Tiefe Wurzeln", "uncommon", "+20 % Schaden, solange du stehst.", standing_damage_pct=20),
 item("nettle", "Brennnessel", "uncommon", "Gegner, die dich berühren, nehmen 8 Schaden.", thorns_flat=8),
 item("honey_pot", "Honigtopf", "uncommon", "Heilt 0,3 HP pro Kill.", heal_per_kill=0.3),
 item("cold_frame", "Frühbeetfenster", "uncommon", "+30 % Schutzzeit nach Treffern.", i_frames_pct=30),
 item("seed_bomb", "Samenbombe", "uncommon", "8 % Chance: Kills explodieren (Radius 60, 50 % Schaden).", explode_on_kill_pct=8),
 item("twin_pod", "Zwillingsschote", "rare", "+1 zusätzlicher Schuss.", extra_attacks=1),
 item("sunflower", "Sonnenblume", "rare", "+15 % Schaden, +10 % Reichweite.", damage_pct=15, range_pct=10),
 item("beehive", "Bienenstock", "rare", "+15 % Angriffstempo, +5 % Lauftempo.", attack_speed_pct=15, move_speed_pct=5),
 item("rain_barrel", "Regentonne", "rare", "+30 Max-HP, +0,5 HP pro Sekunde.", max_hp_flat=30, regen_per_s=0.5),
 item("golden_leaf", "Goldblatt", "rare", "+30 % Samenkörner, +1 Glück.", gold_gain_pct=30, luck=1),
 item("oak_acorn", "Eichel der alten Eiche", "epic", "+25 % Schaden, +25 Max-HP.", damage_pct=25, max_hp_flat=25),
 item("greenhouse", "Gewächshaus", "epic", "+30 % XP, +40 % Aufsammelradius.", xp_gain_pct=30, pickup_radius_pct=40),
 item("gardeners_spade", "Spaten der Gärtnerin", "epic", "+1 zusätzlicher Schuss, Geschosse durchbohren +1 Gegner.", extra_attacks=1, pierce_add=1),
 item("first_seed", "Die erste Saat", "legendary", "+30 % Schaden, +20 % Angriffstempo, +10 % Krit-Chance.", damage_pct=30, attack_speed_pct=20, crit_chance_pct=10),
 # Paket F: Items mit Auslösern und Bedingungen (Megabonk-Prinzip: kleine Zahlen, große Kombinationen)
 item("copper_wire", "Kupferdraht", "uncommon", "8 % Chance: Blitz springt auf 2 nahe Gegner.", shock_chance_pct=8),
 item("burning_glass", "Brennglas", "uncommon", "8 % Chance, Gegner zu entzünden.", ignite_chance_pct=8),
 item("nettle_brew", "Brennnesseljauche", "uncommon", "Treffer vergiften (8 % Schaden/s, stapelt).", poison_pct_per_s=8),
 item("frost_fleece", "Frostvlies", "uncommon", "Treffer verlangsamen um 6 %.", chill_slow_pct=6),
 item("bird_bath", "Vogelbad", "uncommon", "+5 % Ausweichen.", dodge_chance_pct=5),
 item("hedgehog_house", "Igelhaus", "uncommon", "Wirft 50 % des Nahkampfschadens zurück, +1 Rüstung.", thorns_pct=50, flat_damage_reduction=1),
 item("ladybug", "Marienkäfer", "rare", "+2 % Lebensraub, +3 % Krit-Chance.", lifesteal_pct=2, crit_chance_pct=3),
 item("bumblebee", "Hummel", "rare", "Blutrausch: jeder Kill +2 % Angriffstempo (5 s), bis +15 %.", kill_haste_max_pct=15),
 item("weathervane", "Wetterhahn", "rare", "Geschosse prallen 1-mal ab.", bounce_add=1),
 item("pitchfork", "Mistgabel", "rare", "+40 % Schaden gegen Gegner unter 30 % HP.", execute_damage_pct=40),
 item("sun_hat", "Sonnenhut", "uncommon", "+30 % Schaden bei wenig HP (unter 35 %).", low_hp_damage_pct=30),
 item("rain_gauge", "Regenmesser", "rare", "Alle 12 s ein Schild (30 HP).", shield_flat=30),
 item("garden_gnome", "Gartenzwerg", "epic", "Einmal wiederbeleben (50 % HP).", revives=1),
 item("bell_jar", "Glasglocke", "epic", "+45 % Schaden, -20 % Max-HP. Hohes Risiko.", damage_pct=45, max_hp_pct=-20),
 item("thunder_cloud", "Gewitterwolke", "epic", "+15 % Blitzchance, +30 % Elementarschaden.", shock_chance_pct=15, elemental_damage_pct=30),
 item("compost_heart", "Komposthaufen-Herz", "legendary", "Splitter bei 30 % der Kills, +2 HP pro Kill, +20 % Flächenradius.", shrapnel_chance_pct=30, heal_per_kill=2, area_pct=20),
]
# Kartentexte je Stat (Paket F): {v} wird durch den Wert der Karte ersetzt (mit Vorzeichen, deutsch formatiert).
STAT_LABELS = {
 "damage_pct": "{v} % Schaden", "attack_speed_pct": "{v} % Angriffstempo", "range_pct": "{v} % Reichweite",
 "crit_chance_pct": "{v} % Krit-Chance", "crit_mult_add_pct": "{v} % Krit-Schaden", "max_hp_flat": "{v} Max-HP",
 "max_hp_pct": "{v} % Max-HP", "damage_taken_pct": "{v} % erlittener Schaden", "move_speed_pct": "{v} % Lauftempo",
 "pickup_radius_pct": "{v} % Aufsammelradius", "extra_attacks": "{v} zusätzliche Schüsse", "pierce_add": "{v} Durchschlag",
 "regen_per_s": "{v} HP pro Sekunde", "xp_gain_pct": "{v} % XP", "gold_gain_pct": "{v} % Samenkörner", "luck": "{v} Glück",
 "cooldown_pct": "{v} % Abklingzeit", "elite_damage_pct": "{v} % Schaden gegen Elites und Bosse",
 "standing_damage_pct": "{v} % Schaden im Stand", "thorns_flat": "{v} Dornenschaden bei Berührung", "heal_per_kill": "{v} HP pro Kill",
 "i_frames_pct": "{v} % Schutzzeit", "explode_on_kill_pct": "{v} % Chance: Kills explodieren",
 "heal_orb_chance_pct": "{v} % Chance auf Heilkugeln", "area_pct": "{v} % Flächenradius", "thorns_pct": "{v} % Schaden zurückwerfen",
 "projectile_size_pct": "{v} % Geschossgröße", "projectile_speed_pct": "{v} % Geschosstempo", "dodge_chance_pct": "{v} % Ausweichen",
 "flat_damage_reduction": "{v} Rüstung", "rerolls": "{v} Neu würfeln", "banishes": "{v} Verbannen",
 "ignite_chance_pct": "{v} % Brandchance", "chill_slow_pct": "{v} % Verlangsamung bei Treffer", "poison_pct_per_s": "{v} % Gift pro Sekunde",
 "shock_chance_pct": "{v} % Blitzchance", "bounce_add": "{v} Rückprall", "execute_damage_pct": "{v} % Schaden gegen Angeschlagene",
 "lifesteal_pct": "{v} % Lebensraub", "shield_flat": "{v} Schild alle 12 s", "low_hp_damage_pct": "{v} % Schaden bei wenig HP",
 "overcharge_pct": "{v} % Überladung alle 6 s", "explosive_hit_pct": "{v} % Explosionsschaden bei Treffer", "aura_dps": "{v} Aura-Schaden/s",
 "elemental_damage_pct": "{v} % Elementarschaden", "revives": "{v} Wiederbelebung", "kill_haste_max_pct": "{v} % Blutrausch-Tempo",
 "shrapnel_chance_pct": "{v} % Splitterchance",
}

ECONOMY = dict(
    currency=dict(id="seeds", name="Samenkörner", normal_drop_pct=35, normal_value=1, elite_value=10, boss_value=40),
    chests=dict(count=90, price_start=15, price_growth_pct=40, item_min_rarity={"map": "common", "elite": "rare", "boss": "epic"}),
    pots=dict(count=160, contents=dict(seeds=70, heal=20, magnet=5, nothing=5), seeds_min=3, seeds_max=6),
    heal_orb_hp=15,
    rerolls_per_run=2, banishes_per_run=2,
    text="Samenkörner fallen von Gegnern (35 % je normaler Gegner, Elite 10, Boss 40) und aus Vasen. Saatkisten liegen auf der Karte und kosten Samenkörner; jede geöffnete Kiste macht die nächste 40 % teurer. Elite- und Bosskisten sind gratis und enthalten mindestens seltene bzw. epische Items.",
)

# ---------------------------------------------------------------------------- Waffen (Paket C2, 28.10.2026)
# Zusätzliche Waffen neben der Startwaffe des Charakters. Sie erscheinen als Karten beim Level-up,
# solange ein Platz frei ist; dieselbe Waffe erneut wählen hebt ihre Stufe. Werte auf Stufe L:
# base + per_level * (L - 1), Anzahlen abgerundet. Schaden und Tempo skalieren mit den Schadens- und
# Angriffstempo-Boni des Spielers, Krit gilt auch für Waffen. Entwurf, braucht Hannes' Freigabe.
WEAPON_RULES = dict(slots=4, max_level=5,
                    text="4 Waffenplätze (die Startwaffe belegt einen). Neue Waffen erscheinen als Karten beim Level-up, solange ein Platz frei ist; eine Waffe erneut wählen hebt ihre Stufe (höchstens 5). Waffen nutzen Schaden, Angriffstempo und Krit des Spielers.")
def weapon(id, name, kind, rar, text, level_text, base, per_level, style="Fernkampf"):
    return dict(id=id, name=name, kind=kind, rarity=rar, style=style, text=text, level_text=level_text, base=base, per_level=per_level, impl_phase=1)
WEAPON_KINDS = ("fan", "nova", "aura", "orbit", "lobbed", "chain", "boomerang", "trail", "turret", "beam", "mine", "homing", "sweep")
# Paket G (28.10.2026): 15 Waffen für eigene Spielweisen. `style` steht auf der Karte:
# Fernkampf, Rundum, Nahkampf, Fläche, Kette, Bewegung (wirkt nur im Laufen), Stellung (belohnt Stehen), Zielsuche, Durchschlag.
WEAPONS = [
 weapon("thorn_twig", "Dornenzweig", "fan", "common", "Wirft alle 1,2 s einen Fächer aus 3 Dornen auf den nächsten Gegner.", "+2 Schaden, +1 Dorn je 2 Stufen.",
        dict(damage=7, cooldown_s=1.2, count=3, spread_deg=30, speed=520, range=300, pierce=0), dict(damage=2, count=0.5)),
 weapon("dandelion", "Pusteblume", "fan", "uncommon", "Alle 2 s fliegen 8 Schirmchen in alle Richtungen, durchbohren 1 Gegner.", "+2 Schaden, +2 Schirmchen.",
        dict(damage=6, cooldown_s=2.0, count=8, spread_deg=360, speed=360, range=260, pierce=1), dict(damage=2, count=2), "Rundum"),
 weapon("pollen_cloud", "Pollenwolke", "aura", "common", "Eine Wolke um dich (Radius 70) macht alle 0,5 s 4 Schaden.", "+1,5 Schaden, +8 Radius.",
        dict(damage=4, cooldown_s=0.5, radius=70), dict(damage=1.5, radius=8), "Nahkampf"),
 weapon("bees", "Bienenschwarm", "orbit", "uncommon", "2 Bienen kreisen um dich (Radius 64) und stechen für 10 Schaden.", "+3 Schaden, +1 Biene.",
        dict(damage=10, cooldown_s=0.5, count=2, radius=64, hit_radius=10, turns_per_s=0.7), dict(damage=3, count=1), "Nahkampf"),
 weapon("sun_pulse", "Sonnenpuls", "nova", "uncommon", "Alle 3 s ein Lichtring um dich (Radius 110, 14 Schaden).", "+5 Schaden, +10 Radius, -0,2 s Abklingzeit.",
        dict(damage=14, cooldown_s=3.0, radius=110), dict(damage=5, radius=10, cooldown_s=-0.2), "Fläche"),
 weapon("pumpkin_bomb", "Kürbisbombe", "lobbed", "rare", "Wirft alle 2,5 s einen Kürbis auf einen Gegner (bis 320 px), der nach 0,9 s platzt (Radius 70, 30 Schaden).", "+10 Schaden, +6 Radius, +1 Kürbis je 2 Stufen.",
        dict(damage=30, cooldown_s=2.5, count=1, radius=70, range=320, flight_s=0.9), dict(damage=10, radius=6, count=0.5), "Fläche"),
 weapon("firefly", "Glühwürmchen", "chain", "rare", "Alle 1,4 s ein Leuchtblitz, der über 3 Gegner springt (9 Schaden, je Sprung 85 %).", "+3 Schaden, +1 Sprung.",
        dict(damage=9, cooldown_s=1.4, jumps=3, range=280, jump_range=140, falloff=0.85), dict(damage=3, jumps=1), "Kette"),
 weapon("leaf_boomerang", "Ahornbumerang", "boomerang", "uncommon", "Alle 1,6 s fliegt ein Ahornblatt hinaus und kehrt zurück; trifft auf beiden Wegen (12 Schaden).", "+4 Schaden, +1 Blatt je 2 Stufen.",
        dict(damage=12, cooldown_s=1.6, count=1, speed=420, range=260), dict(damage=4, count=0.5), "Durchschlag"),
 weapon("nettle_trail", "Brennnesselspur", "trail", "common", "Im Laufen wachsen hinter dir Brennnesseln (Radius 26, 2,5 s, 5 Schaden alle 0,5 s).", "+2 Schaden, +0,5 s Dauer, +3 Radius.",
        dict(damage=5, cooldown_s=0.3, radius=26, duration_s=2.5), dict(damage=2, duration_s=0.5, radius=3), "Bewegung"),
 weapon("cactus", "Kaktuswächter", "turret", "uncommon", "Pflanzt alle 4 s einen Kaktus (12 s), der Stacheln auf Gegner bis 260 px schießt (8 Schaden, 0,7 s).", "+3 Schaden, +1 Kaktus je 2 Stufen, schneller.",
        dict(damage=8, cooldown_s=4.0, count=1, fire_s=0.7, range=260, life_s=12, speed=480), dict(damage=3, count=0.5, fire_s=-0.05), "Stellung"),
 weapon("sunbeam", "Brennglasstrahl", "beam", "rare", "Alle 2,2 s ein Lichtstrahl durch alle Gegner in einer Linie (360 px, 22 Schaden).", "+7 Schaden, +3 Breite, -0,15 s Abklingzeit.",
        dict(damage=22, cooldown_s=2.2, length=360, width=14), dict(damage=7, width=3, cooldown_s=-0.15), "Durchschlag"),
 weapon("garlic_mine", "Knoblauchminen", "mine", "common", "Im Laufen legst du jede Sekunde eine Knoblauchzehe (höchstens 4), die bei Berührung platzt (Radius 60, 26 Schaden).", "+8 Schaden, +1 Zehe.",
        dict(damage=26, cooldown_s=1.0, count=4, radius=60, trigger=26, life_s=20), dict(damage=8, count=1), "Bewegung"),
 weapon("seed_shotgun", "Saatflinte", "fan", "uncommon", "Alle 1,5 s eine Ladung aus 7 Samen auf kurze Distanz (170 px, je 6 Schaden).", "+2 Schaden, +1 Samen.",
        dict(damage=6, cooldown_s=1.5, count=7, spread_deg=50, speed=600, range=170, pierce=0), dict(damage=2, count=1), "Nahkampf"),
 weapon("dragonfly", "Libellenschwarm", "homing", "rare", "Alle 1,8 s fliegen 2 Libellen los und suchen sich selbst ein Ziel (10 Schaden).", "+3 Schaden, +1 Libelle je 2 Stufen.",
        dict(damage=10, cooldown_s=1.8, count=2, speed=300, range=420, turn=7), dict(damage=3, count=0.5), "Zielsuche"),
 weapon("sickle", "Sichel", "sweep", "common", "Alle 1,1 s ein Hieb im Halbkreis vor dir (Radius 80, 16 Schaden).", "+5 Schaden, +6 Radius.",
        dict(damage=16, cooldown_s=1.1, radius=80, arc_deg=140), dict(damage=5, radius=6), "Nahkampf"),
]

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
             "challenges.json": CHALLENGES, "skins.json": SKINS, "modes.json": MODES, "items.json": dict(items=ITEMS, economy=ECONOMY),
             "weapons.json": dict(WEAPON_RULES, weapons=WEAPONS),
             "stages.json": dict(stages=STAGES, flood=FLOOD, gate=GATE, stat_labels=STAT_LABELS)}
    for n, d in files.items():
        (DATA / n).write_text(json.dumps(d, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")

def md():
    L = []
    P = L.append
    P("# CONTENT: festes Inhaltskonzept\n")
    P("Alle Zahlen sind **Startwerte aus einer Modellrechnung**, nicht aus gespielten Runs. Sie werden später mit einer Headless-Simulation (Bot-Läufe) justiert. Diese Datei wird von `tools/build_content.py` erzeugt, die Quelle der Wahrheit sind die JSON-Dateien in `data/`. IDs nie ohne Rückfrage ändern.\n")
    P("## Lauf und Schwierigkeit\n")
    P("""- **Drei Beete, je 3:00 (Paket F, 28.10.2026; seit Paket I 3:00 statt 5:00, Gegner skalieren x5/3 schneller).** Saatbeet, Gemüsebeet, Komposthaufen. Jedes Beet ist eine eigene Karte; Level, Upgrades, Waffen und Items bleiben beim Wechsel erhalten. Ohne Flut dauert ein Lauf etwa 9 Minuten, mit Flut-Zockerei etwa 10 bis 13.
- **Boss bei 2:06 jedes Beets.** Ist er besiegt, öffnet sich das **Gartentor** zum nächsten Beet (volle Heilung). Der Schnitter im dritten Beet beendet den Lauf mit einem Sieg.
- **Plagenflut:** Läuft die Zeit eines Beets ab, wird es endlos: alle 10 s +40 % Gegner, +15 % HP, +8 % Schaden. Wer den Boss besiegt hat, kann jederzeit durchs Tor.
- Welle alle **30 s** innerhalb des Beets, ohne Pause. Level-ups pausieren das Spiel.
- **Gegnerwerte:** Grundwert x Beet-Faktor (1 / 2,6 / 6 bei HP) x Zeitfaktor im Beet `(1 + 0,10*m + 0,012*m²)`, m = Minuten im Beet.
- **Mehrfach-Skalierung wie bei Megabonk:** Gleiche Quellen addieren sich, verschiedene multiplizieren sich (Schaden x Krit x Angriffstempo). Jede Level-up-Karte hat eine eigene Seltenheit, die ihren Wert vervielfacht (gewöhnlich x1 bis legendär x3).
- **Machbarkeitsregeln:** glatte Kurve ohne Sprünge, jeder gefährliche Angriff hat eine Vorwarnung, jeder Boss hat ein klares Muster.
""")
    rows, hpc = balance_rows()
    P(f"### Modellrechnung (Ø {hpc:.1f} HP je Budgetpunkt, alles wird getötet)\n")
    P("| Minute | Welle | Budget | HP x | Schaden x | nötige HP/s | Level (ca.) | XP gesamt |\n|---|---|---|---|---|---|---|---|")
    for r in rows:
        if r["wave"] in (2, 4, 6, 8, 10, 14, 20, 30, 40):  # minutes within one bed (3:00 = wave 10)
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
        main = max(m["biome_weights"], key=m["biome_weights"].get)
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
    P("### Beete und Plagenflut\n")
    P("| Beet | Dauer | Boss | HP x | Schaden x | Gegnermenge x |\n|---|---|---|---|---|---|")
    for st in STAGES:
        P(f"| {st['index']}. {st['name']} | {st['duration_s'] // 60}:00 | {next(b['name'] for b in BOSSES if b['id'] == st['boss'])} | {st['hp_mult']:g} | {st['damage_mult']:g} | {st['budget_mult']:g} |")
    P("\n" + FLOOD["text"] + " " + GATE["text"] + "\n")
    P("### Bosse\n")
    for b in BOSSES:
        tm = f"{b['spawn_time_s'] // 60}:{b['spawn_time_s'] % 60:02d} im Beet"
        hp = f"HP {b['hp']}, " if b.get("hp") else (f"HP {b['hp_base']} x HP-Faktor, Wutphase nach {b['enrage_after_s']} s, " if b.get("hp_base") else "")
        P(f"- **{b['name']}** (`{b['id']}`, {tm}, Phase {b['impl_phase']}): " + hp + "; ".join(f"ab {p['at_hp_pct']} % HP: {p['pattern']}" for p in b["phases"]) + ".")
    P(f"\n## Beete ({BALANCE['arena_tiles'][0]} x {BALANCE['arena_tiles'][1]} Felder à 32 px)\n")
    P("| ID | Name | Bereich (x, y, Breite, Höhe in Feldern) | Effekt | Phase |\n|---|---|---|---|---|")
    for b in BIOMES:
        P(f"| `{b['id']}` | {b['name']} | {b['rect_tiles']} | {b['effect']} | {b.get('impl_phase', 1)} |")
    P("\nJedes Beet ist eine eigene Karte; die Startfläche in der Mitte bleibt frei. Hindernisse sind pro Beet mit festem Seed verteilt.\n")
    P("Biom-Farben (Pastell): " + "; ".join(f"{b['name']}: Boden {PALETTES[b['id']]['ground']}, Details {PALETTES[b['id']]['detail']}" for b in BIOMES) + ".\n")
    P(f"## Items ({len(ITEMS)}, aus Saatkisten)\n")
    P(ECONOMY["text"] + "\n")
    P("| ID | Name | Seltenheit | Wirkung |\n|---|---|---|---|")
    for i in ITEMS:
        P(f"| `{i['id']}` | {i['name']} | {i['rarity']} | {i['text']} |")
    P("")
    P(f"## Waffen ({len(WEAPONS)}, Karten beim Level-up)\n")
    P(WEAPON_RULES["text"] + "\n")
    P("| ID | Name | Art | Spielweise | Seltenheit | Wirkung | je Stufe |\n|---|---|---|---|---|---|---|")
    for w_ in WEAPONS:
        P(f"| `{w_['id']}` | {w_['name']} | {w_['kind']} | {w_['style']} | {w_['rarity']} | {w_['text']} | {w_['level_text']} |")
    P("")
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
    print("OK: 10 Charaktere, 50 Upgrades (18/14/9/6/3), 10 Mobs,", len(BOSSES), "Bosse,", len(BIOMES), "Beete,", len(CHALLENGES), "Challenges,", len(SKINS), "Skins")
    print("Phasen  Charaktere:", ph(CHARACTERS), " Upgrades:", ph(UPGRADES), " Mobs:", ph(MOBS))
    print("Start freigeschaltet: Upgrades", sum(u["unlocked_at_start"] for u in UPGRADES), "von 50")
