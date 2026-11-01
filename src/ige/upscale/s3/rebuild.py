from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image

from ige.upscale.siax import file_sha256


def rebuild_from_receipts(
    *,
    receipts: list[dict[str, Any]],
    output_path: str | Path,
    output_width: int,
    output_height: int,
    origin_hires: tuple[int, int] = (0, 0),
    min_bytes: int = 1000,
) -> dict[str, Any]:
    """Place child cores onto a canvas. Boxes are absolute hires; origin shifts into local canvas."""
    out = Path(output_path)
    ox, oy = origin_hires
    canvas = np.zeros((output_height, output_width, 3), dtype=np.uint8)
    coverage = np.zeros((output_height, output_width), dtype=np.uint8)
    placed = []
    errors = []
    for item in receipts:
        rec = item.get("receipt") or item
        if rec.get("status") != "ok":
            errors.append(f"{rec.get('child_id')} status={rec.get('status')}")
            continue
        uri = Path(rec["uri"])
        if not uri.is_file():
            errors.append(f"missing {uri}")
            continue
        actual = file_sha256(uri)
        if actual != rec.get("sha256"):
            errors.append(f"sha mismatch {rec.get('child_id')}")
            continue
        x0, y0, x1, y1 = [int(v) for v in rec["output_box_hires"]]
        lx0, ly0, lx1, ly1 = x0 - ox, y0 - oy, x1 - ox, y1 - oy
        if lx0 < 0 or ly0 < 0 or lx1 > output_width or ly1 > output_height:
            errors.append(f"box oob {rec.get('child_id')}")
            continue
        with Image.open(uri) as im:
            tile = np.asarray(im.convert("RGB"), dtype=np.uint8)
        if tile.shape != (ly1 - ly0, lx1 - lx0, 3):
            errors.append(f"shape {rec.get('child_id')}")
            continue
        if np.any(coverage[ly0:ly1, lx0:lx1]):
            errors.append(f"overlap {rec.get('child_id')}")
            continue
        coverage[ly0:ly1, lx0:lx1] = 1
        canvas[ly0:ly1, lx0:lx1] = tile
        placed.append(rec.get("child_id"))
    missing = int(coverage.size - np.count_nonzero(coverage))
    if missing:
        errors.append(f"incomplete coverage missing={missing}")
    if errors:
        raise RuntimeError("rebuild failed: " + "; ".join(errors[:10]))
    out.parent.mkdir(parents=True, exist_ok=True)
    Image.fromarray(canvas, "RGB").save(out, format="PNG", compress_level=3)
    size = out.stat().st_size
    if size < min_bytes:
        raise RuntimeError(f"output too small {size}")
    report = {
        "output_path": str(out.resolve()),
        "output_sha256": file_sha256(out),
        "output_bytes": size,
        "output_dimensions": {"width": output_width, "height": output_height},
        "children_placed": placed,
        "n_placed": len(placed),
        "final_acceptance": False,
        "quality_qualified": False,
        "e3_speed_claim": False,
    }
    sidecar = out.with_suffix(".upscale.json")
    sidecar.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return report


def pixel_match_children(receipts: list[dict[str, Any]], primary: Path, origin_hires=(0, 0)) -> dict[str, Any]:
    with Image.open(primary) as im:
        canvas = np.asarray(im.convert("RGB"), dtype=np.uint8)
    ox, oy = origin_hires
    mismatches = 0
    checked = 0
    for item in receipts:
        rec = item.get("receipt") or item
        uri = Path(rec["uri"])
        x0, y0, x1, y1 = [int(v) for v in rec["output_box_hires"]]
        lx0, ly0, lx1, ly1 = x0 - ox, y0 - oy, x1 - ox, y1 - oy
        with Image.open(uri) as im:
            tile = np.asarray(im.convert("RGB"), dtype=np.uint8)
        region = canvas[ly0:ly1, lx0:lx1]
        checked += 1
        if not np.array_equal(region, tile):
            mismatches += 1
    return {
        "checked": checked,
        "pixel_mismatches": mismatches,
        "ok": mismatches == 0 and checked > 0,
        "primary_sha256": file_sha256(primary),
    }
