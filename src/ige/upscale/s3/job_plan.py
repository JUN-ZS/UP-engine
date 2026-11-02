from __future__ import annotations

from pathlib import Path
from typing import Any

from PIL import Image, ImageOps


def plan_compute_children(
    base_path: str | Path,
    *,
    compute_core: int = 64,
    compute_context: int = 0,
    scale: int = 4,
    region: tuple[int, int, int, int] | None = None,
) -> dict[str, Any]:
    """Plan core-only compute children over full BASE or a [x0,y0,x1,y1] region."""
    with Image.open(base_path) as im:
        base = ImageOps.exif_transpose(im).convert("RGB")
    W, H = base.size
    if region is None:
        rx0, ry0, rx1, ry1 = 0, 0, W, H
    else:
        rx0, ry0, rx1, ry1 = region
        rx0, ry0 = max(0, rx0), max(0, ry0)
        rx1, ry1 = min(W, rx1), min(H, ry1)
    children = []
    for cy in range(ry0, ry1, compute_core):
        for cx in range(rx0, rx1, compute_core):
            cx1, cy1 = min(cx + compute_core, rx1), min(cy + compute_core, ry1)
            ex0 = max(0, cx - compute_context)
            ey0 = max(0, cy - compute_context)
            ex1 = min(W, cx1 + compute_context)
            ey1 = min(H, cy1 + compute_context)
            child_id = f"c_{cy:04d}_{cx:04d}"
            children.append(
                {
                    "child_id": child_id,
                    "core_box_base": [cx, cy, cx1, cy1],
                    "input_box_base": [ex0, ey0, ex1, ey1],
                    "output_box_hires": [cx * scale, cy * scale, cx1 * scale, cy1 * scale],
                }
            )
    return {
        "base_wh": [W, H],
        "region": [rx0, ry0, rx1, ry1],
        "compute_core": compute_core,
        "compute_context": compute_context,
        "scale": scale,
        "children": children,
        "child_count": len(children),
        "output_wh": [(rx1 - rx0) * scale, (ry1 - ry0) * scale],
        "output_origin_hires": [rx0 * scale, ry0 * scale],
    }
