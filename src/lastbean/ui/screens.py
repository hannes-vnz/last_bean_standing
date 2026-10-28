"""Menu, nickname entry, results, leaderboard and pause screens.

They draw on the renderer's canvas, whatever its size (phone in portrait, tablet, desktop),
and return the buttons they drew, so touches and mouse clicks can be matched to actions.
Keyboard shortcuts keep working on desktop.
"""

from __future__ import annotations

import math
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


WOOD = (166, 112, 76)
WOOD_DARK = (122, 78, 56)
WOOD_LIGHT = (196, 142, 98)
PAPER = (255, 250, 240)
GOLD = (255, 212, 94)
LEAF = (126, 217, 87)


def _panel(r: Renderer, rect: pygame.Rect) -> None:
    """Cream paper in a thin wooden frame."""
    c = r.canvas
    c.fill(r.ink, rect.inflate(8, 8))
    c.fill(WOOD, rect.inflate(6, 6))
    c.fill(WOOD_LIGHT, (rect.x - 3, rect.y - 3, rect.w + 6, 1))
    c.fill(PAPER, rect)
    c.fill((240, 230, 210), (rect.x, rect.bottom - 2, rect.w, 2))


def _plank(r: Renderer, rect: pygame.Rect) -> None:
    """A wooden sign: planks with grain lines and two nails."""
    c = r.canvas
    c.fill(r.ink, rect.inflate(4, 4))
    c.fill(WOOD, rect)
    c.fill(WOOD_LIGHT, (rect.x, rect.y, rect.w, 2))
    c.fill(WOOD_DARK, (rect.x, rect.bottom - 3, rect.w, 3))
    for k in range(1, 4):  # grain
        y = rect.y + k * rect.h // 4
        c.fill(WOOD_DARK, (rect.x + 6 + (k * 17) % 20, y, rect.w // 3, 1))
    for nx in (rect.x + 5, rect.right - 7):
        c.fill(r.ink, (nx, rect.y + 4, 2, 2))


def _title(r: Renderer, text: str, pos: tuple[int, int]) -> None:
    """Page title on a wooden sign."""
    w = r.big_font.size(text)[0] + 28
    sign = pygame.Rect(0, 0, min(w, r.w - 8), 26)
    sign.center = pos
    _plank(r, sign)
    r.text(text, pos, r.big_font, center=True)


def _button(r: Renderer, rect: pygame.Rect, label: str, action: str, primary: bool = False) -> Button:
    """Chunky button with a dark lip below, gold for the main action."""
    c = r.canvas
    face = GOLD if primary else PAPER
    c.fill(r.ink, rect.inflate(4, 4).move(0, 2))
    c.fill(r.ink, rect.inflate(4, 4))
    c.fill(face, rect)
    c.fill(tuple(max(0, v - 40) for v in face), (rect.x, rect.bottom - 3, rect.w, 3))
    c.fill(tuple(min(255, v + 30) for v in face), (rect.x, rect.y, rect.w, 2))
    img = r.font.render(label, False, r.ink)
    c.blit(img, (rect.centerx - img.get_width() // 2, rect.centery - img.get_height() // 2 - 1))
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
    """The garden, softly dimmed and darker towards the edges."""
    aw, ah = r.arena_px
    r.draw_ground_at(aw, ah)  # canvas pixels to world units: the clearing in the middle of the map
    key = ("vignette", r.w, r.h)
    veil = r._number_cache.get(key)
    if veil is None:
        veil = pygame.Surface((r.w, r.h), pygame.SRCALPHA)
        veil.fill((*r.ink, 90))
        rings = 24
        for k in range(rings):  # darker towards the rim, in soft steps
            a = 90 + round(110 * ((rings - k) / rings) ** 2)
            pygame.draw.rect(veil, (*r.ink, a), (k * 2, k * 2, r.w - k * 4, r.h - k * 4), 2)
        r._number_cache[key] = veil
    r.canvas.blit(veil, (0, 0))


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


# Garden wisdom on the menu: tips with a wink (one every few seconds).
GARDEN_TIPS = (
    "Gartenweisheit: Wer stillsteht, schießt gezielter. Fragt Aya.",
    "Gartenweisheit: Schnecken sind langsam. Ihre Königin nicht.",
    "Gartenweisheit: Ein Schrein am Tag hält den Schnitter auf Trab.",
    "Gartenweisheit: Die Flut zahlt besser, je länger du zockst.",
    "Gartenweisheit: Goldene Rahmen bringen Glück. Meistens.",
    "Gartenweisheit: Funkelsteine wachsen im Gewächshaus zu Wundern.",
    "Gartenweisheit: Kompost riecht nach Abenteuer.",
    "Gartenweisheit: Tipp die Bohne an. Sie mag das.",
)
BEAN_SAYS = ("Hallo!", "Auf ins Beet!", "Hihi!", "Nicht kitzeln!", "Bereit!", "Wo sind die Schnecken?", "Bohn-jour!")
_logo_font = None


def _logo(r: Renderer, cx: int, y: int, t: int, one_line: bool = False) -> None:
    """LAST BEAN STANDING in big wobbling letters, gold with a dark outline, a sprout on the B.
    Two lines (about 64 px high) or, on short screens, one line (about 34 px)."""
    global _logo_font
    if _logo_font is None:
        from ..render.pixelfont import body_font

        _logo_font = body_font(3)
    words = ("Last Bean Standing",) if one_line else ("Last Bean", "Standing")
    for row, word in enumerate(words):
        width = _logo_font.size(word)[0]
        x = cx - width // 2
        for k, ch in enumerate(word):
            dy = round(2 * math.sin(t / 300 + k * 0.6))
            gold = _logo_font.render(ch, False, GOLD if row == 0 else (255, 236, 170))
            dark = _logo_font.render(ch, False, r.ink)
            yy = y + row * 30 + dy
            for ox, oy in ((-2, 0), (2, 0), (0, -2), (0, 3), (2, 3), (-2, 3)):
                r.canvas.blit(dark, (x + ox, yy + oy))
            r.canvas.blit(gold, (x, yy))
            x += _logo_font.size(ch)[0] + 3
    if one_line:
        sprout_x = cx - _logo_font.size(words[0])[0] // 2 + _logo_font.size("Last Be")[0] + 14
    else:
        sprout_x = cx + _logo_font.size("Last Be")[0] // 2 - 4  # a little sprout grows out of the logo
    r.canvas.fill(r.ink, (sprout_x, y - 9, 3, 9))
    r.canvas.fill(LEAF, (sprout_x + 1, y - 8, 1, 8))
    r.canvas.fill(r.ink, (sprout_x - 6, y - 12, 7, 5))
    r.canvas.fill(LEAF, (sprout_x - 5, y - 11, 5, 3))


def _showcase(r: Renderer, bean: str, x: int, y: int, t: int, poke_ms: int, tint=None) -> pygame.Rect:
    """The chosen bean big on a little soil mound: breathing, hopping when poked, a speech bubble."""
    c = r.canvas
    pygame.draw.ellipse(c, r.ink, (x - 46, y + 18, 92, 22))
    pygame.draw.ellipse(c, (122, 84, 64), (x - 44, y + 19, 88, 18))
    pygame.draw.ellipse(c, (150, 106, 78), (x - 38, y + 20, 70, 8))
    for k in range(5):  # grass tufts on the mound
        gx = x - 36 + k * 18
        c.fill(LEAF, (gx, y + 18, 2, 3))
    since = t - poke_ms
    hop = max(0, round(14 * math.sin(since / 90))) if 0 <= since < 280 else 0
    squash = -1 if (t // 700) % 2 else 0
    img = r.sprites.get(bean, 4.0, False, False, squash, tint)
    rect = pygame.Rect(x - 40, y - 70, 80, 90)
    if img is not None:
        c.blit(img, (x - img.get_width() // 2, y + 24 - img.get_height() - hop))
    if 0 <= since < 2200:  # speech bubble after a poke
        text = BEAN_SAYS[(poke_ms // 7) % len(BEAN_SAYS)]
        w = r.font.size(text)[0] + 12
        bubble = pygame.Rect(min(x + 20, r.w - w - 6), y - 92, w, 18)
        c.fill(r.ink, bubble.inflate(4, 4))
        c.fill(PAPER, bubble)
        c.fill(r.ink, (bubble.x + 6, bubble.bottom + 2, 4, 4))
        r.dark_text(text, (bubble.x + 6, bubble.y + 5))
    return rect


def _gem(r: Renderer, x: int, y: int) -> None:
    c = r.canvas
    c.fill(r.ink, (x - 4, y - 5, 9, 11))
    c.fill((255, 159, 192), (x - 3, y - 4, 7, 9))
    c.fill((255, 214, 230), (x - 2, y - 3, 2, 4))


def _menu_slug(r: Renderer, t: int, squish_ms: int) -> pygame.Rect | None:
    """Every 20 s a slug crawls along the bottom of the menu. Squished ones leave a puff and stay away a while."""
    cycle, period = t // 20_000, 20_000
    since = t - squish_ms
    ground = r.h - getattr(r, "safe", (0, 0, 0, 0))[2] - 24  # just above the tip line
    if 0 <= since < 600:  # squish puff
        x, y = _menu_slug.last if hasattr(_menu_slug, "last") else (r.w // 2, ground)
        for k in range(6):
            r.canvas.fill((200, 230, 160), (x - 8 + k * 3, y - 2 - (since // 60 + k) % 5, 2, 2))
        return None
    if squish_ms // period == cycle and squish_ms > 0:
        return None
    phase = (t % period) / 9000
    if phase > 1.0:
        return None
    x, y = round(-20 + phase * (r.w + 40)), ground
    img = r.sprites.get("slug", 1.0, False, False, (0, 1, 0, -1)[(t // 150) % 4])
    if img is not None:
        r.canvas.blit(img, (x - img.get_width() // 2, y + 6 - img.get_height()))
    _menu_slug.last = (x, y)
    rect = pygame.Rect(x - 14, y - 14, 28, 24).clip(r.canvas.get_rect())
    return rect if rect.w > 8 else None


def _column(r: Renderer, x: int, w: int, top: int, bottom: int, rows: list) -> list[Button]:
    """Stack button rows (height, [(label, action), ...], primary) between `top` and `bottom`;
    rows shrink (down to 70 %) and gaps tighten when the space is short, spare space stays below."""
    base = sum(h for h, _, _ in rows)
    gap = max(4, min(8, (bottom - top - base) // max(1, len(rows) - 1)))
    scale = min(1.0, max(0.7, (bottom - top - gap * (len(rows) - 1)) / base))
    buttons, y = [], top
    for h, items, primary in rows:
        h = round(h * scale)
        step = (w + 4) // len(items)
        for k, (label, action) in enumerate(items):
            rect = pygame.Rect(x + k * step, y, step - 4 if len(items) > 1 else w, h)
            buttons.append(_button(r, rect, label, action, primary=primary))
        y += h + gap
    return buttons


def draw_menu(r: Renderer, profile: dict[str, Any], web: bool, bean: str = "ranger", poke_ms: int = -10_000,
              tint=None, squish_ms: int = -10_000) -> list[Button]:  # fmt: skip
    """Main menu: logo, the chosen bean on its mound, big buttons, Funkelsteine and account in the corner.
    Positions follow the screen height and the safe area (notch, status bar), so nothing overlaps."""
    _backdrop(r)
    t = pygame.time.get_ticks()
    wide = r.w > r.h
    st, sr, sb, sl = getattr(r, "safe", (0, 0, 0, 0))
    signed_in = bool(profile.get("account", {}).get("session"))
    buttons: list[Button] = []
    # top bar: Funkelsteine and account
    _gem(r, 14 + sl, 16 + st)
    r.text(str(profile.get("sparkles", 0)), (22 + sl, 10 + st))
    acc = pygame.Rect(r.w - 96 - sr, 6 + st, 90, 22)
    buttons.append(_button(r, acc, "Konto: an" if signed_in else "Anmelden", "account"))
    small = [("Optionen", "settings"), ("Name", "name")] + ([] if web else [("Beenden", "quit")])
    tip_y = r.h - sb - 14  # the garden tip line; everything else stays above it
    bottom = tip_y - 6
    if wide:
        one_line = r.h - st - sb < 340
        logo_y = st + (18 if one_line else 26)
        _logo(r, r.w // 2, logo_y, t, one_line)
        top = logo_y + (40 if one_line else 72)
        col_w = 176
        rows = [(40, [("Spielen", "play")], True)]
        rows += [(30, [(label, action)], False) for label, action in
                 (("Gewächshaus", "workshop"), ("Challenges", "challenges"), ("Bestenliste", "board"))]  # fmt: skip
        rows.append((24, small, False))
        buttons += _column(r, 24 + sl, col_w, top, bottom, rows)
        bean_x = (24 + sl + col_w + r.w - sr) // 2 + 10
        # bean block: sprite top 70 px above bean_y, sign bottom 78 px below
        bean_y = max(top + 70, min(bottom - 78, (top + bottom) // 2 + 4))
    else:
        logo_y = st + 46
        _logo(r, r.w // 2, logo_y, t)
        top = logo_y + 72
        bean_x = r.w // 2
        bean_y = top + 74
        rows = [(42, [("Spielen", "play")], True)]
        rows += [(32, [(label, action)], False) for label, action in
                 (("Gewächshaus", "workshop"), ("Challenges", "challenges"), ("Bestenliste", "board"))]  # fmt: skip
        rows.append((26, small, False))
        col_top = bean_y + 78 + 12
        if bottom - col_top < 150:  # short portrait screen: pull the bean up under the logo
            bean_y = max(top + 64, bottom - 150 - 90)
            col_top = bean_y + 78 + 12
        spare = max(0, bottom - col_top - 210)
        buttons += _column(r, r.w // 2 - 100, 200, col_top + spare // 3, bottom, rows)
    showcase = _showcase(r, bean, bean_x, bean_y, t, poke_ms, tint)
    buttons.append(Button(showcase, "poke"))
    slug = _menu_slug(r, t, squish_ms)  # a slug crawls by now and then; tap it (buttons go first)
    if slug is not None:
        buttons.append(Button(slug, "squish"))
    best = profile["highscores"]["overall"]
    sign = pygame.Rect(0, 0, 150, 34)
    sign.midtop = (bean_x, bean_y + 44)
    _plank(r, sign)
    titles = profile.get("titles") or []
    hello = f"Hallo, {profile.get('nickname') or 'Bohne'}!"
    r.text(
        _fit(r, f"{hello} ({titles[-1]})" if titles else hello, sign.w + 40), (sign.centerx, sign.y + 9), center=True
    )
    r.text(f"Rekord {best['score']}" if best else "Noch kein Rekord", (sign.centerx, sign.y + 22), center=True)
    tip = GARDEN_TIPS[(t // 6000) % len(GARDEN_TIPS)]
    r.text(_fit(r, tip, r.w - 16 - sl - sr), (r.w // 2, tip_y), center=True)
    return buttons


def draw_characters(
    r: Renderer,
    characters: list,
    current: str,
    best: dict[str, Any],
    skins: dict | None = None,
    skin_label: str = "",
    mode_label: str = "",
    locked: dict | None = None,
) -> list[Button]:
    """Pick a bean: one card per character with sprite, role, passive and active ability.
    Locked beans (`locked`: id -> challenge text) are greyed out and say how to unlock them."""
    _backdrop(r)
    locked = locked or {}
    cx = r.w // 2
    wide = r.w > r.h
    cols = (5 if len(characters) > 6 else 3) if wide else 2
    rows = (len(characters) + cols - 1) // cols
    gap = 8
    cw = min(200, (r.w - 16 - gap * (cols - 1)) // cols)
    ch = min(118, (r.h - 120 - gap * (rows - 1)) // rows)
    top = _top(r, 40 + rows * (ch + gap) + 40)
    _title(r, "Wähle deine Bohne", (cx, top + 14))
    x0 = (r.w - cols * cw - (cols - 1) * gap) // 2
    buttons = []
    for i, c in enumerate(characters):
        rect = pygame.Rect(x0 + (i % cols) * (cw + gap), top + 36 + (i // cols) * (ch + gap), cw, ch)
        chosen = c.id == current
        r.canvas.fill(r.crit_color if chosen else r.ink, rect.inflate(6 if chosen else 4, 6 if chosen else 4))
        r.canvas.fill((58, 42, 74) if c.id not in locked else (40, 34, 48), rect)
        img = r.sprites.get(c.id, 2.0, tint=(skins or {}).get(c.id) if c.id not in locked else (70, 64, 80))
        if img is not None:
            r.canvas.blit(img, (rect.x + 4, rect.y + 6))
        if c.id in locked:  # how to get it
            r.text(c.name, (rect.x + 42, rect.y + 4), r.mid_font)
            r.text("Gesperrt", (rect.x + 42, rect.y + 20))
            y = rect.y + 42
            for part in _wrap(r, locked[c.id], rect.w - 12):
                if y > rect.bottom - 12:
                    break
                r.text(part, (rect.x + 6, y))
                y += 12
            buttons.append(Button(rect, "locked"))
            continue
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
    row = [("Zurück", "menu")] + ([(skin_label, "skin")] if skin_label else [])
    row += [(mode_label, "mode")] if mode_label else []
    buttons += _button_row(r, top + 36 + rows * (ch + gap) + 6, row, width=160)
    if not r.touch and r.w >= 500:
        r.text("Antippen oder Zahlentaste · Enter: die markierte Bohne", (cx, r.h - 14), center=True)
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


GREENHOUSE_TABS = (("wonders", "Wunder"), ("seeds", "Saatgut"), ("workshop", "Kraft"), ("packs", "Vorrat"))
FLOWER_COLORS = ((255, 159, 192), (255, 212, 94), (150, 210, 255), (200, 160, 255), (255, 154, 60))


def _pot(r: Renderer, x: int, y: int, grown: bool, color, t: int) -> None:
    """A clay pot: a seed mound when not bought, a swaying flower when it grows."""
    c = r.canvas
    c.fill(r.ink, (x - 12, y, 25, 16))
    c.fill((214, 120, 84), (x - 11, y + 1, 23, 14))
    c.fill((236, 150, 108), (x - 13, y - 3, 27, 5))
    c.fill(r.ink, (x - 13, y - 3, 27, 1))
    c.fill((122, 84, 64), (x - 10, y - 2, 21, 3))
    if not grown:
        c.fill((150, 106, 78), (x - 2, y - 5, 5, 3))
        c.fill((170, 190, 150), (x, y - 8, 1, 3))
        return
    sway = round(1.5 * math.sin(t / 400 + x))
    c.fill(r.ink, (x - 1 + sway // 2, y - 22, 3, 20))
    c.fill(LEAF, (x + sway // 2, y - 21, 1, 19))
    c.fill(LEAF, (x - 6, y - 12, 5, 3))
    c.fill(LEAF, (x + 2, y - 15, 5, 3))
    fx, fy = x + sway, y - 26
    for dx, dy in ((-4, 0), (4, 0), (0, -4), (0, 4)):
        c.fill(r.ink, (fx + dx - 3, fy + dy - 3, 7, 7))
        c.fill(color, (fx + dx - 2, fy + dy - 2, 5, 5))
    c.fill(GOLD, (fx - 2, fy - 2, 5, 5))


def draw_greenhouse(r: Renderer, content, profile: dict[str, Any], tab: str) -> list[Button]:
    """Gewächshaus: wonders (change how runs go), seeds (weapons grow into the card pool), Kraft (small
    permanent bonuses) and Vorrat (packs for the next run). Everything can be sold back for its full price."""
    from ..meta.workshop import greenhouse, level_cost, levels

    _backdrop(r)
    t = pygame.time.get_ticks()
    cx = r.w // 2
    shop = content.shop
    buttons: list[Button] = []
    _title(r, "Gewächshaus", (cx, 18))
    _gem(r, r.w - 70, 18)
    r.text(str(profile.get("sparkles", 0)), (r.w - 62, 12))
    tab_w = min(110, (r.w - 20) // 4 - 6)
    x0 = cx - (tab_w + 6) * 2 + 3
    for k, (key, label) in enumerate(GREENHOUSE_TABS):
        rect = pygame.Rect(x0 + k * (tab_w + 6), 38, tab_w, 22)
        buttons.append(_button(r, rect, label, f"gh_tab:{key}", primary=key == tab))
    area = pygame.Rect(8, 70, r.w - 16, r.h - 70 - 42)
    owned = greenhouse(profile)
    money = profile.get("sparkles", 0)
    if tab in ("wonders", "seeds"):
        if tab == "wonders":
            entries = [(w["id"], w["name"], w["text"], w["cost"]) for w in shop.raw.get("wonders", [])]
        else:
            weapons = {w.id: w for w in content.weapons}
            entries = [(x["weapon"], weapons[x["weapon"]].name, weapons[x["weapon"]].text, x["cost"])
                       for x in shop.raw.get("seeds", []) if x["weapon"] in weapons]  # fmt: skip
        cols = 5 if r.w > r.h else 2
        rows = (len(entries) + cols - 1) // cols
        cw = (area.w - (cols - 1) * 6) // cols
        ch = min(118, (area.h - (rows - 1) * 6) // rows)
        for i, (iid, name, text, cost) in enumerate(entries):
            cell = pygame.Rect(area.x + (i % cols) * (cw + 6), area.y + (i // cols) * (ch + 6), cw, ch)
            grown = iid in owned[tab]
            _panel(r, cell.inflate(-6, -6))
            _pot(r, cell.centerx, cell.y + 30, grown, FLOWER_COLORS[i % len(FLOWER_COLORS)], t)
            if tab == "seeds":  # the weapon's icon on a little sign in the pot
                icon = r.icons.get("weapon:" + iid, None, 1)
                if not grown:
                    icon = icon.copy()
                    icon.fill((130, 130, 130, 255), special_flags=pygame.BLEND_RGBA_MULT)
                r.canvas.blit(icon, (cell.x + 8, cell.y + 8))
            r.dark_text(_fit(r, name, cw - 12), (cell.centerx, cell.y + 48), center=True)
            lines = _wrap(r, text, cw - 14)[: 3 if ch >= 118 and tab == "wonders" else 2]
            for k, line in enumerate(lines):
                r.dark_text(line, (cell.centerx, cell.y + 60 + k * 10), center=True)
            btn = pygame.Rect(cell.x + 10, cell.bottom - 26, cw - 20, 18)
            if grown:
                buttons.append(_button(r, btn, "zurückgeben", f"gh_sell:{tab}:{iid}"))
            else:
                buttons.append(_button(r, btn, f"Pflanzen {cost}", f"gh_buy:{tab}:{iid}", primary=money >= cost))
    elif tab == "workshop":
        items = shop.workshop
        cols = 2 if r.w >= 520 else 1
        rows = (len(items) + cols - 1) // cols
        cw = (area.w - (cols - 1) * 8) // cols
        ch = max(20, min(30, (area.h - (rows - 1) * 4) // rows))
        own = levels(profile)
        for i, it in enumerate(items):
            rect = pygame.Rect(area.x + (i // rows) * (cw + 8), area.y + (i % rows) * (ch + 4), cw, ch)
            lv = own.get(it.id, 0)
            r.canvas.fill(r.ink, rect.inflate(2, 2))
            r.canvas.fill(PAPER if lv < it.max_level else (232, 246, 214), rect)
            for k in range(it.max_level):  # level pips like little sprouts
                r.canvas.fill(LEAF if k < lv else (210, 200, 186), (rect.x + 5 + k * 5, rect.y + (ch - 6) // 2, 3, 6))
            text_x = rect.x + 8 + it.max_level * 5
            room = rect.right - 2 * 52 - 12 - text_x
            r.dark_text(_fit(r, f"{it.name}: {it.text}", room), (text_x, rect.y + (ch - 10) // 2))
            bw = 52
            if lv < it.max_level:
                cost = level_cost(it, lv + 1)
                buttons.append(_button(r, pygame.Rect(rect.right - 2 * bw - 6, rect.y + 2, bw, ch - 4), str(cost),
                                       f"ws_buy:{it.id}", primary=money >= cost))  # fmt: skip
            if lv:
                buttons.append(_button(r, pygame.Rect(rect.right - bw - 3, rect.y + 2, bw, ch - 4), "zurück",
                                       f"ws_sell:{it.id}"))  # fmt: skip
    else:  # packs for the next run
        bag = profile.get("packs", [])
        r.text(f"Höchstens {shop.run_packs_max_per_run} Pakete, sie gelten nur für den nächsten Lauf.",
               (cx, area.y + 2), center=True)  # fmt: skip
        w = min(440, area.w)
        for i, pack in enumerate(shop.run_packs):
            rect = pygame.Rect(cx - w // 2, area.y + 16 + i * 38, w, 32)
            packed = pack["id"] in bag
            _panel(r, rect)
            if packed:
                r.canvas.fill((232, 246, 214), rect)
            r.dark_text(pack["name"], (rect.x + 6, rect.y + 4))
            r.dark_text(_fit(r, pack["effect"], w - 90), (rect.x + 6, rect.y + 18))
            btn = pygame.Rect(rect.right - 70, rect.y + 5, 64, 22)
            if packed:
                buttons.append(_button(r, btn, "zurück", f"pack_back:{pack['id']}"))
            elif len(bag) < shop.run_packs_max_per_run:
                buttons.append(
                    _button(r, btn, str(pack["cost"]), f"pack_buy:{pack['id']}", primary=money >= pack["cost"])
                )
    buttons += _button_row(r, r.h - 34, [("Fertig", "workshop_back")], width=140)
    return buttons


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
    _title(r, "Werkstatt", (cx, top + 12))
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
    buttons += _button_row(r, top + 44 + rows * (ch + gap), [("Fertig", "workshop_back"), ("Vorrat", "ws_tab")],
                           width=140)  # fmt: skip
    return buttons


def draw_packs(r: Renderer, shop, profile: dict[str, Any]) -> list[Button]:
    """Vorrat: packs for the next run only (at most two), bought with Funkelsteine, returnable before the run."""
    _backdrop(r)
    cx = r.w // 2
    bag = profile.get("packs", [])
    top = _top(r, 40 + len(shop.run_packs) * 40 + 50)
    _title(r, "Vorrat für den nächsten Lauf", (cx, top + 12))
    r.text(f"{profile.get('sparkles', 0)} Funkelsteine · höchstens {shop.run_packs_max_per_run} Pakete", (cx, top + 30),
           center=True)  # fmt: skip
    w = min(420, r.w - 16)
    buttons = []
    for i, pack in enumerate(shop.run_packs):
        rect = pygame.Rect(cx - w // 2, top + 42 + i * 40, w, 34)
        packed = pack["id"] in bag
        r.canvas.fill(r.ink, rect.inflate(2, 2))
        r.canvas.fill((232, 246, 214) if packed else (255, 250, 240), rect)
        r.dark_text(pack["name"], (rect.x + 6, rect.y + 4))
        r.dark_text(_fit(r, pack["effect"], w - 80), (rect.x + 6, rect.y + 19))
        btn = pygame.Rect(rect.right - 64, rect.y + 4, 58, 26)
        if packed:
            r.canvas.fill((214, 204, 232), btn)
            r.dark_text("zurück", (btn.centerx, btn.y + 8), center=True)
            buttons.append(Button(btn, f"pack_back:{pack['id']}"))
        elif len(bag) < shop.run_packs_max_per_run:
            can = profile.get("sparkles", 0) >= pack["cost"]
            r.canvas.fill(r.crit_color if can else (220, 214, 204), btn)
            r.dark_text(str(pack["cost"]), (btn.centerx, btn.y + 8), center=True)
            buttons.append(Button(btn, f"pack_buy:{pack['id']}"))
    y = top + 46 + len(shop.run_packs) * 40
    buttons += _button_row(r, y, [("Fertig", "workshop_back"), ("Werkstatt", "ws_tab")], width=140)
    return buttons


def draw_challenges(r: Renderer, content, profile: dict[str, Any], page: int, playable: int) -> list[Button]:
    """All challenges with progress bars, done ones ticked, a page at a time."""
    from ..meta.challenges import progress, reward_names, reward_text

    _backdrop(r)
    cx = r.w // 2
    items = list(content.challenges)
    done = set(profile.get("challenges_done", []))
    items.sort(key=lambda ch: ch.id in done)  # open ones first
    row_h, top = 30, 44
    per_page = max(3, (r.h - top - 50) // (row_h + 4))
    pages = (len(items) + per_page - 1) // per_page
    page = min(page, pages - 1)
    _title(r, f"Challenges  {len(done)}/{len(items)}", (cx, 16))
    names = reward_names(content)
    w = min(520, r.w - 16)
    x = cx - w // 2
    for i, ch in enumerate(items[page * per_page : (page + 1) * per_page]):
        rect = pygame.Rect(x, top + i * (row_h + 4), w, row_h)
        finished = ch.id in done
        r.canvas.fill(r.ink, rect.inflate(2, 2))
        r.canvas.fill((232, 246, 214) if finished else (255, 250, 240), rect)
        r.dark_text(_fit(r, ("✓ " if finished else "") + ch.text, w - 90), (rect.x + 5, rect.y + 3))
        r.dark_text(_fit(r, reward_text(ch, names), w - 10), (rect.x + 5, rect.y + 16))
        if not finished:
            cur, target = progress(ch, profile, playable)
            bar = pygame.Rect(rect.right - 80, rect.y + 5, 74, 8)
            r.canvas.fill(r.ink, bar.inflate(2, 2))
            r.canvas.fill((220, 214, 204), bar)
            r.canvas.fill(r.crit_color, (bar.x, bar.y, round(bar.w * min(1.0, cur / target)), bar.h))
    nav = [("Zurück", "menu")]
    if page > 0:
        nav.append(("< Seite", "page:-1"))
    if page < pages - 1:
        nav.append(("Seite >", "page:1"))
    buttons = _button_row(r, r.h - 42, nav, width=120)
    r.text(f"{page + 1}/{pages}", (cx, r.h - 52), center=True)
    return buttons


def draw_account(r: Renderer, profile: dict[str, Any], form: dict, status: str, config: dict, online: bool,
                 web: bool) -> list[Button]:  # fmt: skip
    """Account: sign in (name + password, Google, Apple) so the progress lives in the cloud."""
    _backdrop(r)
    cx = r.w // 2
    acc = profile.get("account") or {}
    top = _top(r, 280)
    _title(r, "Konto", (cx, top + 14))
    w = min(320, r.w - 20)
    panel = pygame.Rect(cx - w // 2, top + 36, w, 64)
    _panel(r, panel)
    buttons: list[Button] = []
    if not online:
        r.dark_text("Ohne Server: alles bleibt auf diesem Gerät.", (cx, panel.y + 24), center=True)
        return buttons + _button_row(r, panel.bottom + 16, [("Zurück", "menu")], width=140)
    if acc.get("session"):
        who = acc.get("name") or {"google": "Google-Konto", "apple": "Apple-ID"}.get(acc.get("provider"), "Konto")
        r.dark_text(f"Angemeldet: {who}", (cx, panel.y + 10), center=True)
        when = acc.get("synced_at") or 0
        r.dark_text("In der Cloud gesichert" if when else "Noch nicht gesichert", (cx, panel.y + 26), center=True)
        r.dark_text("Dein Fortschritt ist auf jedem Gerät da.", (cx, panel.y + 42), center=True)
        items = [("Jetzt sichern", "acc_sync"), ("Abmelden", "acc_logout"), ("Zurück", "menu")]
        y = panel.bottom + 16
        if web:  # a passkey on this device: next time Face ID / Touch ID / fingerprint instead of the password
            buttons += _button_row(r, y, [("Face ID hinzufügen", "acc_pk_add")], width=200)
            y += 40
    else:
        r.dark_text("Melde dich an, dann ist dein Fortschritt", (cx, panel.y + 10), center=True)
        r.dark_text("(Bohnen, Challenges, Werkstatt) überall da.", (cx, panel.y + 26), center=True)
        r.dark_text("Ohne Konto bleibt alles auf diesem Gerät.", (cx, panel.y + 42), center=True)
        fields = [
            ("Name", "acc_name", form.get("acc_name", "")),
            ("Passwort", "acc_pw", "*" * len(form.get("acc_pw", ""))),
        ]
        y = panel.bottom + 12
        for label, key, value in fields:
            box = pygame.Rect(cx - w // 2, y, w, 24)
            r.canvas.fill(r.ink, box.inflate(4, 4))
            r.canvas.fill((255, 250, 240), box)
            r.dark_text(f"{label}: {value or '(antippen)'}", (box.x + 8, box.y + 7))
            buttons.append(Button(box, f"acc_field:{key}"))
            y += 30
        items = [("Anmelden", "acc_login"), ("Konto erstellen", "acc_register")]
        if web and config.get("google_client_id"):
            items.append(("Mit Google", "acc_google"))
        if web and config.get("apple_client_id"):
            items.append(("Mit Apple", "acc_apple"))
        items.append(("Zurück", "menu"))
        y += 4
        if web:  # passkeys: Face ID, Touch ID, Windows Hello or fingerprint, no password
            buttons += _button_row(r, y, [("Mit Face ID anmelden", "acc_pk_login"), ("Neu mit Face ID", "acc_pk_new")],
                                   width=170)  # fmt: skip
            y += 38
    if status:
        r.text(_fit(r, status, r.w - 20), (cx, y + 2), center=True)
        y += 16
    buttons += _button_row(r, y, items, width=120)
    return buttons


def draw_settings(r: Renderer, settings: dict[str, Any]) -> list[Button]:
    """Volume, damage numbers, screen shake; first-run tips again."""
    _backdrop(r)
    cx = r.w // 2
    top = _top(r, 250)
    _title(r, "Einstellungen", (cx, top + 14))
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
    _title(r, "Die große Ernte", (cx, top + 14))
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
    r: Renderer,
    current: str,
    valid: bool,
    first_time: bool,
    keyboard: bool = False,
    upper: bool = True,
    title: str | None = None,
    mask: bool = False,
) -> list[Button]:
    """Nickname entry. Touch devices get an on-screen keyboard (the browser's text dialog felt clumsy on
    phones and tablets); with a real keyboard you just type."""
    _backdrop(r)
    cx = r.w // 2
    kb_h = 5 * 30 + 10 if keyboard else 0
    top = _top(r, 150 + kb_h) if keyboard else _top(r, 230)
    title = title or ("Wie heißt deine Bohne?" if first_time else "Neuer Spitzname")
    _title(r, title, (cx, top + 16))
    if mask:  # password: dots instead of letters
        current = "*" * len(current)
    field = pygame.Rect(cx - min(120, r.w // 2 - 10), top + 44, min(240, r.w - 20), 30)
    _panel(r, field)
    caret = "_" if (pygame.time.get_ticks() // 400) % 2 else " "
    r.dark_text(current + caret, (field.x + 10, field.y + 9))
    if not keyboard:
        r.text("2 bis 16 Zeichen: Buchstaben, Ziffern, _ - .", (cx, field.bottom + 16), center=True)
        if not mask:
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
    _title(r, title, (cx, top + 14))
    if result.get("epitaph"):  # a gravestone line with a wink
        r.text(_fit(r, result["epitaph"], r.w - 16), (cx, top + 31), center=True)
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
    done = result.get("challenges") or []
    y = panel.bottom + 12
    if done:  # challenges completed in this run: the first one, and how many more
        more = f" (+{len(done) - 1} weitere)" if len(done) > 1 else ""
        r.text(_fit(r, f"Challenge geschafft: {done[0][0]}", r.w - 20), (cx, y), center=True)
        r.text(_fit(r, done[0][1] + more, r.w - 20), (cx, y + 12), center=True)
        y += 26
    if online:
        r.text(online, (cx, y), center=True)
        y += 14
    return _button_row(r, max(panel.bottom + 30, y + 6), [("Neuer Lauf", "again"), ("Menü", "menu")])


def draw_board(r: Renderer, board: dict, profile: dict[str, Any], enabled: bool) -> list[Button]:
    """Online leaderboard: tabs for all time / week / month, top 10, own name highlighted."""
    _backdrop(r)
    cx = r.w // 2
    rows = 10
    panel_h = 30 + rows * 18
    top = _top(r, 70 + panel_h + 80)
    _title(r, "Bestenliste", (cx, top + 14))
    tab_items = [(v, f"period:{k}") for k, v in PERIOD_NAMES.items()]
    if "eternal_night" in profile.get("unlocked", {}).get("modes", []):
        tab_items.append(("Nacht" if board.get("mode") == "eternal_night" else "Normal", "board_mode"))
    tabs = _button_row(r, top + 32, tab_items, width=90)
    for b in tabs:  # mark the active tab
        if not b.action.startswith("period:"):
            continue
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
    _title(r, "Pause", (cx, top + 14))
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
