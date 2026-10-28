"""Draws simulation snapshots onto a fixed 640x360 canvas, scaled up by an integer factor.

Coloured shapes only (sprites come in M6). Readability rules from DESIGN.md section 16:
dark outlines, own projectiles warm yellow, XP orbs mint, white text with dark outline.
"""

from __future__ import annotations

import contextlib
import math
import random
from collections import OrderedDict

import pygame

from ..data.schema import Content
from ..sim.tuning import BOSS_RADIUS
from ..sim.weapons import WEAPON_PREFIX
from ..sim.world import Snapshot, WorldConfig
from .effects import Effects
from .icons import SIZE as ICON_SIZE
from .icons import IconBank
from .sprites import ASSETS_DIR, SpriteBank

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
        # Colours for particles, the boss bar and the fallback shapes when a sprite is missing.
        self.enemy_colors = {
            "slug": (217, 179, 106), "aphid": (155, 226, 127), "snail": (201, 141, 106), "mold": (183, 166, 224),
            "potato_beetle": (255, 212, 94), "toxic_carrot": (255, 154, 74), "spray_cucumber": (111, 191, 90),
            "pest_tomato": (255, 107, 107), "vole": (165, 138, 122), "spray_shroom": (200, 240, 106),
            "snail_queen": (208, 122, 160), "beetle_king": (232, 130, 58), "reaper": (90, 70, 120),
        }  # fmt: skip
        self.enemy_default = hex_rgb(style.enemy["slime"])
        self.enemy_shot = hex_rgb(style.enemy_projectile["core"])
        self.telegraph = hex_rgb(style.telegraph)
        self.poison = (196, 120, 220)  # violet like enemy projectiles, stands out on green ground
        self.grip = (230, 210, 240)  # slime trail: pale and glossy
        self.boss_names = {b.id: b.name for b in content.bosses}
        self.shot_core = hex_rgb(style.player_projectile["core"])
        self.shot_halo = hex_rgb(style.player_projectile["halo"])
        self.hp_color = hex_rgb(style.heal_orb)
        self.crit_color = hex_rgb(style.crit_text)
        self.xp_color = hex_rgb(style.xp_orb)
        self.upgrades = {u.id: u for u in content.upgrades}
        self.stat_labels = content.stat_labels
        self.tier_mult = {k: float(v) for k, v in content.balance.raw.get("card_tier_mult", {}).items()}
        self.weapons = {w.id: w for w in content.weapons}
        self.items = {i.id: i for i in content.items}
        self.item_names = {i.id: i.name for i in content.items}
        self.weapon_max_level = content.weapon_max_level
        self.pollen = (250, 226, 140)  # warm pastel yellow: own area damage reads as "ours"
        self.pumpkin = (240, 150, 70)
        # Rarity colours (Paket F2): green, blue, purple, red, gold, like the usual loot colours.
        self.rarity_colors = {
            "common": (126, 217, 87),
            "uncommon": (90, 180, 255),
            "rare": (176, 122, 255),
            "epic": (255, 95, 125),
            "legendary": (255, 200, 61),
        }
        self.selected = 0
        self.icons = IconBank(content, self.ink, self.rarity_colors)
        self.tiles, self.decor = _load_tiles({b.id for b in content.biomes})
        self._motes: list[list[float]] = []  # floating pollen, petals or spores (screen space, purely visual)
        self.frame = 0  # counts drawn frames, for animations that run while the game is paused
        self._offer_seen: tuple = ()
        self._offer_frame = 0
        self._build_seen: dict[str, int] = {}  # HUD icon -> level shown last frame
        self._build_pop: dict[str, int] = {}  # HUD icon -> frame it last changed
        self.sprites = SpriteBank()
        self.character_sprite = "ranger"
        self.base_radius = {m.id: float(m.radius) for m in content.mobs}
        self.base_radius.update({b.id: BOSS_RADIUS for b in content.bosses})
        self._last_x: dict[int, float] = {}
        self._flipped: dict[int, bool] = {}
        self._number_cache: dict = {}
        self._arena_obstacles = None
        self.set_arena(WorldConfig.from_content(content))
        # Outside the arena: ink darkened, so the ink border and outlines stay visible.
        self.void = tuple(v * 3 // 5 for v in self.ink)
        self.font = pygame.font.Font(None, 16)
        self.tiny_font = pygame.font.Font(None, 12)
        self.big_font = pygame.font.Font(None, 32)
        self.mid_font = pygame.font.Font(None, 22)

    def draw(
        self, snap: Snapshot, focus_player: int = 0, debug: str | None = None, effects: Effects | None = None
    ) -> pygame.Surface:
        c = self.canvas
        c.fill(self.void)
        self.frame += 1
        if snap.obstacles is not self._arena_obstacles and snap.biome:
            self.set_stage(snap.arena_w, snap.arena_h, snap.biome, snap.obstacles)
        focus = next((p for p in snap.players if p.player_id == focus_player), snap.players[0])
        # Camera: top-left corner of the view in canvas pixels, rounded to whole pixels.
        cam_x = round(focus.x / UNITS_PER_PX) - self.w // 2
        cam_y = round(focus.y / UNITS_PER_PX) - self.h // 2
        if effects:
            dx, dy = effects.shake()
            cam_x, cam_y = cam_x + dx, cam_y + dy
        flash = effects.flash if effects else {}

        self._draw_ground(c, cam_x, cam_y)
        self._draw_motes(cam_x, cam_y)
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
        self._draw_weapon_ground(snap, cam_x, cam_y)
        if snap.gate is not None:
            self._draw_gate(snap, cam_x, cam_y)
        for e in snap.enemies:  # dash warning lines (coral, like every enemy warning)
            if e.aim is not None:
                sx, sy = round(e.x / UNITS_PER_PX) - cam_x, round(e.y / UNITS_PER_PX) - cam_y
                ex, ey = sx + round(e.aim[0] * 110), sy + round(e.aim[1] * 110)
                color = self.telegraph if (snap.tick // 6) % 2 else WHITE
                pygame.draw.line(c, color, (sx, sy), (ex, ey), 3 if e.boss else 2)
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
                if img is not None and e.status == "frozen":  # frozen solid: icy blue
                    img = img.copy()
                    img.fill((90, 160, 255, 0), special_flags=pygame.BLEND_RGBA_ADD)
                if img is not None:
                    c.blit(img, (sx - img.get_width() // 2, sy - img.get_height() // 2))
                else:
                    pygame.draw.circle(c, ink, (sx, sy), r + 1)
                    color = WHITE if e.eid in flash else self.enemy_colors.get(e.kind, self.enemy_default)
                    pygame.draw.circle(c, color, (sx, sy), r)
                if e.shield_frac > 0:
                    pygame.draw.circle(c, WHITE, (sx, sy), r + 2, 1)
                if e.status:  # burning, poisoned or chilled: a small coloured mark above the head
                    c.fill(STATUS_COLORS[e.status], (sx - 1, sy - r - 5, 3, 3))

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
            if p.inferno:  # Mira's ring of fire
                r = round(180 / UNITS_PER_PX)
                for k in range(16):
                    a = k * 0.3927 + snap.tick * 0.08
                    fx_, fy_ = sx + round(math.cos(a) * r), sy + round(math.sin(a) * r)
                    c.fill(self.ink, (fx_ - 2, fy_ - 3, 5, 6))
                    c.fill((255, 140, 60) if k % 2 else (255, 212, 94), (fx_ - 1, fy_ - 2, 3, 4))
            if p.shield >= 1:  # shield bubble ("Bollwerk", "Notschild")
                pygame.draw.circle(c, (180, 220, 255), (sx, sy), 13, 1)
            if p.storm and (snap.tick // 5) % 2:  # Vex's storm: a little cloud above him
                c.fill(self.ink, (sx - 7, sy - 25, 15, 6))
                c.fill((154, 143, 184), (sx - 6, sy - 24, 13, 4))
            bar = pygame.Rect(sx - 9, sy - 15, 18, 3)
            c.fill(ink, bar)
            c.fill(self.hp_color, (bar.x + 1, bar.y + 1, round(16 * p.hp / p.max_hp), 1))

        for pr in snap.projectiles:
            sx, sy = round(pr.x / UNITS_PER_PX) - cam_x, round(pr.y / UNITS_PER_PX) - cam_y
            if 0 <= sx < self.w and 0 <= sy < self.h:
                if pr.weapon == "dragonfly":  # blue body, flickering wings
                    wing = (snap.tick // 3) % 2
                    c.fill(ink, (sx - 2, sy - 2, 5, 5))
                    c.fill((90, 180, 255), (sx - 1, sy - 1, 3, 3))
                    c.fill(WHITE, (sx - 3, sy - 2 - wing, 2, 1))
                    c.fill(WHITE, (sx + 2, sy - 2 - wing, 2, 1))
                    continue
                if pr.weapon == "leaf_boomerang":  # spinning maple leaf
                    spin = (snap.tick // 3) % 2
                    c.fill(ink, (sx - 4, sy - 4, 9, 9) if spin else (sx - 3, sy - 5, 7, 11))
                    c.fill((255, 154, 60), (sx - 3, sy - 3, 7, 7) if spin else (sx - 2, sy - 4, 5, 9))
                    c.set_at((sx, sy), (192, 96, 42))
                    continue
                pygame.draw.circle(c, ink, (sx, sy), 3 if pr.crit else 2)
                halo = WHITE if pr.weapon == "dandelion" else self.shot_halo  # fluffy seeds, still yellow-cored
                pygame.draw.circle(c, halo, (sx, sy), 2 if pr.crit else 1)
                c.set_at((sx, sy), (167, 224, 138) if pr.weapon == "cactus" else self.shot_core)
        self._draw_weapon_air(snap, cam_x, cam_y)

        if effects:
            self._draw_effects(effects, cam_x, cam_y)
        self._draw_boss_arrow(snap, cam_x, cam_y)
        if snap.gate is not None:
            self._draw_edge_arrow(snap.gate[0], snap.gate[1], cam_x, cam_y, (126, 217, 87))
        self._draw_hud(snap, focus)
        self._draw_minimap(snap, focus)
        if effects and effects.banner:
            y = max(70, self.hud_bottom + 34)
            self.text(effects.banner[0], (self.w // 2, y), self.big_font, center=True)
            if effects.subtitle and effects.subtitle[0]:
                self.text(effects.subtitle[0], (self.w // 2, y + 22), center=True)
        if effects and effects.toast:  # item found: name and effect under the HUD
            for i, line in enumerate(_wrap(effects.toast[0], self.font, self.w - 30)):
                self.text(line, (self.w // 2, self.hud_bottom + 70 + i * 14), center=True)
        if snap.boss_bar:
            self._draw_boss_bar(snap.boss_bar)
        if debug:
            self.text(debug, (6, self.h - 16))
        if focus.offer and not snap.over:
            self._draw_offer(focus)
        if effects and effects.reel is not None:
            self._draw_reel(effects.reel)
        return c

    def _draw_reel(self, reel) -> None:
        """The chest's lucky draw: dimmed screen, a window with spinning item icons, then the find."""
        c, ink = self.canvas, self.ink
        dim = pygame.Surface((self.w, self.h), pygame.SRCALPHA)
        dim.fill((*ink, 150))
        c.blit(dim, (0, 0))
        cell = ICON_SIZE * 2 + 6
        win = pygame.Rect(0, 0, min(self.w - 20, cell * 7), ICON_SIZE * 2 + 10)
        win.center = (self.w // 2, self.h // 2)
        color = self.rarity_colors.get(reel.rarity, WHITE) if reel.landed else self.crit_color
        if reel.landed and RARITY_ORDER.index(reel.rarity) >= 2:
            self._draw_rays(win.center, max(self.w, self.h) * 0.6, color, RARITY_ORDER.index(reel.rarity))
        c.fill(color, win.inflate(8, 8))
        c.fill(ink, win.inflate(4, 4))
        c.fill((58, 42, 74), win)
        clip = c.get_clip()
        c.set_clip(win)
        pos = reel.position()
        first = int(pos) - 4
        for k in range(first, first + 10):
            if 0 <= k < len(reel.strip):
                x = win.centerx + round((k - pos) * cell) - ICON_SIZE
                c.blit(self.icons.get("item:" + reel.strip[k], scale=2), (x, win.centery - ICON_SIZE))
        c.set_clip(clip)
        pygame.draw.rect(c, WHITE, (win.centerx - ICON_SIZE - 3, win.y - 2, ICON_SIZE * 2 + 6, win.h + 4), 2)
        self.text("Saatkiste!", (self.w // 2, win.y - 22), self.big_font, center=True)
        if reel.landed:
            name = self.item_names.get(reel.item_id, reel.item_id)
            label = RARITY_NAMES.get(reel.rarity, reel.rarity)
            self.canvas.blit(
                *(lambda img: (img, img.get_rect(center=(self.w // 2, win.bottom + 18))))(
                    self._outlined(f"{name} ({label})", self.mid_font, color)
                )
            )
            if reel.frame % 10 < 5 and RARITY_ORDER.index(reel.rarity) >= 2:
                pygame.draw.rect(c, WHITE, win.inflate(14, 14), 2)
        else:
            self.text("Antippen zum Überspringen" if self.touch else "Taste zum Überspringen",
                      (self.w // 2, win.bottom + 16), center=True)  # fmt: skip

    def _draw_hud(self, snap: Snapshot, focus) -> None:
        c, ink = self.canvas, self.ink
        c.fill(ink, (0, 0, self.w, 5))
        c.fill(self.xp_color, (0, 1, round(self.w * min(1.0, focus.xp / focus.xp_needed)), 3))
        left = snap.stage_duration_s - snap.stage_time_s
        if snap.flood:  # counting up: how long the Plagenflut has lasted
            m, s = divmod(int(-left), 60)
            clock = f"FLUT {snap.flood_wave} +{m}:{s:02d} x{snap.reward_mult:.1f}".replace(".", ",")
        else:
            m, s = divmod(int(left + 0.999), 60)
            clock = f"{m}:{s:02d}"
        parts = [f"Beet {snap.stage}", clock, f"Level {focus.level}", f"Kills {focus.kills}",
                 f"HP {int(focus.hp)}/{int(focus.max_hp)}" + (f" +{int(focus.shield)}" if focus.shield >= 1 else ""),
                 f"Samen {focus.seeds}"]  # fmt: skip
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
        self._draw_build(focus)
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

    def _draw_motes(self, cam_x: int, cam_y: int) -> None:
        """Pollen (Saatbeet), petals (Gemüsebeet) or spores (Kompost) drifting slowly over the ground.
        They live in world space (they stay put when you walk) and wrap around the view."""
        color, count = MOTES.get(self.biome, ((255, 255, 255), 0))
        if len(self._motes) != count:
            rnd = random.Random(7)
            self._motes = [[rnd.uniform(0, 1), rnd.uniform(0, 1), rnd.uniform(0, 6.28)] for _ in range(count)]
        span_w, span_h = self.w + 40, self.h + 40
        c = self.canvas
        for m in self._motes:
            m[2] += 0.03
            m[0] = (m[0] + 0.0004) % 1.0
            m[1] = (m[1] - 0.0002) % 1.0
            x = int((m[0] * span_w * 3 - cam_x) % span_w) - 20 + round(math.sin(m[2]) * 4)
            y = int((m[1] * span_h * 3 - cam_y) % span_h) - 20
            c.fill(color, (x, y, 2, 2))
            if int(m[2] * 3) % 7 == 0:  # occasional glint
                c.fill((255, 255, 255), (x, y, 1, 1))

    def _draw_build(self, focus) -> None:
        """Icon rows under the HUD (weapons, books, items) with level or count. Something new or levelled
        pops up big and settles, with a ring in its rarity colour and a small "+1" or "NEU"."""
        tiers = dict(focus.card_tiers)
        if not focus.weapons and not focus.upgrades and not focus.items:
            self._build_seen.clear()  # a new run: nothing to compare with
        rows = [
            [("weapon:start", 1, "common")]
            + [("weapon:" + wid, lvl, tiers.get("weapon:" + wid)) for wid, lvl in focus.weapons],
            [(uid, lvl, tiers.get(uid)) for uid, lvl in focus.upgrades],
            [("item:" + iid, n, None) for iid, n in focus.items],
        ]
        step = ICON_SIZE + 2
        cols = max(4, (self.w - self.minimap_size() - 20) // step)
        y = self.hud_bottom + 2
        c = self.canvas
        for entries in rows:
            if not entries:
                continue
            for k, (key, n, tier) in enumerate(entries[: cols * 2]):
                row, col = divmod(k, cols)
                x, yy = 6 + col * step, y + row * step
                if self._build_seen.get(key) != n:  # new or levelled since the last frame
                    if key in self._build_seen or self.frame > 2:
                        self._build_pop[key] = self.frame
                    self._build_seen[key] = n
                icon = self.icons.get(key, tier)
                age = self.frame - self._build_pop.get(key, -999)
                if age < POP_FRAMES:
                    k2 = 1.0 + 0.8 * (1.0 - age / POP_FRAMES) ** 2
                    size = round(ICON_SIZE * k2)
                    color = self.rarity_colors.get(tier or "common", WHITE)
                    pygame.draw.rect(c, color, (x - age // 2, yy - age // 2, ICON_SIZE + age, ICON_SIZE + age), 1)
                    c.blit(pygame.transform.scale(icon, (size, size)), (x - (size - ICON_SIZE) // 2,
                                                                         yy - (size - ICON_SIZE) // 2))  # fmt: skip
                    label = "NEU" if n == 1 else "+1"
                    self.canvas.blit(self._outlined(label, self.tiny_font, color), (x + 2, yy - 10 - age // 4))
                else:
                    c.blit(icon, (x, yy))
                if n > 1:
                    img = self._number_cache.get(("lvl", n))
                    if img is None:
                        img = self._outlined(str(n), self.tiny_font, WHITE)
                        self._number_cache[("lvl", n)] = img
                    c.blit(img, (x + ICON_SIZE - img.get_width() + 1, yy + ICON_SIZE - img.get_height() + 2))
            y += step * ((min(len(entries), cols * 2) + cols - 1) // cols)
        self.hud_bottom = y

    def _draw_gate(self, snap: Snapshot, cam_x: int, cam_y: int) -> None:
        """Gartentor: wooden arch with a glowing green opening and flowers, bobbing gently."""
        c, ink = self.canvas, self.ink
        sx, sy = round(snap.gate[0] / UNITS_PER_PX) - cam_x, round(snap.gate[1] / UNITS_PER_PX) - cam_y
        if not (-30 <= sx < self.w + 30 and -40 <= sy < self.h + 40):
            return
        pulse = (self.frame // 8) % 4
        glow = pygame.Surface((44, 44), pygame.SRCALPHA)
        pygame.draw.circle(glow, (126, 217, 87, 70 + pulse * 15), (22, 22), 18 + pulse)
        c.blit(glow, (sx - 22, sy - 26))
        wood, light_wood = (160, 112, 72), (196, 146, 98)
        for dx in (-12, 9):  # posts
            c.fill(ink, (sx + dx - 1, sy - 22, 5, 26))
            c.fill(wood, (sx + dx, sy - 21, 3, 24))
        pygame.draw.arc(c, ink, (sx - 14, sy - 34, 28, 26), 0, 3.15, 5)
        pygame.draw.arc(c, light_wood, (sx - 13, sy - 33, 26, 24), 0, 3.15, 3)
        c.fill((160, 240, 140), (sx - 8, sy - 18, 16, 20))
        c.fill((220, 255, 210), (sx - 4 + pulse % 2, sy - 14, 3, 12))
        for fx, fy, col in ((-13, -26, (255, 159, 192)), (12, -27, (255, 212, 94)), (0, -36, (255, 255, 255))):
            c.fill(ink, (sx + fx - 1, sy + fy - 1, 4, 4))
            c.fill(col, (sx + fx, sy + fy, 2, 2))
        self.text("Gartentor", (sx, sy + 12), center=True)

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
        if snap.gate is not None:
            gx, gy = box.x + int(snap.gate[0] * sx), box.y + int(snap.gate[1] * sy)
            c.fill(self.ink, (gx - 2, gy - 2, 5, 5))
            c.fill((126, 217, 87), (gx - 1, gy - 1, 3, 3))
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
        if boss is not None:
            self._draw_edge_arrow(boss.x, boss.y, cam_x, cam_y, self.telegraph)

    def _draw_edge_arrow(self, wx: float, wy: float, cam_x: int, cam_y: int, color) -> None:
        bx, by = wx / UNITS_PER_PX - cam_x, wy / UNITS_PER_PX - cam_y
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
        pygame.draw.polygon(self.canvas, color, [tip, left, right], 0)
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
        for x, y, x2, y2, width, life in fx.beams:  # light beam: white core, golden glow, thinning out
            a = (round(x / UNITS_PER_PX) - cam_x, round(y / UNITS_PER_PX) - cam_y)
            b = (round(x2 / UNITS_PER_PX) - cam_x, round(y2 / UNITS_PER_PX) - cam_y)
            w = max(1, round(width / UNITS_PER_PX * life / 10))
            pygame.draw.line(c, self.ink, a, b, w + 4)
            pygame.draw.line(c, self.crit_color, a, b, w + 2)
            pygame.draw.line(c, WHITE, a, b, max(1, w - 1))
        for x, y, dx, dy, radius, arc, life in fx.sweeps:  # sickle: a silver arc that fades
            cx, cy = round(x / UNITS_PER_PX) - cam_x, round(y / UNITS_PER_PX) - cam_y
            r = round(radius / UNITS_PER_PX)
            mid = math.atan2(dy, dx)
            half = math.radians(arc) / 2
            pts = [(cx + math.cos(mid - half + k * 2 * half / 8) * r, cy + math.sin(mid - half + k * 2 * half / 8) * r)
                   for k in range(9)]  # fmt: skip
            if len(pts) > 1:
                pygame.draw.lines(c, self.ink, False, pts, 4 if life > 4 else 3)
                pygame.draw.lines(c, (223, 231, 242) if life > 4 else (154, 168, 192), False, pts, 2)
        for b in fx.bolts:  # lightning: jagged yellow-white line with a dark edge
            pts = [(round(x / UNITS_PER_PX) - cam_x, round(y / UNITS_PER_PX) - cam_y) for x, y in b.points]
            jag = []
            for (x0, y0), (x1, y1) in zip(pts, pts[1:], strict=False):
                mx, my = (x0 + x1) // 2 + (3 if b.life % 2 else -3), (y0 + y1) // 2 + (-3 if b.life % 2 else 3)
                jag += [(x0, y0), (mx, my)]
            jag.append(pts[-1])
            pygame.draw.lines(c, self.ink, False, jag, 4)
            pygame.draw.lines(c, self.shot_core, False, jag, 2)
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

    def _draw_weapon_ground(self, snap: Snapshot, cam_x: int, cam_y: int) -> None:
        """Pollen clouds and the landing marks of own bombs (yellow, unlike the coral enemy warnings)."""
        c = self.canvas
        if snap.auras:
            overlay = pygame.Surface((self.w, self.h), pygame.SRCALPHA)
            for _, ax, ay, radius in snap.auras:
                sx, sy = round(ax / UNITS_PER_PX) - cam_x, round(ay / UNITS_PER_PX) - cam_y
                r = round(radius / UNITS_PER_PX)
                pygame.draw.circle(overlay, (*self.pollen, 60), (sx, sy), r)
                pygame.draw.circle(overlay, (*self.pollen, 150), (sx, sy), r, 1)
                for k in range(8):  # drifting pollen specks
                    a = (snap.tick * 0.02 + k * 0.785) % 6.283
                    px = sx + round(math.cos(a) * r * (0.35 + 0.08 * (k % 4)))
                    py = sy + round(math.sin(a) * r * (0.35 + 0.08 * (k % 4)))
                    overlay.fill((*self.pollen, 220), (px, py, 2, 2))
            c.blit(overlay, (0, 0))
        ink = self.ink
        for _, zx, zy, radius, life in snap.zones:  # nettle patches: a ring of little nettles
            sx, sy = round(zx / UNITS_PER_PX) - cam_x, round(zy / UNITS_PER_PX) - cam_y
            r = max(3, round(radius / UNITS_PER_PX))
            if -r <= sx < self.w + r and -r <= sy < self.h + r:
                fade = min(1.0, life)
                for k in range(6):
                    a = k * 1.047 + (zx % 7)
                    px, py = sx + round(math.cos(a) * r * 0.6), sy + round(math.sin(a) * r * 0.6)
                    c.fill(ink, (px - 1, py - 3, 3, 4))
                    c.fill((95, 184, 90) if fade > 0.4 else (150, 190, 120), (px, py - 2, 1, 3))
        for _, mx, my in snap.mines:  # garlic cloves
            sx, sy = round(mx / UNITS_PER_PX) - cam_x, round(my / UNITS_PER_PX) - cam_y
            if 0 <= sx < self.w and 0 <= sy < self.h:
                c.fill(ink, (sx - 3, sy - 3, 7, 7))
                c.fill((255, 246, 234), (sx - 2, sy - 2, 5, 5))
                c.fill((167, 224, 138), (sx, sy - 5, 1, 2))
        for _, tx_, ty_, life in snap.turrets:  # cacti, blinking shortly before they wither
            sx, sy = round(tx_ / UNITS_PER_PX) - cam_x, round(ty_ / UNITS_PER_PX) - cam_y
            if not (-10 <= sx < self.w + 10 and -14 <= sy < self.h + 14) or (life < 2 and (snap.tick // 6) % 2):
                continue
            c.fill(ink, (sx - 3, sy - 11, 7, 14))
            c.fill(ink, (sx - 7, sy - 7, 5, 6))
            c.fill(ink, (sx + 3, sy - 9, 5, 6))
            green = (111, 191, 90)
            c.fill(green, (sx - 2, sy - 10, 5, 12))
            c.fill(green, (sx - 6, sy - 6, 3, 4))
            c.fill(green, (sx + 4, sy - 8, 3, 4))
            c.fill((217, 128, 90), (sx - 3, sy + 1, 7, 3))
            c.set_at((sx, sy - 11), (255, 159, 192))
        blink_on = (snap.tick // 10) % 2 == 0
        for b in snap.bombs:
            tx, ty = round(b.tx / UNITS_PER_PX) - cam_x, round(b.ty / UNITS_PER_PX) - cam_y
            r = max(2, round(b.radius / UNITS_PER_PX))
            if -r <= tx < self.w + r and -r <= ty < self.h + r:
                pygame.draw.circle(c, self.pollen if blink_on else WHITE, (tx, ty), max(2, round(r * b.progress)), 1)

    def _draw_weapon_air(self, snap: Snapshot, cam_x: int, cam_y: int) -> None:
        """Bees and pumpkins in flight, drawn above everything on the ground."""
        c, ink = self.canvas, self.ink
        wing = (snap.tick // 4) % 2
        for _, bx, by in snap.orbiters:
            sx, sy = round(bx / UNITS_PER_PX) - cam_x, round(by / UNITS_PER_PX) - cam_y
            if 0 <= sx < self.w and 0 <= sy < self.h:
                c.fill(WHITE, (sx - 2, sy - 3 - wing, 2, 2))  # wings flap
                c.fill(WHITE, (sx + 1, sy - 4 + wing, 2, 2))
                c.fill(ink, (sx - 3, sy - 2, 7, 5))
                c.fill(self.shot_core, (sx - 2, sy - 1, 5, 3))
                c.fill(ink, (sx, sy - 1, 1, 3))  # stripe
        for b in snap.bombs:
            sx, sy = round(b.x / UNITS_PER_PX) - cam_x, round(b.y / UNITS_PER_PX) - cam_y
            sy -= round(4 * 18 * b.progress * (1.0 - b.progress))  # arc, 18 px high
            if 0 <= sx < self.w and 0 <= sy < self.h:
                pygame.draw.circle(c, ink, (sx, sy), 4)
                pygame.draw.circle(c, self.pumpkin, (sx, sy), 3)
                c.fill((110, 170, 90), (sx, sy - 4, 1, 2))  # stalk

    def _card_surface(self, uid: str, level: int, tier: str, size: tuple[int, int], wide: bool, i: int):
        """Face of a level-up card: dark panel, thick rarity frame, big picture, name, level and stat lines."""
        w, h = size
        key = ("card", uid, level, tier, size, self.touch, i)
        surf = self._number_cache.get(key)
        if surf is not None:
            return surf
        name, _, u, max_level = self._card(uid)
        weapon = uid.startswith(WEAPON_PREFIX)
        color = self.rarity_colors.get(tier, WHITE)
        ink = self.ink
        surf = pygame.Surface(size)
        surf.fill(ink)
        surf.fill(color, (1, 1, w - 2, h - 2))
        surf.fill(tuple(min(255, v + 70) for v in color), (1, 1, w - 2, 1))
        panel = pygame.Rect(4, 4, w - 8, h - 8)
        base = tuple((v + d * 4) // 5 for v, d in zip(color, (58, 42, 74), strict=True))
        surf.fill(base, panel)
        surf.fill(tuple(min(255, v + 14) for v in base), (panel.x, panel.y, panel.w, 22))  # lighter head band
        big = self.icons.get(uid, tier, scale=2)
        surf.blit(big, (panel.x + 4, panel.y + 4))
        tx = panel.x + 4 + big.get_width() + 6
        old, self.canvas = self.canvas, surf  # reuse the text helpers on the card surface
        try:
            self.text(name if self.font.size(name)[0] < panel.right - tx - 4 else name[:16] + "…", (tx, panel.y + 4))
            label = RARITY_NAMES.get(tier, tier) + (f" · {u.style or 'Waffe'}" if weapon else "")
            if not self.touch:
                label = f"{i + 1}  {label}"
            lbl = self._outlined(label, self.font, color)
            surf.blit(lbl, (tx - 1, panel.y + 18))
            if level == 0:
                badge = pygame.Rect(tx, panel.y + 33, 40, 12)
                surf.fill(ink, badge.inflate(2, 2))
                surf.fill(self.crit_color, badge)
                img = self.tiny_font.render("NEU!", True, ink)
                surf.blit(img, img.get_rect(center=badge.center))
            else:
                self.text(f"Lv {level} > {level + 1}" + (f" / {max_level}" if not weapon else ""), (tx, panel.y + 32))
            y = panel.y + big.get_height() + 10
            for line in self._card_lines(uid, u, level, tier, weapon):
                for part in _wrap(line, self.font, panel.w - 12):
                    if y > panel.bottom - 12:
                        break
                    self.text(part, (panel.x + 6, y))
                    y += 13
        finally:
            self.canvas = old
        self._number_cache[key] = surf
        return surf

    def _draw_rays(self, center: tuple[int, int], length: float, color, rank: int) -> None:
        """Slowly turning light rays behind epic and legendary cards (and rare ones, fainter)."""
        overlay = pygame.Surface((self.w, self.h), pygame.SRCALPHA)
        n, turn = 8 + 2 * rank, self.frame * 0.01
        alpha = 40 + 25 * (rank - 2)
        cx, cy = center
        for k in range(n):
            a = turn + k * 6.283 / n
            b = a + 0.12
            pts = [(cx, cy), (cx + math.cos(a) * length, cy + math.sin(a) * length),
                   (cx + math.cos(b) * length, cy + math.sin(b) * length)]  # fmt: skip
            pygame.draw.polygon(overlay, (*color, alpha), pts)
        self.canvas.blit(overlay, (0, 0))

    def _card_lines(self, uid: str, u, level: int, tier: str, weapon: bool) -> list[str]:
        """Stat lines of a card (Megabonk style: one change per line)."""
        text = self._card_text(uid, u, level, tier, weapon)
        if weapon:
            return [text]
        return [part.strip().rstrip(".") for part in text.split(", ")]  # ", " only: "+3,9 %" is one number

    def _card_text(self, uid: str, u, level: int, tier: str, weapon: bool) -> str:
        """Card text with the values of this card's rarity (Paket F: rarer cards are worth more)."""
        mult = self.tier_mult.get(tier, 1.0)
        if weapon:
            base = u.text if level == 0 else u.level_text
            return base if mult == 1.0 else f"{base} +{round((mult - 1) * 100)} % Waffenschaden."
        parts = []
        for e in u.effects:
            stat, per = e.get("stat"), e.get("per_level")
            if stat in self.stat_labels and per is not None:
                parts.append(self.stat_labels[stat].replace("{v}", _signed(per * mult, stat)))
        return ", ".join(parts) + "." if parts else u.text

    def _card(self, uid: str):
        """(name, rarity, definition, max level) of an offered card: upgrade or weapon."""
        if uid.startswith(WEAPON_PREFIX):
            w = self.weapons[uid[len(WEAPON_PREFIX) :]]
            return w.name, w.rarity, w, self.weapon_max_level
        u = self.upgrades[uid]
        return u.name, u.rarity, u, u.max_level

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
        if focus.offer != self._offer_seen:  # new cards: start the reveal animation
            self._offer_seen, self._offer_frame = focus.offer, self.frame
        age = self.frame - self._offer_frame
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
        for i, (uid, level, tier) in enumerate(focus.offer):
            t = (age - i * 6) / 14.0  # cards flip in one after another
            if t <= 0:
                continue
            card = rects[i].move(0, -4 if i == self.selected and not self.touch else 0)
            rank = RARITY_ORDER.index(tier) if tier in RARITY_ORDER else 0
            color = self.rarity_colors.get(tier, WHITE)
            if t >= 1.0 and rank >= 2:  # rare and better: light rays turn slowly behind the card
                self._draw_rays(card.center, max(card.w, card.h) * (0.7 + 0.1 * rank), color, rank)
            surf = self._card_surface(uid, level, tier, card.size, wide, i)
            if t < 1.0:  # flip: the back (rarity colour) narrows, then the front widens
                f = abs(1.0 - 2.0 * t)
                if t < 0.5:
                    surf = pygame.Surface(card.size)
                    surf.fill(ink)
                    surf.fill(color, surf.get_rect().inflate(-6, -6))
                    q = self.big_font.render("?", True, WHITE)
                    surf.blit(q, q.get_rect(center=surf.get_rect().center))
                w_now = max(2, round(card.w * f))
                surf = pygame.transform.scale(surf, (w_now, card.h))
                c.blit(surf, (card.centerx - w_now // 2, card.y))
                continue
            if i == self.selected and not self.touch:
                c.fill(self.crit_color, card.inflate(8, 8))
            c.blit(surf, card)
            since = age - i * 6 - 14  # frames since this card turned face up
            if since < 16 and rank >= 1:  # reveal flash and a ring in the rarity colour
                flash = pygame.Surface(card.size, pygame.SRCALPHA)
                flash.fill((255, 255, 255, max(0, 160 - since * 10)))
                c.blit(flash, card)
                pygame.draw.rect(c, color, card.inflate(since * 2, since * 2), 2)
            if rank == 4:  # legendary: a sweep of light runs over the card
                sweep = (self.frame * 4) % (card.w + 40) - 20
                band = pygame.Surface((10, card.h - 8), pygame.SRCALPHA)
                band.fill((255, 240, 160, 70))
                c.blit(band, (card.x + max(4, min(card.w - 14, sweep)), card.y + 4))
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

    def set_arena(self, config: WorldConfig, stage: int = 0) -> None:
        st = config.stages[stage]
        self.set_stage(config.arena_w, config.arena_h, st.biome, st.obstacles)

    def set_stage(self, arena_w: float, arena_h: float, biome: str, obstacles: tuple) -> None:
        """Prepare the static map of a garden bed. The ground is drawn in chunks on demand (a whole map
        would be a large image, too much for phones); a small overview image feeds the minimap."""
        self._arena_obstacles = obstacles
        self.arena_px = (int(arena_w / UNITS_PER_PX), int(arena_h / UNITS_PER_PX))
        self.biome = biome if biome in self.palettes else next(iter(self.palettes))
        self._chunks: OrderedDict[tuple[int, int], pygame.Surface] = OrderedDict()
        self._chunk_obstacles: dict[tuple[int, int], list] = {}
        reach = 16  # obstacles are drawn a little larger than their radius
        for o in obstacles:
            x, y = o.x / UNITS_PER_PX, o.y / UNITS_PER_PX
            for cx in {int((x - reach) // CHUNK_PX), int((x + reach) // CHUNK_PX)}:
                for cy in {int((y - reach) // CHUNK_PX), int((y + reach) // CHUNK_PX)}:
                    self._chunk_obstacles.setdefault((cx, cy), []).append(o)
        self._number_cache.pop(("minimap", self.minimap_size()), None)
        self._build_overview(arena_w, arena_h, obstacles)

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
        shades = self.tiles.get(self.biome)
        decor = self.decor.get(self.biome)
        pal = self.palettes[self.biome]
        txs = range(max(0, x0 // tile), min(aw, x0 + CHUNK_PX) // tile)
        for ty in range(max(0, y0 // tile), min(ah, y0 + CHUNK_PX) // tile):
            for tx in txs:
                dest = (tx * tile - x0, ty * tile - y0)
                if shades is not None:  # large light and dark patches, so the bed never looks flat
                    sheet = shades[_patch_shade(tx, ty, len(shades))]
                    surf.blit(sheet, dest, (_tile_index(self.biome, tx, ty) * tile, 0, tile, tile))
                else:
                    surf.fill(hex_rgb(pal["detail"] if (tx + ty) % 2 else pal["ground"]), (*dest, tile, tile))
            if self.biome == "veggiebed" and ty % 6 == 0:  # wooden edging along the vegetable rows
                y = ty * tile - y0
                surf.fill((150, 104, 66), (0, y - 1, CHUNK_PX, 1))
                surf.fill((122, 82, 52), (0, y + tile, CHUNK_PX, 1))
        if decor is not None:  # scattered decorations: pebbles, flowers, leaves, ... (no collision)
            n = decor.get_width() // tile
            for ty in range(max(0, y0 // tile), min(ah, y0 + CHUNK_PX) // tile):
                for tx in txs:
                    h = ((tx * 2654435761) ^ (ty * 2246822519)) & 0xFFFFFF
                    if h % 100 < DECOR_PCT:
                        dx, dy = (h >> 8) % 7 - 3, (h >> 12) % 7 - 3
                        surf.blit(
                            decor, (tx * tile - x0 + dx, ty * tile - y0 + dy), ((h >> 16) % n * tile, 0, tile, tile)
                        )
        for o in self._chunk_obstacles.get(key, ()):  # soft shadow first, then the obstacle
            sx, sy = round(o.x / UNITS_PER_PX) - x0, round(o.y / UNITS_PER_PX) - y0
            r = round(o.radius / UNITS_PER_PX) + 3
            shadow = pygame.Surface((2 * r + 4, r + 3), pygame.SRCALPHA)
            pygame.draw.ellipse(shadow, (40, 24, 40, 70), shadow.get_rect())
            surf.blit(shadow, (sx - r - 2 + 3, sy + r - 5))
        for o in self._chunk_obstacles.get(key, ()):
            self._draw_obstacle(surf, o, -x0, -y0)
        pygame.draw.rect(surf, self.ink, (-x0, -y0, aw, ah), 1)  # map border where it crosses this chunk
        self._chunks[key] = surf
        if len(self._chunks) > MAX_CHUNKS:
            self._chunks.popitem(last=False)
        return surf

    def _build_overview(self, arena_w: float, arena_h: float, obstacles: tuple) -> None:
        """One pixel per tile: ground colour and darker dots for obstacles."""
        tiles_w, tiles_h = int(arena_w // self.tile_px), int(arena_h // self.tile_px)
        surf = pygame.Surface((tiles_w, tiles_h))
        pal = self.palettes[self.biome]
        surf.fill(hex_rgb(pal["ground"]))
        dark = tuple(v * 3 // 5 for v in hex_rgb(pal["ground"]))
        for o in obstacles:
            surf.set_at((int(o.x // self.tile_px), int(o.y // self.tile_px)), dark)
        self.overview = surf

    def _draw_obstacle(self, surf: pygame.Surface, o, ox: int = 0, oy: int = 0) -> None:
        x, y = round(o.x / UNITS_PER_PX) + ox, round(o.y / UNITS_PER_PX) + oy
        r = max(3, round(o.radius / UNITS_PER_PX) + 1)
        ink, pal = self.ink, self.palettes.get(self.biome, {})
        if o.kind == "cabbage":  # round head with leaf lines
            green = hex_rgb(pal.get("cabbage") or "#b7e39a")
            pygame.draw.circle(surf, ink, (x, y), r + 2)
            pygame.draw.circle(surf, tuple(v * 4 // 5 for v in green), (x, y), r + 1)
            pygame.draw.circle(surf, green, (x, y - 1), r - 1)
            pygame.draw.line(surf, tuple(v * 3 // 4 for v in green), (x, y - r + 1), (x, y + r - 2))
            pygame.draw.line(surf, tuple(v * 3 // 4 for v in green), (x - r + 2, y), (x - 1, y - r + 3))
            surf.set_at((x - r // 2, y - r // 2), (255, 255, 255))
        elif o.kind == "heap":  # compost mound, oozing a little poison
            brown = hex_rgb(pal.get("heap") or "#6f5b49")
            pygame.draw.ellipse(surf, ink, (x - r - 2, y - r, 2 * r + 4, 2 * r + 2))
            pygame.draw.ellipse(surf, brown, (x - r - 1, y - r + 1, 2 * r + 2, 2 * r))
            pygame.draw.ellipse(surf, tuple(min(255, v + 25) for v in brown), (x - r + 2, y - r + 2, r, r // 2 + 1))
            surf.fill((182, 224, 90), (x + 1, y + 1, 3, 2))
            surf.fill((160, 120, 80), (x - 3, y - 2, 2, 1))
        else:  # "stalk" (and the old "tree"): a tall plant with two leaves and a bud
            stem = hex_rgb(pal.get("stalk") or "#7ccf6a")
            dark = tuple(v * 3 // 4 for v in stem)
            surf.fill(ink, (x - 2, y - r - 6, 5, 2 * r + 8))
            surf.fill(dark, (x - 1, y - r - 5, 3, 2 * r + 6))
            for side in (-1, 1):
                pts = [(x, y - 2 + side * 2), (x + side * (r + 3), y - 6 + side), (x + side * (r - 1), y + 1)]
                pygame.draw.polygon(surf, ink, pts)
                pygame.draw.polygon(surf, stem, [(px - side, py) for px, py in pts])
            pygame.draw.circle(surf, ink, (x, y - r - 6), 4)
            pygame.draw.circle(surf, (255, 212, 94), (x, y - r - 6), 3)
            surf.set_at((x - 1, y - r - 7), (255, 255, 255))

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


RARITY_ORDER = ("common", "uncommon", "rare", "epic", "legendary")
POP_FRAMES = 24  # HUD icon pop when something new arrives
DECOR_PCT = 9  # share of tiles with a decoration
MOTES = {  # floating particles per bed: colour, count
    "seedbed": ((255, 244, 190), 18),
    "veggiebed": ((255, 255, 255), 14),
    "compost": ((190, 236, 110), 20),
}
STATUS_COLORS = {"burn": (255, 140, 60), "poison": (182, 224, 90), "chill": (140, 210, 255), "frozen": (220, 240, 255)}
WHOLE_STATS = frozenset({"extra_attacks", "pierce_add", "bounce_add", "revives", "rerolls", "banishes",
                         "flat_damage_reduction"})  # fmt: skip


def _signed(v: float, stat: str) -> str:
    """+12, -6, +0,6 (German decimal comma); whole-number stats are rounded down like the game does."""
    if stat in WHOLE_STATS:
        v = float(max(1, int(v)) if v > 0 else int(v))
    text = f"{v:+.1f}".replace(".", ",")
    return text[:-2] if text.endswith(",0") else text


def _tile_index(biome: str, tx: int, ty: int) -> int:
    """Which tile of the bed's sheet goes where: rows of seedlings, rows of vegetables, scattered compost bits."""
    h = ((tx * 73856093) ^ (ty * 19349663)) & 0xFFFF
    if biome == "seedbed":
        return 4 + (h % 4) if ty % 4 == 0 else h % 4
    if biome == "veggiebed":
        if ty % 6 == 0:  # vegetable rows: soil, now and then a carrot top
            return 4 if h % 5 else 6
        return (5, 7)[h % 2] if h % 23 == 0 else h % 4
    return 4 + (h % 4) if h % 19 == 0 else h % 4


SHADES = (-8, -4, 0, 4, 7)  # brightness steps of the ground patches (subtle, or they look like a checkerboard)


def _patch_shade(tx: int, ty: int, n: int) -> int:
    """Value noise over 10-tile cells, dithered into n steps: big soft patches of lighter and darker ground."""

    def lattice(ix: int, iy: int) -> float:
        return (((ix * 374761393) ^ (iy * 668265263)) * 1274126177 & 0xFFFF) / 0xFFFF

    cell = 10
    gx, gy = tx / cell, ty / cell
    ix, iy = int(gx), int(gy)
    fx, fy = gx - ix, gy - iy
    fx, fy = fx * fx * (3 - 2 * fx), fy * fy * (3 - 2 * fy)
    top = lattice(ix, iy) + (lattice(ix + 1, iy) - lattice(ix, iy)) * fx
    bottom = lattice(ix, iy + 1) + (lattice(ix + 1, iy + 1) - lattice(ix, iy + 1)) * fx
    v = top + (bottom - top) * fy
    dither = ((tx & 1) * 2 + (ty & 1) * 3) % 4 / 4.0 - 0.375
    return max(0, min(n - 1, int(v * n + dither * 0.9)))


def _load_tiles(biomes: set[str]) -> tuple[dict[str, list[pygame.Surface]], dict[str, pygame.Surface]]:
    """assets/tiles/<biome>.png (in SHADES brightness steps) and <biome>_decor.png from tools/sprites/tiles.py;
    missing sheets fall back to flat colours and no decorations."""
    tiles, decor = {}, {}
    for b in biomes:
        try:
            sheet = pygame.image.load(str(ASSETS_DIR / "tiles" / f"{b}.png"))
        except (OSError, pygame.error, FileNotFoundError):
            continue
        shades = []
        for d in SHADES:
            s = sheet.copy()
            if d:
                s.fill((abs(d),) * 3, special_flags=pygame.BLEND_RGB_ADD if d > 0 else pygame.BLEND_RGB_SUB)
            shades.append(s)
        tiles[b] = shades
        with contextlib.suppress(OSError, pygame.error, FileNotFoundError):
            decor[b] = pygame.image.load(str(ASSETS_DIR / "tiles" / f"{b}_decor.png"))
    return tiles, decor


def effect_palette(r: Renderer) -> tuple[dict, dict]:
    """Colours the effects use, taken from the renderer's style colours."""
    colors = {
        "white": WHITE,
        "crit": r.crit_color,
        "shot_core": r.shot_core,
        "shot_halo": r.shot_halo,
        "telegraph": r.telegraph,
        "poison": r.poison,
        "pumpkin": r.pumpkin,
        "leaf": (124, 207, 106),
        "gate": (126, 217, 87),
    }
    return colors, dict(r.enemy_colors)
