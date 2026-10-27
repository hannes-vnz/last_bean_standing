"""Draws simulation snapshots onto a fixed 640x360 canvas, scaled up by an integer factor.

Coloured shapes only (sprites come in M6). Readability rules from DESIGN.md section 16:
dark outlines, own projectiles warm yellow, XP orbs mint, white text with dark outline.
"""

from __future__ import annotations

import pygame

from ..data.schema import Content
from ..sim.world import Snapshot

CANVAS_W, CANVAS_H = 640, 360
# World units per canvas pixel (DESIGN.md section 16: 1 tile = 32 units = 16 px).
UNITS_PER_PX = 2
WHITE = (255, 255, 255)
RARITY_NAMES = {
    "common": "Gewöhnlich",
    "uncommon": "Ungewöhnlich",
    "rare": "Selten",
    "epic": "Episch",
    "legendary": "Legendär",
}


def hex_rgb(value: str) -> tuple[int, int, int]:
    v = value.lstrip("#")
    return int(v[0:2], 16), int(v[2:4], 16), int(v[4:6], 16)


def integer_scale(window_w: int, window_h: int) -> int:
    """Largest integer factor at which the canvas still fits the window (at least 1)."""
    return max(1, min(window_w // CANVAS_W, window_h // CANVAS_H))


class Renderer:
    def __init__(self, content: Content) -> None:
        self.canvas = pygame.Surface((CANVAS_W, CANVAS_H))
        style = content.style
        plaza = content.biome("plaza").palette
        self.ground = hex_rgb(plaza["ground"])
        self.ground_detail = hex_rgb(plaza["detail"])
        self.ink = hex_rgb(style.ink)
        self.player_body = hex_rgb(style.player["body"])
        self.enemy_colors = {"slimeling": hex_rgb(style.enemy["slime"]), "batswarm": hex_rgb(style.enemy["bat"])}
        self.enemy_default = hex_rgb(style.enemy["slime"])
        self.shot_core = hex_rgb(style.player_projectile["core"])
        self.shot_halo = hex_rgb(style.player_projectile["halo"])
        self.hp_color = hex_rgb(style.heal_orb)
        self.crit_color = hex_rgb(style.crit_text)
        self.xp_color = hex_rgb(style.xp_orb)
        self.upgrades = {u.id: u for u in content.upgrades}
        self.rarity_colors = {
            "common": (236, 236, 236),
            "uncommon": hex_rgb(style.xp_orb),
            "rare": hex_rgb(style.player["body"]),
            "epic": (200, 150, 255),
            "legendary": hex_rgb(style.crit_text),
        }
        self.selected = 0
        # Outside the arena: ink darkened, so the ink border and outlines stay visible.
        self.void = tuple(v * 3 // 5 for v in self.ink)
        self.font = pygame.font.Font(None, 16)
        self.big_font = pygame.font.Font(None, 32)

    def draw(self, snap: Snapshot, focus_player: int = 0) -> pygame.Surface:
        c = self.canvas
        c.fill(self.void)
        focus = next((p for p in snap.players if p.player_id == focus_player), snap.players[0])
        # Camera: top-left corner of the view in canvas pixels, rounded to whole pixels.
        cam_x = round(focus.x / UNITS_PER_PX) - CANVAS_W // 2
        cam_y = round(focus.y / UNITS_PER_PX) - CANVAS_H // 2

        self._draw_ground(c, snap, cam_x, cam_y)
        ink = self.ink

        for o in snap.orbs:
            sx, sy = round(o.x / UNITS_PER_PX) - cam_x, round(o.y / UNITS_PER_PX) - cam_y
            if 0 <= sx < CANVAS_W and 0 <= sy < CANVAS_H:
                c.fill(ink, (sx - 2, sy - 1, 5, 3))
                c.fill(ink, (sx - 1, sy - 2, 3, 5))
                c.fill(self.xp_color, (sx - 1, sy, 3, 1))
                c.fill(self.xp_color, (sx, sy - 1, 1, 3))

        for e in snap.enemies:
            sx, sy = round(e.x / UNITS_PER_PX) - cam_x, round(e.y / UNITS_PER_PX) - cam_y
            r = max(2, round(e.radius / UNITS_PER_PX))
            if -r <= sx < CANVAS_W + r and -r <= sy < CANVAS_H + r:
                pygame.draw.circle(c, ink, (sx, sy), r + 1)
                pygame.draw.circle(c, self.enemy_colors.get(e.kind, self.enemy_default), (sx, sy), r)
                if e.hp_frac < 1.0:
                    c.fill(WHITE, (sx - 1, sy - 1, 2, 2))

        for p in snap.players:
            if not p.alive:
                continue
            sx, sy = round(p.x / UNITS_PER_PX) - cam_x, round(p.y / UNITS_PER_PX) - cam_y
            blink = p.invulnerable and (snap.tick // 4) % 2
            body = pygame.Rect(sx - 8, sy - 8, 16, 16)
            c.fill(ink, body)
            c.fill(WHITE if blink else self.player_body, body.inflate(-2, -2))
            bar = pygame.Rect(sx - 9, sy - 13, 18, 3)
            c.fill(ink, bar)
            c.fill(self.hp_color, (bar.x + 1, bar.y + 1, round(16 * p.hp / p.max_hp), 1))

        for pr in snap.projectiles:
            sx, sy = round(pr.x / UNITS_PER_PX) - cam_x, round(pr.y / UNITS_PER_PX) - cam_y
            if 0 <= sx < CANVAS_W and 0 <= sy < CANVAS_H:
                pygame.draw.circle(c, ink, (sx, sy), 3 if pr.crit else 2)
                pygame.draw.circle(c, self.shot_halo, (sx, sy), 2 if pr.crit else 1)
                c.set_at((sx, sy), self.shot_core)

        self._draw_hud(snap, focus)
        if focus.offer and not snap.over:
            self._draw_offer(focus)
        if snap.over:
            self._text("Die Bohne ist gefallen", (CANVAS_W // 2, CANVAS_H // 2 - 12), self.big_font, center=True)
            self._text("R: neuer Lauf   Esc: Ende", (CANVAS_W // 2, CANVAS_H // 2 + 14), center=True)
        return c

    def _draw_hud(self, snap: Snapshot, focus) -> None:
        c, ink = self.canvas, self.ink
        bar = pygame.Rect(0, 0, CANVAS_W, 5)
        c.fill(ink, bar)
        c.fill(self.xp_color, (0, 1, round(CANVAS_W * min(1.0, focus.xp / focus.xp_needed)), 3))
        m, s = divmod(int(snap.time_s), 60)
        hp = f"{int(focus.hp)}/{int(focus.max_hp)}"
        hud = f"{m}:{s:02d}   Welle {snap.wave}   Level {focus.level}   Kills {focus.kills}   HP {hp}"
        if snap.difficulty != 1.0:
            hud += f"   Schwierigkeit {round(snap.difficulty * 100)} %"
        self._text(hud, (6, 9))

    def _draw_offer(self, focus) -> None:
        c, ink = self.canvas, self.ink
        dim = pygame.Surface((CANVAS_W, CANVAS_H), pygame.SRCALPHA)
        dim.fill((*ink, 140))
        c.blit(dim, (0, 0))
        self._text(f"Level {focus.level}! Wähle ein Upgrade", (CANVAS_W // 2, 70), self.big_font, center=True)
        n = len(focus.offer)
        w, h, gap = 180, 150, 14
        x0 = (CANVAS_W - n * w - (n - 1) * gap) // 2
        self.selected = min(self.selected, n - 1)
        for i, (uid, level) in enumerate(focus.offer):
            u = self.upgrades[uid]
            card = pygame.Rect(x0 + i * (w + gap), 100 - (4 if i == self.selected else 0), w, h)
            if i == self.selected:
                c.fill(self.crit_color, card.inflate(8, 8))
            c.fill(ink, card)
            c.fill((255, 250, 240), card.inflate(-4, -4))
            c.fill(self.rarity_colors.get(u.rarity, WHITE), (card.x + 2, card.y + 2, w - 4, 16))
            c.fill(ink, (card.x + 2, card.y + 18, w - 4, 1))
            self._dark_text(f"{i + 1}   {RARITY_NAMES.get(u.rarity, u.rarity)}", (card.x + 8, card.y + 5))
            self._dark_text(u.name, (card.centerx, card.y + 28), center=True)
            self._dark_text(f"Stufe {level} -> {level + 1} / {u.max_level}", (card.centerx, card.y + 44), center=True)
            for j, line in enumerate(_wrap(u.text, self.font, w - 20)):
                self._dark_text(line, (card.x + 10, card.y + 64 + j * 13))
        self._text("1/2/3 oder Pfeile + Enter", (CANVAS_W // 2, 270), center=True)

    def _dark_text(self, text: str, pos: tuple[int, int], center: bool = False) -> None:
        img = self.font.render(text, True, self.ink)
        x, y = pos
        if center:
            x -= img.get_width() // 2
        self.canvas.blit(img, (x, y))

    def _draw_ground(self, c: pygame.Surface, snap: Snapshot, cam_x: int, cam_y: int) -> None:
        arena = pygame.Rect(-cam_x, -cam_y, int(snap.arena_w / UNITS_PER_PX), int(snap.arena_h / UNITS_PER_PX))
        c.fill(self.ground, arena)
        tile = 32 // UNITS_PER_PX
        # Checker detail every other tile so movement is visible.
        view = arena.clip(c.get_rect())
        cols = range((view.left - arena.left) // tile, -(-(view.right - arena.left) // tile))
        for row in range((view.top - arena.top) // tile, -(-(view.bottom - arena.top) // tile)):
            for col in cols:
                if (row + col) % 2:
                    c.fill(self.ground_detail, (arena.left + col * tile, arena.top + row * tile, tile, tile))
        pygame.draw.rect(c, self.ink, arena, 1)

    def _text(self, text: str, pos: tuple[int, int], font=None, center: bool = False) -> None:
        """White text with a dark outline (readability rule, DESIGN.md section 16)."""
        font = font or self.font
        outline = font.render(text, True, self.ink)
        x, y = pos
        if center:
            x, y = x - outline.get_width() // 2, y - outline.get_height() // 2
        for dx, dy in ((-1, 0), (1, 0), (0, -1), (0, 1)):
            self.canvas.blit(outline, (x + dx, y + dy))
        self.canvas.blit(font.render(text, True, WHITE), (x, y))

    def present(self, window: pygame.Surface) -> None:
        """Nearest-neighbour integer upscale, centred with letterboxing."""
        scale = integer_scale(*window.get_size())
        w, h = CANVAS_W * scale, CANVAS_H * scale
        window.fill((0, 0, 0))
        dest = ((window.get_width() - w) // 2, (window.get_height() - h) // 2)
        window.blit(pygame.transform.scale(self.canvas, (w, h)), dest)


def _wrap(text: str, font: pygame.font.Font, width: int) -> list[str]:
    lines, line = [], ""
    for word in text.split():
        trial = f"{line} {word}".strip()
        if font.size(trial)[0] <= width:
            line = trial
        else:
            lines.append(line)
            line = word
    return [*lines, line] if line else lines
