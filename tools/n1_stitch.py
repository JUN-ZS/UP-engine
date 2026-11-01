#!/usr/bin/env python3
"""N1: stitch native-res tile PNGs onto canvas using plan core boxes."""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for c in iter(lambda: f.read(1 << 20), b""):
            h.update(c)
    return h.hexdigest()


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root / "src"))
    from ige.native4k.n1_canvas import CanvasPlan
    from PIL import Image

    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--plan", type=Path, required=True)
    ap.add_argument("--tiles-dir", type=Path, required=True)
    ap.add_argument("--out", type=Path, default=Path("runs/n1/OUT_NATIVE.png"))
    ap.add_argument("--base-canvas", type=Path, default=None, help="optional starting canvas")
    args = ap.parse_args()

    plan = CanvasPlan.load(args.plan)
    if args.base_canvas and args.base_canvas.is_file():
        canvas = Image.open(args.base_canvas).convert("RGB")
        if canvas.size != (plan.width, plan.height):
            raise SystemExit("base-canvas size must match plan")
    else:
        canvas = Image.new("RGB", (plan.width, plan.height), (0, 0, 0))

    missing = []
    placed = 0
    for t in plan.tiles:
        tid = t["tile_id"]
        path = args.tiles_dir / f"{tid}.png"
        if not path.is_file():
            # also accept jpg
            path = args.tiles_dir / f"{tid}.jpg"
        if not path.is_file():
            missing.append(tid)
            continue
        im = Image.open(path).convert("RGB")
        # tile image is full tile extent; paste core region only
        x0, y0, x1, y1 = t["x0"], t["y0"], t["x1"], t["y1"]
        cx0, cy0, cx1, cy1 = t["core_x0"], t["core_y0"], t["core_x1"], t["core_y1"]
        # local coords inside tile image
        lx0, ly0 = cx0 - x0, cy0 - y0
        lx1, ly1 = cx1 - x0, cy1 - y0
        if im.size != (x1 - x0, y1 - y0):
            im = im.resize((x1 - x0, y1 - y0), Image.Resampling.LANCZOS)
        core = im.crop((lx0, ly0, lx1, ly1))
        canvas.paste(core, (cx0, cy0))
        placed += 1

    args.out.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(args.out, format="PNG", compress_level=3)
    report = {
        "format": "ige.native4k.n1_stitch",
        "path": "native_canvas_tiling",
        "not_siax_4x_upscale": True,
        "placed": placed,
        "missing": missing,
        "tile_count": plan.tile_count,
        "output": str(args.out.resolve()),
        "output_sha256": sha256(args.out),
        "width": plan.width,
        "height": plan.height,
        "native_4k_success": False,
        "scaffold_roundtrip": placed == plan.tile_count and not missing,
        "final_acceptance": False,
    }
    args.out.with_suffix(".n1_stitch.json").write_text(
        json.dumps(report, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(report, indent=2))
    return 0 if report["scaffold_roundtrip"] or placed > 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())
