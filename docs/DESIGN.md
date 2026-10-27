# Last Bean Standing: Designdokument und Plan

Titel: **Last Bean Standing**. Stop-and-Shoot-Roguelite (Spielgefühl wie Archero) mit zeitbasierten, endlos härter werdenden Wellen (Schwierigkeit und Bosse nach Megabonk-Vorbild, ohne Portale) in einer endlichen Arena mit Biomen. **Der Inhalt ist fest** (siehe `docs/CONTENT.md` und `data/*.json`): 10 Charaktere, 50 Upgrades, 10 Mob-Typen, 5 Bosse (4 Biom-Bosse plus der Schnitter), 5 Zonen, 55 Challenges, 20 Skins. Dazu Meta-Progression (Freischaltungen über Challenges, Playstyles, Skins) im Stil von Roguelites wie Megabonk. Am Ende trainiert ein RL-Agent auf derselben Simulation.

Inspiration ja, Kopie nein: Namen, Grafiken, Sounds und Texte anderer Spiele werden nicht übernommen.

## 1. Ziele
1. Ein echtes Spiel, das Spaß macht und in 10 Minuten verstanden ist.
2. Sauberer Code: Simulation getrennt von Darstellung, deterministisch, getestet.
3. Datengetriebener Inhalt (Mobs, Biome, Upgrades, Challenges, Skins als JSON).
4. RL-Agent als "Autopilot", gemessen an Wellen gegen Zufall, Heuristik und Mensch.

## 2. Kernspiel
- Draufsicht, Steuerung WASD oder Pfeile (Gamepad später).
- **Stop-and-Shoot:** Du schießt automatisch auf den nächsten Gegner, aber nur, wenn du stehst. Bewegung unterbricht den Angriff. Entscheidung: wann stehen (Schaden), wann ausweichen.
- Gegner kommen in Wellen. XP-Kugeln der besiegten Gegner füllen die Leiste, bei Level-up wählst du 1 von 3 Upgrades (Spiel pausiert).
- Run endet bei 0 Lebenspunkten. Danach Ergebnis, Challenges, Freischaltungen.

## 3. Arena und Biome
- Feste Karte, z. B. 60 x 60 Felder (32 px), Kamera folgt dem Spieler, Rand ist Wand.
- 4 bis 5 Zonen aus einer JSON-Karte (Bereiche, keine Zufallsgenerierung im MVP):
  - **Wald:** Bäume geben Deckung (blocken Projektile).
  - **Wüste:** Bewegung verlangsamt.
  - **Eis:** Rutschen (Trägheit).
  - **Lava:** Schaden über Zeit, dafür bessere XP-Drops.
- Jedes Biom hat eine Mob-Liste mit Gewichten. Ein Gegner spawnt in der Zone, in der er erscheint, und bekommt deren Mob-Typ.

## 4. Läufe, Schwierigkeit und Bosse (an Megabonk orientiert, ohne Portale)
Vorbild ist der Schwierigkeitsaufbau von Megabonk: Die Schwierigkeit wächst mit der Zeit **und** mit den Entscheidungen des Spielers, Bosse sind Höhepunkte, und am Ende steht eine Flut, die nie aufhört. Übernommen werden nur die Mechanik-Ideen, nicht Namen, Werte oder Grafik. **Es gibt keine Portale und keine Stufenwechsel:** Alles passiert in einer Arena, die über die Zeit "wächst" (neue Mob-Arten, Biom-Bosse, Schwarmflut).

- **Lauf:** Ein Lauf lohnt sich schon nach etwa 5 Minuten (erster Biom-Boss bei 5:00, Highscore). Welle alle **30 s**, ohne Pause, Level-ups pausieren das Spiel.
- **Schwierigkeit = Zeit x Entscheidungen:**
  - *Zeit:* Budget, Gegner-HP, Schaden und Tempo wachsen glatt und steil (Formeln in `data/balance.json`).
  - *Entscheidungen:* **Schreine** erhöhen dauerhaft einen Schwierigkeitsfaktor `D` (mehr Gegner, schnelleres Spawnen, mehr Schaden). Dafür gibt es mehr XP und Punkte (`1 + 0,8*(D-1)`). Wer gierig ist, wächst schneller, riskiert aber mehr. Die Schwierigkeit steht als Prozentwert im HUD. Schreine sind einmal nutzbar und werden durch Stillstehen aktiviert (passt zu Stop-and-Shoot).
- **Multiplikative Skalierung:** Gleiche Quellen addieren sich, verschiedene multiplizieren sich (Schaden x Krit x Angriffstempo). Die Kurve ist steil, Builds entscheiden.
- **Bossplan:** Mini-Boss mit eigener Lebensleiste bei 2:00 und 12:30. Biom-Bosse bei 5:00 (Wald), 7:30 (Wüste), 10:00 (Eis), 15:00 (Lava), jeder in seiner Zone. Elite alle 2:30. Der **Fluchstein** lässt den nächsten Biom-Boss mehrfach antreten.
- **Endboss per Altar:** Ab 10:00 aktiviert der Spieler den **Boss-Altar** in der Lichtung und ruft **Den Schnitter**. Seine HP wachsen mit der Zeit der Beschwörung (`30000 x HP-Faktor`), nach 90 s wird er wütend (kein Aussitzen). Früh rufen heißt weniger Upgrades, aber schwächerer Boss. Der Sieg beendet den Lauf mit Bonus, danach kann man weiterspielen.
- **Schwarmflut ab 20:00:** Fliegende Flutgeister kommen in Schüben, die immer größer und schneller werden (Tempo steigt ab 20:00 weiter). Es gibt keine Obergrenze, nur ein Punktemultiplikator (x1 bis x8). Es bleibt möglich, wird aber immer schwerer. Das ist der Endlos-Modus für den Highscore.
- **Machbarkeitsregeln:** glatte Kurve ohne Sprünge (Sprünge in der Schwierigkeit sind ein bekanntes Ärgernis bei Spielen dieses Genres), jeder gefährliche Angriff hat eine Vorwarnung, jeder Boss ein klares Muster, keine dauerhaften unverwundbaren Gegner. Keine reinen "Lebenspunkte-Schwämme": Bosse fordern Bewegung und Positionierung.
- **Zielkurve (nicht gemessen):** Einsteiger sterben bei 3 bis 5 min, Geübte bei 8 bis 12, Experten bei 14 bis 18. Das wird später mit Bot-Läufen in der Headless-Simulation geprüft und justiert.

## 5. Inhalt (fest)
Alles steht in `data/*.json`, lesbar zusammengefasst in `docs/CONTENT.md` (erzeugt von `tools/build_content.py`). Der Inhalt wird in drei Phasen umgesetzt (Feld `impl_phase`): Phase 1 ist ein spielbarer Vertical Slice (Jäger, 12 Upgrades, 4 Mobs, Wald, Boss Ildra), Phase 2 und 3 ergänzen den Rest. Neuer Inhalt darf nur über die JSON-Dateien kommen.

## 6. Upgrades im Run: Mechanik
- Bei Level-up 3 Karten, Gewichte nach Seltenheit (gewöhnlich 60, ungewöhnlich 25, selten 10, episch 4, legendär 1), Glück verschiebt Gewicht nach oben. Elitetruhen bieten mindestens "selten", Bosstruhen "episch" oder "legendär".
- Upgrades haben Stufen (Stapel bis `max_level`). Neuwurf und Verbannen sind eigene Upgrades.
- Gewichtung nach Charakter-Tags, damit Builds entstehen. Synergien laufen über Tags und Effekt-Schlüssel (`stat`, `special`), nicht über Sonderfälle im Code.

## 7. Meta-Progression (Freischaltungen)
- **Playstyles:** 10 Charaktere, nur der Jäger ist frei. Jeder weitere hat Waffe, Passiv und Fertigkeit (siehe CONTENT.md) und wird über eine Challenge freigeschaltet.
- **Skins:** 20 reine Farbvarianten (2 je Charakter), freigeschaltet durch Minute 10 bzw. 15 mit diesem Charakter.
- **Upgrades:** 18 der 50 Upgrades starten gesperrt (alle epischen und legendären) und kommen erst durch Challenges in den Pool.
- **Meta-Währung Funkelsteine:** Am Laufende gibt es Funkelsteine (Punkte und Schwierigkeit bestimmen die Menge, nichts geht beim Sterben verloren). Ausgeben in der **Werkstatt** (12 kleine, begrenzte Dauerverbesserungen, jederzeit voll erstattbar), für **Startpakete** (verbrauchen sich) und **Farbtöpfe** (Kosmetik). Details in `data/shop.json`. Die Boni sind absichtlich klein, damit der Lauf entscheidet und nicht der Grind.
- **Extras:** Modus "Ewige Nacht" (Gegner-HP x1,5, XP x1,25, Punkte x1,5), Titel.
- **Technik:** Die Simulation sendet Ereignisse (`EnemyKilled`, `WaveStarted`, `PlayerHit`, `BossKilled`, `LevelUp`, `RunEnded` ...). Ein `ChallengeTracker` wertet sie anhand von `challenges.json` aus (`run_stat`, `profile_stat`, `run_flag`). Fortschritt und Freischaltungen liegen im Profil (`profile.json` mit `schema_version`, atomar geschrieben, bei Fehler Backup).

## 8. Architektur
```
Eingabe -> Action -> World.step(action) -> Events -> Challenges / Audio / Effekte
                         |
                    snapshot() -> Renderer (pygame)
```
- **sim/** kennt kein pygame. Fester Zeitschritt (1/60 s), eigener Zufallsgenerator mit Seed. Gleicher Seed plus gleiche Eingaben = gleicher Verlauf (Test).
- **render/** zeichnet nur Snapshots. Das Spiel lässt sich ohne Fenster simulieren (für Tests, Benchmarks und RL).
- Kollisionen über ein räumliches Raster (Spatial Hash), damit viele Gegner flüssig laufen.
- Inhalte aus `data/*.json`, beim Start validiert (Schema, Verweise, Wertebereiche).

## 9. Dateistruktur
```
last-bean-standing/
  README.md  CLAUDE.md  ASSETS.md  pyproject.toml  Makefile
  docs/DESIGN.md                  (dieses Dokument)
  data/                           (erzeugt von tools/build_content.py)
    balance.json  characters.json  upgrades.json  mobs.json  elite.json
    bosses.json  biomes.json  challenges.json  skins.json  modes.json
    shrines.json  swarm.json  style.json  shop.json
  docs/CONTENT.md                 (lesbare Inhaltstabellen)
  tools/build_content.py          (Quelle der Inhalte, prüft Querverweise)
  src/lastbean/
    __main__.py                   (startet das Spiel)
    sim/    world.py player.py enemies.py projectiles.py waves.py
            biomes.py upgrades.py events.py rng.py spatial.py
    meta/   profile.py challenges.py unlocks.py
    data/   loader.py schema.py   (Laden und Validieren)
    render/ renderer.py camera.py sprites.py effects.py
    ui/     menu.py hud.py level_up.py character_select.py results.py
    audio.py
    rl/     env.py train.py evaluate.py autopilot.py   (optionale Abhängigkeiten)
  assets/   sprites/ sounds/ fonts/
  tests/    test_determinism.py test_waves.py test_challenges.py test_profile.py
            test_data_validation.py test_sim_has_no_pygame.py
  .github/workflows/ci.yml
```

## 10. Datenformate (Beispiele)
```json
// mobs.json
{ "id": "ember_imp", "behavior": "ranged", "cost": 3, "min_wave": 6,
  "hp": 18, "speed": 70, "damage": 6, "range": 220, "xp": 4, "biomes": ["lava"], "sprite": "ember_imp" }

// challenges.json
{ "id": "reach_wave_10", "text": "Erreiche Welle 10",
  "condition": { "type": "run_stat", "stat": "wave_reached", "op": ">=", "value": 10 },
  "reward": { "type": "unlock_character", "id": "mage" } }

// skins.json
{ "id": "gold_ranger", "character": "ranger", "name": "Goldjäger",
  "tint": [255, 210, 80], "unlock": "win_wave_15_ranger" }
```

## 11. Meilensteine (jeder für sich spielbar oder testbar)
| | Inhalt | Abnahme |
|---|---|---|
| M0 | Projekt, CI, Fenster, fester Zeitschritt, Headless-Step | `pytest` grün, `python -m lastbean` öffnet ein Fenster |
| M1 | Spieler, ein Gegnertyp, Projektile, Kollision, Tod | Determinismus-Test, 200 Gegner bleiben flüssig |
| M2 | Stop-and-Shoot, Wellen-Budget (zeitbasiert), Level-up mit 3 Karten, 12 Upgrades der Phase 1 | spielbar bis 5:00, Wellenbudget getestet |
| M3 | Arena und Biome mit Effekten | jedes Biom spürbar anders |
| M4 | restliche Phase-1-Mobs, Elite, Boss Ildra, XP-Drops | vollständiger Lauf bis 5:00, neuer Mob nur per JSON hinzufügbar |
| M5 | Profil, Challenges, Freischaltungen, Charakterwahl, Skins, Funkelsteine und Werkstatt | Speichern und Laden getestet, Challenge löst aus |
| M6 | Politur: Sound, Partikel, Treffer-Feedback, Menü, Highscore | 30-s-GIF fürs README |
| M6b | Online-Bestenliste: Client, Warteschlange, Anzeige, Server deployen | Ergebnis erscheint nach dem Lauf mit Rang, Liste aktualisiert sich |
| M7 | RL-Umgebung, Baselines, Training, Autopilot im Spiel | Lernkurve und Vergleich in der Doku |
| M8 | Release: README, Screenshots, Lizenz, optional Web-Version | Fremde können es in 2 Minuten starten |

## 12. RL-Plan (M7)
- Gymnasium-Umgebung `ArenaEnv` um die Headless-Simulation, Training z. B. mit Stable-Baselines3 (PPO).
- **Beobachtung** (feste Größe): Position und HP, Biom (One-Hot), die k nächsten Gegner (relative Position, Typ, HP), die k nächsten gegnerischen Projektile, Welle.
- **Aktion:** diskret, 8 Richtungen plus Stehen. Schießen ergibt sich aus dem Stehen (Stop-and-Shoot). Upgrade-Wahl zunächst per einfacher Heuristik.
- **Belohnung:** kleine Überlebensprämie, Kills, Wellenabschluss, minus Schaden und Tod.
- **Lehrplan:** Start in frühen Wellen, spätere Startwellen nach Fortschritt.
- **Bewertung:** mittlere erreichte Welle über viele feste Seeds gegen Zufalls-Agent, Heuristik und dich. Ehrlich dokumentieren, wo der Agent scheitert.

## 13. Qualität
- Tests: Determinismus, Wellenbudget, Challenge-Auswertung, Profil (Speichern und Laden, kaputte Datei), Datenvalidierung, "sim importiert kein pygame".
- ruff plus pytest in CI, Benchmark-Skript für Simulationsschritte pro Sekunde (Zielwert messen und dokumentieren statt raten).
- Kleine Commits, ein Meilenstein pro Branch.

## 14. Risiken
- Umfang (Endlosprojekt): Meilensteine einhalten, nicht vorziehen. Erst M0 bis M3, dann entscheiden.
- Python-Performance bei vielen Gegnern: Spatial Hash, nur Sichtbereich zeichnen, Kosten messen.
- Balancing: Zahlen in JSON, Wellen-Simulation im Headless-Modus als Balancing-Werkzeug.
- RL: Beobachtung und Belohnung sind der Hauptaufwand, Ergebnis ist nicht garantiert.
- Grafik: erst Formen und Platzhalter, dann freie Assets (Lizenz je Paket prüfen, z. B. CC0-Pakete), alles in `ASSETS.md` listen.

## 15. Offene Entscheidungen
1. Name des Spiels und des Repos.
2. Grafikstil: **entschieden**: Pixel-Art, freundlich und pastellig, mit aufwändigen Effekten (Abschnitt 16).
3. Python mit pygame (Empfehlung wegen RL) oder Godot (echte Engine, RL aufwändiger).
4. Web-Version: **ja, als Ziel** (Freunde sollen per Link spielen können), Desktop zuerst. Siehe Abschnitt 17.

## 16. Optik und Effekte (entschieden)
**Richtung:** nicht fotorealistisch, Pixel-Art als einfachster brauchbarer Stil, aber mit auffälligen Projektil-Animationen und viel Rückmeldung ("Game Feel"). Pro Charakter steht die Effektbeschreibung in `data/characters.json` (Feld `vfx`) und in `docs/CONTENT.md`.

**Auflösung**
- Interne Zeichenfläche **640 x 360**, ganzzahlig skaliert (x2 für 720p, x3 für 1080p, Nearest-Neighbor, keine Glättung). Alles wird zuerst auf diese kleine Fläche gezeichnet.
- **Weltmaßstab:** Die Simulation rechnet in Welteinheiten, 1 Feld = 32 Einheiten = **16 Pixel**. Alle Pixelwerte in `data/` (Reichweite, Tempo, Radius) sind Welteinheiten. Sichtbar sind damit etwa 1280 x 720 Einheiten, genug für die Reichweiten der Charaktere.
- Sprites: 16 x 16 (Gegner, Spieler 16 x 24 erlaubt), Bosse 32 x 32 bis 48 x 48, Projektile 3 bis 8 px.
- Positionen werden beim Zeichnen auf ganze Pixel gerundet. Begrenzte Palette (etwa 32 Farben, eine freie Palette mit passender Lizenz wählen), pro Biom eine Farbstimmung.

**Effekt-Regeln**
- Effekte leben **nur in der Darstellung** und werden durch Ereignisse der Simulation ausgelöst (`EnemyKilled`, `PlayerHit`, Schuss, Explosion ...). Sie nutzen einen eigenen Zufallsgenerator, nie den der Simulation. So bleibt die Simulation deterministisch, und Headless-Läufe (Tests, RL) zeichnen nichts.
- Technik: Partikel in einem Pool (Obergrenze etwa 2000), Leuchten durch additives Überblenden kleiner heller Flächen, Nachbilder durch gespeicherte Positionen, Trauma-basiertes Bildschirmwackeln, Hit-Stop durch kurzes Anhalten der Darstellung.
- Reihenfolge: zuerst farbige Grundformen mit fertigem Effektsystem (damit sich das Spiel früh gut anfühlt), danach 16 x 16 Sprites in einheitlichem Stil (Kontur, 3 Farbtöne je Fläche, Licht von oben links, 2 bis 4 Frames für Laufen und Ruhe).
- Skins sind Paletten-Tausch (Farbrampen im Sprite austauschen), kein Einfärben.

**Assets:** Eigene Sprites in einem freien Pixel-Editor zeichnen oder freie Pakete nutzen (Lizenz je Paket prüfen und in `ASSETS.md` eintragen; gemischte Stile wirken schnell uneinheitlich). Keine Assets aus anderen Spielen.

### Gewählter Stil: freundlich, pastell
Helle, bunte, niedliche Pixel-Art. Farben stehen in `data/style.json`, Biom-Paletten in `data/biomes.json` (Feld `palette`).

- **Grundfarben:** Konturfarbe/Tinte `#4a3358`, Gras `#a6dd82` mit Details `#83c564`, Blumen weiß, rosa und gelb. Spieler: Haar `#ffb04a`, Haut `#ffe0c8`, Körper `#6ec6ff`. Gegner: Schleim `#ff8fb8`, Fledermaus `#7a5cc0`.
- **Biome:** Lichtung hellgrün, Wald saftgrün, Wüste sandgelb, Eis hellblau, Lava korallrosa (keine dunklen Lavafarben). Gefahrenflächen (Giftpfützen, Lavapfützen, Sandverlangsamung, Eisglanz) heben sich über eine eigene `hazard`-Farbe und Animation ab.
- **Lesbarkeit hat Vorrang vor Optik:** Pastellfarben haben wenig Kontrast. Deshalb haben alle spielrelevanten Figuren und Geschosse eine **dunkle Kontur**. Eigene Geschosse sind **warmgelb** (`#fff7a8` mit `#ffd45e`), gegnerische **violett mit dunkler Kontur** (`#8a4fff`). Warnungen und Bossangriffe sind **korallrot** (`#ff6b6b`) mit weißem Rand und blinken. XP-Kugeln mintgrün (`#5ee6b8`), Heilkugeln rosa (`#ff7aa8`). Schadenszahlen weiß mit dunkler Kontur, Krits gelb und größer.
- **Kontrastprobe:** Vor jedem Meilenstein Screenshot in Graustufen prüfen: Spieler, Gegner, Geschosse und Gefahren müssen auch ohne Farbe unterscheidbar sein.
- **Der Schnitter** ist bewusst das einzige dunkle, schwere Element im Spiel (`#2a1d3d`, helle Augen). Der Kontrast zur freundlichen Welt macht ihn bedrohlich.
- **Skins:** Paletten-Tausch der Charakterfarben. Die Skin-Farben in `data/skins.json` sind Startwerte und werden beim Sprite-Bau an den Pastellstil angepasst.
- **Effekte:** weiche, funkelnde Formen statt harter Glühlinien: Projektile mit Funkelkreuz, Treffer als Sternchen und Pünktchen, Explosionen als farbige Ringe. Keine Blut- oder Gore-Effekte, Gegner lösen sich in Partikeln auf.

### Charakterstil: Bohnen-Maskottchen (gewählt, Detailgrad in Abstimmung)
Gewählt ist Stil C ("Bohnen-Maskottchen"): runder Körper und Kopf in einem, große Augen, Wangen, Kostüm und Waffe als Details. Der Detailgrad soll etwa dem des Chibi-Stils A entsprechen, ein Stück mehr.

- 16 x 16 Pixel, Körper in der Charakterfarbe, Hut, Haube, Gürtel, Schild, Waffe usw. als Überlagerungen. Der Entwurf für Fenn, Mira, Brun und Aya liegt unter `docs/art/characters_bean_draft.png`.
- **Konturen:** dunkle, getönte Konturen (Farbe des Nachbarpixels, stark abgedunkelt). Das erfüllt die Lesbarkeitsregel (dunkle Kontur) und wirkt weicher als eine einheitlich schwarze Linie.
- Erst nach Freigabe werden alle 10 Charaktere so gezeichnet. Bosse bleiben größer (32 x 32) im selben weichen Stil.

## 17. Verteilung an Freunde
Ziel: Freunde sollen das Spiel ohne Installation ausprobieren können.

| Weg | Was Freunde tun | Aufwand und Risiko |
|---|---|---|
| **Browser-Version** (pygbag, gehostet auf itch.io oder GitHub Pages) | Link öffnen | Spielschleife muss asynchron sein. Python im Browser ist langsamer: früh testen, ob 300+ Gegner flüssig laufen |
| **Download** (PyInstaller, als GitHub Release oder auf itch.io) | ZIP laden, entpacken, starten | pro Betriebssystem ein Build (GitHub Actions); unsignierte Programme lösen Sicherheitswarnungen aus |
| **Co-op online** | gemeinsam spielen | großer Umbau (Netzwerk), nicht im Plan |

**Regeln für den Code (damit die Browser-Version später möglich bleibt):** nur pygame-ce; Hauptschleife als `async` mit `await asyncio.sleep(0)` je Durchlauf; keine Threads; Assets als PNG und OGG; RL und Training (`rl/`) sind optionale Abhängigkeiten und gehören nicht in die Web-Version; Speicherstand hinter einer kleinen Schnittstelle kapseln (im Browser anderer Speicherort).
**Frühtest:** Kurz nach M2 (spielbare Wellen) ein erster Web-Build mit pygbag, um das Performance-Risiko zu messen, bevor viel Inhalt dazukommt.

## 18. Co-op, Freunde und Speicherstände (spätere Updates, jetzt nur vorbereiten)
Co-op für 2 bis 4 Spieler ist als **Update nach dem Hauptspiel** geplant. Es wird jetzt nicht gebaut, aber die Architektur darf es nicht verbauen. Diese Regeln gelten ab M0, weil sie später sehr teuer nachzurüsten wären:

- **Simulation für N Spieler:** `World` hält eine Liste von Spielern (zunächst mit einem Eintrag), Eingaben kommen je Spieler (`player_id`), Ereignisse tragen die `player_id`. Keine globalen Einzelobjekte für "den Spieler".
- **Deterministisch und eingabegesteuert** (gilt schon): gleicher Seed plus gleiche Eingaben ergibt gleichen Verlauf. Damit ist später Lockstep möglich (nur Eingaben senden). Mathematik so schreiben, dass sie plattformübergreifend gleich rechnet (keine Abhängigkeit von Systemfunktionen, wo es auf Bit-Gleichheit ankommt), und einen Zustands-Hash zur Desync-Erkennung vorsehen.
- **Schwierigkeit hat einen `player_count`-Hook** (mehr Budget, mehr Boss-HP je zusätzlichem Spieler).
- **Level-ups dürfen nicht das ganze Spiel anhalten** können: Die Auswahl läuft als eigener Zustand je Spieler. Im Einzelspiel darf das Spiel dabei pausieren, in Co-op nicht (z. B. kurze Verlangsamung oder Schutzblase für den wählenden Spieler).
- **Meta-Fortschritt** (Profil, Funkelsteine, Werkstatt) liegt immer im lokalen Profil des Spielers. Der Lauf selbst gehört dem Host.

**Stufenplan**
| Stufe | Inhalt | Backend nötig |
|---|---|---|
| 0 | Einzelspiel, Spielstand lokal, Export/Import als Textcode | nein |
| 1 | Highscore teilen (Bild oder Code) | nein |
| 2 | Co-op per Raumcode (2 bis 4 Spieler), Spitznamen statt Konten | kleiner Relay-Server (WebSocket) |
| 3 | Konten, Freundesliste, Cloud-Speicherstand | ja (eigener Server oder Fremddienst) |

**Speicherstand:** Desktop in einem Nutzerordner (`profile.json`), im Browser im Browser-Speicher (kann gelöscht werden, gilt nur für ein Gerät). Deshalb ab Stufe 0 ein **Export/Import-Code**. Der Speicherstand läuft hinter einer kleinen Schnittstelle, damit Ablageort und Cloud später austauschbar sind. Das Profil hat eine `schema_version`.

**Datenschutz (Stufe 3):** Konten bedeuten personenbezogene Daten (Nutzername, evtl. E-Mail). Sparsam bleiben (nur Spitzname und zufällige ID, keine E-Mail), Löschfunktion einplanen und die rechtlichen Pflichten (Datenschutzerklärung, in Deutschland ggf. Impressum) vor dem Start prüfen. Das ist keine Rechtsberatung.

## 19. Online-Bestenliste
Eine Rangliste, die online liegt und sich laufend aktualisiert. Ein Referenzserver mit 16 Tests liegt in `server/` (siehe `server/README.md`). Der Client wird in M6b gebaut.

- **Anzeige:** Reiter Gesamt, je Charakter, Woche und Monat, Modus "Ewige Nacht". Später ein Reiter Freunde (Stufe 3). Sortiert nach Punkten, bei Gleichstand kürzere Zeit. Die eigene Zeile wird hervorgehoben, auch außerhalb der Top 50.
- **Aktualisierung:** Nach jedem Lauf wird das Ergebnis sofort gesendet und der eigene Rang angezeigt. Die Liste wird beim Öffnen geladen und solange sie offen ist alle 60 s neu abgefragt (kein Dauerkanal nötig).
- **Offline:** Das Spiel funktioniert ohne Server. Nicht gesendete Ergebnisse liegen in einer Warteschlange im Profil und werden später erneut gesendet (die `run_id` macht das Senden wiederholbar).
- **Identität ohne Konto:** Spitzname (2 bis 16 Zeichen) und ein lokal erzeugtes zufälliges Token. Der Server speichert nur den Hash des Tokens. Damit kann man alle eigenen Einträge löschen. Keine E-Mail.
- **Eingereichte Felder:** Punkte, Zeit, Welle, Kills, Level, Bosse, Schwierigkeitsfaktor, Flutzeit, Sieg, Charakter, Modus, Spielversion, Seed, optional Replay.
- **Missbrauchsschutz in Stufen:**
  - *Stufe 1 (im Referenzserver):* Plausibilitätsprüfung (Obergrenze aus der Punkteformel, Kills pro Sekunde, Welle zur Zeit), Rate-Limit, erlaubte Spielversionen, Moderation per Admin-Token.
  - *Stufe 2 (vorbereitet):* Der Client sendet Seed und Eingabeprotokoll, der Server simuliert den Lauf mit der deterministischen Simulation nach und markiert den Eintrag als `verified`. Voraussetzungen: Simulation ohne Abweichungen zwischen Geräten, feste Spielversion je Eintrag, komprimiertes Replay-Format. Erst für eine öffentliche Liste nötig.
- **Schnittstelle im Spiel:** `online/leaderboard.py` mit zwei Umsetzungen, Desktop (Standardbibliothek) und Browser (Aufrufe über die Browser-Schnittstelle, im Web-Frühtest prüfen). Die Server-URL ist konfigurierbar.
- **Hosting:** Der Server läuft als Container oder direkt auf einem kleinen Server. SQLite braucht dauerhaften Speicher und eine Sicherung. HTTPS ist nötig, sobald die Browser-Version die Liste anspricht, und `ALLOWED_ORIGINS` wird auf die Domain des Spiels gesetzt. Kostenlose Angebote gibt es, ihre Bedingungen ändern sich: vorher prüfen.
- **Datenschutz:** Spitzname und Token, die IP nur kurz im Arbeitsspeicher. Löschfunktion im Spiel anbieten. Pflichten vor dem Start prüfen (keine Rechtsberatung).

