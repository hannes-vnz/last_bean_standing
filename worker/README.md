# Bestenliste auf Cloudflare Workers + D1

Port des Referenzservers `server/app.py` (gleiche Routen, gleiches JSON, gleiche Prüfungen). Kostenlos im Free-Plan,
schläft nicht ein, Daten liegen dauerhaft in D1 (SQLite). Beide Server prüft dieselbe Testsuite
`tests/test_server_contract.py`.

## Einmalige Einrichtung (Hannes)
1. Kostenloses Konto auf https://dash.cloudflare.com anlegen.
2. **D1-Datenbank:** Storage & Databases → D1 → *Create* → Name `last-bean-standing`. Die angezeigte *Database ID* kopieren.
3. **API-Token:** My Profile → API Tokens → *Create Token* → Vorlage „Edit Cloudflare Workers“, zusätzlich Berechtigung
   *Account → D1 → Edit* hinzufügen. Token kopieren.
4. **Account-ID:** steht im Dashboard rechts unter „Account ID“ (Workers & Pages).
5. **GitHub-Secrets** im Repo (Settings → Secrets and variables → Actions → *New repository secret*):
   - `CLOUDFLARE_API_TOKEN` (Schritt 3)
   - `CLOUDFLARE_ACCOUNT_ID` (Schritt 4)
   - `CLOUDFLARE_D1_ID` (Schritt 2)
   - `LEADERBOARD_ADMIN_TOKEN`: ein langes Zufallspasswort für die Moderation (Einträge löschen)
6. Actions → „Leaderboard (Cloudflare Worker)“ → *Run workflow*. Danach läuft der Worker unter
   `https://last-bean-standing.<dein-subdomain>.workers.dev` (steht im Log und im Dashboard).
7. Die Adresse im Spiel eintragen: `DEFAULT_URL` in `src/lastbean/online/leaderboard.py`.

Danach deployt jeder Push auf `main`, der `worker/` ändert, automatisch.

Aktuelle Adresse: `https://last-bean-standing.hannesvincenz.workers.dev`.

## Lokal
```bash
cd worker
npm install
npx wrangler d1 migrations apply last-bean-standing --local
npx wrangler dev --local          # http://localhost:8787
```

## Einstellungen (`wrangler.toml`, `[vars]`)
| Name | Bedeutung |
|---|---|
| `ALLOWED_ORIGINS` | erlaubte Herkunft der Browser-Version (GitHub Pages), kommagetrennt, `*` = alle |
| `ALLOWED_VERSIONS` | akzeptierte Spielversionen, kommagetrennt, leer = alle |
| `RATE_LIMIT_PER_MIN` | Einreichungen pro Minute und IP (je Worker-Instanz, also eine Bremse, keine harte Grenze) |
| `ADMIN_TOKEN` (Secret) | Moderation per `DELETE /v1/scores/{id}` mit Header `X-Admin-Token` |

Datenschutz: gespeichert werden Spitzname, Ergebnis und der Hash des Tokens. Die IP wird nur für das Rate-Limit kurz im
Arbeitsspeicher gehalten. Pflichten vor einem öffentlichen Start prüfen (keine Rechtsberatung).
