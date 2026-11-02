from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Iterator


@dataclass(frozen=True)
class TileBox:
    tile_id: str
    x0: int
    y0: int
    x1: int
    y1: int
    core_x0: int
    core_y0: int
    core_x1: int
    core_y1: int

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class CanvasPlan:
    format: str
    format_version: str
    path: str
    not_siax_4x_upscale: bool
    width: int
    height: int
    tile: int
    overlap: int
    step: int
    tile_count: int
    tiles: list[dict[str, Any]]
    native_4k_success: bool
    final_acceptance: bool

    def to_json(self) -> str:
        return json.dumps(asdict(self), indent=2, ensure_ascii=False) + "\n"

    def write(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(self.to_json(), encoding="utf-8")

    @staticmethod
    def load(path: Path) -> "CanvasPlan":
        d = json.loads(Path(path).read_text(encoding="utf-8"))
        return CanvasPlan(**{k: d[k] for k in CanvasPlan.__dataclass_fields__})


def tile_boxes(width: int, height: int, tile: int, overlap: int) -> Iterator[TileBox]:
    if width < 1 or height < 1:
        raise ValueError("canvas size must be positive")
    if tile < 32:
        raise ValueError("tile must be >= 32")
    if overlap < 0 or overlap >= tile:
        raise ValueError("overlap must be in [0, tile)")
    step = tile - overlap
    idx = 0
    y = 0
    while y < height:
        x = 0
        y1 = min(y + tile, height)
        while x < width:
            x1 = min(x + tile, width)
            # core: exclude overlap on max edges except canvas border
            core_x0 = x if x == 0 else x + overlap // 2
            core_y0 = y if y == 0 else y + overlap // 2
            core_x1 = x1 if x1 >= width else x1 - overlap // 2
            core_y1 = y1 if y1 >= height else y1 - overlap // 2
            if core_x1 < core_x0:
                core_x0, core_x1 = x, x1
            if core_y1 < core_y0:
                core_y0, core_y1 = y, y1
            tid = f"n1_{idx:04d}_{x:04d}_{y:04d}"
            yield TileBox(tid, x, y, x1, y1, core_x0, core_y0, core_x1, core_y1)
            idx += 1
            if x1 >= width:
                break
            x += step
        if y1 >= height:
            break
        y += step


def build_plan(
    width: int = 3840,
    height: int = 2160,
    tile: int = 512,
    overlap: int = 64,
) -> CanvasPlan:
    tiles = [t.as_dict() for t in tile_boxes(width, height, tile, overlap)]
    return CanvasPlan(
        format="ige.native4k.n1_plan",
        format_version="1.0",
        path="native_canvas_tiling",
        not_siax_4x_upscale=True,
        width=width,
        height=height,
        tile=tile,
        overlap=overlap,
        step=tile - overlap,
        tile_count=len(tiles),
        tiles=tiles,
        native_4k_success=False,
        final_acceptance=False,
    )
