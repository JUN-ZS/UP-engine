#!/usr/bin/env python3
"""N1: stitch native-res tile PNGs onto canvas using plan core boxes.

Fail-closed (v1.1): missing tiles, wrong size (unless --allow-resize), or incomplete
set → non-zero exit and no PASS flag. Partial PNG only if --allow-partial (debug).
"""
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
    ap.add_argument("--base-canvas", type=Path, default=None)
    ap.add_argument(
        "--allow-partial",
        action="store_true",
        help="DEBUG only: write PNG even if tiles missing (never sets complete=true)",
    )
    ap.add_argument(
        "--allow-resize",
        action="store_true",
        help="DEBUG only: Lanczos-resize wrong-size tiles (hides generator bugs; default OFF)",
    )
    ap.add_argument(
        "--require-tiles",
        type=str,
        default="",
        help="comma tile_ids subset required (empty = all plan tiles)",
    )
    args = ap.parse_args()

    plan = CanvasPlan.load(args.plan)
    required_ids = (
        [s.strip() for s in args.require_tiles.split(",") if s.strip()]
        if args.require_tiles
        else [t["tile_id"] for t in plan.tiles]
    )
    required_set = set(required_ids)
    tiles_by_id = {t["tile_id"]: t for t in plan.tiles}
    for rid in required_ids:
        if rid not in tiles_by_id:
            print(json.dumps({"ok": False, "error": f"unknown tile_id in --require-tiles: {rid}"}))
            return 2

    if args.base_canvas and args.base_canvas.is_file():
        canvas = Image.open(args.base_canvas).convert("RGB")
        if canvas.size != (plan.width, plan.height):
            print(json.dumps({"ok": False, "error": "base-canvas size must match plan"}))
            return 2
    else:
        canvas = Image.new("RGB", (plan.width, plan.height), (0, 0, 0))

    missing = []
    wrong_size = []
    placed = []
    tile_receipts = []

    for tid in required_ids:
        t = tiles_by_id[tid]
        path = args.tiles_dir / f"{tid}.png"
        if not path.is_file():
            path = args.tiles_dir / f"{tid}.jpg"
        if not path.is_file():
            missing.append(tid)
            continue
        im = Image.open(path).convert("RGB")
        x0, y0, x1, y1 = t["x0"], t["y0"], t["x1"], t["y1"]
        expect = (x1 - x0, y1 - y0)
        if im.size != expect:
            if args.allow_resize:
                im = im.resize(expect, Image.Resampling.LANCZOS)
                wrong_size.append({"tile_id": tid, "got": list(im.size), "expected": list(expect), "resized": True})
            else:
                wrong_size.append({"tile_id": tid, "got": list(im.size), "expected": list(expect), "resized": False})
                continue
        cx0, cy0, cx1, cy1 = t["core_x0"], t["core_y0"], t["core_x1"], t["core_y1"]
        lx0, ly0 = cx0 - x0, cy0 - y0
        lx1, ly1 = cx1 - x0, cy1 - y0
        core = im.crop((lx0, ly0, lx1, ly1))
        canvas.paste(core, (cx0, cy0))
        placed.append(tid)
        tile_receipts.append(
            {
                "tile_id": tid,
                "path": str(path),
                "sha256": sha256(path),
                "box": [x0, y0, x1, y1],
                "core": [cx0, cy0, cx1, cy1],
            }
        )

    complete = (
        len(missing) == 0
        and all(w.get("resized") for w in wrong_size) is not False
        and len([w for w in wrong_size if not w.get("resized")]) == 0
        and set(placed) == required_set
    )
    # fix complete logic
    complete = len(missing) == 0 and not any(not w.get("resized") for w in wrong_size) and set(placed) == required_set

    write_png = complete or args.allow_partial
    report = {
        "format": "ige.native4k.n1_stitch",
        "format_version": "1.1",
        "path": "native_canvas_tiling",
        "not_siax_4x_upscale": True,
        "ok": complete,
        "complete": complete,
        "fail_closed": not args.allow_partial,
        "placed": placed,
        "placed_count": len(placed),
        "missing": missing,
        "wrong_size": wrong_size,
        "required_count": len(required_ids),
        "tile_count_plan": plan.tile_count,
        "tile_receipts": tile_receipts,
        "width": plan.width,
        "height": plan.height,
        "native_4k_success": False,
        "n1_gen_pilot_ok": False,
        "final_acceptance": False,
    }

    if write_png:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        canvas.save(args.out, format="PNG", compress_level=3)
        report["output"] = str(args.out.resolve())
        report["output_sha256"] = sha256(args.out)
    else:
        report["output"] = None
        report["output_sha256"] = None
        report["error"] = "fail_closed: refusing to write incomplete canvas"

    side = args.out.with_suffix(".n1_stitch.json")
    side.parent.mkdir(parents=True, exist_ok=True)
    side.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0 if complete else 3


if __name__ == "__main__":
    raise SystemExit(main())
