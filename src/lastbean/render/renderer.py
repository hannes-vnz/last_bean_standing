"""Draws simulation snapshots onto a fixed 640x360 canvas, scaled up by an integer factor.

M0: pastel ground, arena border and a test square in the player colour. No sprites yet.
"""

from __future__ import annotations

import pygame

from ..data.schema import Content
from ..sim.world import Snapshot

CANVAS_W, CANVAS_H = 640, 360
# World units per canvas pixel (DESIGN.md section 16: 1 tile = 32 units = 16 px).
UNITS_PER_PX = 2


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
        # Outside the arena: ink darkened, so the ink border and outlines stay visible.
        self.void = tuple(v * 3 // 5 for v in self.ink)
        self.font = pygame.font.Font(None, 16)

    def draw(self, snap: Snapshot, focus_player: int = 0) -> pygame.Surface:
        c = self.canvas
        c.fill(self.void)
        fx, fy = next(((x, y) for pid, x, y, _ in snap.players if pid == focus_player), (0.0, 0.0))
        # Camera: top-left corner of the view in canvas pixels, rounded to whole pixels.
        cam_x = round(fx / UNITS_PER_PX) - CANVAS_W // 2
        cam_y = round(fy / UNITS_PER_PX) - CANVAS_H // 2

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

        for _pid, x, y, _standing in snap.players:
            sx, sy = round(x / UNITS_PER_PX) - cam_x, round(y / UNITS_PER_PX) - cam_y
            body = pygame.Rect(sx - 8, sy - 8, 16, 16)
            c.fill(self.ink, body)
            c.fill(self.player_body, body.inflate(-2, -2))

        m, s = divmod(int(snap.time_s), 60)
        hud = f"{m}:{s:02d}  wave {snap.wave}"
        # White text with a dark outline (readability rule, DESIGN.md section 16).
        outline = self.font.render(hud, False, self.ink)
        for dx, dy in ((-1, 0), (1, 0), (0, -1), (0, 1)):
            c.blit(outline, (6 + dx, 6 + dy))
        c.blit(self.font.render(hud, False, (255, 255, 255)), (6, 6))
        return c

    def present(self, window: pygame.Surface) -> None:
        """Nearest-neighbour integer upscale, centred with letterboxing."""
        scale = integer_scale(*window.get_size())
        w, h = CANVAS_W * scale, CANVAS_H * scale
        window.fill((0, 0, 0))
        dest = ((window.get_width() - w) // 2, (window.get_height() - h) // 2)
        window.blit(pygame.transform.scale(self.canvas, (w, h)), dest)
