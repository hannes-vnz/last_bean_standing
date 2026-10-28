# CONTENT: festes Inhaltskonzept

Alle Zahlen sind **Startwerte aus einer Modellrechnung**, nicht aus gespielten Runs. Sie werden später mit einer Headless-Simulation (Bot-Läufe) justiert. Diese Datei wird von `tools/build_content.py` erzeugt, die Quelle der Wahrheit sind die JSON-Dateien in `data/`. IDs nie ohne Rückfrage ändern.

## Lauf und Schwierigkeit

- **Drei Beete, je 3:00 (Paket F, 28.10.2026; seit Paket I 3:00 statt 5:00, Gegner skalieren x5/3 schneller).** Saatbeet, Gemüsebeet, Komposthaufen. Jedes Beet ist eine eigene Karte; Level, Upgrades, Waffen und Items bleiben beim Wechsel erhalten. Ohne Flut dauert ein Lauf etwa 9 Minuten, mit Flut-Zockerei etwa 10 bis 13.
- **Boss bei 2:06 jedes Beets.** Ist er besiegt, öffnet sich das **Gartentor** zum nächsten Beet (volle Heilung). Der Schnitter im dritten Beet beendet den Lauf mit einem Sieg.
- **Plagenflut:** Läuft die Zeit eines Beets ab, wird es endlos: alle 10 s +40 % Gegner, +15 % HP, +8 % Schaden. Wer den Boss besiegt hat, kann jederzeit durchs Tor.
- Welle alle **30 s** innerhalb des Beets, ohne Pause. Level-ups pausieren das Spiel.
- **Gegnerwerte:** Grundwert x Beet-Faktor (1 / 2,6 / 6 bei HP) x Zeitfaktor im Beet `(1 + 0,10*m + 0,012*m²)`, m = Minuten im Beet.
- **Mehrfach-Skalierung wie bei Megabonk:** Gleiche Quellen addieren sich, verschiedene multiplizieren sich (Schaden x Krit x Angriffstempo). Jede Level-up-Karte hat eine eigene Seltenheit, die ihren Wert vervielfacht (gewöhnlich x1 bis legendär x3).
- **Machbarkeitsregeln:** glatte Kurve ohne Sprünge, jeder gefährliche Angriff hat eine Vorwarnung, jeder Boss hat ein klares Muster.

### Modellrechnung (Ø 9.0 HP je Budgetpunkt, alles wird getötet)

| Minute | Welle | Budget | HP x | Schaden x | nötige HP/s | Level (ca.) | XP gesamt |
|---|---|---|---|---|---|---|---|
| 0.6 | 2 | 55 | 1.1 | 1.1 | 30 | 9 | 102 |
| 1.2 | 4 | 72 | 1.3 | 1.1 | 45 | 14 | 237 |
| 1.8 | 6 | 90 | 1.4 | 1.2 | 63 | 17 | 407 |
| 2.4 | 8 | 110 | 1.6 | 1.3 | 88 | 20 | 617 |
| 3 | 10 | 132 | 1.8 | 1.4 | 119 | 23 | 870 |
| 4.2 | 14 | 181 | 2.3 | 1.6 | 207 | 29 | 1518 |
| 6 | 20 | 268 | 3.2 | 1.9 | 428 | 37 | 2901 |
| 9 | 30 | 448 | 5.2 | 2.7 | 1161 | 50 | 6535 |
| 12 | 40 | 672 | 7.8 | 3.6 | 2609 | 62 | 12211 |

Die Spalte „nötige HP/s“ ist die Leistung, die du brauchst, um alles Erscheinende zu töten. Ein Start-Jäger macht rund 19 Schaden pro Sekunde auf ein Ziel. Das Spiel soll so gebaut sein, dass starke Builds (Flächenschaden, Durchschlag, Ketten) diese Kurve bis etwa Minute 14 bis 18 halten können.

## Charaktere (10)

| Name | Spielstil | HP | Tempo | Schaden | Schuss/s | Reichweite | Krit | Waffe | Passiv | Fertigkeit | Freischaltung | Phase |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| **Fenn der Falkenauge** (`ranger`) | Jäger: ausgewogen, durchschlagende Pfeile | 100 | 225 | 12 | 2.0 | 380 | 5 % | Ein Pfeil, durchschlägt 1 Gegner. | **Weitblick**: +12 % Reichweite. +8 % Schaden auf Ziele über 250 px. | **Pfeilhagel** (18 s): 16 Pfeile in alle Richtungen (je 60 % Schaden). | von Anfang an | 1 |
| **Mira Aschenglut** (`pyro`) | Pyromantin: Flächenschaden und Brand | 80 | 175 | 14 | 1.1 | 320 | 5 % | Feuerball explodiert (Radius 64) und entzündet (3 s, 20 % Schaden/s). | **Hitzewelle**: Brennende Gegner erleiden +20 % Schaden. | **Inferno** (22 s): Feuerring (Radius 180) um dich, 4 s, 40 % Schaden/s. | Erreiche Minute 3 mit beliebigem Charakter. | 1 |
| **Kaz Nachtmesser** (`rogue`) | Schurke: schnell, kritisch, kurze Reichweite | 85 | 238 | 7 | 2.2 | 210 | 20 % | Fächer aus 3 Wurfmessern. | **Nervenkitzel**: +15 % Lauftempo. +6 % Schaden je Gegner im Umkreis 150 px (max. 5). | **Schattenschritt** (5 s): Dash über 220 px, 0,3 s unverwundbar. | Räume eine Welle ab Welle 5, ohne Schaden zu nehmen. | 1 |
| **Brun Eisenschulter** (`guardian`) | Wächter: Nahkampf-Tank mit Dornen | 160 | 150 | 20 | 0.9 | 110 | 0 % | Schockwelle um dich (Radius 110) mit Rückstoß. | **Eisenhaut**: -15 % erlittener Schaden. Reflektiert 25 % des Nahkampfschadens. | **Bollwerk** (25 s): Schild für 3 s, absorbiert 150 Schaden. | Erleide insgesamt 5000 Schaden. | 1 |
| **Ysa Winterhauch** (`cryo`) | Frostmagierin: Kontrolle und Verlangsamung | 90 | 181 | 10 | 1.3 | 340 | 5 % | Frostgeschoss verlangsamt um 30 % (2 s). 3 Kältestapel frieren 1,2 s ein. | **Frostaura**: Gegner im Umkreis von 140 px sind 15 % langsamer. | **Eiszeit** (24 s): Friert alle Gegner im Bild 2 s ein. | Besiege 300 Gegner im Komposthaufen. | 1 |
| **Thorn Geisterruf** (`summoner`) | Beschwörer: Begleiter kämpfen für ihn | 90 | 175 | 6 | 1.0 | 300 | 5 % | Schwacher Geisterbolzen. 2 Geister-Begleiter greifen selbstständig an (8 Schaden, 1,5/s). | **Seelenband**: Geister erhalten 50 % deiner Schadensboni. | **Totenruf** (30 s): 4 zusätzliche Geister für 10 s. | Erreiche Level 15 in einem Run. | 3 |
| **Vex Donnerhall** (`storm`) | Sturmrufer: Kettenblitze, hohe Schussrate | 80 | 200 | 8 | 2.4 | 300 | 5 % | Kettenblitz springt 2-mal (160 px, je 80 % Schaden). | **Statische Ladung**: Jeder 10. Schuss ruft einen Blitzschlag (200 % Schaden) auf einen zufälligen Gegner. | **Gewittersturm** (28 s): 6 s lang 4 Blitze pro Sekunde auf zufällige Gegner. | Erreiche das zweite Beet. | 1 |
| **Orm Zündfunke** (`bomber`) | Sprengmeister: Bomben im Stand, Minen im Lauf | 110 | 188 | 26 | 0.7 | 300 | 5 % | Bombe im Bogen, explodiert nach 0,6 s (Radius 90). | **Minenleger**: Legt beim Laufen alle 1,5 s eine Mine (60 % Schaden, Radius 70, max. 6). | **Megabombe** (20 s): Große Bombe (Radius 200, 500 % Schaden). | Besiege insgesamt 2000 Gegner. | 3 |
| **Lilu Schierling** (`venom`) | Giftmischerin: Giftpfützen und Seuche | 85 | 188 | 5 | 1.4 | 330 | 5 % | Giftphiole: Pfütze (Radius 55, 3 s, 12 Gift/s, stapelt bis 4x). | **Seuche**: Vergiftete Gegner verbreiten beim Tod Gift (Radius 80). | **Giftnebel** (26 s): Wolke (Radius 160) für 8 s, 35 % Schaden/s, verlangsamt 20 %. | Verursache insgesamt 10000 Giftschaden. | 3 |
| **Aya Stillstand** (`sniper`) | Scharfschützin: je länger sie steht, desto härter | 75 | 162 | 40 | 0.45 | 600 | 10 % | Durchschlag-Schuss (3). +10 % Schaden je Sekunde Stillstand (max. +100 %). | **Ruhe vor dem Schuss**: Nach 2 s Stillstand ist der nächste Schuss ein garantierter Krit (x2,5). | **Fokus** (20 s): 4 s lang: schießt auch im Lauf, doppelte Schussrate. | Besiege alle drei Beet-Bosse (Schleimrun, Knollgrimm, den Schnitter). | 3 |

Zwei Skins je Charakter (reine Farbvarianten, Freischaltung: Minute 10 bzw. 15 mit diesem Charakter): Fenn: Waldläufer / Goldjäger; Mira: Glutrot / Weißglut; Kaz: Mitternacht / Schattenfürst; Brun: Stahlgrau / Goldplatte; Ysa: Gletscher / Polarlicht; Thorn: Nekrogrün / Seelenlicht; Vex: Gewitterblau / Himmelsgold; Orm: Zunderorange / Funkenweiß; Lilu: Giftgrün / Schierlingsviolett; Aya: Wüstentarn / Schneetarn.

## Optik und Effekte (Pixel-Art)

Stil: Pixel-Art, begrenzte Palette, **Effekte sind das Aushängeschild** (siehe `DESIGN.md` Abschnitt 16 für Auflösung und Regeln).

| Charakter | Projektil | Treffer | Fertigkeit |
|---|---|---|---|
| Fenn | Pfeil (3 px lang, helle Spitze) mit Schweif aus 3 verblassenden Pixeln | 4 Funken und 2 Frames weißes Aufblitzen am Gegner | Pfeilhagel: Mündungsring, 16 Pfeile in alle Richtungen |
| Mira | Feuerball (6 px, 3-Frame-Flackern) mit Glutschweif (orange, rot, dunkelrot) | expandierender Explosionsring (4 Frames), Glutpartikel; brennende Gegner tragen kleine Flammen | Inferno: rotierender Flammenring um den Spieler |
| Kaz | drehendes Messer (4 Frames) mit blaugrauen Nachbildern | weißer Diagonal-Schnitt (3 Frames) | Schattenschritt: Schatten-Nachbilder und kleiner Rauchpuff |
| Brun | Schockwelle: Ring mit 2 px Kante expandiert, Staubpartikel am Boden | Rückstoß mit Staub, leichtes Bildschirmwackeln | Bollwerk: schimmernder Sechseck-Schild |
| Ysa | Eiskristall (5 px) mit Glitzerpixeln | 6 Eisscherben und blaues Aufblitzen; eingefrorene Gegner bläulich mit Kristallhülle | Eiszeit: weiß-blauer Ring über den ganzen Bildschirm |
| Thorn | grüner Wisp mit Schweif | Seelenfunken steigen auf | Totenruf: Rune am Boden, Geister steigen auf; Begleiter (8 px) schweben sinusförmig |
| Vex | Kettenblitz: gezackte 1-px-Linie, 3-Frame-Flackern, Funken an den Knoten | Blitzschlag von oben (senkrechter Strahl) mit Bodenfunken | Gewittersturm: dunkle Pixelwolke über dem Spieler, Blitze im Takt |
| Orm | Bombe im Bogen mit Bodenschatten und funkensprühender Lunte | großer Feuerball, Rauchring und Bildschirmwackeln; Minen blinken rot | Megabombe: roter Warnkreis, dann Einschlag |
| Lilu | Phiole dreht sich im Bogen | grüner Platscher mit Tropfen; Pfütze mit blubbernden Blasen | Giftnebel: wabernde Partikelwolke |
| Aya | Aufladen: wachsender heller Punkt am Lauf und feine Zielline | langer heller Strahl (1 px, 2 Frames) mit Mündungsblitz; Krit: goldener Ring plus Hit-Stop | Fokus: leichte Entsättigung des Bildes während der 4 s |

Allgemein: Stil freundlich-pastellig: jede spielrelevante Figur hat eine dunkle Kontur (#4a3358), eigene Geschosse sind warmgelb, gegnerische violett mit Kontur; Treffer-Aufblitzen: 2 Frames weiß; Hit-Stop von 2 bis 3 Frames bei Krit, Elite- und Bosstod; Bildschirmwackeln nach Trauma-Prinzip (Explosionen, Bosse); Schadenszahlen in Pixelschrift, Krit größer und gelb; Todes-Pop: 8 Partikel in der Gegnerfarbe; XP-Kugeln glitzern und fliegen zum Spieler; Level-up: Ring und Funkenregen; Boss-Warnungen: rote Linien und Kreise, 2 Hz Blinken; Biom-Partikel: Blätter (Wald), Sandwind (Wüste), Schnee (Eis), Glut (Lava); Skins als Paletten-Tausch der Charakterfarben.

## Upgrades (50)

Auswahl: Gewichte gewöhnlich 60, ungewöhnlich 25, selten 10, episch 4, legendär 1. Jeder Punkt Glück verschiebt 0,4 % Gewicht von den unteren zu den oberen Stufen. Bei Level-up 3 Karten, Elitetruhen bieten mindestens „selten“, Bosstruhen „episch“ oder „legendär“. Upgrades haben Stufen (Stapel bis `max_level`). Gewichtung nach Charakter-Tags.

### Gewöhnlich

| ID | Name | Max. Stufe | Effekt | Tags | Freischaltung | Phase |
|---|---|---|---|---|---|---|
| `sharp_edges` | Geschärfte Spitzen | 5 | +8 % Schaden je Stufe. | damage | von Anfang an | 1 |
| `quick_hands` | Flinke Hände | 5 | +7 % Angriffstempo je Stufe. | speed | von Anfang an | 1 |
| `long_reach` | Weitsicht | 4 | +10 % Reichweite je Stufe. | range | von Anfang an | 1 |
| `keen_eye` | Scharfblick | 5 | +4 % Krit-Chance je Stufe. | crit | von Anfang an | 1 |
| `vitality` | Lebenskraft | 5 | +15 Max-HP je Stufe (heilt um 15). | defense | von Anfang an | 1 |
| `thick_skin` | Dicke Haut | 4 | -6 % erlittener Schaden je Stufe. | defense | von Anfang an | 1 |
| `swift_feet` | Flinke Füße | 5 | +6 % Lauftempo je Stufe. | movement | von Anfang an | 1 |
| `magnet` | XP-Magnet | 4 | +30 % Aufsammelradius je Stufe. | utility | von Anfang an | 1 |
| `quick_learner` | Schnelle Auffassung | 4 | +10 % XP je Stufe. | utility | von Anfang an | 1 |
| `heal_orbs` | Heilkugeln | 3 | Gegner lassen mit 3 % je Stufe Heilkugeln fallen (15 HP). | defense, utility | von Anfang an | 1 |
| `wide_blast` | Breite Wirkung | 4 | +12 % Flächenradius je Stufe (Waffen, Explosionen, Aura). | area | von Anfang an | 1 |
| `thorns` | Dornenpanzer | 4 | Reflektiert 40 % des erlittenen Nahkampfschadens je Stufe. | defense, thorns | von Anfang an | 1 |
| `big_shots` | Schwere Geschosse | 3 | +25 % Geschossgröße je Stufe (trifft leichter). | projectile | von Anfang an | 1 |
| `fast_shots` | Schnelle Geschosse | 3 | +15 % Geschosstempo und +5 % Schaden je Stufe. | projectile | von Anfang an | 1 |
| `dodge` | Ausweichen | 5 | 4 % Chance je Stufe, einem Treffer zu entgehen. | defense | von Anfang an | 1 |
| `armor_plating` | Panzerplatten | 4 | -1 Schaden je Treffer und Stufe (mindestens 1). | defense | von Anfang an | 1 |
| `lucky_charm` | Glücksklee | 4 | +1 Glück je Stufe: seltenere Karten, Items und Krits. | utility | von Anfang an | 1 |
| `bounty_hunter` | Kopfgeldjäger | 4 | +12 % Schaden gegen Elites und Bosse je Stufe. | damage | von Anfang an | 1 |

### Ungewöhnlich

| ID | Name | Max. Stufe | Effekt | Tags | Freischaltung | Phase |
|---|---|---|---|---|---|---|
| `brutal_crits` | Brutale Treffer | 4 | +20 % Krit-Schaden je Stufe (Basis 150 %). | crit | von Anfang an | 1 |
| `double_shot` | Mehrfachangriff | 3 | +1 zusätzlicher Angriff je Stufe (60 % Schaden, leichte Streuung). | projectile | von Anfang an | 1 |
| `piercing` | Durchschlag | 3 | Geschosse durchbohren +1 Gegner je Stufe. | pierce, projectile | von Anfang an | 1 |
| `heavy_hitter` | Schwergewicht | 3 | +25 % Schaden, -10 % Angriffstempo je Stufe. | damage | von Anfang an | 1 |
| `regeneration` | Regeneration | 4 | +0,6 HP pro Sekunde je Stufe. | defense | von Anfang an | 1 |
| `reroll` | Neuwurf | 3 | +1 Neu würfeln je Stufe (sofort). | utility | von Anfang an | 1 |
| `banish` | Verbannung | 3 | +1 Verbannen je Stufe (sofort). | utility | von Anfang an | 1 |
| `stillness` | Meditation | 3 | +15 % Schaden im Stand je Stufe. | stillness, damage | von Anfang an | 1 |
| `ignite` | Entzünden | 4 | 10 % Chance je Stufe zu entzünden (3 s, 30 % Schaden/s). | fire, elemental | von Anfang an | 1 |
| `chill` | Kälte | 4 | Treffer verlangsamen um 8 % je Stufe für 2 s (max. 60 %). | frost, elemental | von Anfang an | 1 |
| `toxin` | Toxin | 4 | Treffer vergiften (12 % Schaden/s je Stufe, 3 s, stapelt bis 4x). | poison, elemental | von Anfang an | 1 |
| `shock` | Schock | 3 | 12 % Chance je Stufe auf einen Blitz (60 % Schaden), der auf 2 nahe Gegner springt. | lightning, elemental | von Anfang an | 1 |
| `minion_horde` | Gefolgschaft | 3 | +1 Begleiter je Stufe (ohne Beschwörer: Irrlicht mit 50 % Schaden). | summon | Schalte 3 Charaktere frei. | 3 |
| `orbiting_blades` | Kreisende Klingen | 4 | Eine zusätzliche Klinge je Stufe umkreist dich (6 Schaden). | area, melee | Erreiche Level 20 in einem Run. | 3 |

### Selten

| ID | Name | Max. Stufe | Effekt | Tags | Freischaltung | Phase |
|---|---|---|---|---|---|---|
| `ricochet` | Rückprall | 3 | Geschosse springen +1-mal je Stufe auf einen nahen Gegner. | bounce, projectile | von Anfang an | 1 |
| `executioner` | Henker | 3 | +30 % Schaden gegen Gegner unter 30 % HP je Stufe. | damage | von Anfang an | 1 |
| `lifesteal` | Aderlass | 3 | Heilt 2 % des verursachten Schadens je Stufe. | defense, damage | von Anfang an | 1 |
| `shield_burst` | Notschild | 3 | Alle 12 s ein Schild, der 25 Schaden je Stufe abfängt. | defense | von Anfang an | 1 |
| `last_stand` | Letztes Gefecht | 3 | Unter 35 % HP: +30 % Schaden und +15 % Tempo je Stufe. | defense, damage | von Anfang an | 1 |
| `overcharge` | Überladung | 3 | Alle 6 s trifft der nächste Schuss mit +200 % Schaden je Stufe. | damage | von Anfang an | 1 |
| `explosive_rounds` | Sprengmunition | 3 | Treffer explodieren (Radius 50, 30 % Schaden je Stufe). | area, projectile | von Anfang an | 1 |
| `aura_of_pain` | Brennnesselkranz | 4 | Gegner im Umkreis von 100 px erleiden 6 Schaden/s je Stufe. | area, melee | von Anfang an | 1 |
| `elemental_mastery` | Elementarmeister | 3 | +25 % Schaden von Brand, Gift und Blitz je Stufe. | elemental | von Anfang an | 1 |

### Episch

| ID | Name | Max. Stufe | Effekt | Tags | Freischaltung | Phase |
|---|---|---|---|---|---|---|
| `second_wind` | Zweiter Atem | 2 | Einmal wiederbeleben je Stufe (mit 50 % HP, 2 s unverwundbar). | defense | von Anfang an | 1 |
| `gravity_well` | Schwerkraftbrunnen | 2 | Alle 12 s zieht ein Sog alle Gegner im Radius 200 zusammen (Stufe 2: Radius 280, alle 9 s). | control, area | Erreiche das dritte Beet. | 3 |
| `bloodlust` | Blutrausch | 3 | Jeder Kill: +2 % Angriffstempo für 5 s, stapelt bis +20 % je Stufe. | speed | von Anfang an | 1 |
| `time_warp` | Zeitdehnung | 2 | Im Stand sind alle Gegner im Radius 250 um 12 % / 20 % langsamer. | control, stillness | Überlebe 2 Minuten Plagenflut. | 3 |
| `shrapnel` | Splitterhagel | 3 | Sterbende Gegner verschießen mit 20 % Chance je Stufe 6 Splitter (50 % Schaden). | area, projectile | von Anfang an | 1 |
| `titan_heart` | Titanenherz | 3 | +30 % Max-HP und +10 % Schaden je Stufe. | defense | von Anfang an | 1 |

### Legendär

| ID | Name | Max. Stufe | Effekt | Tags | Freischaltung | Phase |
|---|---|---|---|---|---|---|
| `glass_cannon` | Glaskanone | 1 | +100 % Schaden, -40 % Max-HP. | damage | von Anfang an | 1 |
| `reaper_pact` | Pakt der Sense | 1 | Jeder Kill heilt 1 HP, 25 % Chance auf eine Explosion beim Kill. | damage, defense | von Anfang an | 1 |
| `elemental_storm` | Elementarsturm | 1 | Je 15 % Chance auf Brand und Blitz, Gift und Kälte bei jedem Treffer, +50 % Elementarschaden. | elemental | von Anfang an | 1 |

## Mob-Typen (10)

| ID | Name | Verhalten | HP | Tempo | Schaden | Kosten | XP | ab Sek. | Biom | Beschreibung | Phase |
|---|---|---|---|---|---|---|---|---|---|---|---|
| `slug` | Nacktschnecke | chaser | 12 | 80 | 5 | 1 | 1 | 0 | seedbed | Kriecht stur auf dich zu. Die häufigste Plage. | 1 |
| `aphid` | Blattlaus | swarm | 4 | 160 | 3 | 0.4 | 0.4 | 12 | seedbed | Kommt in Schwärmen zu 5, wuselt schnell und unregelmäßig. | 1 |
| `snail` | Gartenschnecke | chaser_tank | 50 | 52 | 10 | 4 | 4 | 36 | seedbed | Langsam, aber das Haus hält viel aus. | 1 |
| `mold` | Schimmelpilz | ranged_lobbed | 16 | 60 | 4 | 3 | 3 | 54 | seedbed | Hält 260 px Abstand und wirft Sporen, die eine Schimmelpfütze (4 Schaden/s, 3 s) hinterlassen. | 1 |
| `potato_beetle` | Kartoffelkäfer | chaser | 18 | 130 | 7 | 2 | 2 | 0 | veggiebed | Flinker Käfer, kommt im Trupp zu 3. | 1 |
| `toxic_carrot` | Giftmöhre | charger | 30 | 70 | 12 | 3 | 3 | 18 | veggiebed | Zielt 0,8 s (Warnlinie), stürmt dann 0,6 s mit Tempo 340 los und ist 1 s benommen. | 1 |
| `spray_cucumber` | Spritzgurke | ranged_direct | 14 | 70 | 7 | 2 | 2 | 36 | veggiebed | Hält 300 px Abstand und spritzt gerade Giftstrahlen (Tempo 280). | 1 |
| `pest_tomato` | Pestizid-Tomate | exploder | 10 | 140 | 18 | 2 | 2 | 0 | compost | Rollt auf dich zu und platzt bei Berührung (Radius 70, 18 Schaden, 0,4 s Warnung). | 1 |
| `vole` | Wühlmaus | chaser_tank | 90 | 58 | 14 | 7 | 7 | 36 | compost | Zäh und bissig, frisst sich durch alles. | 1 |
| `spray_shroom` | Sprühpilz | ranged_lobbed | 18 | 64 | 7 | 3 | 3 | 18 | compost | Hält 280 px Abstand und sprüht Giftwolken (Radius 50, 3 s). | 1 |

Spawn: Position bestimmt das Biom, dort gewichtet `biome_weights` die Mob-Auswahl (nur Mobs mit `min_time_s` erreicht). Gruppen (`group_size`) kosten ihr Budget einmal je Gegner.

### Elite-Gegner

HP x4, Schaden x1.5, XP x5, Größe x1.35, lässt eine Elitetruhe fallen. Affixe (1 ab Start, 2 ab Minute 10, 3 ab Minute 15): **Gepanzert** (-30 % erlittener Schaden.); **Flink** (+40 % Tempo.); **Regenerierend** (Heilt 3 % Max-HP pro Sekunde.); **Explosiv** (Explodiert beim Tod (Radius 100).); **Vampirisch** (Heilt sich um 100 % des verursachten Schadens.); **Schildträger** (Schild in Höhe von 50 % der HP, lädt nach 8 s ohne Treffer neu.).

### Mini-Boss

Bei 2:00 und 12:30: eine zufällige, schon freigeschaltete Mob-Art der Zone, in der der Spieler steht, HP x12, Schaden x2, XP x15, Größe x1.8, eigene Lebensleiste, lässt eine Boss-Truhe (mindestens "selten") fallen.

### Schreine (Risiko gegen Belohnung)

| Schrein | Anzahl | Aktivierung | Schwierigkeit | Effekt | Belohnung | Phase |
|---|---|---|---|---|---|---|
| **Gier-Schrein** (`greed`) | 6 | 1.5 s im Radius 60 px | +5 % | Dauerhaft +5 % Schwierigkeit. | +10 % XP-Gewinn und +5 % Punktemultiplikator je Aktivierung (stapelt). | 2 |
| **Mut-Schrein** (`courage`) | 3 | 20 s im Radius 120 px | +8 % | Dauerhaft +8 %. 20 s im markierten Kreis stehen, währenddessen 1,5x Spawnrate in der Nähe (Fortschritt pausiert außerhalb). | Eine Gratis-Upgradewahl mit mindestens Seltenheit "selten". | 3 |
| **Fluchstein** (`curse`) | 2 | 1.5 s im Radius 60 px | +5 % | Dauerhaft +5 %. Der nächste Biom-Boss erscheint einmal mehr (höchstens +3 Kopien insgesamt). | Bosstruhen bieten eine Karte mehr und eine Seltenheitsstufe höher. | 3 |
| **Elite-Schrein** (`elite`) | 2 | 1.5 s im Radius 60 px | +3 % | Dauerhaft +3 %. Ruft sofort 3 Elite-Gegner mit Affixen. | Jeder Elite lässt eine Elitetruhe fallen (mindestens "selten"). | 3 |

Pro Lauf liegen die Schreine mit festem Seed in den Zonen (jede Zone mindestens einen, nicht in der Lichtung). Aktiviert wird durch Stillstehen im Radius (passt zu Stop-and-Shoot: du schießt dabei weiter). Jeder Schrein ist einmal nutzbar. Die Schwierigkeit zeigt das HUD als Prozentwert.

### Beete und Plagenflut

| Beet | Dauer | Boss | HP x | Schaden x | Gegnermenge x |
|---|---|---|---|---|---|
| 1. Saatbeet | 3:00 | Schleimrun, die Schneckenkönigin | 1 | 1 | 1 |
| 2. Gemüsebeet | 3:00 | Knollgrimm, der Käferkönig | 2.6 | 1.7 | 1.35 |
| 3. Komposthaufen | 3:00 | Der Schnitter | 6 | 2.6 | 1.7 |

Läuft die Zeit eines Beets ab, beginnt die Plagenflut: alle 10 s +40 % Gegner, +15 % Gegner-HP und +8 % Schaden, ohne Ende. Dafür steigen XP und Samenkörner um +25 % je 10 s und die Flutzeit zählt Punkte: Wer zockt, wird stärker und reicher. Alle 30 s rollt eine neue Flutwelle heran: ein Ring aus 12 + 8 je Welle Gegnern direkt um dich, und alle neuen Gegner sind je Welle 8 % schneller. Das Gartentor bleibt offen, sobald der Boss besiegt ist. Gartentor: erscheint, wenn der Boss des Beets besiegt ist. Hineinlaufen bringt dich ins nächste Beet (volle Heilung).

### Bosse

- **Schleimrun, die Schneckenkönigin** (`snail_queen`, 2:06 im Beet, Phase 1): HP 2400, ab 100 % HP: Schleimring (8 Tropfen), alle 4 s; ab 60 % HP: Schleimspur: verlangsamt dich 40 % in einem Kreis, ruft 3 Gartenschnecken; ab 30 % HP: Schleimring doppelt so schnell, Sporenregen.
- **Knollgrimm, der Käferkönig** (`beetle_king`, 2:06 im Beet, Phase 1): HP 6000, ab 100 % HP: Stachelfächer (5 Geschosse, alle 3 s) und Sturmangriff nach Warnlinie (Tempo 380); ab 60 % HP: ruft 4 Kartoffelkäfer, Fächer mit 7 Geschossen; ab 30 % HP: stürmt zweimal hintereinander, Fächer doppelt so schnell.
- **Der Schnitter** (`reaper`, 2:06 im Beet, Phase 1): HP 14000, ab 100 % HP: Sensenring (12 Geschosse), alle 3,5 s; ab 66 % HP: Seelenregen: 6 Einschläge mit Warnkreis (Radius 80), ruft Pestizid-Tomaten; ab 33 % HP: Sensenring alle 2 s, stürmt nach Warnlinie.

## Beete (120 x 120 Felder à 32 px)

| ID | Name | Bereich (x, y, Breite, Höhe in Feldern) | Effekt | Phase |
|---|---|---|---|---|
| `seedbed` | Saatbeet | [0, 0, 120, 120] | Hohe Stauden blockieren Geschosse (Deckung für beide Seiten) | 1 |
| `veggiebed` | Gemüsebeet | [0, 0, 120, 120] | Kohlköpfe versperren den Weg, Geschosse fliegen darüber | 1 |
| `compost` | Komposthaufen | [0, 0, 120, 120] | Giftige Komposthügel versperren den Weg | 1 |

Jedes Beet ist eine eigene Karte; die Startfläche in der Mitte bleibt frei. Hindernisse sind pro Beet mit festem Seed verteilt.

Biom-Farben (Pastell): Saatbeet: Boden #b98a62, Details #a37552; Gemüsebeet: Boden #a8d887, Details #8fc46f; Komposthaufen: Boden #8c7a6a, Details #77665a.

## Items (46, aus Saatkisten)

Samenkörner fallen von Gegnern (35 % je normaler Gegner, Elite 10, Boss 40) und aus Vasen. Saatkisten liegen auf der Karte und kosten Samenkörner; jede geöffnete Kiste macht die nächste 40 % teurer. Elite- und Bosskisten sind gratis und enthalten mindestens seltene bzw. epische Items.

| ID | Name | Seltenheit | Wirkung |
|---|---|---|---|
| `watering_can` | Gießkanne | common | +8 % Angriffstempo. |
| `compost` | Kompost | common | +12 Max-HP. |
| `garden_gloves` | Gartenhandschuhe | common | +8 % Schaden. |
| `straw_hat` | Strohhut | common | -5 % erlittener Schaden. |
| `seed_pouch` | Samenbeutel | common | +15 % Samenkörner. |
| `rake` | Rechen | common | +20 % Aufsammelradius. |
| `snail_shell` | Schneckenhaus | common | +0,4 HP pro Sekunde. |
| `sprout_boots` | Keimstiefel | common | +6 % Lauftempo. |
| `magnifier` | Lupe | common | +5 % Krit-Chance. |
| `sundial` | Sonnenuhr | common | -10 % Abklingzeit der Fähigkeit. |
| `earthworm` | Regenwurm | common | +10 % XP. |
| `garden_twine` | Gartenschnur | common | +8 % Reichweite. |
| `clover` | Kleeblatt | uncommon | +1 Glück: seltenere Karten und Items. |
| `trellis` | Rankhilfe | uncommon | Geschosse durchbohren +1 Gegner. |
| `pruning_shears` | Gartenschere | uncommon | +25 % Krit-Schaden. |
| `scarecrow` | Vogelscheuche | uncommon | +20 % Schaden gegen Elites und Bosse. |
| `deep_roots` | Tiefe Wurzeln | uncommon | +20 % Schaden, solange du stehst. |
| `nettle` | Brennnessel | uncommon | Gegner, die dich berühren, nehmen 8 Schaden. |
| `honey_pot` | Honigtopf | uncommon | Heilt 0,3 HP pro Kill. |
| `cold_frame` | Frühbeetfenster | uncommon | +30 % Schutzzeit nach Treffern. |
| `seed_bomb` | Samenbombe | uncommon | 8 % Chance: Kills explodieren (Radius 60, 50 % Schaden). |
| `twin_pod` | Zwillingsschote | rare | +1 zusätzlicher Schuss. |
| `sunflower` | Sonnenblume | rare | +15 % Schaden, +10 % Reichweite. |
| `beehive` | Bienenstock | rare | +15 % Angriffstempo, +5 % Lauftempo. |
| `rain_barrel` | Regentonne | rare | +30 Max-HP, +0,5 HP pro Sekunde. |
| `golden_leaf` | Goldblatt | rare | +30 % Samenkörner, +1 Glück. |
| `oak_acorn` | Eichel der alten Eiche | epic | +25 % Schaden, +25 Max-HP. |
| `greenhouse` | Gewächshaus | epic | +30 % XP, +40 % Aufsammelradius. |
| `gardeners_spade` | Spaten der Gärtnerin | epic | +1 zusätzlicher Schuss, Geschosse durchbohren +1 Gegner. |
| `first_seed` | Die erste Saat | legendary | +30 % Schaden, +20 % Angriffstempo, +10 % Krit-Chance. |
| `copper_wire` | Kupferdraht | uncommon | 8 % Chance: Blitz springt auf 2 nahe Gegner. |
| `burning_glass` | Brennglas | uncommon | 8 % Chance, Gegner zu entzünden. |
| `nettle_brew` | Brennnesseljauche | uncommon | Treffer vergiften (8 % Schaden/s, stapelt). |
| `frost_fleece` | Frostvlies | uncommon | Treffer verlangsamen um 6 %. |
| `bird_bath` | Vogelbad | uncommon | +5 % Ausweichen. |
| `hedgehog_house` | Igelhaus | uncommon | Wirft 50 % des Nahkampfschadens zurück, +1 Rüstung. |
| `ladybug` | Marienkäfer | rare | +2 % Lebensraub, +3 % Krit-Chance. |
| `bumblebee` | Hummel | rare | Blutrausch: jeder Kill +2 % Angriffstempo (5 s), bis +15 %. |
| `weathervane` | Wetterhahn | rare | Geschosse prallen 1-mal ab. |
| `pitchfork` | Mistgabel | rare | +40 % Schaden gegen Gegner unter 30 % HP. |
| `sun_hat` | Sonnenhut | uncommon | +30 % Schaden bei wenig HP (unter 35 %). |
| `rain_gauge` | Regenmesser | rare | Alle 12 s ein Schild (30 HP). |
| `garden_gnome` | Gartenzwerg | epic | Einmal wiederbeleben (50 % HP). |
| `bell_jar` | Glasglocke | epic | +45 % Schaden, -20 % Max-HP. Hohes Risiko. |
| `thunder_cloud` | Gewitterwolke | epic | +15 % Blitzchance, +30 % Elementarschaden. |
| `compost_heart` | Komposthaufen-Herz | legendary | Splitter bei 30 % der Kills, +2 HP pro Kill, +20 % Flächenradius. |

## Waffen (15, Karten beim Level-up)

4 Waffenplätze (die Startwaffe belegt einen). Neue Waffen erscheinen als Karten beim Level-up, solange ein Platz frei ist; eine Waffe erneut wählen hebt ihre Stufe (höchstens 5). Waffen nutzen Schaden, Angriffstempo und Krit des Spielers.

| ID | Name | Art | Spielweise | Seltenheit | Wirkung | je Stufe |
|---|---|---|---|---|---|---|
| `thorn_twig` | Dornenzweig | fan | Fernkampf | common | Wirft alle 1,2 s einen Fächer aus 3 Dornen auf den nächsten Gegner. | +2 Schaden, +1 Dorn je 2 Stufen. |
| `dandelion` | Pusteblume | fan | Rundum | uncommon | Alle 2 s fliegen 8 Schirmchen in alle Richtungen, durchbohren 1 Gegner. | +2 Schaden, +2 Schirmchen. |
| `pollen_cloud` | Pollenwolke | aura | Nahkampf | common | Eine Wolke um dich (Radius 70) macht alle 0,5 s 4 Schaden. | +1,5 Schaden, +8 Radius. |
| `bees` | Bienenschwarm | orbit | Nahkampf | uncommon | 2 Bienen kreisen um dich (Radius 64) und stechen für 10 Schaden. | +3 Schaden, +1 Biene. |
| `sun_pulse` | Sonnenpuls | nova | Fläche | uncommon | Alle 3 s ein Lichtring um dich (Radius 110, 14 Schaden). | +5 Schaden, +10 Radius, -0,2 s Abklingzeit. |
| `pumpkin_bomb` | Kürbisbombe | lobbed | Fläche | rare | Wirft alle 2,5 s einen Kürbis auf einen Gegner (bis 320 px), der nach 0,9 s platzt (Radius 70, 30 Schaden). | +10 Schaden, +6 Radius, +1 Kürbis je 2 Stufen. |
| `firefly` | Glühwürmchen | chain | Kette | rare | Alle 1,4 s ein Leuchtblitz, der über 3 Gegner springt (9 Schaden, je Sprung 85 %). | +3 Schaden, +1 Sprung. |
| `leaf_boomerang` | Ahornbumerang | boomerang | Durchschlag | uncommon | Alle 1,6 s fliegt ein Ahornblatt hinaus und kehrt zurück; trifft auf beiden Wegen (12 Schaden). | +4 Schaden, +1 Blatt je 2 Stufen. |
| `nettle_trail` | Brennnesselspur | trail | Bewegung | common | Im Laufen wachsen hinter dir Brennnesseln (Radius 26, 2,5 s, 5 Schaden alle 0,5 s). | +2 Schaden, +0,5 s Dauer, +3 Radius. |
| `cactus` | Kaktuswächter | turret | Stellung | uncommon | Pflanzt alle 4 s einen Kaktus (12 s), der Stacheln auf Gegner bis 260 px schießt (8 Schaden, 0,7 s). | +3 Schaden, +1 Kaktus je 2 Stufen, schneller. |
| `sunbeam` | Brennglasstrahl | beam | Durchschlag | rare | Alle 2,2 s ein Lichtstrahl durch alle Gegner in einer Linie (360 px, 22 Schaden). | +7 Schaden, +3 Breite, -0,15 s Abklingzeit. |
| `garlic_mine` | Knoblauchminen | mine | Bewegung | common | Im Laufen legst du jede Sekunde eine Knoblauchzehe (höchstens 4), die bei Berührung platzt (Radius 60, 26 Schaden). | +8 Schaden, +1 Zehe. |
| `seed_shotgun` | Saatflinte | fan | Nahkampf | uncommon | Alle 1,5 s eine Ladung aus 7 Samen auf kurze Distanz (170 px, je 6 Schaden). | +2 Schaden, +1 Samen. |
| `dragonfly` | Libellenschwarm | homing | Zielsuche | rare | Alle 1,8 s fliegen 2 Libellen los und suchen sich selbst ein Ziel (10 Schaden). | +3 Schaden, +1 Libelle je 2 Stufen. |
| `sickle` | Sichel | sweep | Nahkampf | common | Alle 1,1 s ein Hieb im Halbkreis vor dir (Radius 80, 16 Schaden). | +5 Schaden, +6 Radius. |

## Punkte

`Punkte = 2 x Sekunden + 5 x Kills + 20 x Level + 500 x Bosse` (Sieg über den Schnitter +20000; in der Schwarmflut +1000 je 10 s mal Flut-Multiplikator, der Schwierigkeitsfaktor erhöht die Punkte). Highscore je Charakter und gesamt, lokal gespeichert. Modus „Ewige Nacht“ (nach Challenge „Erreiche 20:00“): Gegner-HP x1,5, XP x1,25, Punkte x1,5.

## Funkelsteine, Werkstatt und Startpakete (Meta-Währung)

**Funkelsteine** (`sparkles`): Am Laufende: floor(Punkte / 100 x Belohnungsfaktor). Der Belohnungsfaktor ist 1 + 0,8 x (D - 1), also steigt die Auszahlung mit der Schwierigkeit (Schreine). Nichts geht beim Sterben verloren. Drops im Lauf: normale Gegner 1.5 % Chance auf 1, Elite 2, Mini-Boss 8, Biom-Boss 20, Schnitter 100, Sieg +100, Truhen 3. Challenges zahlen zusätzlich aus (Feld `reward.stones`). Ein 5-Minuten-Lauf bringt etwa 40 bis 50, ein starker 15-Minuten-Lauf etwa 200 Funkelsteine (Modellrechnung, nicht gemessen). Aufschlüsselung: Zeit, Kills, Level, Bosse, Schwierigkeitsbonus, Drops, Challenges.

### Werkstatt (dauerhafte Mini-Verbesserungen)

Kosten je Stufe: `round(base_cost x 1.5^(Stufe-1))`. Jederzeit zu 100 % erstattbar, damit niemand etwas bereut. Die Boni sind klein und begrenzt, damit der Lauf selbst entscheidet und nicht der Grind.

| ID | Name | Effekt | Max. Stufe | Grundpreis | Gesamtpreis |
|---|---|---|---|---|---|
| `ws_hp` | Zähigkeit | +3 % Max-HP je Stufe. | 5 | 50 | 659 |
| `ws_damage` | Kraft | +2 % Schaden je Stufe. | 5 | 60 | 791 |
| `ws_attack` | Eifer | +2 % Angriffstempo je Stufe. | 5 | 60 | 791 |
| `ws_move` | Beinarbeit | +2 % Lauftempo je Stufe. | 5 | 40 | 527 |
| `ws_magnet` | Sammelfreude | +8 % Aufsammelradius je Stufe. | 5 | 30 | 396 |
| `ws_xp` | Wissensdurst | +3 % XP je Stufe. | 5 | 50 | 659 |
| `ws_luck` | Kleeblatt | +2 Glück je Stufe. | 5 | 70 | 923 |
| `ws_range` | Weitblick | +2 % Reichweite je Stufe. | 5 | 40 | 527 |
| `ws_reroll` | Neuwurf-Vorrat | +1 Neuwurf je Stufe (pro Lauf). | 2 | 150 | 375 |
| `ws_banish` | Verbannungs-Vorrat | +1 Verbannen je Stufe (pro Lauf). | 2 | 150 | 375 |
| `ws_shield` | Startschild | +20 Schild-HP zu Beginn, verfällt nach 20 s. | 3 | 80 | 380 |
| `ws_radar` | Schrein-Radar | Schreine sind auf der Karte sichtbar. | 1 | 300 | 300 |

Alle Werkstatt-Stufen zusammen kosten 6703 Funkelsteine. Bei etwa 60 Funkelsteinen je Lauf sind das rund 112 Läufe, also ein langes, aber freiwilliges Ziel.

### Gewächshaus: Wunder und Saatgut

Wunder (einmal kaufen, gelten für jeden Lauf): **Vierblatt** (400): Beim Level-up stehen 4 Karten zur Wahl statt 3.; **Großes Beet** (600): Ein fünfter Waffenplatz.; **Zweite Saat** (500): Einmal pro Lauf wiederbeleben.; **Startpaket** (300): Jeder Lauf beginnt mit einer zufälligen Zusatzwaffe.; **Kistenschlüssel** (250): Kisten auf der Karte kosten 25 % weniger Samen..

Saatgut (Waffe wächst in den Kartenpool): `leaf_boomerang` 120, `nettle_trail` 120, `garlic_mine` 150, `seed_shotgun` 150, `cactus` 180, `firefly` 200, `sickle` 200, `dragonfly` 220, `sunbeam` 250. Die übrigen Waffen sind von Anfang an da.

### Startpakete (vor dem Lauf, verbrauchen sich)

Höchstens 2 je Lauf. **Proviant** (25): +5 % Heilkugel-Chance in diesem Lauf.; **Glücksbringer** (40): +10 Glück in diesem Lauf.; **Schatzkarte** (30): Schreine sind in diesem Lauf auf der Karte sichtbar.; **Frühstart** (60): Start bei Level 3 (2 Gratis-Upgradewahlen)..

### Farbtöpfe (Kosmetik)

Rein kosmetische Zusatzfarben für jeden Charakter (Paletten-Tausch der Ramp-Farben). 3 Varianten je Charakter (Zuckerwatte, Minze, Sonnenuntergang) für je 150 Funkelsteine, zusammen 4500.

## Challenges (67)

| ID | Aufgabe | Belohnung |
|---|---|---|
| `unlock_pyro` | Erreiche Minute 3 mit beliebigem Charakter. | unlock_character: pyro |
| `unlock_rogue` | Räume eine Welle ab Welle 5, ohne Schaden zu nehmen. | unlock_character: rogue |
| `unlock_guardian` | Erleide insgesamt 5000 Schaden. | unlock_character: guardian |
| `unlock_cryo` | Besiege 300 Gegner im Komposthaufen. | unlock_character: cryo |
| `unlock_summoner` | Erreiche Level 15 in einem Run. | unlock_character: summoner |
| `unlock_storm` | Erreiche das zweite Beet. | unlock_character: storm |
| `unlock_bomber` | Besiege insgesamt 2000 Gegner. | unlock_character: bomber |
| `unlock_venom` | Verursache insgesamt 10000 Giftschaden. | unlock_character: venom |
| `unlock_sniper` | Besiege alle drei Beet-Bosse (Schleimrun, Knollgrimm, den Schnitter). | unlock_character: sniper |
| `unlock_up_stillness` | Schließe 10 Runs ab. | title: Ausdauernd |
| `unlock_up_minion_horde` | Schalte 3 Charaktere frei. | unlock_upgrade: minion_horde |
| `unlock_up_orbiting_blades` | Erreiche Level 20 in einem Run. | unlock_upgrade: orbiting_blades |
| `unlock_up_executioner` | Besiege 25 Elite-Gegner. | title: Elitejäger |
| `unlock_up_lifesteal` | Besiege insgesamt 1000 Gegner. | title: Plagenschreck |
| `unlock_up_shield_burst` | Räume eine Welle ab Welle 8, ohne Schaden zu nehmen. | title: Unberührt |
| `unlock_up_last_stand` | Verbringe insgesamt 60 s mit unter 20 % HP. | title: Zähe Bohne |
| `unlock_up_overcharge` | Lande insgesamt 3000 kritische Treffer. | title: Volltreffer |
| `unlock_up_explosive_rounds` | Besiege insgesamt 3000 Gegner. | title: Gärtnermeister |
| `unlock_up_second_wind` | Besiege den ersten Boss. | title: Beetbefreier |
| `unlock_up_gravity_well` | Erreiche das dritte Beet. | unlock_upgrade: gravity_well |
| `unlock_up_bloodlust` | Besiege 800 Gegner in einem Run. | title: Blutrausch |
| `unlock_up_time_warp` | Überlebe 2 Minuten Plagenflut. | unlock_upgrade: time_warp |
| `unlock_up_shrapnel` | Besiege insgesamt 10000 Gegner. | title: Erntehelfer |
| `unlock_up_titan_heart` | Erleide 1500 Schaden in einem Run. | title: Dickhaut |
| `unlock_up_glass_cannon` | Erreiche das zweite Beet in unter 4 Minuten. | title: Eilig |
| `unlock_up_reaper_pact` | Besiege insgesamt 10 Bosse. | title: Bossbrecher |
| `unlock_up_elemental_storm` | Besitze Entzünden, Kälte, Toxin und Schock in einem Run. | title: Elementar |
| `skin_ranger_a` | Erreiche mit Fenn das zweite Beet. | unlock_skin: ranger_a |
| `skin_ranger_b` | Erreiche mit Fenn das dritte Beet. | unlock_skin: ranger_b |
| `skin_pyro_a` | Erreiche mit Mira das zweite Beet. | unlock_skin: pyro_a |
| `skin_pyro_b` | Erreiche mit Mira das dritte Beet. | unlock_skin: pyro_b |
| `skin_rogue_a` | Erreiche mit Kaz das zweite Beet. | unlock_skin: rogue_a |
| `skin_rogue_b` | Erreiche mit Kaz das dritte Beet. | unlock_skin: rogue_b |
| `skin_guardian_a` | Erreiche mit Brun das zweite Beet. | unlock_skin: guardian_a |
| `skin_guardian_b` | Erreiche mit Brun das dritte Beet. | unlock_skin: guardian_b |
| `skin_cryo_a` | Erreiche mit Ysa das zweite Beet. | unlock_skin: cryo_a |
| `skin_cryo_b` | Erreiche mit Ysa das dritte Beet. | unlock_skin: cryo_b |
| `skin_summoner_a` | Erreiche mit Thorn das zweite Beet. | unlock_skin: summoner_a |
| `skin_summoner_b` | Erreiche mit Thorn das dritte Beet. | unlock_skin: summoner_b |
| `skin_storm_a` | Erreiche mit Vex das zweite Beet. | unlock_skin: storm_a |
| `skin_storm_b` | Erreiche mit Vex das dritte Beet. | unlock_skin: storm_b |
| `skin_bomber_a` | Erreiche mit Orm das zweite Beet. | unlock_skin: bomber_a |
| `skin_bomber_b` | Erreiche mit Orm das dritte Beet. | unlock_skin: bomber_b |
| `skin_venom_a` | Erreiche mit Lilu das zweite Beet. | unlock_skin: venom_a |
| `skin_venom_b` | Erreiche mit Lilu das dritte Beet. | unlock_skin: venom_b |
| `skin_sniper_a` | Erreiche mit Aya das zweite Beet. | unlock_skin: sniper_a |
| `skin_sniper_b` | Erreiche mit Aya das dritte Beet. | unlock_skin: sniper_b |
| `boss_snail_queen` | Besiege Schleimrun. | title: Schneckenschreck |
| `boss_beetle_king` | Besiege Knollgrimm. | title: Käferknacker |
| `reach_swarm` | Überlebe 30 s Plagenflut. | unlock_mode: eternal_night |
| `boss_reaper` | Besiege den Schnitter. | title: Sensenmeister |
| `shrines_5` | Aktiviere 5 Schreine in einem Run. | title: Wagemutig |
| `swarm_5min` | Überlebe 3 Minuten Plagenflut. | title: Flutreiter |
| `golden_snail_1` | Fang eine Goldschnecke. | title: Goldgräber |
| `golden_snail_3` | Fang drei Goldschnecken in einem Lauf. | title: Schneckenbaron |
| `gnome_free` | Finde und befreie den Gartenzwerg. | title: Zwergenfreund |
| `ladybugs_3` | Sammle drei Glückskäfer in einem Lauf. | title: Glückspilz |
| `still_life` | Stehe 30 Sekunden am Stück still. | title: Stillleben |
| `flawless_boss` | Besiege einen Boss, ohne getroffen zu werden. | title: Unantastbar |
| `marathon` | Laufe in einem Lauf 2000 Meter. | title: Marathonbohne |
| `hoarder` | Besitze fünf Kopien desselben Items. | title: Hamsterbohne |
| `pilgrim` | Aktiviere alle vier Schreinarten in einem Lauf. | title: Pilgerbohne |
| `menu_squish` | Zerdrücke zehn Schnecken im Hauptmenü. | title: Pausenclown |
| `express_boss` | Besiege Schleimrun vor 2:30. | title: Schneckenpost |
| `chain_reaction` | Besiege 60 Gegner innerhalb von 10 Sekunden. | title: Kettenreaktion |
| `night_owl` | Erreiche in der Ewigen Nacht das zweite Beet. | title: Nachteule |
| `arsenal` | Fülle alle Waffenplätze in einem Lauf. | title: Waffennarr |

## Umsetzungsphasen (Vertical Slice zuerst)

- **Phase 1:** Jäger, 12 Upgrades (Phase 1), Mobs Schleimling, Fledermaus, Wurzelwächter, Sporenschütze, Biom Wald plus Lichtung, Boss Ildra. Spielbar von 0 bis 5:00.
- **Phase 2:** Pyro, Schurke, Wächter, Frost; restliche gewöhnliche/ungewöhnliche/seltene Upgrades; Wüste und Eis; Skarra, Kalthorn; Mini-Boss, Gier-Schreine, Schwarmflut; Profil, Challenges, Skins.
- **Phase 3:** Beschwörer, Sturm, Sprengmeister, Gift, Scharfschütze; epische und legendäre Upgrades; Lava; Ignarok; Boss-Altar mit dem Schnitter, Mut-Schrein, Fluchstein, Elite-Schrein; RL-Umgebung.

