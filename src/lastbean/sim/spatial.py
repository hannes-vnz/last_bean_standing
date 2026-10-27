"""Uniform grid for neighbour queries (spatial hash). Rebuilt every tick."""

from __future__ import annotations


class SpatialHash:
    __slots__ = ("cell", "_cells")

    def __init__(self, cell: float) -> None:
        self.cell = cell
        self._cells: dict[tuple[int, int], list] = {}

    def clear(self) -> None:
        self._cells.clear()

    def insert(self, item, x: float, y: float) -> None:
        key = (int(x // self.cell), int(y // self.cell))
        bucket = self._cells.get(key)
        if bucket is None:
            self._cells[key] = [item]
        else:
            bucket.append(item)

    def query(self, x: float, y: float, radius: float) -> list:
        """Items in all cells overlapping the square around (x, y). Callers do the exact distance test."""
        c = self.cell
        x0, x1 = int((x - radius) // c), int((x + radius) // c)
        y0, y1 = int((y - radius) // c), int((y + radius) // c)
        out: list = []
        cells = self._cells
        for cy in range(y0, y1 + 1):
            for cx in range(x0, x1 + 1):
                bucket = cells.get((cx, cy))
                if bucket:
                    out.extend(bucket)
        return out
