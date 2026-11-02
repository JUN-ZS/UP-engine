#!/usr/bin/env python3
"""N1.gen dual-tile pilot scaffold.

Prepares two adjacent native tiles with global-ref crops and job contracts.
Does NOT claim AI generation success until a real generator fills tile PNGs
at exact target-pixel sizes.

See docs/N1_GEN_CHARTER.md
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root / "src"))
    from ige.native4k.n1_canvas import CanvasPlan
    from PIL import Image

    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--plan", type=Path, required=True)
    ap.add_argument("--list-pairs", action="store_true")
    ap.add_argument("--pair", type=int, default=0, help="index into horizontal adjacent pairs")
    ap.add_argument("--global-ref", type=Path, default=None)
    ap.add_argument("--out-dir", type=Path, default=Path("runs/n1/gen_dual"))
    ap.add_argument("--scene-lock", type=str, default=(
        "Cinematic warrior woman in gold scale armor swinging bronze hammer in mud rain lightning; "
        "preserve hammer continuity, hands grip, armor scales, face identity across tiles."
    ))
    args = ap.parse_args()

    plan = CanvasPlan.load(args.plan)
    tiles = plan.tiles
    # horizontal neighbors: same y0, x0 of B == x0 of A + step (approx)
    pairs = []
    by_y: dict[int, list] = {}
    for t in tiles:
        by_y.setdefault(t["y0"], []).append(t)
    for y0, row in sorted(by_y.items()):
        row = sorted(row, key=lambda t: t["x0"])
        for i in range(len(row) - 1):
            a, b = row[i], row[i + 1]
            if b["x0"] <= a["x1"] and b["x0"] >= a["x0"]:
                pairs.append((a, b))

    if args.list_pairs:
        out = [
            {
                "pair_index": i,
                "a": a["tile_id"],
                "b": b["tile_id"],
                "a_box": [a["x0"], a["y0"], a["x1"], a["y1"]],
                "b_box": [b["x0"], b["y0"], b["x1"], b["y1"]],
            }
            for i, (a, b) in enumerate(pairs)
        ]
        print(json.dumps({"pair_count": len(pairs), "pairs": out[:30], "note": "first 30"}, indent=2))
        return 0

    if not pairs:
        print(json.dumps({"ok": False, "error": "no horizontal adjacent pairs"}))
        return 2
    if args.pair < 0 or args.pair >= len(pairs):
        print(json.dumps({"ok": False, "error": f"pair index out of range 0..{len(pairs)-1}"}))
        return 2

    a, b = pairs[args.pair]
    out_dir = args.out_dir
    tiles_dir = out_dir / "tiles"
    refs_dir = out_dir / "refs"
    jobs_dir = out_dir / "jobs"
    for d in (tiles_dir, refs_dir, jobs_dir):
        d.mkdir(parents=True, exist_ok=True)

    # Map global-ref (any size) into canvas coords via contain fit (same as n1_init structure)
    ref_meta = None
    if args.global_ref and args.global_ref.is_file():
        base = Image.open(args.global_ref).convert("RGB")
        bw, bh = base.size
        W, H = plan.width, plan.height
        scale = min(W / bw, H / bh)
        nw, nh = max(1, int(bw * scale)), max(1, int(bh * scale))
        xoff, yoff = (W - nw) // 2, (H - nh) // 2
        resized = base.resize((nw, nh), Image.Resampling.LANCZOS)
        canvas_ref = Image.new("RGB", (W, H), (16, 16, 16))
        canvas_ref.paste(resized, (xoff, yoff))
        ref_meta = {
            "global_ref": str(args.global_ref),
            "base_wh": [bw, bh],
            "fit": "contain",
            "placed_wh": [nw, nh],
            "offset": [xoff, yoff],
            "note": "ref crops are layout hints only — NOT native generation and NOT Siax 4x",
        }
        for t in (a, b):
            crop = canvas_ref.crop((t["x0"], t["y0"], t["x1"], t["y1"]))
            # exact tile size
            assert crop.size == (t["x1"] - t["x0"], t["y1"] - t["y0"])
            crop.save(refs_dir / f"{t['tile_id']}_ref.png")

    def job_for(t, neighbor):
        return {
            "format": "ige.native4k.n1_gen_tile_job",
            "format_version": "1.0",
            "path": "native_canvas_tiling",
            "not_siax_4x_upscale": True,
            "tile_id": t["tile_id"],
            "box": [t["x0"], t["y0"], t["x1"], t["y1"]],
            "core": [t["core_x0"], t["core_y0"], t["core_x1"], t["core_y1"]],
            "expect_wh": [t["x1"] - t["x0"], t["y1"] - t["y0"]],
            "canvas_wh": [plan.width, plan.height],
            "neighbor_id": neighbor["tile_id"],
            "overlap": plan.overlap,
            "scene_lock": args.scene_lock,
            "global_ref_crop": str(refs_dir / f"{t['tile_id']}_ref.png") if ref_meta else None,
            "output_tile_png": str(tiles_dir / f"{t['tile_id']}.png"),
            "status": "PENDING_GENERATOR",
            "n1_gen_pilot_ok": False,
            "native_4k_success": False,
            "instructions": (
                "Fill output_tile_png with REAL generative content at expect_wh pixels. "
                "Use global_ref_crop + scene_lock + neighbor continuity. "
                "Do not Lanczos-only upscale the ref and claim N1_GEN_PILOT_OK."
            ),
        }

    jobs = [job_for(a, b), job_for(b, a)]
    for j in jobs:
        (jobs_dir / f"{j['tile_id']}.json").write_text(json.dumps(j, indent=2) + "\n", encoding="utf-8")

    manifest = {
        "format": "ige.native4k.n1_gen_dual_pilot",
        "format_version": "1.0",
        "status": "JOBS_READY_AWAITING_GENERATOR",
        "pair_index": args.pair,
        "tile_ids": [a["tile_id"], b["tile_id"]],
        "jobs": [str(jobs_dir / f"{j['tile_id']}.json") for j in jobs],
        "tiles_dir": str(tiles_dir),
        "ref_meta": ref_meta,
        "stitch_cmd": (
            f"python tools/n1_stitch.py --plan {args.plan} --tiles-dir {tiles_dir} "
            f"--require-tiles {a['tile_id']},{b['tile_id']} --out {out_dir / 'OUT_DUAL.png'}"
        ),
        "labels": {
            "N1_GEN_PILOT_OK": False,
            "N1_SEAM_CONTINUITY_OK": False,
            "NATIVE_4K_PILOT_OK": False,
        },
        "not_siax_4x_upscale": True,
        "note": "Scaffold only until generator writes exact-size tile PNGs.",
    }
    (out_dir / "dual_manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(manifest, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
