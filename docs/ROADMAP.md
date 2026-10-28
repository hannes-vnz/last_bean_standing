# Weg zur Version 1.0

Stand 28.10.2026. Ziel: ein Lauf, der sich schnell und belohnend anfühlt, auf einer großen Karte mit Items und Kisten,
spielbar im Browser mit Online-Bestenliste. Vorbild für **Mechaniken** ist Megabonk (Items, Kisten auf der Karte,
schnelle Progression), Optik, Namen und Texte bleiben eigene (Bohnen, Pastell).

**Was schon steht (M0 bis M6b):** Simulation, Wellen, 4 Gegnerarten, Elite, Boss Ildra, 12 Upgrades, Wald mit Deckung,
Sprites, Effekte, Sound, Profil und Highscore, Browser-Version, Bestenlisten-Client und Cloudflare-Server.

## Paket A: Tempo und Gefühl (zuerst, kleinster Aufwand, größte Wirkung)
- [x] **Feuern auch im Laufen** (ersetzt Stop-and-Shoot). Stehenbleiben gibt keinen allgemeinen Vorteil, nur bestimmte Items belohnen es.
- [x] **Schnellere Progression:** flachere XP-Kurve; gemessen: Bot erreicht um 5:00 Level 8 bis 9 (vorher 2 bis 4).
- [x] **Größerer Aufsammelradius** (130) und **Magnet**: fällt selten von Gegnern, immer von Elites, zieht alle XP-Kugeln an. Auf der Karte verteilt kommt er mit Paket B/C.
- [x] Höheres Lauf- und Angriffstempo des Jägers (180, 2 Schüsse/s).
- [x] **Fenns Fähigkeiten:** Passiv „Weitblick“ und Aktiv „Pfeilhagel“ (Leertaste oder E, 18 s Abklingzeit).
- [x] **Pausenmenü** (Esc oder P; pausiert auch automatisch, wenn das Fenster den Fokus verliert).
- [ ] Bildrate im echten Browser messen (F3) und falls nötig optimieren.
- [x] Fledermausschwärme entschärfen (Gewicht 0,5).

## Paket A2: Vollbild, Handy, iPad (direkt nach A)
- [ ] **Vollbild:** Die Seite füllt das ganze Browserfenster ohne Rand und Ladeterminal; ein Knopf (und Taste F) schaltet echtes Vollbild ein (Fullscreen-API; auf dem iPhone nur „Zum Home-Bildschirm“).
- [ ] **Bildformat passt sich an:** Statt fester 16:9-Fläche mit Rand wird der sichtbare Kartenausschnitt an das Gerät angepasst (Querformat breiter, Hochformat höher), Pixel weiter ganzzahlig skaliert.
- [ ] **Lesbar auf kleinen Bildschirmen:** HUD, Karten und Menüs mit größerer Schrift und größeren Flächen; auf dem Handy etwas näher herangezoomt.
- [ ] **Touch-Steuerung:** virtueller Joystick (Daumen irgendwo links aufsetzen), Knopf für die Fähigkeit, Upgrade-Karten und Menüs per Antippen. Funktioniert, weil im Laufen gefeuert wird.
- [ ] Desktop-Fenster startet maximiert bzw. im Vollbild (F11 / Taste F), Mausklicks in Menüs.
- [ ] Test auf echtem iPad, Handy (iOS und Android) und Desktop-Browsern.

## Paket B: Große Karte
- [ ] Karte **deutlich größer**: Vorschlag 200 x 200 statt 60 x 60 Felder (rund 11-mal die Fläche).
- [ ] Biome als große zusammenhängende Gebiete, Lichtung in der Mitte, mit Seed verteilte Hindernisse, Deko und Fundstellen.
- [ ] Karte in Kacheln vorrendern (nur sichtbare Teile), damit Speicher und Browser mitkommen.
- [ ] **Minikarte** mit Kisten, Schreinen, Boss; Pfeil am Bildschirmrand zum Boss.
- [ ] Wüste, Eis, Lava zeigen schon ihre Effekte? (offene Frage 4)

## Paket C: Items und Kisten
- [ ] **Gold** als Laufwährung: fällt von Gegnern, aus Vasen und Kisten.
- [ ] **Kisten auf der Karte:** kosten Gold, der Preis steigt mit jeder geöffneten Kiste; Elite- und Bosskisten sind gratis.
- [ ] **Items:** passive Gegenstände mit Seltenheit (gewöhnlich bis legendär), stapelbar, wirken über dieselben Stat-Schlüssel wie Upgrades. Für 1.0 etwa 30 Stück (Entwurf von mir, Freigabe durch dich).
- [ ] Level-up gibt weiterhin Upgrade-Karten; Kisten geben Items (Megabonk-Prinzip: zwei Wege, stärker zu werden).
- [ ] **Zerbrechliche Vasen und Kisten** auf der Karte: Gold, Heilung, gelegentlich Magnet.
- [ ] **Heilkugeln** (Farbe steht schon in `style.json`).
- [ ] **Schreine** auf der Karte (Gier-Schrein aus Phase 2 vorziehen: mehr Schwierigkeit gegen mehr XP und Punkte).
- [ ] Item-Leiste im HUD und Build-Übersicht im Pausenmenü.
- [ ] **Neuwurf und Verbannen** bei der Kartenwahl.

## Paket C2: Mehrere Waffen (entschieden 28.10.2026: in 1.0)
- [ ] Waffen-Plätze (Vorschlag 4); neue Waffen erscheinen als Karten beim Level-up neben den Upgrades.
- [ ] Waffenstufen (Waffe erneut wählen = stärker).
- [ ] Für 1.0 etwa 6 bis 8 Waffen, Entwurf von mir, Freigabe durch dich. Die Startwaffe bleibt die des Charakters.

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
