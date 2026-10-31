from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
import json
from pathlib import Path
import re

from PIL import Image, ImageDraw
import numpy as np


class RegionPermission(StrEnum):
    EDITABLE = "editable"
    PROTECTED = "protected"


@dataclass(frozen=True)
class RegionAnnotation:
    region_id: str
    label: str
    semantic_type: str
    permission: RegionPermission
    tags: tuple[str, ...]
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
        semantic_type = str(item.get("semantic_type", "")).strip()
        if not region_id or not re.fullmatch(r"[A-Za-z0-9_.-]+", region_id):
            raise ValueError(f"regions[{index}].id must use letters, digits, dot, underscore or hyphen")
        if region_id in seen:
            raise ValueError(f"duplicate region id: {region_id}")
        seen.add(region_id)
        if not label or not semantic_type:
            raise ValueError(f"regions[{index}].label and semantic_type must be non-empty")
        try:
            permission = RegionPermission(item.get("permission"))
        except ValueError as exc:
            raise ValueError(f"regions[{index}].permission must be editable or protected") from exc
        tags_raw = item.get("tags", [])
        if not isinstance(tags_raw, list) or any(not isinstance(tag, str) or not tag.strip() for tag in tags_raw):
            raise ValueError(f"regions[{index}].tags must be a list of non-empty strings")
        tags = tuple(tag.strip() for tag in tags_raw)
        if len(set(tags)) != len(tags):
            raise ValueError(f"regions[{index}].tags cannot contain duplicates")
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
        result.append(
            RegionAnnotation(region_id, label, semantic_type, permission, tags, tuple(polygon))
        )
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
