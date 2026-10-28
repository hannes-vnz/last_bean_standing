"""Static arena obstacles (trees, rocks, ...) generated from `biomes.json` with a fixed seed.

Obstacles are circles on tile centres. Solid ones push players and walking enemies out;
ones that block projectiles give cover (forest: "Bäume blockieren Geschosse").
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from .rng import Rng
from .spatial import SpatialHash
from .waves import BiomeArea

# Collision radius of an obstacle in world units (a tile is 32). Not in data/ yet.
OBSTACLE_RADIUS = 14.0
# Kinds that exist in the data and how they behave. Phase-2/3 kinds are added with their biome.
OBSTACLE_KINDS = {"tree": {"solid": True, "blocks_projectiles": True}}


@dataclass(frozen=True, slots=True)
class Obstacle:
    kind: str
    x: float
    y: float
    radius: float
    solid: bool
    blocks_projectiles: bool


def generate_obstacles(
    area: BiomeArea, kind: str, count: int, seed: int, tile: float, keep_free: tuple[BiomeArea, ...]
) -> tuple[Obstacle, ...]:
    """`count` obstacles on distinct tiles of `area`, never next to each other, the arena edge or `keep_free`."""
    behaviour = OBSTACLE_KINDS[kind]
    rng = Rng(seed)
    cols, rows = int(area.w // tile), int(area.h // tile)
    taken: set[tuple[int, int]] = set()
    out: list[Obstacle] = []
    attempts = 0
    while len(out) < count and attempts < count * 200:
        attempts += 1
        c, r = rng.randint(1, cols - 2), rng.randint(1, rows - 2)
        x, y = area.x + (c + 0.5) * tile, area.y + (r + 0.5) * tile
        if any((c + dc, r + dr) in taken for dc in (-1, 0, 1) for dr in (-1, 0, 1)):
            continue
        if any(f.x - tile <= x < f.x + f.w + tile and f.y - tile <= y < f.y + f.h + tile for f in keep_free):
            continue
        taken.add((c, r))
        out.append(Obstacle(kind, x, y, OBSTACLE_RADIUS, behaviour["solid"], behaviour["blocks_projectiles"]))
    return tuple(out)


def obstacles_from_content(content, max_phase: int) -> tuple[Obstacle, ...]:
    from .waves import biome_areas_from_content

    tile = float(content.balance.tile_px)
    areas = {a.id: a for a in biome_areas_from_content(content)}
    # Areas without obstacles (the central clearing) stay free.
    keep_free = tuple(areas[b.id] for b in content.biomes if "obstacles" not in b.extra)
    out: list[Obstacle] = []
    for b in content.biomes:
        spec = b.extra.get("obstacles")
        if not spec or b.impl_phase > max_phase or spec["type"] not in OBSTACLE_KINDS:
            continue  # later phases and kinds without implemented behaviour
        out.extend(generate_obstacles(areas[b.id], spec["type"], spec["count"], spec["seed"], tile, keep_free))
    return tuple(out)


class ObstacleMap:
    """Spatial lookup for the static obstacles, built once per world."""

    def __init__(self, obstacles: tuple[Obstacle, ...], cell: float = 64.0) -> None:
        self.obstacles = obstacles
        self.cell = cell
        self._grid = SpatialHash(cell)
        for o in obstacles:
            self._grid.insert(o, o.x, o.y)
        self.max_radius = max((o.radius for o in obstacles), default=0.0)
        # Cells with an obstacle in them or next to them: everything else skips the lookup (fast path).
        self._hot: set[tuple[int, int]] = set()
        for o in obstacles:
            cx, cy = int(o.x // cell), int(o.y // cell)
            self._hot.update((cx + dx, cy + dy) for dx in (-1, 0, 1) for dy in (-1, 0, 1))

    def near(self, x: float, y: float, radius: float) -> list[Obstacle]:
        return self._grid.query(x, y, radius + self.max_radius) if self.obstacles else []

    def push_out(self, x: float, y: float, radius: float) -> tuple[float, float]:
        """Move a circle out of every solid obstacle it overlaps."""
        if (int(x // self.cell), int(y // self.cell)) not in self._hot:
            return x, y
        for o in self.near(x, y, radius):
            if not o.solid:
                continue
            dx, dy = x - o.x, y - o.y
            min_d = radius + o.radius
            d2 = dx * dx + dy * dy
            if d2 >= min_d * min_d:
                continue
            if d2 < 1e-12:
                dx, dy, d = 1.0, 0.0, 1.0  # exactly on the centre: push to the right
            else:
                d = math.sqrt(d2)
            x, y = o.x + dx / d * min_d, o.y + dy / d * min_d
        return x, y

    def blocks_point(self, x: float, y: float, radius: float) -> bool:
        if (int(x // self.cell), int(y // self.cell)) not in self._hot:
            return False
        for o in self.near(x, y, radius):
            if o.blocks_projectiles:
                r = o.radius + radius
                if (x - o.x) ** 2 + (y - o.y) ** 2 < r * r:
                    return True
        return False

    def line_blocked(self, x0: float, y0: float, x1: float, y1: float, radius: float = 0.0) -> bool:
        """Does the segment (widened by `radius`) cross an obstacle that blocks projectiles?"""
        if not self.obstacles:
            return False
        dx, dy = x1 - x0, y1 - y0
        length2 = dx * dx + dy * dy
        mx, my = (x0 + x1) / 2, (y0 + y1) / 2
        half = math.sqrt(length2) / 2
        for o in self.near(mx, my, half + radius):
            if not o.blocks_projectiles:
                continue
            t = 0.0 if length2 == 0 else max(0.0, min(1.0, ((o.x - x0) * dx + (o.y - y0) * dy) / length2))
            px, py = x0 + dx * t, y0 + dy * t
            r = o.radius + radius
            if (px - o.x) ** 2 + (py - o.y) ** 2 < r * r:
                return True
        return False
