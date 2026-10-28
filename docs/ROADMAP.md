# Weg zur Version 1.0

Stand 28.10.2026. Ziel: ein Lauf, der sich schnell und belohnend anfühlt, auf einer großen Karte mit Items und Kisten,
spielbar im Browser mit Online-Bestenliste. Vorbild für **Mechaniken** ist Megabonk (Items, Kisten auf der Karte,
schnelle Progression), Optik, Namen und Texte bleiben eigene (Bohnen, Pastell).

**Was schon steht (M0 bis M6b):** Simulation, Wellen, 4 Gegnerarten, Elite, Boss Ildra, 12 Upgrades, Wald mit Deckung,
Sprites, Effekte, Sound, Profil und Highscore, Browser-Version, Bestenlisten-Client und Cloudflare-Server.

## Paket A: Tempo und Gefühl (zuerst, kleinster Aufwand, größte Wirkung)
- [x] **Feuern auch im Laufen** (ersetzt Stop-and-Shoot). Stehenbleiben gibt keinen allgemeinen Vorteil, nur bestimmte Items belohnen es.
- [x] **Schnellere Progression** (Variante C, 28.10.2026): XP 3 + 1,5n + 0,15n², Wellenbudget 40 + 7w, Aufsammelradius 220. Gemessen mit dem Bot: Level 2 nach etwa 10 s, Level 5 um 0:31, Level 10 um 1:36, Level 15 um 3:08 (vorher Level 2 erst nach 45 s). Bot stirbt im Median bei 2:55 statt 3:55.
- [x] **Größerer Aufsammelradius** (130) und **Magnet**: fällt selten von Gegnern, immer von Elites, zieht alle XP-Kugeln an. Auf der Karte verteilt kommt er mit Paket B/C.
- [x] Höheres Lauf- und Angriffstempo des Jägers (180, 2 Schüsse/s).
- [x] **Fenns Fähigkeiten:** Passiv „Weitblick“ und Aktiv „Pfeilhagel“ (Leertaste oder E, 18 s Abklingzeit).
- [x] **Pausenmenü** (Esc oder P; pausiert auch automatisch, wenn das Fenster den Fokus verliert).
- [ ] Bildrate im echten Browser messen (F3) und falls nötig optimieren.
- [x] Fledermausschwärme entschärfen (Gewicht 0,5).

## Paket A2: Vollbild, Handy, iPad (Hauptplattform seit 28.10.2026)
- [x] **Vollbild:** Die Seite füllt den ganzen Bildschirm; Android und Tablets wechseln beim ersten Antippen ins Vollbild; iPhone: „Teilen → Zum Home-Bildschirm“ startet als Vollbild-App. Desktop: F11.
- [x] **Bildformat passt sich an** (Hoch- und Querformat, Drehen während des Spiels), Pixel ganzzahlig skaliert.
- [x] **Lesbar auf kleinen Bildschirmen:** auf dem Handy näher herangezoomt, Karten im Hochformat untereinander, HUD bricht um, alle Menüs mit großen Knöpfen.
- [x] **Touch-Steuerung:** Joystick dort, wo der Daumen aufsetzt; Fähigkeits- und Pause-Knopf; Karten und Menüs antippen; Name über die Handy-Tastatur.
- [x] Desktop: Fenster frei skalierbar, F11 Vollbild, Mausklicks in Menüs.
- [x] **Zoom** mit zwei Fingern (Desktop: Mausrad, +/-), 8 Stufen zwischen nah und weit, wird im Profil gemerkt.
- [x] **Kein „Antippen zum Start“ mehr:** eigenes Startbild mit Bohne, solange Python lädt; Ton wird beim ersten Antippen freigeschaltet.
- [x] Fehler behoben: Level-up-Karten ließen sich auf dem Handy nicht antippen (Test in `tests/test_touch_loop.py`).
- [ ] Test auf echtem iPad, Handy (iOS und Android) und Desktop-Browsern. (Im Browser mit Handy-Emulation geprüft: Name, Menü, Joystick, Fähigkeit, Pause.)

## Paket B: Große Karte
- [x] Karte **deutlich größer**: 200 x 200 statt 60 x 60 Felder (rund 11-mal die Fläche); Biome je 100 x 100, Lichtung 30 x 30; Hindernisse mit gleicher Dichte (Wald 780 Bäume).
- [x] Biome als große zusammenhängende Gebiete, Lichtung in der Mitte, Hindernisse mit Seed verteilt. Deko und Fundstellen folgen mit Paket C/D.
- [x] Boden in Kacheln (256 px, nur sichtbare, höchstens 40 im Speicher) statt eines 3200 x 3200 Bildes.
- [x] **Minikarte** (Biome, du, Elites, Boss; Kisten und Schreine folgen mit Paket C) und Pfeil am Bildschirmrand zum Boss. Bosse erscheinen in deiner Nähe, wenn möglich in ihrem Biom.
- [ ] Wüste, Eis, Lava zeigen schon ihre Effekte? (offene Frage 4)

## Paket C: Items und Kisten
- [x] **Samenkörner** (das Gold der Story) als Laufwährung: 35 % je Gegner, Elite 10, Boss 40, Vasen 3 bis 6.
- [x] **Saatkisten auf der Karte** (90, neu verteilt in jedem Lauf): Start 15 Samen, +40 % je geöffneter Kiste; Elite- und Bosskisten gratis (mindestens selten bzw. episch).
- [x] **30 Items** aus Gartenwerkzeug und Gärtnerkram (12/9/5/3/1 je Seltenheit), stapelbar; neue Effekte: XP, Samen, Glück, Abklingzeit, Schaden gegen Elites, Schaden im Stand, Dornen, Heilen pro Kill, Schutzzeit, Explosion beim Kill.
- [x] Level-up gibt weiterhin Upgrade-Karten; Kisten geben Items.
- [x] **Vasen** (160) zerbrechen beim Drüberlaufen: Samen, Heilung, selten Magnet.
- [x] **Heilkugeln** (15 HP) aus Vasen.
- [ ] **Schreine** auf der Karte (Gier-Schrein aus Phase 2 vorziehen: mehr Schwierigkeit gegen mehr XP und Punkte).
- [x] Samenzähler im HUD, Item-Einblendung beim Fund, Kisten auf der Minikarte. (Build-Übersicht mit Items im Pausenmenü: offen)
- [x] **Neu würfeln und Verbannen** bei der Kartenwahl (je 2 pro Lauf).

## Paket C2: Mehrere Waffen (entschieden 28.10.2026: in 1.0)
- [x] 4 Waffen-Plätze (inkl. Startwaffe); neue Waffen erscheinen als Karten beim Level-up neben den Upgrades.
- [x] Waffenstufen (Waffe erneut wählen = stärker, höchstens Stufe 5).
- [x] 6 Waffen (Entwurf, Werte in `docs/CONTENT.md`): Dornenzweig, Pusteblume, Pollenwolke, Bienenschwarm, Sonnenpuls, Kürbisbombe.

## Paket T: Technik (Rückmeldung Hannes 28.10.2026)
- [x] Ruckeln beim Laufen: Zeichnen zwischen den Simulationsschritten (Interpolation), Browser bestimmt die Bildrate.
- [x] Lag nach einigen Minuten: Gedränge-Berechnung je Gitterzelle (350 Gegner: 3,2 auf 2,1 ms je Schritt), weit entfernte Gegner springen zurück in deine Nähe statt sich zu stapeln, Browser skaliert das Bild.
- [x] Hochkant im Vollbild nichts antippbar: Tippen rechnet jetzt mit der echten Größe der Spielfläche.
- [x] Monster und Held 25 % schneller.
- [ ] Auf echten Geräten prüfen (Bildrate mit F3).

## Paket F: Drei Beete, Gartenplagen, mehr Dopamin (Rückmeldung Hannes 28.10.2026)
- [x] Drei Beete à 5:00 (Saatbeet, Gemüsebeet, Komposthaufen) mit eigenen Karten, Bodenkacheln und Hindernissen; Lauf höchstens etwa 15 Minuten.
- [x] Boss je Beet bei 3:30: Schleimrun (Schneckenkönigin), Knollgrimm (Käferkönig), der Schnitter. Gartentor ins nächste Beet, Sieg nach dem Schnitter.
- [x] Plagenflut nach Ablauf eines Beets: endlos, alle 10 s +40 % Gegner, +15 % HP, +8 % Schaden.
- [x] 10 neue Gegner: Gartenplagen und verpestetes Gemüse (Nacktschnecke, Blattlaus, Gartenschnecke, Schimmelpilz, Kartoffelkäfer, Giftmöhre mit Sturmangriff, Spritzgurke, Pestizid-Tomate, Wühlmaus, Sprühpilz).
- [x] Schnellere Level (XP 2 + 1,2n + 0,12n²).
- [x] Kartenseltenheit: jede Level-up-Karte würfelt eine Seltenheit, die den Wert vervielfacht (x1 / x1,3 / x1,7 / x2,2 / x3); seltene Karten leuchten, legendäre glänzen; Karten fallen nacheinander ins Bild.
- [x] Glücksrad bei Kisten: Item-Symbole drehen sich und landen auf dem Fund (antippen überspringt).
- [x] Komplexere Boni: Brand, Gift, Kälte, Kettenblitz, Sprengtreffer, Rückprall, Henker, Lebensraub, Schild, Ausweichen, Rüstung, Letztes Gefecht, Überladung, Blutrausch, Splitter, Wiederbeleben, Aura; 46 von 50 Upgrades im Pool, 16 neue Items mit Auslösern.
- [x] Icons für jede Waffe, jedes Upgrade und Item, gestapelt unter dem HUD mit Stufe.
- [ ] Balance mit echten Läufen (Bot: Median-Tod 4:01, meist im ersten Beet).

## Paket F2: Optik nach Rückmeldung (28.10.2026)
- [x] Seltenheitsfarben grün, blau, lila, rot, gold; dicke Rahmen mit Licht- und Schattenkante.
- [x] Eigene Pixelbilder für alle 46 Items und 7 Waffen (`tools/sprites/items.py`), Upgrades als Bücher mit Symbol.
- [x] Level-up-Karten: dunkle Karte mit großem Bild, Werte zeilenweise, Umdrehen beim Erscheinen, Blitz und Ring, Lichtstrahlen ab „selten“.
- [x] HUD: Waffen, Bücher und Items in eigenen Reihen; Neues und Stufenaufstiege springen groß auf („NEU“, „+1“).
- [x] Boden: große helle und dunkle Flecken, Deko (Kiesel, Blumen, Blätter, Pilze, Eierschalen …), Schatten unter Hindernissen, Holzkanten an Gemüsereihen, schwebende Pollen, Blüten oder Sporen.
- [x] Scharfe Pixel und Schrift im Browser: jeder Spielpixel ist genau 2, 3 oder 4 Bildschirmpixel.
- [x] Bildschirmtastatur für den Namen auf Handy und iPad (PC tippt normal).

## Paket G: Waffen für Spielweisen, schnellerer Start, Flut als Zocken (28.10.2026)
- [x] 15 Waffen (9 neu), jede mit Spielweise auf der Karte: Glühwürmchen (Kette), Ahornbumerang (hin und zurück),
  Brennnesselspur und Knoblauchminen (wirken nur im Laufen), Kaktuswächter (pflanzen, Stellung halten),
  Brennglasstrahl (Linie durch alles), Saatflinte (kurz und breit), Libellenschwarm (sucht Ziele), Sichel (Hieb vorn).
- [x] Beet 2 und 3 starten heiß: 150 bzw. 180 s Wellen-Vorsprung (Gegnermenge und -arten) und volles Budget beim Betreten.
- [x] Plagenflut als Zocken: XP und Samenkörner +25 % je 10 s Flut, Flutzeit zählt Punkte; das Tor bleibt offen.

## Als Nächstes (Vorschlag)
1. Auf echten Geräten prüfen: Bildrate (F3), Schärfe, Tippen, Tastatur.
2. Animationen für Bohne und Gegner (Laufen, Treffer, Tod) und Geschoss-Sprites (Paket D).
3. Pixelschrift mit freier Lizenz statt der Standardschrift.
4. Schreine auf der Karte (Gier-Schrein), dann Einstellungen und Hinweise beim ersten Lauf (Paket E).

## Paket D: Grafik-Durchgang
- [ ] Boden-Kacheln je Biom mit Details (Gras, Blumen, Steine), Übergänge zwischen Biomen.
- [ ] Animationen: Laufen und Ruhe (2 bis 4 Bilder), Treffer, Tod.
- [ ] Geschoss-Sprites (Pfeil mit Funkelkreuz), Kisten, Vasen, Gold, Items, Schreine, Magnet.
- [ ] Pixelschrift mit freier Lizenz (OFL) statt der Standardschrift.
- [ ] Wer zeichnet? (offene Frage 3)

## Paket E: Release 1.0
- [ ] Online-Bestenliste live: Server läuft (`last-bean-standing.hannesvincenz.workers.dev`), Adresse eingetragen; im Browser auf dem Handy und am Rechner prüfen.
- [ ] Spielstand exportieren und importieren im Menü.
- [ ] Einstellungen: Lautstärke, Schadenszahlen an/aus, Bildschirmwackeln an/aus.
- [ ] Kurze Hinweise beim ersten Lauf (Steuerung, Kisten, Level-up).
- [ ] Balance-Durchgang: Bot-Messung plus Testspiele mit den Kumpels; Ziel „Einsteiger sterben bei 3 bis 5 Minuten, ein guter Lauf schafft Ildra“.
- [ ] README mit neuem GIF, Screenshots, Link zur Seite.

## Nach 1.0
Weitere Charaktere (Phase 2/3), Biom-Bosse 2 bis 4, Schnitter und Schwarmflut, Challenges und Freischaltungen,
Werkstatt und Funkelsteine, Co-op, RL-Agent.

## Vorgeschlagene Werte (brauchen deine Freigabe, weil sie in `data/` stehen)
| Wert | heute | Vorschlag |
|---|---|---|
| Lauftempo Jäger | 150 | 180 |
| Schüsse pro Sekunde Jäger | 1,6 | 2,0 |
| Aufsammelradius | 70 | 130 |
| XP für Level n | 12 + 8n + 0,5n² | 8 + 5n + 0,4n² |
| Kartengröße | 60 x 60 Felder | 200 x 200 Felder |
| Fledermaus-Gewicht | 1 in allen Biomen | 0,5 |
| Kistenpreis | neu | Start 15 Gold, +40 % je geöffneter Kiste |

## Offene Fragen
Entschieden: Stehen gibt keinen allgemeinen Bonus (nur Items); mehrere Waffen kommen in 1.0.

3. Grafik: zeichne ich per Code, zeichnet ihr in Aseprite/LibreSprite, oder nehmen wir ein freies Paket?
4. Bekommen Wüste, Eis und Lava in 1.0 schon ihre Effekte (langsamer, rutschig, Schaden)? Auf der großen Karte fällt ihr Fehlen auf.
