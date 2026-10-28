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

## In Arbeit: Paket C2 Mehrere Waffen (Branch `c2-weapons`, Commit „WIP Paket C2“)
Fertig: `tools/build_content.py` (6 Waffen, `weapons.json`), Loader/Schema (`ExtraWeapon`), `src/lastbean/sim/weapons.py`
(fan, nova, aura, orbit, lobbed; deterministisches `cos_sin`), Welt-Integration (Waffenkarten `weapon:<id>` im Level-up-Pool,
4 Plätze inkl. Startwaffe, `_use_weapons`, `_area_damage`, `_weapon_hit`, Kürbisbomben, Snapshot `orbiters/auras/bombs`).
Offen:
1. Renderer: Kartenanzeige für `weapon:`-Karten (Name/Text aus `content.weapons`, `per_level` bei Stufenaufstieg) – aktuell KeyError in `_draw_offer`.
2. Renderer: Bienen (orbiters), Pollenwolke (auras), Kürbisbomben mit Landewarnung, Nova-/Bomben-Ring über `WeaponPulse` in `effects.py`.
3. Pausenmenü: Waffen und Items im Build anzeigen.
4. Tests anpassen: `test_several_levels_at_once_queue_offers`, `test_run_to_five_minutes` (gewählte Karten können Waffen sein: `sum(upgrades) + sum(Waffenstufen) == level - 1`), `test_touch_loop`. Neue Tests für jede Waffenart, Slot-Grenze, Stufen, Determinismus.
5. Balance messen (`python tools/balance.py --seeds 12`), Bench (`tools/bench.py --render`), README/ROADMAP aktualisieren, mergen, pushen.

## Danach laut Roadmap
Gier-Schreine auf der Karte, Paket D (Grafik: Boden-Details, Animationen, Geschoss-Sprites, Pixelschrift),
Paket E (Export/Import im Menü, Einstellungen, Hinweise beim ersten Lauf, Balance mit Testspielern).

## Offene Fragen an Hannes
- Werte in `sim/tuning.py` (Annahmen ohne Daten) bestätigen.
- Ob Vollbild-Taps auf seinem Handy jetzt gehen (Fix: kein automatisches requestFullscreen mehr).
