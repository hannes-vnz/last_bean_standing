"""Draws simulation snapshots onto a fixed 640x360 canvas, scaled up by an integer factor.

Coloured shapes only (sprites come in M6). Readability rules from DESIGN.md section 16:
dark outlines, own projectiles warm yellow, XP orbs mint, white text with dark outline.
"""

from __future__ import annotations

import pygame

from ..data.schema import Content
from ..sim.waves import biome_at
from ..sim.world import Snapshot, WorldConfig

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
        self.tile_px = content.balance.tile_px
        self.palettes = {b.id: b.palette for b in content.biomes}
        self.ink = hex_rgb(style.ink)
        self.player_body = hex_rgb(style.player["body"])
        forest = self.palettes["forest"]
        # Placeholder colours until sprites exist (M6): style.json where it has one, biome palettes otherwise.
        self.enemy_colors = {
            "slimeling": hex_rgb(style.enemy["slime"]),
            "batswarm": hex_rgb(style.enemy["bat"]),
            "rootguard": hex_rgb(forest.get("trunk") or "#8a6a4a"),
            "sporeshooter": (212, 138, 224),
            "ildra": (200, 80, 106),
        }
        self.enemy_default = hex_rgb(style.enemy["slime"])
        self.enemy_shot = hex_rgb(style.enemy_projectile["core"])
        self.telegraph = hex_rgb(style.telegraph)
        self.poison = (196, 120, 220)  # violet like enemy projectiles, stands out on green ground
        self.grip = hex_rgb(forest.get("trunk") or "#8a6a4a")
        self.boss_names = {b.id: b.name for b in content.bosses}
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
        self.set_arena(WorldConfig.from_content(content))
        # Outside the arena: ink darkened, so the ink border and outlines stay visible.
        self.void = tuple(v * 3 // 5 for v in self.ink)
        self.font = pygame.font.Font(None, 16)
        self.big_font = pygame.font.Font(None, 32)

    def draw(self, snap: Snapshot, focus_player: int = 0, debug: str | None = None) -> pygame.Surface:
        c = self.canvas
        c.fill(self.void)
        focus = next((p for p in snap.players if p.player_id == focus_player), snap.players[0])
        # Camera: top-left corner of the view in canvas pixels, rounded to whole pixels.
        cam_x = round(focus.x / UNITS_PER_PX) - CANVAS_W // 2
        cam_y = round(focus.y / UNITS_PER_PX) - CANVAS_H // 2

        self._draw_ground(c, cam_x, cam_y)
        ink = self.ink

        for o in snap.orbs:
            sx, sy = round(o.x / UNITS_PER_PX) - cam_x, round(o.y / UNITS_PER_PX) - cam_y
            if 0 <= sx < CANVAS_W and 0 <= sy < CANVAS_H:
                c.fill(ink, (sx - 2, sy - 1, 5, 3))
                c.fill(ink, (sx - 1, sy - 2, 3, 5))
                c.fill(self.xp_color, (sx - 1, sy, 3, 1))
                c.fill(self.xp_color, (sx, sy - 1, 1, 3))

        self._draw_hazards(snap, cam_x, cam_y)
        for cx, cy in snap.chests:
            sx, sy = round(cx / UNITS_PER_PX) - cam_x, round(cy / UNITS_PER_PX) - cam_y
            c.fill(ink, (sx - 6, sy - 5, 13, 11))
            c.fill(self.crit_color, (sx - 5, sy - 4, 11, 9))
            c.fill(ink, (sx - 5, sy - 1, 11, 1))
            c.fill(WHITE, (sx - 1, sy - 2, 3, 3))

        for e in snap.enemies:
            sx, sy = round(e.x / UNITS_PER_PX) - cam_x, round(e.y / UNITS_PER_PX) - cam_y
            r = max(2, round(e.radius / UNITS_PER_PX))
            if -r - 3 <= sx < CANVAS_W + r + 3 and -r - 3 <= sy < CANVAS_H + r + 3:
                if e.elite:  # golden halo so elites stand out in a crowd
                    pygame.draw.circle(c, self.crit_color, (sx, sy), r + 3)
                pygame.draw.circle(c, ink, (sx, sy), r + 1)
                pygame.draw.circle(c, self.enemy_colors.get(e.kind, self.enemy_default), (sx, sy), r)
                if e.boss:
                    pygame.draw.circle(c, WHITE, (sx - r // 3, sy - r // 3), max(2, r // 4))
                if e.shield_frac > 0:
                    pygame.draw.circle(c, WHITE, (sx, sy), r + 1, 1)
                if e.hp_frac < 1.0 and not e.boss:
                    c.fill(WHITE, (sx - 1, sy - 1, 2, 2))

        for s in snap.enemy_shots:
            sx, sy = round(s.x / UNITS_PER_PX) - cam_x, round(s.y / UNITS_PER_PX) - cam_y
            if not (0 <= sx < CANVAS_W and 0 <= sy < CANVAS_H):
                continue
            if s.lobbed:  # spore in flight: small, the landing warning is drawn with the hazards
                pygame.draw.circle(c, ink, (sx, sy), 3)
                pygame.draw.circle(c, self.poison, (sx, sy), 2)
            else:
                pygame.draw.circle(c, ink, (sx, sy), 3)
                pygame.draw.circle(c, self.enemy_shot, (sx, sy), 2)

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
        if snap.boss_bar:
            self._draw_boss_bar(snap.boss_bar)
        if debug:
            self.text(debug, (6, CANVAS_H - 16))
        if focus.offer and not snap.over:
            self._draw_offer(focus)
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
        self.text(hud, (6, 9))

    def _draw_hazards(self, snap: Snapshot, cam_x: int, cam_y: int) -> None:
        """Warnings are coral and blink at 2 Hz (DESIGN.md section 16); active zones are soft and translucent."""
        c, ink = self.canvas, self.ink
        blink_on = (snap.tick // 15) % 2 == 0
        overlay = None
        for s in snap.enemy_shots:
            if s.lobbed:
                tx, ty = round(s.tx / UNITS_PER_PX) - cam_x, round(s.ty / UNITS_PER_PX) - cam_y
                pygame.draw.circle(c, self.telegraph if blink_on else WHITE, (tx, ty), 20 // UNITS_PER_PX + 8, 1)
        for h in snap.hazards:
            sx, sy = round(h.x / UNITS_PER_PX) - cam_x, round(h.y / UNITS_PER_PX) - cam_y
            r = round(h.radius / UNITS_PER_PX)
            if sx + r < 0 or sx - r >= CANVAS_W or sy + r < 0 or sy - r >= CANVAS_H:
                continue
            if not h.armed:
                pygame.draw.circle(c, self.telegraph if blink_on else WHITE, (sx, sy), r, 2)
                continue
            if overlay is None:
                overlay = pygame.Surface((CANVAS_W, CANVAS_H), pygame.SRCALPHA)
            color = self.poison if h.kind == "poison" else self.grip if h.kind == "grip" else self.telegraph
            pygame.draw.circle(overlay, (*color, 150), (sx, sy), r)
            pygame.draw.circle(overlay, (*ink, 230), (sx, sy), r, 2)
        if overlay is not None:
            c.blit(overlay, (0, 0))

    def _draw_boss_bar(self, bar) -> None:
        c, ink = self.canvas, self.ink
        w = 300
        rect = pygame.Rect((CANVAS_W - w) // 2, 30, w, 8)
        c.fill(ink, rect.inflate(2, 2))
        c.fill((90, 60, 100), rect)
        c.fill(self.enemy_colors.get(bar.boss, self.telegraph), (rect.x, rect.y, round(w * bar.hp_frac), rect.h))
        self.text(self.boss_names.get(bar.boss, bar.boss), (CANVAS_W // 2, 46), center=True)

    def _draw_offer(self, focus) -> None:
        c, ink = self.canvas, self.ink
        dim = pygame.Surface((CANVAS_W, CANVAS_H), pygame.SRCALPHA)
        dim.fill((*ink, 140))
        c.blit(dim, (0, 0))
        title = (
            "Truhe! Wähle ein Upgrade" if focus.offer_source == "chest" else f"Level {focus.level}! Wähle ein Upgrade"
        )
        self.text(title, (CANVAS_W // 2, 70), self.big_font, center=True)
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
            self.dark_text(f"{i + 1}   {RARITY_NAMES.get(u.rarity, u.rarity)}", (card.x + 8, card.y + 5))
            self.dark_text(u.name, (card.centerx, card.y + 28), center=True)
            self.dark_text(f"Stufe {level} -> {level + 1} / {u.max_level}", (card.centerx, card.y + 44), center=True)
            for j, line in enumerate(_wrap(u.text, self.font, w - 20)):
                self.dark_text(line, (card.x + 10, card.y + 64 + j * 13))
        self.text("1/2/3 oder Pfeile + Enter", (CANVAS_W // 2, 270), center=True)

    def dark_text(self, text: str, pos: tuple[int, int], center: bool = False) -> None:
        img = self.font.render(text, True, self.ink)
        x, y = pos
        if center:
            x -= img.get_width() // 2
        self.canvas.blit(img, (x, y))

    def set_arena(self, config: WorldConfig) -> None:
        """Pre-render the static map (biome grounds, obstacles) once; each frame blits the visible part."""
        tile = self.tile_px // UNITS_PER_PX
        w, h = int(config.arena_w / UNITS_PER_PX), int(config.arena_h / UNITS_PER_PX)
        surf = pygame.Surface((w, h))
        for row in range(h // tile):
            for col in range(w // tile):
                cx, cy = (col + 0.5) * tile * UNITS_PER_PX, (row + 0.5) * tile * UNITS_PER_PX
                pal = self.palettes.get(biome_at(config.biomes, cx, cy) or "plaza", self.palettes["plaza"])
                color = pal["detail"] if (row + col) % 2 else pal["ground"]
                surf.fill(hex_rgb(color), (col * tile, row * tile, tile, tile))
        for o in config.obstacles:
            self._draw_obstacle(surf, o)
        pygame.draw.rect(surf, self.ink, surf.get_rect(), 1)
        self.map_surface = surf

    def _draw_obstacle(self, surf: pygame.Surface, o) -> None:
        x, y = round(o.x / UNITS_PER_PX), round(o.y / UNITS_PER_PX)
        r = max(3, round(o.radius / UNITS_PER_PX) + 1)
        pal = self.palettes.get("forest", {})
        canopy = hex_rgb(pal.get("tree") or "#5aa05a")
        trunk = hex_rgb(pal.get("trunk") or "#8a6a4a")
        ink = self.ink
        # Trunk below, round canopy with a light spot (light from the top left), dark outline.
        surf.fill(ink, (x - 2, y + r - 4, 5, 7))
        surf.fill(trunk, (x - 1, y + r - 3, 3, 5))
        pygame.draw.circle(surf, ink, (x, y - 1), r + 1)
        pygame.draw.circle(surf, canopy, (x, y - 1), r)
        light = tuple(min(255, v + 40) for v in canopy)
        pygame.draw.circle(surf, light, (x - r // 3, y - 1 - r // 3), max(1, r // 3))

    def _draw_ground(self, c: pygame.Surface, cam_x: int, cam_y: int) -> None:
        c.blit(self.map_surface, (-cam_x, -cam_y))

    def text(self, text: str, pos: tuple[int, int], font=None, center: bool = False) -> None:
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
