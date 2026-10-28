# Weg zur Version 1.0

Stand 28.10.2026. Ziel: ein Lauf, der sich schnell und belohnend anfühlt, auf einer großen Karte mit Items und Kisten,
spielbar im Browser mit Online-Bestenliste. Vorbild für **Mechaniken** ist Megabonk (Items, Kisten auf der Karte,
schnelle Progression), Optik, Namen und Texte bleiben eigene (Bohnen, Pastell).

**Was schon steht (M0 bis M6b):** Simulation, Wellen, 4 Gegnerarten, Elite, Boss Ildra, 12 Upgrades, Wald mit Deckung,
Sprites, Effekte, Sound, Profil und Highscore, Browser-Version, Bestenlisten-Client und Cloudflare-Server.

## Paket A: Tempo und Gefühl (zuerst, kleinster Aufwand, größte Wirkung)
- [ ] **Feuern auch im Laufen** (ersetzt Stop-and-Shoot, siehe DESIGN.md Abschnitt 15).
- [ ] **Schnellere Progression:** flachere XP-Kurve, mehr XP je Kill, Ziel etwa Level 8 bis 10 um 5:00 (heute 2 bis 4).
- [ ] **Größerer Aufsammelradius** und **Magnet** als Fundstück auf der Karte: zieht alle XP-Kugeln an.
- [ ] Höheres Lauf- und Angriffstempo des Jägers (Werte unten).
- [ ] **Fenns Fähigkeiten**, die in den Daten stehen, aber noch fehlen: Passiv „Weitblick“ und Aktiv „Pfeilhagel“ (Taste Leertaste, 18 s Abklingzeit).
- [ ] **Pausenmenü** (Esc pausiert statt abzubrechen; Weiter, Neustart, Menü, Ton an/aus).
- [ ] Bildrate im echten Browser messen (F3) und falls nötig optimieren.
- [ ] Fledermausschwärme entschärfen (Gewicht oder Kosten).

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

## Paket D: Grafik-Durchgang
- [ ] Boden-Kacheln je Biom mit Details (Gras, Blumen, Steine), Übergänge zwischen Biomen.
- [ ] Animationen: Laufen und Ruhe (2 bis 4 Bilder), Treffer, Tod.
- [ ] Geschoss-Sprites (Pfeil mit Funkelkreuz), Kisten, Vasen, Gold, Items, Schreine, Magnet.
- [ ] Pixelschrift mit freier Lizenz (OFL) statt der Standardschrift.
- [ ] Wer zeichnet? (offene Frage 3)

## Paket E: Release 1.0
- [ ] Online-Bestenliste live (Server läuft, Adresse eingetragen, im Browser geprüft).
- [ ] Spielstand exportieren und importieren im Menü.
- [ ] Einstellungen: Lautstärke, Schadenszahlen an/aus, Bildschirmwackeln an/aus.
- [ ] Kurze Hinweise beim ersten Lauf (Steuerung, Kisten, Level-up).
- [ ] Balance-Durchgang: Bot-Messung plus Testspiele mit den Kumpels; Ziel „Einsteiger sterben bei 3 bis 5 Minuten, ein guter Lauf schafft Ildra“.
- [ ] README mit neuem GIF, Screenshots, Link zur Seite.

## Nach 1.0
Weitere Charaktere und Waffen (Phase 2/3), Biom-Bosse 2 bis 4, Schnitter und Schwarmflut, Challenges und Freischaltungen,
Werkstatt und Funkelsteine, mehrere Waffen gleichzeitig, Co-op, RL-Agent.

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
1. Soll Stehenbleiben noch einen kleinen Vorteil geben (z. B. +15 % Angriffstempo im Stand), oder ganz weg?
2. Mehrere Waffen gleichzeitig schon in 1.0 (Megabonk-typisch) oder erst danach? Empfehlung: danach, Items reichen für 1.0.
3. Grafik: zeichne ich per Code, zeichnet ihr in Aseprite/LibreSprite, oder nehmen wir ein freies Paket?
4. Bekommen Wüste, Eis und Lava in 1.0 schon ihre Effekte (langsamer, rutschig, Schaden)? Auf der großen Karte fällt ihr Fehlen auf.
