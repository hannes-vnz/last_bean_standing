"""Menu, nickname entry, results, leaderboard and pause screens.

They draw on the renderer's canvas, whatever its size (phone in portrait, tablet, desktop),
and return the buttons they drew, so touches and mouse clicks can be matched to actions.
Keyboard shortcuts keep working on desktop.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pygame

from ..render.renderer import Renderer

PERIOD_NAMES = {"all": "Gesamt", "week": "Woche", "month": "Monat"}
BUTTON_H = 30


@dataclass(frozen=True)
class Button:
    rect: pygame.Rect
    action: str


def hit(buttons: list[Button], pos: tuple[int, int]) -> str | None:
    for b in buttons:
        if b.rect.collidepoint(pos):
            return b.action
    return None


def _panel(r: Renderer, rect: pygame.Rect) -> None:
    r.canvas.fill(r.ink, rect.inflate(4, 4))
    r.canvas.fill((255, 250, 240), rect)


def _button(r: Renderer, rect: pygame.Rect, label: str, action: str, primary: bool = False) -> Button:
    r.canvas.fill(r.ink, rect.inflate(4, 4))
    r.canvas.fill(r.crit_color if primary else (255, 250, 240), rect)
    img = r.font.render(label, False, r.ink)
    r.canvas.blit(img, (rect.centerx - img.get_width() // 2, rect.centery - img.get_height() // 2))
    return Button(rect, action)


def _button_column(r: Renderer, top: int, items: list[tuple[str, str]], width: int = 200) -> list[Button]:
    """Buttons stacked vertically, centred; the first one is the main action."""
    x = (r.w - width) // 2
    return [
        _button(r, pygame.Rect(x, top + i * (BUTTON_H + 10), width, BUTTON_H), label, action, primary=i == 0)
        for i, (label, action) in enumerate(items)
    ]


def _button_row(r: Renderer, y: int, items: list[tuple[str, str]], width: int = 120) -> list[Button]:
    gap = 10
    width = min(width, (r.w - 20 - gap * (len(items) - 1)) // len(items))
    x0 = (r.w - len(items) * width - (len(items) - 1) * gap) // 2
    return [
        _button(r, pygame.Rect(x0 + i * (width + gap), y, width, BUTTON_H), label, action, primary=i == 0)
        for i, (label, action) in enumerate(items)
    ]


def _dim(r: Renderer, alpha: int) -> None:
    dim = pygame.Surface((r.w, r.h), pygame.SRCALPHA)
    dim.fill((*r.ink, alpha))
    r.canvas.blit(dim, (0, 0))


def _backdrop(r: Renderer) -> None:
    """The arena map, dimmed, as a friendly background."""
    aw, ah = r.arena_px
    r.draw_ground_at(aw, ah)  # canvas pixels to world units: the clearing in the middle of the map
    _dim(r, 120)


def _mmss(seconds: int) -> str:
    return f"{seconds // 60}:{seconds % 60:02d}"


def _fit(r: Renderer, text: str, width: int) -> str:
    """Shorten text with an ellipsis until it fits `width` pixels."""
    if r.font.size(text)[0] <= width:
        return text
    while text and r.font.size(text + "…")[0] > width:
        text = text[:-1]
    return text + "…"


def _top(r: Renderer, content_h: int) -> int:
    """Vertical start so that a block of `content_h` pixels sits in the middle."""
    return max(10, (r.h - content_h) // 2)


def draw_menu(r: Renderer, profile: dict[str, Any], web: bool) -> list[Button]:
    _backdrop(r)
    cx = r.w // 2
    top = _top(r, 300)
    r.text("Last Bean Standing", (cx, top + 16), r.big_font, center=True)
    r.text("Der Schnitter kommt zur Ernte.", (cx, top + 42), center=True)
    panel = pygame.Rect(cx - min(150, r.w // 2 - 10), top + 60, min(300, r.w - 20), 92)
    _panel(r, panel)
    r.dark_text(f"Hallo, {profile.get('nickname') or '?'}!", (cx, panel.y + 10), center=True)
    best = profile["highscores"]["overall"]
    if best:
        r.dark_text(f"Rekord: {best['score']} Punkte", (cx, panel.y + 32), center=True)
        r.dark_text(f"{_mmss(best['seconds'])}, {best['kills']} Kills, Level {best['level']}", (cx, panel.y + 48),
                    center=True)  # fmt: skip
    else:
        r.dark_text("Noch kein Rekord.", (cx, panel.y + 38), center=True)
    t = profile["totals"]
    r.dark_text(f"Läufe {t['runs']}   Funkelsteine {profile.get('sparkles', 0)}", (cx, panel.y + 70), center=True)
    items = [("Spielen", "play"), ("Werkstatt", "workshop"), ("Bestenliste", "board"), ("Name ändern", "name"),
             ("Einstellungen", "settings")]  # fmt: skip
    if not web:
        items.append(("Beenden", "quit"))
    if r.w > r.h:  # landscape: "Spielen" big, the rest in one row, so it fits the 360 pixel height
        buttons = _button_column(r, panel.bottom + 14, items[:1])
        buttons += _button_row(r, panel.bottom + 54, items[1:], width=118)
    else:
        buttons = _button_column(r, panel.bottom + 16, items)
    if not r.touch and r.w >= 500:  # keyboard hints only where a keyboard is likely and there is room
        r.text("Enter spielen · L Bestenliste · N Name · Leertaste Fähigkeit", (cx, r.h - 18), center=True)
    return buttons


def draw_characters(r: Renderer, characters: list, current: str, best: dict[str, Any]) -> list[Button]:
    """Pick a bean: one card per playable character with sprite, role, passive and active ability."""
    _backdrop(r)
    cx = r.w // 2
    wide = r.w > r.h
    cols = 3 if wide else 2
    rows = (len(characters) + cols - 1) // cols
    gap = 8
    cw = min(200, (r.w - 16 - gap * (cols - 1)) // cols)
    ch = min(118, (r.h - 120 - gap * (rows - 1)) // rows)
    top = _top(r, 40 + rows * (ch + gap) + 40)
    r.text("Wähle deine Bohne", (cx, top + 14), r.big_font, center=True)
    x0 = (r.w - cols * cw - (cols - 1) * gap) // 2
    buttons = []
    for i, c in enumerate(characters):
        rect = pygame.Rect(x0 + (i % cols) * (cw + gap), top + 36 + (i // cols) * (ch + gap), cw, ch)
        chosen = c.id == current
        r.canvas.fill(r.crit_color if chosen else r.ink, rect.inflate(6 if chosen else 4, 6 if chosen else 4))
        r.canvas.fill((58, 42, 74), rect)
        img = r.sprites.get(c.id, 2.0)
        if img is not None:
            r.canvas.blit(img, (rect.x + 4, rect.y + 6))
        tx = rect.x + 42
        r.text(c.name, (tx, rect.y + 4), r.mid_font)
        r.text(c.title, (tx, rect.y + 22))
        lines = [c.archetype.split(":")[0], f"HP {c.hp}  Tempo {c.speed}"]
        lines += [f"Passiv: {c.passive.name}", f"Fähigkeit: {c.active.name}"]
        record = best.get(c.id)
        if record and ch >= 110:
            lines.append(f"Rekord {record['score']}")
        y = rect.y + 40
        for line in lines:
            if y > rect.bottom - 12:
                break
            for part in _wrap(r, line, rect.right - 6 - (tx if y < rect.y + 46 else rect.x + 6)):
                r.text(part, (rect.x + 6 if y >= rect.y + 46 else tx, y))
                y += 12
        buttons.append(Button(rect, f"char:{c.id}"))
    buttons += _button_row(r, top + 36 + rows * (ch + gap) + 6, [("Zurück", "menu")], width=140)
    if not r.touch and r.w >= 500:
        r.text("Antippen oder 1 bis 6 · Enter: die markierte Bohne", (cx, r.h - 14), center=True)
    return buttons


def _wrap(r: Renderer, text: str, width: int) -> list[str]:
    words, lines, line = text.split(), [], ""
    for w in words:
        trial = f"{line} {w}".strip()
        if line and r.font.size(trial)[0] > width:
            lines.append(line)
            line = w
        else:
            line = trial
    return [*lines, line] if line else lines


PROLOGUE = (
    "Auf der Lichtung keimt die letzte Saat des Gartens.",
    "Der Schnitter will die große Ernte einfahren.",
    "Seine Fäulnis verdirbt Plagen und Beete.",
    "Du bist eine Bohne. Halte die Saat, so lange du kannst.",
)


def draw_workshop(r: Renderer, shop, profile: dict[str, Any]) -> list[Button]:
    """Werkstatt: small permanent bonuses for Funkelsteine; every item can be sold back at full price."""
    from ..meta.workshop import level_cost, levels

    _backdrop(r)
    cx = r.w // 2
    items = shop.workshop
    cols = 2 if r.w >= 520 else 1
    rows = (len(items) + cols - 1) // cols
    gap = 4
    cw = min(300, (r.w - 16 - gap * (cols - 1)) // cols)
    ch = max(24, min(34, (r.h - 100 - gap * (rows - 1)) // rows))
    top = _top(r, 40 + rows * (ch + gap) + 40)
    r.text("Werkstatt", (cx, top + 12), r.big_font, center=True)
    r.text(f"{profile.get('sparkles', 0)} Funkelsteine · Verkaufen gibt alles zurück", (cx, top + 30), center=True)
    x0 = (r.w - cols * cw - (cols - 1) * gap) // 2
    owned = levels(profile)
    buttons = []
    for i, it in enumerate(items):
        rect = pygame.Rect(x0 + (i // rows) * (cw + gap), top + 40 + (i % rows) * (ch + gap), cw, ch)
        lv = owned.get(it.id, 0)
        r.canvas.fill(r.ink, rect.inflate(2, 2))
        r.canvas.fill((255, 250, 240) if lv < it.max_level else (232, 246, 214), rect)
        r.dark_text(f"{it.name}  {lv}/{it.max_level}", (rect.x + 5, rect.y + 3))
        r.dark_text(_fit(r, it.text, cw - 2 * 52 - 16), (rect.x + 5, rect.y + ch - 13))
        bw = 52
        buy = pygame.Rect(rect.right - 2 * bw - 6, rect.y + 3, bw, ch - 6)
        sell = pygame.Rect(rect.right - bw - 3, rect.y + 3, bw, ch - 6)
        if lv < it.max_level:
            cost = level_cost(it, lv + 1)
            can = profile.get("sparkles", 0) >= cost
            r.canvas.fill(r.crit_color if can else (220, 214, 204), buy)
            r.dark_text(str(cost), (buy.centerx, buy.centery - 5), center=True)
            buttons.append(Button(buy, f"ws_buy:{it.id}"))
        if lv:
            r.canvas.fill((214, 204, 232), sell)
            r.dark_text("zurück", (sell.centerx, sell.centery - 5), center=True)
            buttons.append(Button(sell, f"ws_sell:{it.id}"))
    buttons += _button_row(r, top + 44 + rows * (ch + gap), [("Fertig", "workshop_back")], width=140)
    return buttons


def draw_settings(r: Renderer, settings: dict[str, Any]) -> list[Button]:
    """Volume, damage numbers, screen shake; first-run tips again."""
    _backdrop(r)
    cx = r.w // 2
    top = _top(r, 250)
    r.text("Einstellungen", (cx, top + 14), r.big_font, center=True)
    items = [
        (f"Lautstärke: {settings['volume']} %", "set:volume"),
        ("Schadenszahlen: " + ("an" if settings["numbers"] else "aus"), "set:numbers"),
        ("Bildschirmwackeln: " + ("an" if settings["shake"] else "aus"), "set:shake"),
        ("Tipps wieder zeigen", "set:hints"),
        ("Zurück", "settings_back"),
    ]
    return _button_column(r, top + 40, items, width=220)


def draw_prologue(r: Renderer) -> list[Button]:
    """Shown once on the very first start (docs/STORY.md)."""
    _backdrop(r)
    cx = r.w // 2
    top = _top(r, 60 + len(PROLOGUE) * 34 + 60)
    r.text("Die große Ernte", (cx, top + 14), r.big_font, center=True)
    for i, line in enumerate(PROLOGUE):
        for j, part in enumerate(_wrap_lines(r, line, r.w - 30)):
            r.text(part, (cx, top + 56 + i * 34 + j * 14), center=True)
    return _button_column(r, top + 56 + len(PROLOGUE) * 34 + 10, [("Los geht's", "prologue_done")])


def _wrap_lines(r: Renderer, text: str, width: int) -> list[str]:
    lines, line = [], ""
    for word in text.split():
        trial = f"{line} {word}".strip()
        if r.font.size(trial)[0] <= width:
            line = trial
        else:
            lines.append(line)
            line = word
    return [*lines, line] if line else lines


KEY_ROWS = ("1234567890", "QWERTZUIOPÜ", "ASDFGHJKLÖÄ", "YXCVBNMß")


def draw_name_entry(
    r: Renderer, current: str, valid: bool, first_time: bool, keyboard: bool = False, upper: bool = True
) -> list[Button]:
    """Nickname entry. Touch devices get an on-screen keyboard (the browser's text dialog felt clumsy on
    phones and tablets); with a real keyboard you just type."""
    _backdrop(r)
    cx = r.w // 2
    kb_h = 5 * 30 + 10 if keyboard else 0
    top = _top(r, 150 + kb_h) if keyboard else _top(r, 230)
    r.text("Wie heißt deine Bohne?" if first_time else "Neuer Spitzname", (cx, top + 16), r.big_font, center=True)
    field = pygame.Rect(cx - min(120, r.w // 2 - 10), top + 44, min(240, r.w - 20), 30)
    _panel(r, field)
    caret = "_" if (pygame.time.get_ticks() // 400) % 2 else " "
    r.dark_text(current + caret, (field.x + 10, field.y + 9))
    if not keyboard:
        r.text("2 bis 16 Zeichen: Buchstaben, Ziffern, _ - .", (cx, field.bottom + 16), center=True)
        r.text("Der Name erscheint in der Bestenliste.", (cx, field.bottom + 32), center=True)
        items = [("Übernehmen" if valid else "Name eintippen", "ok" if valid else "type")]
        if not first_time:
            items.append(("Abbrechen", "cancel"))
        return [Button(field, "type"), *_button_column(r, field.bottom + 52, items)]
    buttons = _keyboard(r, field.bottom + 14, upper)
    y = field.bottom + 14 + 5 * 30 + 6
    items = [("Übernehmen", "ok")] if valid else []
    if not first_time:
        items.append(("Abbrechen", "cancel"))
    if items:
        buttons += _button_row(r, y, items)
    else:
        r.text("2 bis 16 Zeichen", (cx, y + 10), center=True)
    return buttons


def _keyboard(r: Renderer, top: int, upper: bool) -> list[Button]:
    """Four rows of letter keys plus _ - . space and delete; keys big enough for a thumb."""
    gap, key_h = 3, 27
    key_w = min(34, (r.w - 16 - gap * 10) // 11)
    buttons = []

    def key(rect: pygame.Rect, label: str, action: str, wide: bool = False) -> None:
        r.canvas.fill(r.ink, rect.inflate(2, 2))
        r.canvas.fill((235, 228, 245) if wide else (255, 250, 240), rect)
        img = r.font.render(label, False, r.ink)
        r.canvas.blit(img, img.get_rect(center=rect.center))
        buttons.append(Button(rect, action))

    for row_i, row in enumerate(KEY_ROWS):
        chars = row if upper or row_i == 0 else row.lower()
        if row_i == 3:
            chars = chars.replace("SS", "ß")  # "ß".upper() would be "SS"
        n = len(chars) + (2 if row_i == 3 else 0)
        x = (r.w - (n * key_w + (n - 1) * gap)) // 2
        y = top + row_i * (key_h + gap)
        if row_i == 3:
            key(pygame.Rect(x, y, key_w, key_h), "aA", "key:shift", wide=True)
            x += key_w + gap
        for ch in chars:
            key(pygame.Rect(x, y, key_w, key_h), ch, "key:" + ch)
            x += key_w + gap
        if row_i == 3:
            key(pygame.Rect(x, y, key_w, key_h), "<", "key:back", wide=True)
    y = top + 4 * (key_h + gap)
    small = [("_", "key:_"), ("-", "key:-"), (".", "key:.")]
    space_w = min(160, r.w - 16 - 3 * (key_w + gap) - gap)
    x = (r.w - (3 * (key_w + gap) + space_w)) // 2
    for label, action in small:
        key(pygame.Rect(x, y, key_w, key_h), label, action)
        x += key_w + gap
    key(pygame.Rect(x, y, space_w, key_h), "Leerzeichen", "key: ", wide=True)
    return buttons


def draw_results(
    r: Renderer, result: dict[str, Any], flags: dict[str, bool], profile: dict[str, Any], online: str = ""
) -> list[Button]:
    _dim(r, 150)
    cx = r.w // 2
    top = _top(r, 290)
    title = "Sieg! Die Saat ist gerettet" if result.get("victory") else "Die Bohne ist gefallen"
    r.text(title, (cx, top + 14), r.big_font, center=True)
    panel = pygame.Rect(cx - min(140, r.w // 2 - 10), top + 38, min(280, r.w - 20), 184)
    _panel(r, panel)
    r.dark_text(f"{result['score']} Punkte", (cx, panel.y + 12), center=True)
    if flags.get("new_best"):
        badge = pygame.Rect(cx - 60, panel.y + 30, 120, 16)
        r.canvas.fill(r.crit_color, badge)
        r.dark_text("Neuer Rekord!", (cx, badge.y + 2), center=True)
    rows = [
        ("Zeit", _mmss(result["seconds"])),
        ("Beet", f"{result.get('stage', 1)} / 3"),
        ("Kills", str(result["kills"])),
        ("Level", str(result["level"])),
        ("Bosse", str(result["bosses"])),
    ]
    if result.get("swarm_seconds"):
        rows.append(("Plagenflut", _mmss(result["swarm_seconds"])))
    for i, (label, value) in enumerate(rows):
        y = panel.y + 54 + i * 16
        r.dark_text(label, (panel.x + 30, y))
        _right(r, value, panel.right - 30, y)
    best = profile["highscores"]["overall"]
    if best and not flags.get("new_best"):
        r.dark_text(f"Rekord: {best['score']}", (cx, panel.y + 30), center=True)
    sparkles = result.get("sparkles") or {}
    if sparkles:  # Funkelsteine of this run, itemised
        y = panel.y + 56 + len(rows) * 16
        r.canvas.fill(r.crit_color, (panel.x + 10, y, panel.w - 20, 30))
        r.dark_text(f"+{sum(sparkles.values())} Funkelsteine", (cx, y + 3), center=True)
        detail = " · ".join(f"{k} {v}" for k, v in sparkles.items())
        r.dark_text(_fit(r, detail, panel.w - 24), (cx, y + 16), center=True)
    if online:
        r.text(online, (cx, panel.bottom + 14), center=True)
    return _button_row(r, panel.bottom + 30, [("Neuer Lauf", "again"), ("Menü", "menu")])


def draw_board(r: Renderer, board: dict, profile: dict[str, Any], enabled: bool) -> list[Button]:
    """Online leaderboard: tabs for all time / week / month, top 10, own name highlighted."""
    _backdrop(r)
    cx = r.w // 2
    rows = 10
    panel_h = 30 + rows * 18
    top = _top(r, 70 + panel_h + 80)
    r.text("Bestenliste", (cx, top + 14), r.big_font, center=True)
    tabs = _button_row(r, top + 32, [(v, f"period:{k}") for k, v in PERIOD_NAMES.items()], width=90)
    for b in tabs:  # mark the active tab
        if b.action == f"period:{board['period']}":
            r.canvas.fill(r.crit_color, b.rect)
            img = r.font.render(PERIOD_NAMES[board["period"]], False, r.ink)
            r.canvas.blit(img, (b.rect.centerx - img.get_width() // 2, b.rect.centery - img.get_height() // 2))
        else:
            r.canvas.fill((255, 250, 240), b.rect)
            img = r.font.render(PERIOD_NAMES[b.action.split(":")[1]], False, r.ink)
            r.canvas.blit(img, (b.rect.centerx - img.get_width() // 2, b.rect.centery - img.get_height() // 2))
    panel = pygame.Rect(cx - min(200, r.w // 2 - 6), top + 72, min(400, r.w - 12), panel_h)
    _panel(r, panel)
    entries = board.get("entries")
    narrow = panel.w < 340  # portrait phone: drop the kills column
    if not enabled:
        r.dark_text("Die Online-Bestenliste ist nicht verbunden.", (cx, panel.y + 90), center=True)
    elif entries is None:
        msg = "Lade ..." if board.get("loading") else "Server nicht erreichbar."
        r.dark_text(msg, (cx, panel.y + 90), center=True)
    elif not entries:
        r.dark_text("Noch keine Einträge. Sei die erste Bohne!", (cx, panel.y + 90), center=True)
    else:
        right = panel.right - 10
        cols = {
            "rank": panel.x + 10,
            "name": panel.x + 36,
            "time": right - (110 if narrow else 180),
            "kills": right - 100,
        }
        r.dark_text("#", (cols["rank"], panel.y + 8))
        r.dark_text("Name", (cols["name"], panel.y + 8))
        r.dark_text("Zeit", (cols["time"], panel.y + 8))
        if not narrow:
            r.dark_text("Kills", (cols["kills"], panel.y + 8))
        _right(r, "Punkte", right, panel.y + 8)
        me = profile.get("nickname")
        for i, e in enumerate(entries[:rows]):
            y = panel.y + 28 + i * 18
            if e.get("name") == me:
                r.canvas.fill(r.crit_color, (panel.x + 4, y - 2, panel.w - 8, 16))
            r.dark_text(str(e["rank"]), (cols["rank"], y))
            r.dark_text(str(e["name"]), (cols["name"], y))
            r.dark_text(_mmss(int(e["seconds"])), (cols["time"], y))
            if not narrow:
                r.dark_text(str(e["kills"]), (cols["kills"], y))
            _right(r, str(e["score"]), right, y)
    best = (profile.get("online") or {}).get("best_rank")
    pending = len(profile.get("pending_submissions", []))
    footer = f"Dein bester Rang: #{best}" if best else "Noch kein Lauf online"
    if pending:
        footer += f" ({pending} warten aufs Senden)"
    r.text(footer, (cx, panel.bottom + 14), center=True)
    return [*tabs, *_button_row(r, panel.bottom + 30, [("Zurück", "back")])]


def _right(r: Renderer, text: str, right_x: int, y: int) -> None:
    img = r.font.render(text, False, r.ink)
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


def draw_pause(r: Renderer, snap, muted: bool) -> list[Button]:
    """Pause overlay with the current build: weapons, upgrades and items with their levels or stacks."""
    _dim(r, 160)
    cx = r.w // 2
    top = _top(r, 270 if r.w > r.h else 360)
    r.text("Pause", (cx, top + 14), r.big_font, center=True)
    panel = pygame.Rect(cx - min(150, r.w // 2 - 10), top + 36, min(300, r.w - 20), 180)
    _panel(r, panel)
    focus = snap.players[0]
    summary = f"Level {focus.level}   Kills {focus.kills}   {_mmss(int(snap.time_s))}"
    r.dark_text(summary, (cx, panel.y + 10), center=True)
    build = [f"{r.weapons[wid].name} {lvl}" for wid, lvl in focus.weapons if wid in r.weapons]
    build += [f"{r.upgrades[uid].name} {lvl}" for uid, lvl in focus.upgrades if uid in r.upgrades]
    build += [f"{r.items[iid].name}" + (f" x{n}" if n > 1 else "") for iid, n in focus.items if iid in r.items]
    if not build:
        r.dark_text("Noch keine Waffen, Upgrades oder Items", (cx, panel.y + 40), center=True)
    col_w = (panel.w - 20) // 2
    rows = (panel.h - 40) // 14
    shown = build if len(build) <= rows * 2 else [*build[: rows * 2 - 1], f"+{len(build) - rows * 2 + 1} weitere"]
    for i, line in enumerate(shown):
        col, row = i // rows, i % rows  # column by column: weapons first, then upgrades, then items
        r.dark_text(_fit(r, line, col_w - 4), (panel.x + 10 + col * col_w, panel.y + 30 + row * 14))
    items = [
        ("Weiter", "resume"),
        ("Neuer Lauf", "again"),
        ("Menü", "menu"),
        ("Ton an" if muted else "Ton aus", "mute"),
        ("Optionen", "settings"),
    ]
    if r.w > r.h:  # landscape: one row, so it fits the 360 pixel height
        return _button_row(r, panel.bottom + 16, items, width=110)
    return _button_column(r, panel.bottom + 16, items)
