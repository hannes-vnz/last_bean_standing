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

## Konten und Cloud-Speicherstand (Paket K)

Spieler können sich freiwillig anmelden; danach liegt ihr Profil in D1 (`/v1/save`). Die Tabellen kommen mit
`migrations/0002_accounts.sql` (der Deploy-Workflow wendet Migrationen automatisch an).

- **Name + Passwort** funktioniert sofort (PBKDF2-SHA256, 100 000 Runden, nur der Hash wird gespeichert).
- **Mit Google anmelden** (kostenlos): In der [Google Cloud Console](https://console.cloud.google.com/apis/credentials)
  „OAuth-Client-ID“ vom Typ *Webanwendung* anlegen, als autorisierten JavaScript-Ursprung
  `https://hannes-vnz.github.io` eintragen, die Client-ID in `wrangler.toml` unter `[vars]` als
  `GOOGLE_CLIENT_ID = "…apps.googleusercontent.com"` setzen und pushen. Die Client-ID ist kein Geheimnis.
- **Mit Apple anmelden**: braucht das Apple Developer Program (99 $/Jahr). Dort eine *Services ID* mit
  „Sign in with Apple“ anlegen, die Domain `hannes-vnz.github.io` und als Return-URL die Spielseite eintragen,
  dann `APPLE_CLIENT_ID = "<Services ID>"` in `[vars]` setzen.

Die Knöpfe „Mit Google“ / „Mit Apple“ erscheinen im Spiel (Browser-Version), sobald die jeweilige ID gesetzt ist
(`GET /v1/config`). Der Worker prüft das ID-Token gegen die öffentlichen Schlüssel des Anbieters (Signatur,
Aussteller, Client-ID, Ablauf). `DELETE /v1/account` löscht Konto, Sitzungen und Spielstand.

### Passkeys (Face ID, Touch ID, Windows Hello, Fingerabdruck)

Kostenlos und ohne Entwicklerkonto: `POST /v1/passkey/begin`, `/v1/passkey/register`, `/v1/passkey/login`
(Tabellen aus `migrations/0003_passkeys.sql`). Der Schlüssel liegt im Gerät (bei Apple im iCloud-Schlüsselbund und
damit auf allen Apple-Geräten), der Server kennt nur den öffentlichen Schlüssel und prüft Herausforderung,
Herkunft, Relying Party und Signatur (ES256 oder RS256). Passkeys gelten nur für die Spielseite:
`PASSKEY_RP_ID` (Standard `hannes-vnz.github.io`) und `PASSKEY_ORIGINS` (Standard `https://hannes-vnz.github.io`).
Mit Anmeldung (`Authorization`) kommt ein neuer Passkey zum bestehenden Konto dazu („Face ID hinzufügen“).
