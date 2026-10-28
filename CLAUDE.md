# Last Bean Standing

Roguelite mit Auto-Feuer nach Megabonk-Vorbild (eigene Optik: Bohnen verteidigen die letzte Saat gegen Gartenplagen): drei Beete à 3:00 (Saatbeet, Gemüsebeet, Komposthaufen), Boss je Beet bei 2:06, Gartentor ins nächste Beet, nach Ablauf der Zeit endlose Plagenflut, Sieg mit dem Schnitter. Python plus pygame, Simulation und Darstellung getrennt.

## Quellen der Wahrheit
- `docs/DESIGN.md`: Konzept, Architektur, Meilensteine M0 bis M8.
- `data/*.json`: fester Spielinhalt (10 Charaktere: 6 von Anfang an, 4 per Challenge, 50 Upgrades, 46 Items, 6 Waffen, 10 Gartenplagen, 3 Bosse, 3 Beete in `stages.json`, 53 Challenges, 20 Skins). `docs/CONTENT.md` ist nur die lesbare Fassung.
- `tools/build_content.py` erzeugt beides und prüft Querverweise. Inhalt ändern: dort, dann `python tools/build_content.py`.

## Regeln
- IDs, Zahlen und Namen aus `data/` nicht ohne Rückfrage ändern. Unklares oder Widersprüchliches als Frage melden, nicht erfinden.
- `src/lastbean/sim/` importiert kein pygame (Test sichert das). Fester Zeitschritt 1/60 s, eigener Zufallsgenerator mit Seed, gleicher Seed plus gleiche Eingaben ergibt gleichen Verlauf.
- Inhalte kommen aus JSON, nicht aus dem Code. Neuer Mob/Upgrade = neuer Eintrag.
- Umsetzung nach `impl_phase` (1 zuerst). Nicht vorziehen.
- Optik: Pixel-Art, freundlich und pastellig (`data/style.json`; Lesbarkeit vor Optik: dunkle Konturen, eigene Geschosse gelb, gegnerische violett), 640x360 intern, ganzzahlig skaliert (`docs/DESIGN.md` Abschnitt 16). Effekte nur in `render/`, ausgelöst durch Ereignisse, mit eigenem Zufallsgenerator. Simulation zeichnet nichts.
- Keine Namen, Grafiken, Sounds oder Texte aus anderen Spielen. Freie Assets nur mit Lizenz in `ASSETS.md`.
- Zielwerte (Schritte pro Sekunde, Balance) messen statt raten.

- Webtauglich bleiben (Abschnitt 17): nur pygame-ce, async Hauptschleife mit `await asyncio.sleep(0)`, keine Threads, Assets PNG/OGG, Speicherstand hinter einer Schnittstelle.

- Co-op später (Abschnitt 18): `World` mit Liste von Spielern und Eingaben je `player_id`, Ereignisse mit `player_id`, `player_count`-Hook in der Schwierigkeit, Spielstand hinter einer Schnittstelle. Kein Co-op jetzt bauen.

- Online-Bestenliste (Abschnitt 19): Referenzserver `server/` (Python), Produktion `worker/` (Cloudflare Workers + D1, gleiche API; `tests/test_server_contract.py` prüft beide). Das Spiel muss auch ohne Server laufen. Punkteformel in `docs/CONTENT.md` und `server/app.py` synchron halten.

## Befehle
- Tests: `python -m pytest -q`; Lint: `ruff check`
- Inhalt prüfen: `python tools/build_content.py`
- Spiel (ab M0): `python -m lastbean`
- Setup: `python -m venv .venv && .venv/bin/pip install -e ".[dev]"` (Python 3.11+); `make check` = Lint + Tests + Inhalt synchron
- Benchmark Simulation: `python tools/bench.py` (Schritte pro Sekunde, Ergebnis messen und notieren)
- Web: `python tools/build_web.py [--serve]` (pygbag; `web/main.py` muss pygame direkt importieren); Push auf `main` deployt GitHub Pages

## Struktur (Stand Paket F)
- `sim/world.py`: `World(seed, WorldConfig.from_content(...))`, `step(inputs) -> events`, `snapshot()`, `state_hash()`; `PlayerInput(player_id, move_x, move_y, choice)`; Level-up pausiert nur im Einzelspiel; Beete als `StageConfig` (eigene Hindernisse, Boss, Faktoren), `stage`/`stage_tick`, Gartentor, Plagenflut; Boni mit Auslösern (`_weapon_hit`, `_on_hit_effects`, `_tick_statuses`), Kartenseltenheit (`offer_tiers`, `upgrade_power`)
- `sim/weapons.py`: Zusatzwaffen (Fächer, Nova, Aura, Orbit, Wurf), deterministisches `cos_sin`
- `sim/waves.py` (Budget, Skalierung, XP-Kurve, Biome), `sim/upgrades.py` (Stat-Summen, Kartenwahl), `sim/arena.py` (Hindernisse, Deckung), `sim/enemies.py` (Verhalten je `behavior`, Elite-Affixe, Boss-Muster), `sim/entities.py`, `sim/spatial.py`; neue Verhalten in `BEHAVIORS`/`BOSS_BEHAVIORS`, Hindernisarten in `OBSTACLE_KINDS`
- `sim/shrines.py`: Schreine aus `shrines.json` (Gier, Mut, Fluchstein, Elite) je Beet, Aufladen im Kreis, `World._charge_shrines`
- `sim/tuning.py`: Zahlen, die noch nicht in `data/` stehen (Annahmen, mit Hannes klären und dann ins JSON)
- `online/leaderboard.py`: Senden mit Warteschlange im Profil, Rangliste; `online/http.py`: async HTTP ohne Threads (Desktop: asyncio, Browser: fetch); Server-URL `DEFAULT_URL` oder `LBS_LEADERBOARD_URL`
- `bots.py`: Heuristik-Spieler; `tools/balance.py` misst Todeszeiten über viele Seeds
- `data/loader.py`: `load_content()` liefert typisierte `Content` (`data/schema.py`), sammelt alle Fehler in `ContentError`
- `meta/profile.py`: Profil (Spitzname, Token, Highscores, Export-Code, Funkelsteine), Speicher Datei/localStorage; `meta/workshop.py`: Werkstatt (Kauf, volle Erstattung, `meta_mods` für `WorldConfig`) und Funkelstein-Auszahlung; `meta/challenges.py`: Challenges (Lauf-Statistik `World.run_stats`, Lebenszeit-Summen, Belohnungen, Skins); `sim/score.py`: Punkte (synchron mit `server/app.py`); `ui/screens.py`: Bildschirme mit Knöpfen (Touch/Maus), Einstellungen (Lautstärke, Zahlen, Wackeln), Tipps beim ersten Lauf (`app.first_run_hints`), `ui/layout.py` Bildgröße je Gerät, `ui/touch.py` Joystick; `render/pixelfont.py` (eigene Bitmap-Schrift), `render/effects.py` (Partikel, Tod/Treffer-Animation, Blitz, Zahlen, Wackeln, Hit-Stop aus Ereignissen), `render/sprites.py` (`assets/sprites/sprites.json`, erzeugt von `tools/sprites/mobs.py`), `render/icons.py` (Pixel-Icons je Bonus, HUD-Stapel), Bodenkacheln `assets/tiles/*.png` (`tools/sprites/tiles.py`), `render/interp.py` (Zeichnen zwischen Ticks), `audio.py` (synthetische Töne); `render/renderer.py`: Fläche je nach Gerät, ganzzahlig skaliert, Karte in Kacheln je Beet (`set_stage`), Level-up-Karten mit Animation, Kisten-Glücksrad
