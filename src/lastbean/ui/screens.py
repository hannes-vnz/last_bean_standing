"""Menu, nickname entry and results screens. They draw on the renderer's 640x360 canvas."""

from __future__ import annotations

from typing import Any

import pygame

from ..render.renderer import CANVAS_H, CANVAS_W, Renderer

CX = CANVAS_W // 2


def _panel(r: Renderer, rect: pygame.Rect) -> None:
    r.canvas.fill(r.ink, rect.inflate(4, 4))
    r.canvas.fill((255, 250, 240), rect)


def _backdrop(r: Renderer) -> None:
    """The arena map, dimmed, as a friendly background."""
    r.canvas.fill(r.void)
    m = r.map_surface
    r.canvas.blit(m, (CX - m.get_width() // 2, CANVAS_H // 2 - m.get_height() // 2))
    dim = pygame.Surface((CANVAS_W, CANVAS_H), pygame.SRCALPHA)
    dim.fill((*r.ink, 120))
    r.canvas.blit(dim, (0, 0))


def _mmss(seconds: int) -> str:
    return f"{seconds // 60}:{seconds % 60:02d}"


def draw_menu(r: Renderer, profile: dict[str, Any], web: bool) -> None:
    _backdrop(r)
    r.text("Last Bean Standing", (CX, 70), r.big_font, center=True)
    r.text("Bleib stehen, um zu schießen. Lauf, um zu überleben.", (CX, 96), center=True)
    panel = pygame.Rect(CX - 150, 120, 300, 130)
    _panel(r, panel)
    name = profile.get("nickname") or "?"
    r.dark_text(f"Hallo, {name}!", (CX, panel.y + 12), center=True)
    best = profile["highscores"]["overall"]
    if best:
        r.dark_text(f"Rekord: {best['score']} Punkte", (CX, panel.y + 34), center=True)
        r.dark_text(f"{_mmss(best['seconds'])}, {best['kills']} Kills, Level {best['level']}", (CX, panel.y + 50),
                    center=True)  # fmt: skip
    else:
        r.dark_text("Noch kein Rekord. Zeit für den ersten Lauf!", (CX, panel.y + 40), center=True)
    t = profile["totals"]
    r.dark_text(f"Läufe {t['runs']}   Kills gesamt {t['kills']}", (CX, panel.y + 74), center=True)
    r.dark_text("Enter: Spielen   L: Bestenliste   N: Name", (CX, panel.y + 100), center=True)
    if not web:
        r.text("Esc: Beenden", (CX, 270), center=True)
    r.text("WASD/Pfeile laufen  ·  im Stand wird geschossen  ·  1/2/3 Upgrade wählen", (CX, CANVAS_H - 24), center=True)


def draw_name_entry(r: Renderer, current: str, valid: bool, first_time: bool) -> None:
    _backdrop(r)
    r.text("Wie heißt deine Bohne?" if first_time else "Neuer Spitzname", (CX, 90), r.big_font, center=True)
    field = pygame.Rect(CX - 110, 130, 220, 28)
    _panel(r, field)
    caret = "_" if (pygame.time.get_ticks() // 400) % 2 else " "
    r.dark_text(current + caret, (field.x + 10, field.y + 8))
    r.text("2 bis 16 Zeichen: Buchstaben, Ziffern, Leerzeichen, _ - .", (CX, 176), center=True)
    r.text("Enter: Übernehmen" if valid else "Name noch nicht gültig", (CX, 200), center=True)
    if not first_time:
        r.text("Esc: Abbrechen", (CX, 218), center=True)
    r.text("Der Name erscheint später in der Online-Bestenliste.", (CX, 260), center=True)


def draw_results(
    r: Renderer, result: dict[str, Any], flags: dict[str, bool], profile: dict[str, Any], online: str = ""
) -> None:
    dim = pygame.Surface((CANVAS_W, CANVAS_H), pygame.SRCALPHA)
    dim.fill((*r.ink, 150))
    r.canvas.blit(dim, (0, 0))
    r.text("Die Bohne ist gefallen", (CX, 60), r.big_font, center=True)
    panel = pygame.Rect(CX - 140, 86, 280, 168)
    _panel(r, panel)
    r.dark_text(f"{result['score']} Punkte", (CX, panel.y + 12), center=True)
    if flags.get("new_best"):
        badge = pygame.Rect(CX - 60, panel.y + 30, 120, 16)
        r.canvas.fill(r.crit_color, badge)
        r.dark_text("Neuer Rekord!", (CX, badge.y + 2), center=True)
    rows = [
        ("Zeit", _mmss(result["seconds"])),
        ("Welle", str(result["wave"])),
        ("Kills", str(result["kills"])),
        ("Level", str(result["level"])),
        ("Bosse", str(result["bosses"])),
    ]
    for i, (label, value) in enumerate(rows):
        y = panel.y + 54 + i * 16
        r.dark_text(label, (panel.x + 40, y))
        img = r.font.render(value, True, r.ink)
        r.canvas.blit(img, (panel.right - 40 - img.get_width(), y))
    best = profile["highscores"]["overall"]
    if best and not flags.get("new_best"):
        r.dark_text(f"Rekord: {best['score']}", (CX, panel.bottom - 22), center=True)
    if online:
        r.text(online, (CX, panel.bottom + 14), center=True)
    r.text("R: neuer Lauf     Enter: Menü", (CX, panel.bottom + 32), center=True)


PERIOD_NAMES = {"all": "Gesamt", "week": "Woche", "month": "Monat"}


def draw_board(r: Renderer, board: dict, profile: dict[str, Any], enabled: bool) -> None:
    """Online leaderboard: tabs for all time / week / month, top 10, own name highlighted."""
    _backdrop(r)
    r.text("Bestenliste", (CX, 34), r.big_font, center=True)
    tabs = " ".join(f"[{v}]" if k == board["period"] else f" {v} " for k, v in PERIOD_NAMES.items())
    r.text(tabs, (CX, 58), center=True)
    panel = pygame.Rect(CX - 200, 74, 400, 214)
    _panel(r, panel)
    entries = board.get("entries")
    if not enabled:
        r.dark_text("Die Online-Bestenliste ist noch nicht verbunden.", (CX, panel.y + 90), center=True)
    elif entries is None:
        msg = "Lade ..." if board.get("loading") else "Server nicht erreichbar. Versuch es später nochmal."
        r.dark_text(msg, (CX, panel.y + 90), center=True)
    elif not entries:
        r.dark_text("Noch keine Einträge. Sei die erste Bohne!", (CX, panel.y + 90), center=True)
    else:
        cols = (panel.x + 14, panel.x + 54, panel.x + 210, panel.x + 290, panel.x + 386)
        for label, x in zip(("#", "Name", "Zeit", "Kills"), cols, strict=False):
            r.dark_text(label, (x, panel.y + 8))
        _right(r, "Punkte", cols[4], panel.y + 8)
        me = profile.get("nickname")
        for i, e in enumerate(entries[:10]):
            y = panel.y + 28 + i * 18
            if e.get("name") == me:
                r.canvas.fill(r.crit_color, (panel.x + 4, y - 2, panel.w - 8, 16))
            r.dark_text(str(e["rank"]), (cols[0], y))
            r.dark_text(str(e["name"]), (cols[1], y))
            r.dark_text(_mmss(int(e["seconds"])), (cols[2], y))
            r.dark_text(str(e["kills"]), (cols[3], y))
            _right(r, str(e["score"]), cols[4], y)
    best = (profile.get("online") or {}).get("best_rank")
    pending = len(profile.get("pending_submissions", []))
    footer = f"Dein bester Rang: #{best}" if best else "Noch kein Lauf online"
    if pending:
        footer += f"   ({pending} Lauf/Läufe warten aufs Senden)"
    r.text(footer, (CX, 300), center=True)
    r.text("Pfeile: Zeitraum   Esc/Enter: zurück", (CX, 322), center=True)


def _right(r: Renderer, text: str, right_x: int, y: int) -> None:
    img = r.font.render(text, True, r.ink)
    r.canvas.blit(img, (right_x - img.get_width(), y))


def online_line(status: str, rank: int | None, rank_character: int | None) -> str:
    if status == "sending":
        return "Wird an die Bestenliste gesendet ..."
    if status == "rank" and rank:
        return f"Online-Rang #{rank}" + (f" (Jäger #{rank_character})" if rank_character else "")
    if status == "offline":
        return "Offline: wird später gesendet"
    if status == "no_name":
        return ""
    return status


def draw_pause(r: Renderer, snap, muted: bool) -> None:
    """Pause overlay with the current build (upgrades and their levels)."""
    dim = pygame.Surface((CANVAS_W, CANVAS_H), pygame.SRCALPHA)
    dim.fill((*r.ink, 160))
    r.canvas.blit(dim, (0, 0))
    r.text("Pause", (CX, 60), r.big_font, center=True)
    panel = pygame.Rect(CX - 150, 84, 300, 170)
    _panel(r, panel)
    focus = snap.players[0]
    r.dark_text(
        f"Level {focus.level}   Kills {focus.kills}   {_mmss(int(snap.time_s))}", (CX, panel.y + 10), center=True
    )
    ups = [(r.upgrades[uid].name, lvl) for uid, lvl in focus.upgrades if uid in r.upgrades]
    if not ups:
        r.dark_text("Noch keine Upgrades", (CX, panel.y + 40), center=True)
    for i, (name, lvl) in enumerate(ups[:16]):
        col, row = i % 2, i // 2
        r.dark_text(f"{name} {lvl}", (panel.x + 16 + col * 146, panel.y + 34 + row * 16))
    r.text("Esc: weiter   R: neuer Lauf   Q: Menü   M: Ton " + ("an" if muted else "aus"), (CX, 272), center=True)
