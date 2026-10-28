"""Draws simulation snapshots onto a fixed 640x360 canvas, scaled up by an integer factor.

Coloured shapes only (sprites come in M6). Readability rules from DESIGN.md section 16:
dark outlines, own projectiles warm yellow, XP orbs mint, white text with dark outline.
"""

from __future__ import annotations

from collections import OrderedDict

import pygame

from ..data.schema import Content
from ..sim.tuning import BOSS_RADIUS
from ..sim.waves import biome_at
from ..sim.world import Snapshot, WorldConfig
from .effects import Effects
from .sprites import SpriteBank

CANVAS_W, CANVAS_H = 640, 360
# World units per canvas pixel (DESIGN.md section 16: 1 tile = 32 units = 16 px).
UNITS_PER_PX = 2
WHITE = (255, 255, 255)
CHUNK_PX = 256  # ground is rendered in square chunks of this many canvas pixels
MAX_CHUNKS = 40  # chunks kept in memory (about 10 MB)
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
    def __init__(self, content: Content, size: tuple[int, int] = (CANVAS_W, CANVAS_H)) -> None:
        self.w, self.h = size
        self.canvas = pygame.Surface(size)
        self.card_rects: list[pygame.Rect] = []
        self.offer_buttons: list[tuple[pygame.Rect, str]] = []
        self.banish_mode = False
        self.ability_rect = pygame.Rect(0, 0, 0, 0)
        self.pause_rect = pygame.Rect(0, 0, 0, 0)
        self.touch = False  # touch device: bigger buttons, no keyboard hints
        self.hud_bottom = 24
        self._dest, self._scale = (0, 0), 1
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
        self.sprites = SpriteBank()
        self.character_sprite = "ranger"
        self.base_radius = {m.id: float(m.radius) for m in content.mobs}
        self.base_radius.update({b.id: BOSS_RADIUS for b in content.bosses})
        self._last_x: dict[int, float] = {}
        self._flipped: dict[int, bool] = {}
        self._number_cache: dict = {}
        self.set_arena(WorldConfig.from_content(content))
        # Outside the arena: ink darkened, so the ink border and outlines stay visible.
        self.void = tuple(v * 3 // 5 for v in self.ink)
        self.font = pygame.font.Font(None, 16)
        self.big_font = pygame.font.Font(None, 32)
        self.mid_font = pygame.font.Font(None, 22)

    def draw(
        self, snap: Snapshot, focus_player: int = 0, debug: str | None = None, effects: Effects | None = None
    ) -> pygame.Surface:
        c = self.canvas
        c.fill(self.void)
        focus = next((p for p in snap.players if p.player_id == focus_player), snap.players[0])
        # Camera: top-left corner of the view in canvas pixels, rounded to whole pixels.
        cam_x = round(focus.x / UNITS_PER_PX) - self.w // 2
        cam_y = round(focus.y / UNITS_PER_PX) - self.h // 2
        if effects:
            dx, dy = effects.shake()
            cam_x, cam_y = cam_x + dx, cam_y + dy
        flash = effects.flash if effects else {}

        self._draw_ground(c, cam_x, cam_y)
        ink = self.ink

        for px, py in snap.pots:
            sx, sy = round(px / UNITS_PER_PX) - cam_x, round(py / UNITS_PER_PX) - cam_y
            if -8 <= sx < self.w + 8 and -10 <= sy < self.h + 10:
                self._draw_pot(sx, sy)
        for o in snap.orbs:
            sx, sy = round(o.x / UNITS_PER_PX) - cam_x, round(o.y / UNITS_PER_PX) - cam_y
            if 0 <= sx < self.w and 0 <= sy < self.h:
                if o.kind == "seeds":  # golden seed
                    c.fill(ink, (sx - 2, sy - 3, 5, 7))
                    c.fill(self.crit_color, (sx - 1, sy - 2, 3, 5))
                    c.set_at((sx, sy - 2), WHITE)
                elif o.kind == "heal":  # pink heart-ish blob
                    c.fill(ink, (sx - 3, sy - 2, 7, 6))
                    c.fill(self.hp_color, (sx - 2, sy - 1, 5, 4))
                    c.fill(WHITE, (sx - 1, sy - 1, 1, 1))
                else:
                    c.fill(ink, (sx - 2, sy - 1, 5, 3))
                    c.fill(ink, (sx - 1, sy - 2, 3, 5))
                    c.fill(self.xp_color, (sx - 1, sy, 3, 1))
                    c.fill(self.xp_color, (sx, sy - 1, 1, 3))

        self._draw_hazards(snap, cam_x, cam_y)
        for kind, kx, ky in snap.pickups:
            sx, sy = round(kx / UNITS_PER_PX) - cam_x, round(ky / UNITS_PER_PX) - cam_y
            if kind == "magnet" and -8 <= sx < self.w + 8 and -8 <= sy < self.h + 8:
                bob = 1 if (snap.tick // 15) % 2 else 0  # little float so it catches the eye
                self._draw_magnet(sx, sy - bob)
        for cx, cy, kind in snap.chests:
            sx, sy = round(cx / UNITS_PER_PX) - cam_x, round(cy / UNITS_PER_PX) - cam_y
            if -20 <= sx < self.w + 20 and -20 <= sy < self.h + 20:
                self._draw_chest(sx, sy, kind, snap.chest_price, focus.seeds)

        for e in snap.enemies:
            sx, sy = round(e.x / UNITS_PER_PX) - cam_x, round(e.y / UNITS_PER_PX) - cam_y
            r = max(2, round(e.radius / UNITS_PER_PX))
            if -r - 16 <= sx < self.w + r + 16 and -r - 16 <= sy < self.h + r + 16:
                if e.elite:  # golden halo so elites stand out in a crowd
                    pygame.draw.circle(c, self.crit_color, (sx, sy), r + 4)
                flip = self._facing(e.eid, e.x)
                img = self.sprites.get(e.kind, self._sprite_scale(e), flip, e.eid in flash)
                if img is not None:
                    c.blit(img, (sx - img.get_width() // 2, sy - img.get_height() // 2))
                else:
                    pygame.draw.circle(c, ink, (sx, sy), r + 1)
                    color = WHITE if e.eid in flash else self.enemy_colors.get(e.kind, self.enemy_default)
                    pygame.draw.circle(c, color, (sx, sy), r)
                if e.shield_frac > 0:
                    pygame.draw.circle(c, WHITE, (sx, sy), r + 2, 1)

        for s in snap.enemy_shots:
            sx, sy = round(s.x / UNITS_PER_PX) - cam_x, round(s.y / UNITS_PER_PX) - cam_y
            if not (0 <= sx < self.w and 0 <= sy < self.h):
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
            blink = bool(p.invulnerable and (snap.tick // 4) % 2)
            bob = 1 if (not p.standing and (snap.tick // 8) % 2) else 0  # little hop while walking
            img = self.sprites.get(self.character_sprite, 1.0, self._facing(-1 - p.player_id, p.x), blink)
            if img is not None:
                c.blit(img, (sx - img.get_width() // 2, sy - img.get_height() // 2 - bob))
            else:
                body = pygame.Rect(sx - 8, sy - 8, 16, 16)
                c.fill(ink, body)
                c.fill(WHITE if blink else self.player_body, body.inflate(-2, -2))
            bar = pygame.Rect(sx - 9, sy - 15, 18, 3)
            c.fill(ink, bar)
            c.fill(self.hp_color, (bar.x + 1, bar.y + 1, round(16 * p.hp / p.max_hp), 1))

        for pr in snap.projectiles:
            sx, sy = round(pr.x / UNITS_PER_PX) - cam_x, round(pr.y / UNITS_PER_PX) - cam_y
            if 0 <= sx < self.w and 0 <= sy < self.h:
                pygame.draw.circle(c, ink, (sx, sy), 3 if pr.crit else 2)
                pygame.draw.circle(c, self.shot_halo, (sx, sy), 2 if pr.crit else 1)
                c.set_at((sx, sy), self.shot_core)

        if effects:
            self._draw_effects(effects, cam_x, cam_y)
        self._draw_boss_arrow(snap, cam_x, cam_y)
        self._draw_hud(snap, focus)
        self._draw_minimap(snap, focus)
        if effects and effects.banner:
            self.text(effects.banner[0], (self.w // 2, 70), self.big_font, center=True)
        if effects and effects.toast:  # item found: name and effect under the HUD
            for i, line in enumerate(_wrap(effects.toast[0], self.font, self.w - 30)):
                self.text(line, (self.w // 2, self.hud_bottom + 70 + i * 14), center=True)
        if snap.boss_bar:
            self._draw_boss_bar(snap.boss_bar)
        if debug:
            self.text(debug, (6, self.h - 16))
        if focus.offer and not snap.over:
            self._draw_offer(focus)
        return c

    def _draw_hud(self, snap: Snapshot, focus) -> None:
        c, ink = self.canvas, self.ink
        c.fill(ink, (0, 0, self.w, 5))
        c.fill(self.xp_color, (0, 1, round(self.w * min(1.0, focus.xp / focus.xp_needed)), 3))
        m, s = divmod(int(snap.time_s), 60)
        parts = [f"{m}:{s:02d}", f"Welle {snap.wave}", f"Level {focus.level}", f"Kills {focus.kills}",
                 f"HP {int(focus.hp)}/{int(focus.max_hp)}", f"Samen {focus.seeds}"]  # fmt: skip
        if snap.difficulty != 1.0:
            parts.append(f"Schwierigkeit {round(snap.difficulty * 100)} %")
        line, y = "", 9
        for part in parts:  # wrap onto a second line on narrow (portrait) screens
            trial = f"{line}   {part}" if line else part
            if line and self.font.size(trial)[0] > self.w - 50:
                self.text(line, (6, y))
                line, y = part, y + 14
            else:
                line = trial
        self.text(line, (6, y))
        self.hud_bottom = y + 14
        # Pause button (touch has no Esc key) and ability button, both big enough for a thumb on touch.
        size = 22 if self.touch else 0
        self.pause_rect = pygame.Rect(self.w - size - 6, 8, size, size)
        if self.touch:
            c.fill(ink, self.pause_rect.inflate(4, 4))
            c.fill((90, 60, 100), self.pause_rect)
            c.fill(WHITE, (self.pause_rect.x + 6, self.pause_rect.y + 5, 3, 12))
            c.fill(WHITE, (self.pause_rect.x + 13, self.pause_rect.y + 5, 3, 12))
        side = 46 if self.touch else 28
        box = pygame.Rect(self.w - side - 10, self.h - side - 10, side, side)
        self.ability_rect = box
        c.fill(ink, box.inflate(4, 4))
        c.fill((90, 60, 100), box)
        filled = round(box.h * min(1.0, focus.ability_ready))
        c.fill(self.crit_color if focus.ability_ready >= 1.0 else self.shot_halo,
               (box.x, box.bottom - filled, box.w, filled))  # fmt: skip
        # Arrow-burst icon so the button reads as "Pfeilhagel" without text.
        cx, cy = box.center
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1), (1, 1), (-1, -1), (1, -1), (-1, 1)):
            c.fill(ink, (cx + dx * side // 5, cy + dy * side // 5, 3, 3))
        c.fill(WHITE, (cx - 2, cy - 2, 5, 5))
        if not self.touch:
            self.text("Leer", (box.centerx, box.y - 9), center=True)

    def _draw_minimap(self, snap: Snapshot, focus) -> None:
        """Small map in the top right: biomes, you (white), elites (gold), the boss (coral)."""
        size = self.minimap_size()
        key = ("minimap", size)
        img = self._number_cache.get(key)
        if img is None:
            img = pygame.transform.scale(self.overview, (size, size))
            self._number_cache[key] = img
        top = self.pause_rect.bottom + 6 if self.touch else 8
        box = pygame.Rect(self.w - size - 6, top, size, size)
        c = self.canvas
        c.fill(self.ink, box.inflate(4, 4))
        c.blit(img, box)
        sx, sy = size / snap.arena_w, size / snap.arena_h
        for chx, chy, kind in snap.chests:
            dot = self.crit_color if kind != "map" else (150, 90, 50)
            c.set_at((box.x + int(chx * sx), box.y + int(chy * sy)), dot)
        for e in snap.enemies:
            if e.boss or e.elite:
                color = self.telegraph if e.boss else self.crit_color
                c.fill(self.ink, (box.x + int(e.x * sx) - 2, box.y + int(e.y * sy) - 2, 5, 5))
                c.fill(color, (box.x + int(e.x * sx) - 1, box.y + int(e.y * sy) - 1, 3, 3))
        view_w, view_h = max(2, int(self.w * UNITS_PER_PX * sx)), max(2, int(self.h * UNITS_PER_PX * sy))
        px, py = box.x + int(focus.x * sx), box.y + int(focus.y * sy)
        pygame.draw.rect(c, WHITE, (px - view_w // 2, py - view_h // 2, view_w, view_h), 1)
        c.fill(self.ink, (px - 2, py - 2, 5, 5))
        c.fill(WHITE, (px - 1, py - 1, 3, 3))

    def _draw_boss_arrow(self, snap: Snapshot, cam_x: int, cam_y: int) -> None:
        """Coral arrow at the screen edge pointing to a boss that is off screen."""
        boss = next((e for e in snap.enemies if e.boss), None)
        if boss is None:
            return
        bx, by = boss.x / UNITS_PER_PX - cam_x, boss.y / UNITS_PER_PX - cam_y
        if 0 <= bx < self.w and 0 <= by < self.h:
            return
        cx, cy = self.w / 2, self.h / 2
        dx, dy = bx - cx, by - cy
        # Scale the direction so the arrow sits just inside the screen edge.
        t = min((self.w / 2 - 22) / abs(dx) if dx else 1e9, (self.h / 2 - 22) / abs(dy) if dy else 1e9)
        ax, ay = cx + dx * t, cy + dy * t
        ay = max(ay, self.hud_bottom + 40)  # stay below the HUD lines and the boss bar
        if ay < self.minimap_size() + 50:
            ax = min(ax, self.w - self.minimap_size() - 24)  # and left of the minimap
        length = (dx * dx + dy * dy) ** 0.5 or 1.0
        ux, uy = dx / length, dy / length
        tip = (ax + ux * 10, ay + uy * 10)
        left = (ax - uy * 7 - ux * 6, ay + ux * 7 - uy * 6)
        right = (ax + uy * 7 - ux * 6, ay - ux * 7 - uy * 6)
        pygame.draw.polygon(self.canvas, self.ink, [tip, left, right])
        pygame.draw.polygon(self.canvas, self.telegraph, [tip, left, right], 0)
        pygame.draw.polygon(self.canvas, self.ink, [tip, left, right], 2)

    def draw_stick(self, stick) -> None:
        """Floating touch joystick: translucent base where the thumb landed, knob under the thumb."""
        from ..ui.touch import RADIUS

        overlay = pygame.Surface((self.w, self.h), pygame.SRCALPHA)
        ox, oy = round(stick.ox), round(stick.oy)
        kx, ky = (round(v) for v in stick.knob())
        pygame.draw.circle(overlay, (*WHITE, 50), (ox, oy), round(RADIUS))
        pygame.draw.circle(overlay, (*self.ink, 140), (ox, oy), round(RADIUS), 2)
        pygame.draw.circle(overlay, (*WHITE, 150), (kx, ky), 13)
        pygame.draw.circle(overlay, (*self.ink, 200), (kx, ky), 13, 2)
        self.canvas.blit(overlay, (0, 0))

    def _draw_chest(self, sx: int, sy: int, kind: str, price: int, seeds: int) -> None:
        """Seed chest: wooden box; elite/boss chests golden. Map chests carry their price (green if affordable)."""
        c, ink = self.canvas, self.ink
        body = self.crit_color if kind != "map" else (196, 140, 90)
        c.fill(ink, (sx - 7, sy - 6, 15, 12))
        c.fill(body, (sx - 6, sy - 5, 13, 10))
        c.fill(tuple(max(0, v - 50) for v in body), (sx - 6, sy - 1, 13, 1))
        c.fill(WHITE if kind != "map" else self.crit_color, (sx - 1, sy - 2, 3, 3))
        if kind == "map":
            label = f"{price}"
            color = self.xp_color if seeds >= price else WHITE
            img = self._number_cache.get(("price", label, color))
            if img is None:
                img = self._outlined(label, self.font, color)
                self._number_cache[("price", label, color)] = img
            c.blit(img, (sx - img.get_width() // 2, sy - 20))

    def _draw_pot(self, sx: int, sy: int) -> None:
        """Clay pot: walk into it to break it."""
        c, ink = self.canvas, self.ink
        clay = (226, 150, 120)
        c.fill(ink, (sx - 5, sy - 6, 11, 12))
        c.fill(clay, (sx - 4, sy - 4, 9, 9))
        c.fill(ink, (sx - 3, sy - 7, 7, 3))
        c.fill(tuple(min(255, v + 30) for v in clay), (sx - 2, sy - 6, 5, 1))
        c.fill(WHITE, (sx - 3, sy - 3, 1, 2))

    def _draw_magnet(self, sx: int, sy: int) -> None:
        """Horseshoe magnet: coral bow with white tips and dark outline (no sprite yet)."""
        c, ink = self.canvas, self.ink
        pygame.draw.circle(c, ink, (sx, sy), 7)
        pygame.draw.circle(c, self.telegraph, (sx, sy), 6)
        pygame.draw.circle(c, ink, (sx, sy + 1), 3)
        c.fill(ink, (sx - 3, sy + 1, 7, 7))
        c.fill(WHITE, (sx - 6, sy + 2, 3, 3))
        c.fill(WHITE, (sx + 4, sy + 2, 3, 3))

    def _facing(self, key: int, x: float) -> bool:
        """True when the entity last moved left (sprites face right)."""
        last = self._last_x.get(key)
        self._last_x[key] = x
        flipped = self._flipped.get(key, False)
        if last is not None and abs(x - last) > 0.05:
            flipped = x < last
            self._flipped[key] = flipped
        return flipped

    def _sprite_scale(self, e) -> float:
        """Elites are drawn bigger by their size factor; base sprites match the base radius."""
        base = self.base_radius.get(e.kind)
        return e.radius / base if base else 1.0

    def _draw_effects(self, fx: Effects, cam_x: int, cam_y: int) -> None:
        c = self.canvas
        for g in fx.rings:
            sx, sy = round(g.x / UNITS_PER_PX) - cam_x, round(g.y / UNITS_PER_PX) - cam_y
            pygame.draw.circle(c, g.color, (sx, sy), max(1, round(g.radius / UNITS_PER_PX)), 2)
        for p in fx.particles:
            sx, sy = round(p.x / UNITS_PER_PX) - cam_x, round(p.y / UNITS_PER_PX) - cam_y
            if 0 <= sx < self.w and 0 <= sy < self.h:
                size = p.size if p.life > p.max_life // 3 else 1
                c.fill(p.color, (sx, sy, size, size))
        for t in fx.texts:
            sx, sy = round(t.x / UNITS_PER_PX) - cam_x, round(t.y / UNITS_PER_PX) - cam_y
            if 0 <= sx < self.w and 0 <= sy < self.h:
                font = self.font if not t.big else self.mid_font
                img = self._number_cache.get((t.text, t.color, t.big))
                if img is None:
                    img = self._outlined(t.text, font, t.color)
                    if len(self._number_cache) > 500:
                        self._number_cache.clear()
                    self._number_cache[(t.text, t.color, t.big)] = img
                c.blit(img, (sx - img.get_width() // 2, sy - img.get_height() // 2))

    def _outlined(self, text: str, font, color) -> pygame.Surface:
        inner = font.render(text, True, color)
        outline = font.render(text, True, self.ink)
        surf = pygame.Surface((inner.get_width() + 2, inner.get_height() + 2), pygame.SRCALPHA)
        for dx, dy in ((0, 1), (2, 1), (1, 0), (1, 2)):
            surf.blit(outline, (dx, dy))
        surf.blit(inner, (1, 1))
        return surf

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
            if sx + r < 0 or sx - r >= self.w or sy + r < 0 or sy - r >= self.h:
                continue
            if not h.armed:
                pygame.draw.circle(c, self.telegraph if blink_on else WHITE, (sx, sy), r, 2)
                continue
            if overlay is None:
                overlay = pygame.Surface((self.w, self.h), pygame.SRCALPHA)
            color = self.poison if h.kind == "poison" else self.grip if h.kind == "grip" else self.telegraph
            pygame.draw.circle(overlay, (*color, 150), (sx, sy), r)
            pygame.draw.circle(overlay, (*ink, 230), (sx, sy), r, 2)
        if overlay is not None:
            c.blit(overlay, (0, 0))

    def _draw_boss_bar(self, bar) -> None:
        """Below the HUD lines and left of the minimap, so nothing overlaps on narrow screens."""
        c, ink = self.canvas, self.ink
        free = self.w - self.minimap_size() - 24  # room left of the minimap
        w = min(300, free)
        rect = pygame.Rect(6 + (free - w) // 2, self.hud_bottom + 6, w, 8)
        c.fill(ink, rect.inflate(2, 2))
        c.fill((90, 60, 100), rect)
        c.fill(self.enemy_colors.get(bar.boss, self.telegraph), (rect.x, rect.y, round(w * bar.hp_frac), rect.h))
        self.text(self.boss_names.get(bar.boss, bar.boss), (rect.centerx, rect.bottom + 10), center=True)

    def minimap_size(self) -> int:
        return 64 if min(self.w, self.h) < 340 else 80

    def _draw_offer(self, focus) -> None:
        c, ink = self.canvas, self.ink
        dim = pygame.Surface((self.w, self.h), pygame.SRCALPHA)
        dim.fill((*ink, 140))
        c.blit(dim, (0, 0))
        title = "Truhe! Wähle ein Upgrade" if focus.offer_source == "chest" else f"Level {focus.level}!"
        n = len(focus.offer)
        self.selected = min(self.selected, n - 1)
        wide = self.w > self.h  # landscape: cards side by side; portrait: stacked
        if wide:
            gap = 14
            w, h = min(180, (self.w - 20 - (n - 1) * gap) // n), 150
            top = max(80, (self.h - h) // 2 - 10)
            x0 = (self.w - n * w - (n - 1) * gap) // 2
            rects = [pygame.Rect(x0 + i * (w + gap), top, w, h) for i in range(n)]
        else:  # phone in portrait: cards stacked, full width
            w, h, gap = min(340, self.w - 20), 92, 10
            top = max(70, (self.h - n * h - (n - 1) * gap) // 2)
            rects = [pygame.Rect((self.w - w) // 2, top + i * (h + gap), w, h) for i in range(n)]
        self.text(title, (self.w // 2, top - 30), self.big_font, center=True)
        self.card_rects = rects
        for i, (uid, level) in enumerate(focus.offer):
            u = self.upgrades[uid]
            card = rects[i].move(0, -4 if i == self.selected and not self.touch else 0)
            if i == self.selected and not self.touch:
                c.fill(self.crit_color, card.inflate(8, 8))
            c.fill(ink, card)
            c.fill((255, 250, 240), card.inflate(-4, -4))
            c.fill(self.rarity_colors.get(u.rarity, WHITE), (card.x + 2, card.y + 2, card.w - 4, 16))
            c.fill(ink, (card.x + 2, card.y + 18, card.w - 4, 1))
            label = RARITY_NAMES.get(u.rarity, u.rarity)
            self.dark_text(label if self.touch else f"{i + 1}   {label}", (card.x + 8, card.y + 5))
            stage = f"Stufe {level} -> {level + 1} / {u.max_level}"
            if wide:
                self.dark_text(u.name, (card.centerx, card.y + 28), center=True)
                self.dark_text(stage, (card.centerx, card.y + 44), center=True)
                for j, line in enumerate(_wrap(u.text, self.font, card.w - 20)):
                    self.dark_text(line, (card.x + 10, card.y + 64 + j * 13))
            else:
                self.dark_text(u.name, (card.x + 10, card.y + 26))
                img = self.font.render(stage, True, ink)
                c.blit(img, (card.right - 10 - img.get_width(), card.y + 26))
                for j, line in enumerate(_wrap(u.text, self.font, card.w - 20)[:3]):
                    self.dark_text(line, (card.x + 10, card.y + 44 + j * 13))
        if self.banish_mode:
            for rect in rects:
                pygame.draw.rect(c, self.telegraph, rect.inflate(6, 6), 3)
        # Reroll and banish (limited per run): buttons below the cards.
        y = rects[-1].bottom + 12
        bw = min(140, (self.w - 30) // 2)
        self.offer_buttons = []
        for i, (label, action, left) in enumerate([("Neu würfeln", "reroll", focus.rerolls),
                                                    ("Verbannen", "banish", focus.banishes)]):  # fmt: skip
            rect = pygame.Rect(self.w // 2 - bw - 5 + i * (bw + 10), y, bw, 26)
            active = left > 0
            c.fill(ink, rect.inflate(4, 4))
            c.fill(self.telegraph if action == "banish" and self.banish_mode else
                   (255, 250, 240) if active else (150, 140, 160), rect)  # fmt: skip
            self.dark_text(f"{label} ({left})", (rect.centerx, rect.y + 7), center=True)
            if active:
                self.offer_buttons.append((rect, action))
        if self.banish_mode:
            hint = "Welche Karte soll verschwinden?"
        else:
            hint = "Karte antippen" if self.touch else "1/2/3 oder Pfeile + Enter · R neu · B verbannen"
        self.text(hint, (self.w // 2, y + 42), center=True)

    def dark_text(self, text: str, pos: tuple[int, int], center: bool = False) -> None:
        img = self.font.render(text, True, self.ink)
        x, y = pos
        if center:
            x -= img.get_width() // 2
        self.canvas.blit(img, (x, y))

    def set_arena(self, config: WorldConfig) -> None:
        """Prepare the static map. The ground is drawn in chunks on demand (the 200 x 200 tile map would be
        a 3200 x 3200 pixel image, too much for phones); a small overview image feeds the minimap."""
        self.arena_px = (int(config.arena_w / UNITS_PER_PX), int(config.arena_h / UNITS_PER_PX))
        self.arena_biomes = config.biomes
        self._chunks: OrderedDict[tuple[int, int], pygame.Surface] = OrderedDict()
        self._chunk_obstacles: dict[tuple[int, int], list] = {}
        reach = 16  # obstacles are drawn a little larger than their radius
        for o in config.obstacles:
            x, y = o.x / UNITS_PER_PX, o.y / UNITS_PER_PX
            for cx in {int((x - reach) // CHUNK_PX), int((x + reach) // CHUNK_PX)}:
                for cy in {int((y - reach) // CHUNK_PX), int((y + reach) // CHUNK_PX)}:
                    self._chunk_obstacles.setdefault((cx, cy), []).append(o)
        self._build_overview(config)

    def _chunk(self, cx: int, cy: int) -> pygame.Surface:
        key = (cx, cy)
        surf = self._chunks.get(key)
        if surf is not None:
            self._chunks.move_to_end(key)
            return surf
        tile = self.tile_px // UNITS_PER_PX
        surf = pygame.Surface((CHUNK_PX, CHUNK_PX))
        surf.fill(self.void)
        x0, y0 = cx * CHUNK_PX, cy * CHUNK_PX
        aw, ah = self.arena_px
        for ty in range(y0 // tile, min(ah, y0 + CHUNK_PX) // tile):
            for tx in range(x0 // tile, min(aw, x0 + CHUNK_PX) // tile):
                if tx < 0 or ty < 0:
                    continue
                wx, wy = (tx + 0.5) * tile * UNITS_PER_PX, (ty + 0.5) * tile * UNITS_PER_PX
                pal = self.palettes.get(biome_at(self.arena_biomes, wx, wy) or "plaza", self.palettes["plaza"])
                color = pal["detail"] if (tx + ty) % 2 else pal["ground"]
                surf.fill(hex_rgb(color), (tx * tile - x0, ty * tile - y0, tile, tile))
        for o in self._chunk_obstacles.get(key, ()):
            self._draw_obstacle(surf, o, -x0, -y0)
        pygame.draw.rect(surf, self.ink, (-x0, -y0, aw, ah), 1)  # arena border where it crosses this chunk
        self._chunks[key] = surf
        if len(self._chunks) > MAX_CHUNKS:
            self._chunks.popitem(last=False)
        return surf

    def _build_overview(self, config: WorldConfig) -> None:
        """One pixel per tile: biome colours and darker dots for obstacles."""
        tiles_w = int(config.arena_w // self.tile_px)
        tiles_h = int(config.arena_h // self.tile_px)
        surf = pygame.Surface((tiles_w, tiles_h))
        for b in sorted(config.biomes, key=lambda a: -a.w * a.h):  # big areas first, the clearing on top
            surf.fill(hex_rgb(self.palettes[b.id]["ground"]),
                      (b.x // self.tile_px, b.y // self.tile_px, b.w // self.tile_px, b.h // self.tile_px))  # fmt: skip
        dark = hex_rgb(self.palettes["forest"].get("tree") or "#5aa05a")
        for o in config.obstacles:
            surf.set_at((int(o.x // self.tile_px), int(o.y // self.tile_px)), dark)
        self.overview = surf

    def _draw_obstacle(self, surf: pygame.Surface, o, ox: int = 0, oy: int = 0) -> None:
        x, y = round(o.x / UNITS_PER_PX) + ox, round(o.y / UNITS_PER_PX) + oy
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
        for cy in range(cam_y // CHUNK_PX, (cam_y + self.h) // CHUNK_PX + 1):
            for cx in range(cam_x // CHUNK_PX, (cam_x + self.w) // CHUNK_PX + 1):
                c.blit(self._chunk(cx, cy), (cx * CHUNK_PX - cam_x, cy * CHUNK_PX - cam_y))

    def draw_ground_at(self, wx: float, wy: float) -> None:
        """Menus: the map around a world position as background."""
        cam_x = round(wx / UNITS_PER_PX) - self.w // 2
        cam_y = round(wy / UNITS_PER_PX) - self.h // 2
        self.canvas.fill(self.void)
        self._draw_ground(self.canvas, cam_x, cam_y)

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

    def resize(self, w: int, h: int) -> None:
        """Change the logical canvas size (portrait or landscape); the world view grows with it."""
        if (w, h) != (self.w, self.h):
            self.w, self.h = w, h
            self.canvas = pygame.Surface((w, h))

    def present(self, window: pygame.Surface) -> None:
        """Nearest-neighbour integer upscale, centred with letterboxing."""
        scale = max(1, min(window.get_width() // self.w, window.get_height() // self.h))
        w, h = self.w * scale, self.h * scale
        window.fill(self.void)
        dest = ((window.get_width() - w) // 2, (window.get_height() - h) // 2)
        self._dest, self._scale = dest, scale
        if scale == 1:
            window.blit(self.canvas, dest)
        else:
            window.blit(pygame.transform.scale(self.canvas, (w, h)), dest)

    def window_to_canvas(self, x: float, y: float) -> tuple[int, int]:
        """Window pixel (mouse, finger) to canvas pixel."""
        return int((x - self._dest[0]) // self._scale), int((y - self._dest[1]) // self._scale)


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


def effect_palette(r: Renderer) -> tuple[dict, dict]:
    """Colours the effects use, taken from the renderer's style colours."""
    colors = {
        "white": WHITE,
        "crit": r.crit_color,
        "shot_core": r.shot_core,
        "shot_halo": r.shot_halo,
        "telegraph": r.telegraph,
        "poison": r.poison,
        "leaf": hex_rgb(r.palettes["forest"].get("tree") or "#5aa05a"),
    }
    return colors, dict(r.enemy_colors)
