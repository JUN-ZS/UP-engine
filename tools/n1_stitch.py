#!/usr/bin/env python3
"""N1 stitch v1.2 — fail-closed + subset vs whole-canvas flags + atomic out.

- missing / wrong size → exit 3, do not claim complete
- default: refuse overwrite of existing --out (use --force-out or unique path)
- on failure: never leave a *new* partial as the success path; do not delete
  foreign files unless --out was written this run (atomic tmp then replace only on success)
- report required_subset_complete vs whole_canvas_complete separately
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import time
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
    ap.add_argument("--allow-partial", action="store_true")
    ap.add_argument("--allow-resize", action="store_true")
    ap.add_argument("--require-tiles", type=str, default="")
    ap.add_argument("--force-out", action="store_true", help="allow replace existing --out")
    ap.add_argument("--run-id", type=str, default="", help="if set, out becomes *_{run_id}.png")
    args = ap.parse_args()

    plan = CanvasPlan.load(args.plan)
    all_ids = [t["tile_id"] for t in plan.tiles]
    required_ids = (
        [s.strip() for s in args.require_tiles.split(",") if s.strip()]
        if args.require_tiles
        else list(all_ids)
    )
    required_set = set(required_ids)
    tiles_by_id = {t["tile_id"]: t for t in plan.tiles}
    for rid in required_ids:
        if rid not in tiles_by_id:
            print(json.dumps({"ok": False, "error": f"unknown tile_id: {rid}"}))
            return 2

    out_path = Path(args.out)
    if args.run_id:
        out_path = out_path.with_name(f"{out_path.stem}_{args.run_id}{out_path.suffix}")

    # overwrite policy independent of allow-partial (partial may write, but still needs --force-out to clobber)
    if out_path.exists() and not args.force_out:
        print(
            json.dumps(
                {
                    "ok": False,
                    "error": "output_exists",
                    "path": str(out_path),
                    "hint": "use --force-out or --run-id unique; refuse clobber so stale PNG is not mistaken for this run",
                },
                indent=2,
            )
        )
        return 4

    if args.base_canvas and args.base_canvas.is_file():
        canvas = Image.open(args.base_canvas).convert("RGB")
        if canvas.size != (plan.width, plan.height):
            print(json.dumps({"ok": False, "error": "base-canvas size must match plan"}))
            return 2
    else:
        canvas = Image.new("RGB", (plan.width, plan.height), (0, 0, 0))

    missing, wrong_size, placed, tile_receipts = [], [], [], []
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
        core = im.crop((cx0 - x0, cy0 - y0, cx1 - x0, cy1 - y0))
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

    size_ok = not any(not w.get("resized") for w in wrong_size)
    required_subset_complete = len(missing) == 0 and size_ok and set(placed) == required_set
    whole_canvas_complete = required_subset_complete and set(required_ids) == set(all_ids)
    # legacy alias: complete == required_subset_complete (NOT whole canvas)
    complete = required_subset_complete

    report = {
        "format": "ige.native4k.n1_stitch",
        "format_version": "1.2",
        "path": "native_canvas_tiling",
        "not_siax_4x_upscale": True,
        "ok": complete,
        "complete": complete,
        "required_subset_complete": required_subset_complete,
        "whole_canvas_complete": whole_canvas_complete,
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
        "run_id": args.run_id or None,
        "native_4k_success": False,
        "n1_gen_pilot_ok": False,
        "final_acceptance": False,
    }

    write_png = complete or args.allow_partial
    side = out_path.with_suffix(".n1_stitch.json")
    side.parent.mkdir(parents=True, exist_ok=True)

    if write_png:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        tmp = out_path.with_name(f".{out_path.name}.{os.getpid()}.{int(time.time())}.tmp.png")
        try:
            canvas.save(tmp, format="PNG", compress_level=3)
            os.replace(tmp, out_path)
        except Exception:
            if tmp.exists():
                tmp.unlink()
            raise
        report["output"] = str(out_path.resolve())
        report["output_sha256"] = sha256(out_path)
    else:
        report["output"] = None
        report["output_sha256"] = None
        report["error"] = "fail_closed: refusing to write incomplete canvas"
        if out_path.exists():
            report["stale_output_left_on_disk"] = str(out_path.resolve())
            report["stale_warning"] = (
                "Existing file was NOT deleted and NOT updated; do not treat it as this run's result. "
                "Use --run-id for unique paths."
            )

    side.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0 if complete else 3


if __name__ == "__main__":
    raise SystemExit(main())
