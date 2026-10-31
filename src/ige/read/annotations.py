from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
import json
from pathlib import Path
import re

from PIL import Image, ImageDraw
import numpy as np


class RegionRole(StrEnum):
    EDITABLE = "editable"
    PROTECTED = "protected"
    CONTEXT = "context"
    OBJECT = "object"


@dataclass(frozen=True)
class RegionAnnotation:
    region_id: str
    label: str
    role: RegionRole
    polygon: tuple[tuple[float, float], ...]


def load_regions(path: str | Path | None) -> tuple[RegionAnnotation, ...]:
    if path is None:
        return ()
    with Path(path).open("r", encoding="utf-8") as handle:
        raw = json.load(handle)
    if not isinstance(raw, dict) or raw.get("coordinate_space") != "normalized_0_1":
        raise ValueError("regions file must declare coordinate_space='normalized_0_1'")
    entries = raw.get("regions")
    if not isinstance(entries, list):
        raise ValueError("regions must be a list")
    result: list[RegionAnnotation] = []
    seen: set[str] = set()
    for index, item in enumerate(entries):
        if not isinstance(item, dict):
            raise ValueError(f"regions[{index}] must be an object")
        region_id = str(item.get("id", "")).strip()
        label = str(item.get("label", "")).strip()
        if not region_id or not re.fullmatch(r"[A-Za-z0-9_.-]+", region_id):
            raise ValueError(f"regions[{index}].id must use letters, digits, dot, underscore or hyphen")
        if region_id in seen:
            raise ValueError(f"duplicate region id: {region_id}")
        seen.add(region_id)
        if not label:
            raise ValueError(f"regions[{index}].label must be non-empty")
        try:
            role = RegionRole(item.get("role"))
        except ValueError as exc:
            raise ValueError(f"regions[{index}].role must be one of {[r.value for r in RegionRole]}") from exc
        points = item.get("polygon")
        if not isinstance(points, list) or len(points) < 3:
            raise ValueError(f"regions[{index}].polygon must contain at least three points")
        polygon: list[tuple[float, float]] = []
        for point in points:
            if not isinstance(point, list) or len(point) != 2:
                raise ValueError(f"regions[{index}] points must be [x, y] pairs")
            x, y = float(point[0]), float(point[1])
            if not (0.0 <= x <= 1.0 and 0.0 <= y <= 1.0):
                raise ValueError(f"regions[{index}] coordinates must be normalized to [0, 1]")
            polygon.append((x, y))
        result.append(RegionAnnotation(region_id, label, role, tuple(polygon)))
    return tuple(result)


def rasterize_region(region: RegionAnnotation, width: int, height: int) -> np.ndarray:
    if width <= 0 or height <= 0:
        raise ValueError("image dimensions must be positive")
    layer = Image.new("L", (width, height), 0)
    draw = ImageDraw.Draw(layer)
    points = [
        (round(x * (width - 1)), round(y * (height - 1)))
        for x, y in region.polygon
    ]
    draw.polygon(points, fill=255)
    mask = np.asarray(layer, dtype=np.uint8).copy()
    if not np.any(mask):
        raise ValueError(f"region {region.region_id!r} rasterized to an empty mask")
    return mask
