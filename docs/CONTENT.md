# CONTENT: festes Inhaltskonzept

Alle Zahlen sind **Startwerte aus einer Modellrechnung**, nicht aus gespielten Runs. Sie werden später mit einer Headless-Simulation (Bot-Läufe) justiert. Diese Datei wird von `tools/build_content.py` erzeugt, die Quelle der Wahrheit sind die JSON-Dateien in `data/`. IDs nie ohne Rückfrage ändern.

## Lauf und Schwierigkeit

- **Eine Arena, keine Portale, keine Stufenwechsel.** Die Arena wächst über die Zeit: neue Mob-Arten, Biom-Bosse, später die Schwarmflut. Das Vorbild beim Schwierigkeitsaufbau ist Megabonk (ohne dessen Portale und Stufen).
- Welle alle **30 s**, ohne Pause. Level-ups pausieren das Spiel.
- **Schwierigkeit = Zeit x Entscheidungen.** Zeit: Budget je Welle `w` = `10 + 5,5*w + 0,22*w²`, Gegner-HP `x (1 + 0,10*m + 0,012*m²)`, Schaden `x (1 + 0,05*m + 0,004*m²)`, Tempo `x (1 + 0,01*m)` bis 1,2 (m = Minuten). Entscheidungen: Schreine erhöhen einen Schwierigkeitsfaktor `D` dauerhaft. `D` wirkt auf Gegnerzahl, Spawnrate und Gegnerschaden. Dafür steigen XP und Punkte um `1 + 0,8*(D-1)`. Die Schwierigkeit steht als Prozentwert im HUD. Höchstens 350 Gegner gleichzeitig.
- **Mehrfach-Skalierung wie bei Megabonk:** Gleiche Quellen addieren sich, verschiedene multiplizieren sich (Schaden x Krit x Angriffstempo). So entsteht die steile Kurve, in der Builds den Unterschied machen.
- **Bossplan:** Mini-Boss mit eigener Lebensleiste bei **2:00** und **12:30**. Biom-Bosse: **5:00** Ildra (Wald), **7:30** Skarra (Wüste), **10:00** Kalthorn (Eis), **15:00** Ignarok (Lava), jeder in seiner Zone. Elite alle 5 Wellen (2:30, 5:00 ...). Der Fluchstein verdoppelt Bossauftritte.
- **Endboss per Altar:** Ab **10:00** kann der Boss-Altar in der Lichtung aktiviert werden. Er ruft **Den Schnitter** (HP `30000 x HP-Faktor zur Beschwörungszeit`, nach 90 s Wutphase). Früher rufen heißt weniger Upgrades, aber schwächerer Boss, später heißt stärker und stärkerer Boss. Sieg beendet den Lauf (+20000 Punkte), danach optional weiterspielen.
- **Schwarmflut ab 20:00** (wenn der Schnitter nicht schon besiegt ist): fliegende Flutgeister in Schüben alle 3 s, Schubgröße +10 % pro Minute, Tempo +8 % pro Minute, Punktemultiplikator von x1 bis x8 (+1 je 45 s). Die Skalierung endet nie: Es bleibt möglich, wird aber immer schwerer.
- **Machbarkeitsregeln:** glatte Kurve ohne Sprünge, jeder gefährliche Angriff hat eine Vorwarnung, jeder Boss hat ein klares Muster, nichts ist unverwundbar außer kurzen Phasen.
- **Zielkurve (Ziel, nicht gemessen):** Einsteiger sterben bei 3 bis 5 min, Geübte bei 8 bis 12, Experten bei 14 bis 18, 20:00 erreicht kaum jemand.

### Modellrechnung (Ø 9.2 HP je Budgetpunkt, alles wird getötet)

| Minute | Welle | Budget | HP x | Schaden x | nötige HP/s | Level (ca.) | XP gesamt |
|---|---|---|---|---|---|---|---|
| 1 | 2 | 55 | 1.1 | 1.1 | 19 | 8 | 102 |
| 5 | 10 | 132 | 1.8 | 1.4 | 73 | 21 | 870 |
| 10 | 20 | 268 | 3.2 | 1.9 | 263 | 34 | 2901 |
| 15 | 30 | 448 | 5.2 | 2.6 | 714 | 46 | 6535 |
| 20 | 40 | 672 | 7.8 | 3.6 | 1606 | 58 | 12211 |

Die Spalte „nötige HP/s“ ist die Leistung, die du brauchst, um alles Erscheinende zu töten. Ein Start-Jäger macht rund 19 Schaden pro Sekunde auf ein Ziel. Das Spiel soll so gebaut sein, dass starke Builds (Flächenschaden, Durchschlag, Ketten) diese Kurve bis etwa Minute 14 bis 18 halten können.

## Charaktere (10)

| Name | Spielstil | HP | Tempo | Schaden | Schuss/s | Reichweite | Krit | Waffe | Passiv | Fertigkeit | Freischaltung | Phase |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| **Fenn der Falkenauge** (`ranger`) | Jäger: ausgewogen, durchschlagende Pfeile | 100 | 180 | 12 | 2.0 | 380 | 5 % | Ein Pfeil, durchschlägt 1 Gegner. | **Weitblick**: +12 % Reichweite. +8 % Schaden auf Ziele über 250 px. | **Pfeilhagel** (18 s): 16 Pfeile in alle Richtungen (je 60 % Schaden). | von Anfang an | 1 |
| **Mira Aschenglut** (`pyro`) | Pyromantin: Flächenschaden und Brand | 80 | 140 | 14 | 1.1 | 320 | 5 % | Feuerball explodiert (Radius 64) und entzündet (3 s, 20 % Schaden/s). | **Hitzewelle**: Brennende Gegner erleiden +20 % Schaden. | **Inferno** (22 s): Feuerring (Radius 180) um dich, 4 s, 40 % Schaden/s. | Erreiche Minute 5 mit beliebigem Charakter. | 2 |
| **Kaz Nachtmesser** (`rogue`) | Schurke: schnell, kritisch, kurze Reichweite | 85 | 190 | 7 | 2.2 | 210 | 20 % | Fächer aus 3 Wurfmessern. | **Nervenkitzel**: +15 % Lauftempo. +6 % Schaden je Gegner im Umkreis 150 px (max. 5). | **Schattenschritt** (5 s): Dash über 220 px, 0,3 s unverwundbar. | Räume eine Welle ab Welle 5, ohne Schaden zu nehmen. | 2 |
| **Brun Eisenschulter** (`guardian`) | Wächter: Nahkampf-Tank mit Dornen | 160 | 120 | 20 | 0.9 | 110 | 0 % | Schockwelle um dich (Radius 110) mit Rückstoß. | **Eisenhaut**: -15 % erlittener Schaden. Reflektiert 25 % des Nahkampfschadens. | **Bollwerk** (25 s): Schild für 3 s, absorbiert 150 Schaden. | Erleide insgesamt 5000 Schaden. | 2 |
| **Ysa Winterhauch** (`cryo`) | Frostmagierin: Kontrolle und Verlangsamung | 90 | 145 | 10 | 1.3 | 340 | 5 % | Frostgeschoss verlangsamt um 30 % (2 s). 3 Kältestapel frieren 1,2 s ein. | **Frostaura**: Gegner im Umkreis von 140 px sind 15 % langsamer. | **Eiszeit** (24 s): Friert alle Gegner im Bild 2 s ein. | Besiege 300 Gegner im Eisbiom. | 2 |
| **Thorn Geisterruf** (`summoner`) | Beschwörer: Begleiter kämpfen für ihn | 90 | 140 | 6 | 1.0 | 300 | 5 % | Schwacher Geisterbolzen. 2 Geister-Begleiter greifen selbstständig an (8 Schaden, 1,5/s). | **Seelenband**: Geister erhalten 50 % deiner Schadensboni. | **Totenruf** (30 s): 4 zusätzliche Geister für 10 s. | Erreiche Level 15 in einem Run. | 3 |
| **Vex Donnerhall** (`storm`) | Sturmrufer: Kettenblitze, hohe Schussrate | 80 | 160 | 8 | 2.4 | 300 | 5 % | Kettenblitz springt 2-mal (160 px, je 80 % Schaden). | **Statische Ladung**: Jeder 10. Schuss ruft einen Blitzschlag (200 % Schaden) auf einen zufälligen Gegner. | **Gewittersturm** (28 s): 6 s lang 4 Blitze pro Sekunde auf zufällige Gegner. | Erreiche Minute 8. | 3 |
| **Orm Zündfunke** (`bomber`) | Sprengmeister: Bomben im Stand, Minen im Lauf | 110 | 150 | 26 | 0.7 | 300 | 5 % | Bombe im Bogen, explodiert nach 0,6 s (Radius 90). | **Minenleger**: Legt beim Laufen alle 1,5 s eine Mine (60 % Schaden, Radius 70, max. 6). | **Megabombe** (20 s): Große Bombe (Radius 200, 500 % Schaden). | Besiege insgesamt 2000 Gegner. | 3 |
| **Lilu Schierling** (`venom`) | Giftmischerin: Giftpfützen und Seuche | 85 | 150 | 5 | 1.4 | 330 | 5 % | Giftphiole: Pfütze (Radius 55, 3 s, 12 Gift/s, stapelt bis 4x). | **Seuche**: Vergiftete Gegner verbreiten beim Tod Gift (Radius 80). | **Giftnebel** (26 s): Wolke (Radius 160) für 8 s, 35 % Schaden/s, verlangsamt 20 %. | Verursache insgesamt 10000 Giftschaden. | 3 |
| **Aya Stillstand** (`sniper`) | Scharfschützin: je länger sie steht, desto härter | 75 | 130 | 40 | 0.45 | 600 | 10 % | Durchschlag-Schuss (3). +10 % Schaden je Sekunde Stillstand (max. +100 %). | **Ruhe vor dem Schuss**: Nach 2 s Stillstand ist der nächste Schuss ein garantierter Krit (x2,5). | **Fokus** (20 s): 4 s lang: schießt auch im Lauf, doppelte Schussrate. | Besiege alle vier Biom-Bosse (Ildra, Skarra, Kalthorn, Ignarok). | 3 |

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
| `quick_learner` | Schnelle Auffassung | 4 | +8 % XP je Stufe. | utility | von Anfang an | 2 |
| `heal_orbs` | Heilkugeln | 3 | Gegner lassen mit 3 % je Stufe Heilkugeln fallen (5 HP). | defense, utility | von Anfang an | 2 |
| `wide_blast` | Breite Wirkung | 4 | +10 % Flächenradius je Stufe. | area | von Anfang an | 2 |
| `thorns` | Dornenpanzer | 4 | Reflektiert 20 % des erlittenen Nahkampfschadens je Stufe. | defense, thorns | von Anfang an | 2 |
| `big_shots` | Schwere Geschosse | 3 | +12 % Geschossgröße je Stufe (trifft leichter). | projectile | von Anfang an | 2 |
| `fast_shots` | Schnelle Geschosse | 3 | +12 % Geschossgeschwindigkeit je Stufe. | projectile | von Anfang an | 2 |
| `dodge` | Ausweichen | 5 | 3 % Chance je Stufe, einem Treffer zu entgehen. | defense | von Anfang an | 2 |
| `armor_plating` | Panzerplatten | 4 | -1 Schaden je Treffer und Stufe (mindestens 1). | defense | von Anfang an | 2 |
| `lucky_charm` | Glücksklee | 4 | +5 Glück je Stufe: seltenere Upgrades werden wahrscheinlicher. | utility | von Anfang an | 2 |
| `bounty_hunter` | Kopfgeldjäger | 4 | +6 % Schaden gegen Elite und Bosse je Stufe. | damage | von Anfang an | 2 |

### Ungewöhnlich

| ID | Name | Max. Stufe | Effekt | Tags | Freischaltung | Phase |
|---|---|---|---|---|---|---|
| `brutal_crits` | Brutale Treffer | 4 | +20 % Krit-Schaden je Stufe (Basis 150 %). | crit | von Anfang an | 1 |
| `double_shot` | Mehrfachangriff | 3 | +1 zusätzlicher Angriff je Stufe (60 % Schaden, leichte Streuung). | projectile | von Anfang an | 1 |
| `piercing` | Durchschlag | 3 | Geschosse durchbohren +1 Gegner je Stufe. | pierce, projectile | von Anfang an | 1 |
| `heavy_hitter` | Schwergewicht | 3 | +25 % Schaden, -10 % Angriffstempo je Stufe. | damage | von Anfang an | 2 |
| `regeneration` | Regeneration | 4 | +0,6 HP pro Sekunde je Stufe. | defense | von Anfang an | 1 |
| `reroll` | Neuwurf | 3 | +1 Neuwurf der Upgrade-Auswahl je Stufe (pro Run). | utility | von Anfang an | 2 |
| `banish` | Verbannung | 3 | +1 Verbannen je Stufe: entfernt ein Upgrade aus dem Pool dieses Runs. | utility | von Anfang an | 2 |
| `stillness` | Meditation | 3 | Nach 1 s Stillstand +12 % Schaden je Stufe. | stillness, damage | Schließe 10 Runs ab. | 2 |
| `ignite` | Entzünden | 4 | 12 % Chance je Stufe zu entzünden (3 s, 30 % Schaden/s). | fire, elemental | von Anfang an | 2 |
| `chill` | Kälte | 4 | Treffer verlangsamen um 8 % je Stufe (max. 32 %). | frost, elemental | von Anfang an | 2 |
| `toxin` | Toxin | 4 | Treffer vergiften (15 % Schaden/s je Stufe, 3 s, stapelt 4x). | poison, elemental | von Anfang an | 2 |
| `shock` | Schock | 3 | 15 % Chance je Stufe auf einen Blitz (60 % Schaden) auf einen nahen Gegner. | lightning, elemental | von Anfang an | 2 |
| `minion_horde` | Gefolgschaft | 3 | +1 Begleiter je Stufe (ohne Beschwörer: Irrlicht mit 50 % Schaden). | summon | Schalte 3 Charaktere frei. | 3 |
| `orbiting_blades` | Kreisende Klingen | 4 | Eine zusätzliche Klinge je Stufe umkreist dich (6 Schaden). | area, melee | Erreiche Level 20 in einem Run. | 3 |

### Selten

| ID | Name | Max. Stufe | Effekt | Tags | Freischaltung | Phase |
|---|---|---|---|---|---|---|
| `ricochet` | Rückprall | 3 | Geschosse springen +1-mal je Stufe auf einen nahen Gegner (70 % Schaden). | bounce, projectile | von Anfang an | 2 |
| `executioner` | Henker | 3 | +30 % Schaden gegen Gegner unter 30 % HP je Stufe. | damage | Besiege 25 Elite-Gegner. | 2 |
| `lifesteal` | Aderlass | 3 | Heilt 2 % des verursachten Schadens je Stufe. | defense, damage | Besiege insgesamt 1000 Gegner. | 2 |
| `shield_burst` | Notschild | 3 | Schild (40 HP) alle 20 s, -2 s je Stufe. | defense | Räume eine Welle ab Welle 8, ohne Schaden zu nehmen. | 2 |
| `last_stand` | Letztes Gefecht | 3 | Unter 30 % HP: +30 % Schaden und +20 % Tempo je Stufe. | defense, damage | Verbringe insgesamt 60 s mit unter 20 % HP. | 2 |
| `overcharge` | Überladung | 3 | Alle 15 s (-2 s je Stufe) trifft der nächste Angriff mit 300 % Schaden. | damage | Lande insgesamt 3000 kritische Treffer. | 2 |
| `explosive_rounds` | Sprengmunition | 3 | Treffer lösen eine kleine Explosion aus (Radius 50, 40 % Schaden je Stufe). | area, projectile | Besiege insgesamt 3000 Gegner. | 2 |
| `aura_of_pain` | Aura des Schmerzes | 4 | Gegner im Umkreis von 100 px erleiden 4 Schaden/s je Stufe. | area, melee | von Anfang an | 2 |
| `elemental_mastery` | Elementarmeister | 3 | +20 % Schaden aller Elementareffekte (Brand, Frost, Gift, Schock) je Stufe. | elemental | von Anfang an | 2 |

### Episch

| ID | Name | Max. Stufe | Effekt | Tags | Freischaltung | Phase |
|---|---|---|---|---|---|---|
| `second_wind` | Zweiter Atem | 2 | Stufe 1: einmal pro Run mit 40 % HP wiederbeleben. Stufe 2: 60 % HP und 2 s unverwundbar. | defense | Besiege den ersten Boss. | 3 |
| `gravity_well` | Schwerkraftbrunnen | 2 | Alle 12 s zieht ein Sog alle Gegner im Radius 200 zusammen (Stufe 2: Radius 280, alle 9 s). | control, area | Erreiche Minute 10. | 3 |
| `bloodlust` | Blutrausch | 3 | Jeder Kill: +2 % Angriffstempo für 5 s, stapelt bis 20 % / 30 % / 40 %. | speed | Besiege 800 Gegner in einem Run. | 3 |
| `time_warp` | Zeitdehnung | 2 | Im Stand sind alle Gegner im Radius 250 um 12 % / 20 % langsamer. | control, stillness | Erreiche Minute 12. | 3 |
| `shrapnel` | Splitterhagel | 3 | Sterbende Gegner lösen mit 20 % Chance 6 Splitter aus (50 % Schaden), +10 % je Stufe. | area, projectile | Besiege insgesamt 10000 Gegner. | 3 |
| `titan_heart` | Titanenherz | 3 | +30 % Max-HP je Stufe. +1 % Schaden je 10 Max-HP. | defense | Erleide 1500 Schaden in einem Run. | 3 |

### Legendär

| ID | Name | Max. Stufe | Effekt | Tags | Freischaltung | Phase |
|---|---|---|---|---|---|---|
| `glass_cannon` | Glaskanone | 1 | +100 % Schaden, -40 % Max-HP. | damage | Erreiche Minute 15. | 3 |
| `reaper_pact` | Pakt der Sense | 1 | Jeder Kill heilt 1 HP. Alle 25 Kills ein Todesschlag (Radius 250, 500 % Schaden). | damage, defense | Besiege insgesamt 10 Bosse. | 3 |
| `elemental_storm` | Elementarsturm | 1 | Alle Elementareffekte (Brand, Frost, Gift, Schock) können auf jeden Treffer wirken, +50 % Elementarschaden. | elemental | Besitze Entzünden, Kälte, Toxin und Schock in einem Run. | 3 |

## Mob-Typen (10)

| ID | Name | Verhalten | HP | Tempo | Schaden | Kosten | XP | ab Sek. | Biom | Beschreibung | Phase |
|---|---|---|---|---|---|---|---|---|---|---|---|
| `slimeling` | Schleimling | chaser | 12 | 62 | 5 | 1 | 1 | 0 | alle | Läuft geradeaus auf dich zu. Der Standardgegner. | 1 |
| `batswarm` | Fledermaus | swarm | 5 | 120 | 3 | 0.5 | 0.5 | 60 | forest | Kommt in Gruppen zu 4, flattert unregelmäßig, sehr schnell. | 1 |
| `rootguard` | Wurzelwächter | chaser_tank | 55 | 38 | 10 | 4 | 4 | 90 | forest | Langsam und zäh, kaum Rückstoß. | 1 |
| `sporeshooter` | Sporenschütze | ranged_lobbed | 16 | 45 | 4 | 3 | 3 | 120 | forest | Hält 260 px Abstand und wirft Sporen, die eine Giftpfütze (4 Schaden/s, 3 s) hinterlassen. | 1 |
| `sandspitter` | Sandspeier | ranged_direct | 14 | 55 | 7 | 2 | 2 | 100 | desert | Hält 300 px Abstand und schießt gerade Sandgeschosse (Tempo 260). | 2 |
| `dunescorpion` | Dünenskorpion | charger | 30 | 50 | 12 | 3 | 3 | 150 | desert | Markiert 0,8 s eine Linie, stürmt dann 0,6 s mit Tempo 260 los und ist 1,2 s erschöpft. | 2 |
| `frostwolf` | Frostwolf | chaser_pack | 20 | 105 | 7 | 2 | 2 | 180 | ice | Schneller Läufer, kommt im Rudel zu 3. | 2 |
| `icegolem` | Eisgolem | chaser_tank | 90 | 32 | 14 | 7 | 7 | 240 | ice | Sehr zäh und langsam. Zerplatzt beim Tod in 8 Eissplitter (6 Schaden). | 2 |
| `emberimp` | Glutimp | ranged_lobbed | 18 | 58 | 9 | 3 | 3 | 210 | lava | Hält 280 px Abstand und wirft Feuerbälle (Radius 50), die 3 s Feuer am Boden hinterlassen. | 3 |
| `lavabug` | Lavakäfer | exploder | 10 | 95 | 18 | 2 | 2 | 270 | lava | Rennt auf dich zu und explodiert bei Berührung (Radius 70, 18 Schaden), auch beim Tod (50 %). | 3 |

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

### Schwarmflut (ab 20:00)

Ab 20:00 beginnt die Schwarmflut: fliegende Flutgeister in Schüben, die nie aufhört und immer schneller wird. Sie ist der Endlos-Modus für den Highscore. Flutgeist: HP 6, Tempo 75, Schaden 6, fliegt und ignoriert Hindernisse. Schub alle 3 s mit 40 Gegnern (+10 % je Minute), Tempo +8 % je Minute. Punktemultiplikator x1, +1 je 45 s, höchstens x8. HP und Schaden skalieren weiter wie bei normalen Gegnern.

### Bosse

- **Ildra, die Dornenkönigin** (`ildra`, 5:00, Phase 1): HP 2500, ab 100 % HP: Rotierender Dornenring (8 Geschosse), alle 4 s; ab 60 % HP: Wurzelgriff: verlangsamt dich 40 % in einem Kreis, ruft 3 Wurzelwächter; ab 30 % HP: Dornenring doppelt so schnell, Spore-Regen.
- **Skarra, die Sandkönigin** (`skarra`, 7:30, Phase 2): HP 5000, ab 100 % HP: Stachelfächer (5 Sandstacheln, alle 3 s) und Sturmangriff nach Warnlinie (Tempo 300); ab 60 % HP: Eingraben: verschwindet, bricht nach 1,5 s Warnkreis (Radius 120) unter dir hervor, ruft Dünenskorpione; ab 30 % HP: Sandwirbel über Teilen des Bildes (halbtransparent, Gegner und Geschosse bleiben sichtbar), Stachelfächer doppelt so schnell.
- **Kalthorn, der Eiswurm** (`kalthorn`, 10:00, Phase 2): HP 9000, ab 100 % HP: Frostbahn: Linie markieren, dann Sturm (Tempo 320); ab 60 % HP: Eisnova (Radius 260), ruft Frostwolf-Rudel; ab 30 % HP: Eisnova alle 5 s, Boden wird rutschig.
- **Ignarok, der Glutkoloss** (`ignarok`, 15:00, Phase 3): HP 24000, ab 100 % HP: Meteorregen (6 Einschläge, 1,2 s Vorwarnung); ab 60 % HP: Stampfen: Schockwelle (Radius 300), Lavapfützen; ab 30 % HP: Meteore doppelt, ruft Lavakäfer.
- **Der Schnitter** (`reaper`, per Altar ab 10:00, Phase 3): HP 30000 x HP-Faktor, Wutphase nach 90 s, ab 100 % HP: Sensenwirbel: rotierender Kegel mit 1 s Warnfläche, alle 5 s; ab 66 % HP: Seelenregen: 8 Einschläge mit Warnkreis (Radius 90) in Wellen, ruft Flutgeister; ab 33 % HP: Zeitriss: du bist 3 s lang 30 % langsamer, er stürmt dreimal; danach 25 % mehr Tempo.

## Arena und Biome (200 x 200 Felder à 32 px)

| ID | Name | Bereich (x, y, Breite, Höhe in Feldern) | Effekt | Phase |
|---|---|---|---|---|
| `plaza` | Lichtung (Start) | [85, 85, 30, 30] | Keine, enthält den Boss-Altar (ab 10:00 aktivierbar, ruft den Schnitter) | 1 |
| `forest` | Wald | [0, 0, 100, 100] | Bäume blockieren Geschosse (Deckung für beide Seiten) | 1 |
| `desert` | Wüste | [100, 0, 100, 100] | Du bist 15 % langsamer | 2 |
| `ice` | Eis | [0, 100, 100, 100] | Rutschen: träge Beschleunigung und Bremsen | 2 |
| `lava` | Lava | [100, 100, 100, 100] | 4 Schaden pro Sekunde in Lavapfützen, dafür +25 % XP in der Zone | 3 |

Layout (seit 28.10.2026 große Karte): Lichtung in der Mitte (30 x 30, überlagert die Quadranten), Wald oben links, Wüste oben rechts, Eis unten links, Lava unten rechts. Hindernisse sind pro Biom mit festem Seed verteilt.

Biom-Farben (Pastell): Lichtung (Start): Boden #b9e08f, Details #9fcf72; Wald: Boden #a6dd82, Details #83c564; Wüste: Boden #f6dfa8, Details #e8c47a; Eis: Boden #d6ecff, Details #b4d6f5; Lava: Boden #ffc9b0, Details #ff9f86. Gefahren (Lava, Sand, Eisglanz) heben sich über die Farbe `hazard` ab.

## Items (30, aus Saatkisten)

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

## Waffen (6, Karten beim Level-up)

4 Waffenplätze (die Startwaffe belegt einen). Neue Waffen erscheinen als Karten beim Level-up, solange ein Platz frei ist; eine Waffe erneut wählen hebt ihre Stufe (höchstens 5). Waffen nutzen Schaden, Angriffstempo und Krit des Spielers.

| ID | Name | Art | Seltenheit | Wirkung | je Stufe |
|---|---|---|---|---|---|
| `thorn_twig` | Dornenzweig | fan | common | Wirft alle 1,2 s einen Fächer aus 3 Dornen auf den nächsten Gegner. | +2 Schaden, +1 Dorn je 2 Stufen. |
| `dandelion` | Pusteblume | fan | uncommon | Alle 2 s fliegen 8 Schirmchen in alle Richtungen, durchbohren 1 Gegner. | +2 Schaden, +2 Schirmchen. |
| `pollen_cloud` | Pollenwolke | aura | common | Eine Wolke um dich (Radius 70) macht alle 0,5 s 4 Schaden. | +1,5 Schaden, +8 Radius. |
| `bees` | Bienenschwarm | orbit | uncommon | 2 Bienen kreisen um dich (Radius 64) und stechen für 10 Schaden. | +3 Schaden, +1 Biene. |
| `sun_pulse` | Sonnenpuls | nova | uncommon | Alle 3 s ein Lichtring um dich (Radius 110, 14 Schaden). | +5 Schaden, +10 Radius, -0,2 s Abklingzeit. |
| `pumpkin_bomb` | Kürbisbombe | lobbed | rare | Wirft alle 2,5 s einen Kürbis auf einen Gegner (bis 320 px), der nach 0,9 s platzt (Radius 70, 30 Schaden). | +10 Schaden, +6 Radius, +1 Kürbis je 2 Stufen. |

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

### Startpakete (vor dem Lauf, verbrauchen sich)

Höchstens 2 je Lauf. **Proviant** (25): +5 % Heilkugel-Chance in diesem Lauf.; **Glücksbringer** (40): +10 Glück in diesem Lauf.; **Schatzkarte** (30): Schreine sind in diesem Lauf auf der Karte sichtbar.; **Frühstart** (60): Start bei Level 3 (2 Gratis-Upgradewahlen)..

### Farbtöpfe (Kosmetik)

Rein kosmetische Zusatzfarben für jeden Charakter (Paletten-Tausch der Ramp-Farben). 3 Varianten je Charakter (Zuckerwatte, Minze, Sonnenuntergang) für je 150 Funkelsteine, zusammen 4500.

## Challenges (55)

| ID | Aufgabe | Belohnung |
|---|---|---|
| `unlock_pyro` | Erreiche Minute 5 mit beliebigem Charakter. | unlock_character: pyro |
| `unlock_rogue` | Räume eine Welle ab Welle 5, ohne Schaden zu nehmen. | unlock_character: rogue |
| `unlock_guardian` | Erleide insgesamt 5000 Schaden. | unlock_character: guardian |
| `unlock_cryo` | Besiege 300 Gegner im Eisbiom. | unlock_character: cryo |
| `unlock_summoner` | Erreiche Level 15 in einem Run. | unlock_character: summoner |
| `unlock_storm` | Erreiche Minute 8. | unlock_character: storm |
| `unlock_bomber` | Besiege insgesamt 2000 Gegner. | unlock_character: bomber |
| `unlock_venom` | Verursache insgesamt 10000 Giftschaden. | unlock_character: venom |
| `unlock_sniper` | Besiege alle vier Biom-Bosse (Ildra, Skarra, Kalthorn, Ignarok). | unlock_character: sniper |
| `unlock_up_stillness` | Schließe 10 Runs ab. | unlock_upgrade: stillness |
| `unlock_up_minion_horde` | Schalte 3 Charaktere frei. | unlock_upgrade: minion_horde |
| `unlock_up_orbiting_blades` | Erreiche Level 20 in einem Run. | unlock_upgrade: orbiting_blades |
| `unlock_up_executioner` | Besiege 25 Elite-Gegner. | unlock_upgrade: executioner |
| `unlock_up_lifesteal` | Besiege insgesamt 1000 Gegner. | unlock_upgrade: lifesteal |
| `unlock_up_shield_burst` | Räume eine Welle ab Welle 8, ohne Schaden zu nehmen. | unlock_upgrade: shield_burst |
| `unlock_up_last_stand` | Verbringe insgesamt 60 s mit unter 20 % HP. | unlock_upgrade: last_stand |
| `unlock_up_overcharge` | Lande insgesamt 3000 kritische Treffer. | unlock_upgrade: overcharge |
| `unlock_up_explosive_rounds` | Besiege insgesamt 3000 Gegner. | unlock_upgrade: explosive_rounds |
| `unlock_up_second_wind` | Besiege den ersten Boss. | unlock_upgrade: second_wind |
| `unlock_up_gravity_well` | Erreiche Minute 10. | unlock_upgrade: gravity_well |
| `unlock_up_bloodlust` | Besiege 800 Gegner in einem Run. | unlock_upgrade: bloodlust |
| `unlock_up_time_warp` | Erreiche Minute 12. | unlock_upgrade: time_warp |
| `unlock_up_shrapnel` | Besiege insgesamt 10000 Gegner. | unlock_upgrade: shrapnel |
| `unlock_up_titan_heart` | Erleide 1500 Schaden in einem Run. | unlock_upgrade: titan_heart |
| `unlock_up_glass_cannon` | Erreiche Minute 15. | unlock_upgrade: glass_cannon |
| `unlock_up_reaper_pact` | Besiege insgesamt 10 Bosse. | unlock_upgrade: reaper_pact |
| `unlock_up_elemental_storm` | Besitze Entzünden, Kälte, Toxin und Schock in einem Run. | unlock_upgrade: elemental_storm |
| `skin_ranger_a` | Erreiche Minute 10 mit Fenn. | unlock_skin: ranger_a |
| `skin_ranger_b` | Erreiche Minute 15 mit Fenn. | unlock_skin: ranger_b |
| `skin_pyro_a` | Erreiche Minute 10 mit Mira. | unlock_skin: pyro_a |
| `skin_pyro_b` | Erreiche Minute 15 mit Mira. | unlock_skin: pyro_b |
| `skin_rogue_a` | Erreiche Minute 10 mit Kaz. | unlock_skin: rogue_a |
| `skin_rogue_b` | Erreiche Minute 15 mit Kaz. | unlock_skin: rogue_b |
| `skin_guardian_a` | Erreiche Minute 10 mit Brun. | unlock_skin: guardian_a |
| `skin_guardian_b` | Erreiche Minute 15 mit Brun. | unlock_skin: guardian_b |
| `skin_cryo_a` | Erreiche Minute 10 mit Ysa. | unlock_skin: cryo_a |
| `skin_cryo_b` | Erreiche Minute 15 mit Ysa. | unlock_skin: cryo_b |
| `skin_summoner_a` | Erreiche Minute 10 mit Thorn. | unlock_skin: summoner_a |
| `skin_summoner_b` | Erreiche Minute 15 mit Thorn. | unlock_skin: summoner_b |
| `skin_storm_a` | Erreiche Minute 10 mit Vex. | unlock_skin: storm_a |
| `skin_storm_b` | Erreiche Minute 15 mit Vex. | unlock_skin: storm_b |
| `skin_bomber_a` | Erreiche Minute 10 mit Orm. | unlock_skin: bomber_a |
| `skin_bomber_b` | Erreiche Minute 15 mit Orm. | unlock_skin: bomber_b |
| `skin_venom_a` | Erreiche Minute 10 mit Lilu. | unlock_skin: venom_a |
| `skin_venom_b` | Erreiche Minute 15 mit Lilu. | unlock_skin: venom_b |
| `skin_sniper_a` | Erreiche Minute 10 mit Aya. | unlock_skin: sniper_a |
| `skin_sniper_b` | Erreiche Minute 15 mit Aya. | unlock_skin: sniper_b |
| `boss_ildra` | Besiege Ildra. | title: Dornenbrecher |
| `boss_skarra` | Besiege Skarra. | title: Sandbezwinger |
| `boss_kalthorn` | Besiege Kalthorn. | title: Eisbrecher |
| `boss_ignarok` | Besiege Ignarok. | title: Glutlöscher |
| `reach_swarm` | Erreiche 20:00 (Beginn der Schwarmflut). | unlock_mode: eternal_night |
| `boss_reaper` | Besiege den Schnitter. | title: Sensenmeister |
| `shrines_5` | Aktiviere 5 Schreine in einem Run. | title: Wagemutig |
| `swarm_5min` | Überlebe 5 Minuten der Schwarmflut. | title: Flutreiter |

## Umsetzungsphasen (Vertical Slice zuerst)

- **Phase 1:** Jäger, 12 Upgrades (Phase 1), Mobs Schleimling, Fledermaus, Wurzelwächter, Sporenschütze, Biom Wald plus Lichtung, Boss Ildra. Spielbar von 0 bis 5:00.
- **Phase 2:** Pyro, Schurke, Wächter, Frost; restliche gewöhnliche/ungewöhnliche/seltene Upgrades; Wüste und Eis; Skarra, Kalthorn; Mini-Boss, Gier-Schreine, Schwarmflut; Profil, Challenges, Skins.
- **Phase 3:** Beschwörer, Sturm, Sprengmeister, Gift, Scharfschütze; epische und legendäre Upgrades; Lava; Ignarok; Boss-Altar mit dem Schnitter, Mut-Schrein, Fluchstein, Elite-Schrein; RL-Umgebung.

