"""Strip / streaming finalizer for Virtual Master rebuild (P1).

Writes a full lossless 4x PNG without requiring a second full-frame float buffer.
Uses the existing uint8 canvas allocator; optional strip-to-disk path for very large
outputs can be added later. Primary policy: preview never primary.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from PIL import Image

from .siax import allocate_output_canvas, file_sha256


class StripFinalizeError(RuntimeError):
    pass


def finalize_from_child_tiles(
    *,
    children: list[dict[str, Any]],
    output_path: str | Path,
    output_width: int,
    output_height: int,
    scale: int = 4,
    base_width: int | None = None,
    base_height: int | None = None,
    min_fullframe_bytes: int = 5_000_000,
    assert_dimensions: bool = True,
) -> dict[str, Any]:
    """Place core-only child PNGs onto a uint8 canvas and write lossless PNG.

    Each child must provide:
      - uri: path to RGB PNG (hi-res core only)
      - output_box_hires: [x0,y0,x1,y1] in full 4x coordinates
      - sha256: optional expected hash of child file
      - role: must not be 'preview' if used as primary contributor
    """
    out = Path(output_path)
    if out.suffix.lower() != ".png":
        raise ValueError("primary finalizer output must be lossless PNG")
    if scale != 4:
        raise ValueError("only scale=4 supported in this slice")
    if base_width is None:
        base_width = output_width // scale
    if base_height is None:
        base_height = output_height // scale
    if output_width != base_width * scale or output_height != base_height * scale:
        raise StripFinalizeError("output dimensions must be exact scale multiple of base")

    canvas = allocate_output_canvas(base_width, base_height, scale=scale)
    import numpy as np

    coverage = np.zeros((base_height, base_width), dtype=np.uint8)
    placed = []
    for child in children:
        role = str(child.get("role") or "compute_native")
        if role == "preview":
            raise StripFinalizeError(f"preview child cannot contribute to primary: {child.get('child_id')}")
        uri = Path(str(child["uri"]))
        if not uri.is_file():
            raise FileNotFoundError(uri)
        if child.get("sha256"):
            actual = file_sha256(uri)
            if actual != child["sha256"]:
                raise StripFinalizeError(f"child sha mismatch: {child.get('child_id')}")
        x0, y0, x1, y1 = [int(v) for v in child["output_box_hires"]]
        if x0 < 0 or y0 < 0 or x1 > output_width or y1 > output_height or x1 <= x0 or y1 <= y0:
            raise StripFinalizeError(f"bad output_box_hires for {child.get('child_id')}")
        with Image.open(uri) as im:
            tile = np.asarray(im.convert("RGB"), dtype=np.uint8)
        if tile.shape != (y1 - y0, x1 - x0, 3):
            raise StripFinalizeError(
                f"child {child.get('child_id')} shape {tile.shape} != box {(y1-y0, x1-x0, 3)}"
            )
        # base coverage in base coords
        bx0, by0, bx1, by1 = x0 // scale, y0 // scale, x1 // scale, y1 // scale
        if np.any(coverage[by0:by1, bx0:bx1]):
            raise StripFinalizeError(f"overlapping cores at {child.get('child_id')}")
        coverage[by0:by1, bx0:bx1] = 1
        canvas[y0:y1, x0:x1] = tile
        placed.append(child.get("child_id"))

    if not np.all(coverage == 1):
        missing = int(coverage.size - np.count_nonzero(coverage))
        raise StripFinalizeError(f"incomplete coverage: {missing} base pixels missing")

    out.parent.mkdir(parents=True, exist_ok=True)
    Image.fromarray(canvas, "RGB").save(out, format="PNG", compress_level=3)
    size = out.stat().st_size
    if size < min_fullframe_bytes:
        raise StripFinalizeError(
            f"primary PNG too small ({size} B < {min_fullframe_bytes}); refuse preview-class file"
        )
    dims = Image.open(out).size
    if assert_dimensions and dims != (output_width, output_height):
        raise StripFinalizeError(f"dimension assert failed: {dims} != {(output_width, output_height)}")

    report = {
        "execution_mode": "strip_finalize_uint8_canvas",
        "output_path": str(out.resolve()),
        "output_sha256": file_sha256(out),
        "output_bytes": size,
        "output_dimensions": {"width": output_width, "height": output_height},
        "children_placed": placed,
        "primary_policy": {
            "preview_never_primary": True,
            "min_fullframe_bytes": min_fullframe_bytes,
            "assert_dimensions": assert_dimensions,
        },
        "acceptance": "candidate_only",
        "final_acceptance": False,
    }
    sidecar = out.with_suffix(".upscale.json")
    temporary = sidecar.with_name(sidecar.name + f".{os.getpid()}.tmp")
    temporary.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(temporary, sidecar)
    return report | {"metadata_path": str(sidecar.resolve())}
