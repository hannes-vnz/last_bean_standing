# Bestenlisten-Server (Referenzimplementierung)

Im Betrieb läuft die Bestenliste als Cloudflare Worker in `worker/` (gleiche Schnittstelle). Dieser Server bleibt Referenz und Spezifikation; `tests/test_server_contract.py` prüft beide gegen dieselben Anfragen.

Kleiner Server für die Online-Bestenliste von Last Bean Standing. FastAPI plus SQLite, keine Konten. Spieler haben einen Spitznamen und ein zufälliges Token, das nur lokal liegt (der Server speichert nur den Hash).

## Starten
```bash
cd server
pip install -r requirements.txt
ADMIN_TOKEN=<geheim> uvicorn app:app --host 0.0.0.0 --port 8000
```
Tests: `pip install -r requirements-dev.txt && python -m pytest -q` (16 Tests).

## Umgebungsvariablen
| Name | Bedeutung | Standard |
|---|---|---|
| `LEADERBOARD_DB` | Pfad der SQLite-Datei (persistenter Speicher und Backup nötig) | `leaderboard.db` |
| `ADMIN_TOKEN` | Token für Moderation (Eintrag löschen). Leer = Moderation aus | leer |
| `ALLOWED_ORIGINS` | erlaubte Herkunft der Browser-Version, kommagetrennt (z. B. die itch.io- oder GitHub-Pages-Domain) | `*` |
| `ALLOWED_VERSIONS` | akzeptierte Spielversionen, kommagetrennt | alle |
| `RATE_LIMIT_PER_MIN` | Einreichungen pro Minute und IP | `10` |

## Schnittstelle
| Methode und Pfad | Zweck |
|---|---|
| `POST /v1/scores` | Ergebnis einreichen (idempotent über `run_id`), Antwort mit Rang gesamt und je Charakter |
| `GET /v1/leaderboard?mode=&character=&period=all\|day\|week\|month&limit=&offset=` | Rangliste (Punkte absteigend, bei Gleichstand kürzere Zeit) |
| `DELETE /v1/me` (Header `X-Client-Token`) | alle eigenen Einträge löschen |
| `DELETE /v1/scores/{id}` (Header `X-Admin-Token`) | Moderation |
| `GET /v1/health` | Lebenszeichen |

## Was geprüft wird (Stufe 1)
Namensformat, bekannter Charakter und Modus, Obergrenze der Punkte aus der Formel in `docs/CONTENT.md` (Zeit, Kills, Level, Bosse, Sieg, Flut, Schwierigkeit), Kills pro Sekunde, Welle zur Spielzeit, Flutzeit, Rate-Limit, erlaubte Version.

## Grenzen
Wer die Schnittstelle direkt anspricht, kann innerhalb der Plausibilitätsgrenzen schummeln. Für eine Liste unter Freunden reicht das. Für eine öffentliche Liste ist Stufe 2 vorgesehen: Der Client sendet Seed und Eingabeprotokoll (`replay`), der Server simuliert den Lauf mit der deterministischen Simulation nach und setzt `verified`. Das Feld wird schon gespeichert.

## Betrieb
HTTPS ist nötig, wenn die Browser-Version die Liste anspricht (Seiten über HTTPS dürfen keine unverschlüsselten Anfragen stellen). Datenschutz: Die IP liegt nur kurz im Arbeitsspeicher für das Rate-Limit und wird nicht gespeichert. Pflichten (Datenschutzerklärung usw.) vor dem Start prüfen.
