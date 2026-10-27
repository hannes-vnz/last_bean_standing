# Last Bean Standing

Stop-and-Shoot-Roguelite: zeitbasierte, endlos härter werdende Wellen in einer endlichen Arena, Schwierigkeit und Bosse nach Megabonk-Vorbild ohne Portale (Schreine, Endboss per Altar, ab 20:00 endlose Schwarmflut). Python plus pygame, Simulation und Darstellung getrennt.

## Quellen der Wahrheit
- `docs/DESIGN.md`: Konzept, Architektur, Meilensteine M0 bis M8.
- `data/*.json`: fester Spielinhalt (10 Charaktere, 50 Upgrades, 10 Mobs, 5 Bosse, 5 Zonen, 55 Challenges, 20 Skins). `docs/CONTENT.md` ist nur die lesbare Fassung.
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

- Online-Bestenliste (Abschnitt 19): Server in `server/` (Tests: `cd server && python -m pytest -q`). Das Spiel muss auch ohne Server laufen. Punkteformel in `docs/CONTENT.md` und `server/app.py` synchron halten.

## Befehle
- Tests: `python -m pytest -q`; Lint: `ruff check`
- Inhalt prüfen: `python tools/build_content.py`
- Spiel (ab M0): `python -m lastbean`
