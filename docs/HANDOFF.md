# Übergabe an einen neuen Chat (Stand 28.10.2026)

Lies zuerst `CLAUDE.md`, dann diese Datei, dann `docs/ROADMAP.md` (Pakete A bis E) und `docs/STORY.md`.

## Arbeitsweise mit Hannes
- **Einfach weitermachen, bis Hannes „Stopp“ sagt:** fertige Pakete selbst nach `main` mergen und pushen (GitHub Pages deployt), zwischendurch kurz berichten.
- Handy und iPad sind die Hauptplattform. Im Browser-Pane mit `resize_window preset mobile` und per JS ausgelösten Touch-Events testen (siehe frühere Tests: `new Touch(...)` + `TouchEvent` auf `#canvas`).
- Werte in `data/` nur über `tools/build_content.py` ändern, dann `python tools/build_content.py`. Selbst gewählte Werte im Bericht nennen.
- Nie Secrets in Dateien oder Chat übernehmen.

## Live
- Spiel: https://hannes-vnz.github.io/last_bean_standing/ (`?debug` zeigt Touch-Diagnose)
- Bestenliste: https://last-bean-standing.hannesvincenz.workers.dev (Cloudflare Worker + D1, `worker/`)
- CI/Deploy prüfen: `curl https://api.github.com/repos/hannes-vnz/last_bean_standing/actions/runs?head_sha=<sha>` (kein `gh` installiert)

## Erledigt
M0 bis M6b, Paket A (Feuern im Laufen, Magnet, Fenns Fähigkeiten, Pause), A2 (Handy/iPad, Touch, Zoom, Startbild),
schnellere Progression (Variante C), Paket B (Karte 200 x 200, Minikarte, Boss-Pfeil), Story „Die große Ernte“,
Paket C (Samenkörner, 90 Saatkisten, Vasen, Heilkugeln, 30 Items, Neu würfeln/Verbannen).

## Zuletzt erledigt (28.10.2026, zweiter Chat)
- Paket C2 (6 Waffen, 4 Plätze, Stufen), Paket T (Interpolation, schnellere Gedränge-Berechnung, Gegner-Recycling,
  Tipp-Fix hochkant, Tempo x1,25), Paket F (drei Beete, Gartenplagen, 3 Bosse, Gartentor, Plagenflut, Sieg,
  Kartenseltenheit, Glücksrad, komplexe Boni, Icons, Bodenkacheln). Details in `docs/ROADMAP.md`.
- Push klappt erst, seit Hannes GitHub neu verbunden hat; Merge nach `main` braucht seine Freigabe in der Sitzung.
- Bestenlisten-Server: Plausibilitätsprüfung der Flutzeit geändert (300 statt 1200 s) in `server/app.py` und
  `worker/src/index.js`; der Worker muss neu deployt werden (`wrangler deploy`), sonst lehnt er Flut-Läufe ab.

## Danach laut Roadmap
Bildrate auf echten Geräten prüfen, Balance mit Testspielern, Gier-Schreine, Paket D (Animationen, Geschoss-Sprites, Pixelschrift),
Paket E (Export/Import im Menü, Einstellungen, Hinweise beim ersten Lauf, Balance mit Testspielern).

## Offene Fragen an Hannes
- Werte in `sim/tuning.py` (Annahmen ohne Daten) bestätigen.
- Ob Vollbild-Taps auf seinem Handy jetzt gehen (Fix: kein automatisches requestFullscreen mehr).
