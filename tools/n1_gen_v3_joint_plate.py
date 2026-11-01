#!/usr/bin/env python3
"""N1.gen v3 — Joint A∪B plate scaffold + split.

Builds exact canvas bounding box covering tiles A and B (including overlaps),
exports a layout guide crop from global-ref (structure only), writes job contract,
and after a generator writes the joint plate, splits into exact A/B tile PNGs
by canvas coordinates (with optional hard equality check on overlap).

Does NOT claim seam PASS or native 4K success.
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
    sub = ap.add_subparsers(dest="cmd", required=True)

    p_prep = sub.add_parser("prep", help="write joint job + structure guide")
    p_prep.add_argument("--plan", type=Path, required=True)
    p_prep.add_argument("--tile-a", required=True)
    p_prep.add_argument("--tile-b", required=True)
    p_prep.add_argument("--global-ref", type=Path, default=None)
    p_prep.add_argument("--out-dir", type=Path, default=Path("runs/n1/gen_v3_joint"))
    p_prep.add_argument(
        "--scene-lock",
        type=str,
        default=(
            "Same single cinematic camera: warrior woman gold scale armor, wet black hair, "
            "mud rain lightning; continuous horizontal pan covering both tiles; preserve face, "
            "shoulder armor, hair flow without re-centering each half."
        ),
    )

    p_split = sub.add_parser("split", help="split joint plate into A/B exact tiles")
    p_split.add_argument("--plan", type=Path, required=True)
    p_split.add_argument("--tile-a", required=True)
    p_split.add_argument("--tile-b", required=True)
    p_split.add_argument("--joint-png", type=Path, required=True)
    p_split.add_argument("--out-dir", type=Path, default=Path("runs/n1/gen_v3_joint"))
    p_split.add_argument("--allow-resize-joint", action="store_true")

    p_met = sub.add_parser("metrics", help="overlap equality + generation frontier MAE")
    p_met.add_argument("--plan", type=Path, required=True)
    p_met.add_argument("--tile-a", required=True)
    p_met.add_argument("--tile-b", required=True)
    p_met.add_argument("--tiles-dir", type=Path, required=True)
    p_met.add_argument("--stitched", type=Path, default=None)

    args = ap.parse_args()
    plan = CanvasPlan.load(args.plan)
    by = {t["tile_id"]: t for t in plan.tiles}

    def ab():
        if args.tile_a not in by or args.tile_b not in by:
            raise SystemExit("unknown tile")
        a, b = by[args.tile_a], by[args.tile_b]
        if a["y0"] != b["y0"] or b["x0"] < a["x0"]:
            raise SystemExit("need horizontal A left of B same row")
        return a, b

    if args.cmd == "prep":
        a, b = ab()
        jx0 = min(a["x0"], b["x0"])
        jy0 = min(a["y0"], b["y0"])
        jx1 = max(a["x1"], b["x1"])
        jy1 = max(a["y1"], b["y1"])
        jw, jh = jx1 - jx0, jy1 - jy0
        out = Path(args.out_dir)
        for d in ("guides", "jobs", "tiles", "joint"):
            (out / d).mkdir(parents=True, exist_ok=True)

        guide_meta = None
        if args.global_ref and args.global_ref.is_file():
            base = Image.open(args.global_ref).convert("RGB")
            W, H = plan.width, plan.height
            scale = min(W / base.size[0], H / base.size[1])
            nw, nh = max(1, int(base.size[0] * scale)), max(1, int(base.size[1] * scale))
            xoff, yoff = (W - nw) // 2, (H - nh) // 2
            canvas = Image.new("RGB", (W, H), (16, 16, 16))
            canvas.paste(base.resize((nw, nh), Image.Resampling.LANCZOS), (xoff, yoff))
            joint_guide = canvas.crop((jx0, jy0, jx1, jy1))
            assert joint_guide.size == (jw, jh)
            gpath = out / "guides" / "joint_structure_guide.png"
            joint_guide.save(gpath)
            guide_meta = {
                "path": str(gpath),
                "note": "Lanczos structure hint only — not generation success",
                "fit": "contain",
            }

        job = {
            "format": "ige.native4k.n1_gen_v3_joint_job",
            "format_version": "1.0",
            "mechanism": "joint_AUB_plate",
            "tile_a": args.tile_a,
            "tile_b": args.tile_b,
            "joint_box_canvas": [jx0, jy0, jx1, jy1],
            "joint_wh": [jw, jh],
            "a_box": [a["x0"], a["y0"], a["x1"], a["y1"]],
            "b_box": [b["x0"], b["y0"], b["x1"], b["y1"]],
            "overlap": plan.overlap,
            "scene_lock": args.scene_lock,
            "structure_guide": guide_meta,
            "output_joint_png": str(out / "joint" / "JOINT_PLATE.png"),
            "status": "PENDING_GENERATOR",
            "instructions": (
                f"Generate ONE continuous image covering canvas region [{jx0},{jy0}]-[{jx1},{jy1}] "
                f"size {jw}x{jh} (or higher res same aspect for pack). Same camera across full width. "
                "Do not produce two independent portraits. Then run split."
            ),
            "n1_seam_continuity_ok": False,
            "not_siax_4x_upscale": True,
        }
        (out / "jobs" / "joint_job.json").write_text(json.dumps(job, indent=2) + "\n")
        man = {
            "format": "ige.native4k.n1_gen_v3_kit",
            "status": "JOINT_JOB_READY",
            "joint_wh": [jw, jh],
            "aspect_approx": round(jw / jh, 4),
            "tile_ids": [args.tile_a, args.tile_b],
            "labels": {
                "N1_SEAM_CONTINUITY_OK": False,
                "NATIVE_4K_PILOT_OK": False,
            },
            "baselines": ["v1_independent_FAIL", "v2_POSTGEN_HARDLOCK"],
        }
        (out / "v3_manifest.json").write_text(json.dumps(man, indent=2) + "\n")
        print(json.dumps({**man, "job": job}, indent=2))
        return 0

    if args.cmd == "split":
        a, b = ab()
        jx0 = min(a["x0"], b["x0"])
        jy0 = min(a["y0"], b["y0"])
        jx1 = max(a["x1"], b["x1"])
        jy1 = max(a["y1"], b["y1"])
        jw, jh = jx1 - jx0, jy1 - jy0
        out = Path(args.out_dir)
        (out / "tiles").mkdir(parents=True, exist_ok=True)
        im = Image.open(args.joint_png).convert("RGB")
        gen_wh = im.size
        if im.size != (jw, jh):
            if not args.allow_resize_joint:
                print(json.dumps({"ok": False, "error": "joint_size_mismatch", "got": list(im.size), "expected": [jw, jh]}))
                return 3
            im = im.resize((jw, jh), Image.Resampling.LANCZOS)
        # crop A/B in joint-local coords
        def crop_tile(t):
            lx0, ly0 = t["x0"] - jx0, t["y0"] - jy0
            lx1, ly1 = t["x1"] - jx0, t["y1"] - jy0
            tile = im.crop((lx0, ly0, lx1, ly1))
            exp = (t["x1"] - t["x0"], t["y1"] - t["y0"])
            assert tile.size == exp
            path = out / "tiles" / f"{t['tile_id']}.png"
            tile.save(path)
            return {"tile_id": t["tile_id"], "sha256": sha256(path), "path": str(path), "wh": list(exp)}

        ra, rb = crop_tile(a), crop_tile(b)
        # overlap equality in tile local: B left ov vs A right ov
        ov = plan.overlap
        a_im = Image.open(ra["path"]).convert("RGB")
        b_im = Image.open(rb["path"]).convert("RGB")
        # canvas overlap starts at b.x0; in A local: b.x0 - a.x0
        x_on_a = b["x0"] - a["x0"]
        a_strip = a_im.crop((x_on_a, 0, x_on_a + ov, a_im.size[1]))
        b_strip = b_im.crop((0, 0, ov, b_im.size[1]))
        import numpy as np
        sa = np.asarray(a_strip, dtype=np.float32)
        sb = np.asarray(b_strip, dtype=np.float32)
        overlap_mae = float(np.mean(np.abs(sa - sb)))
        report = {
            "format": "ige.native4k.n1_gen_v3_split",
            "ok": True,
            "joint_gen_wh": list(gen_wh),
            "joint_packed_wh": [jw, jh],
            "tile_a": ra,
            "tile_b": rb,
            "overlap_equality_mae": overlap_mae,
            "note": "joint same capture => overlap_equality should be ~0",
        }
        (out / "split_report.json").write_text(json.dumps(report, indent=2) + "\n")
        print(json.dumps(report, indent=2))
        return 0

    if args.cmd == "metrics":
        a, b = ab()
        import numpy as np
        from PIL import Image as PILImage

        a_im = PILImage.open(Path(args.tiles_dir) / f"{args.tile_a}.png").convert("RGB")
        b_im = PILImage.open(Path(args.tiles_dir) / f"{args.tile_b}.png").convert("RGB")
        ov = plan.overlap
        x_on_a = b["x0"] - a["x0"]
        a_strip = np.asarray(a_im.crop((x_on_a, 0, x_on_a + ov, a_im.size[1])), dtype=np.float32)
        b_strip = np.asarray(b_im.crop((0, 0, ov, b_im.size[1])), dtype=np.float32)
        overlap_equality_mae = float(np.mean(np.abs(a_strip - b_strip)))

        # generation frontier: A last free col vs B first free col
        # free region of B starts at local x=ov (canvas x = b.x0+ov). A at that canvas x: local = b.x0+ov - a.x0
        # For hard-lock B, frontier is at x=a.x1 relative... A ends at a.x1; B free starts b.x0+ov.
        # If a.x1 == b.x0+ov (tile 512, step 448, ov 64: a.x1=2304, b.x0+ov=2304) yes.
        frontier_canvas_x = b["x0"] + ov
        a_local_x = frontier_canvas_x - 1 - a["x0"]  # last A pixel before free B
        b_local_x = ov  # first free B pixel
        if 0 <= a_local_x < a_im.size[0] and b_local_x < b_im.size[1]:
            col_a = np.asarray(a_im)[:, a_local_x].astype(np.float32)
            col_b = np.asarray(b_im)[:, b_local_x].astype(np.float32)
            h = min(len(col_a), len(col_b))
            generation_frontier_mae = float(np.mean(np.abs(col_a[:h] - col_b[:h])))
        else:
            generation_frontier_mae = None

        out = {
            "format": "ige.native4k.n1_seam_metrics_v1",
            "tile_a": args.tile_a,
            "tile_b": args.tile_b,
            "overlap_px": ov,
            "overlap_equality_mae": overlap_equality_mae,
            "generation_frontier_mae": generation_frontier_mae,
            "frontier_canvas_x": frontier_canvas_x,
            "semantic_continuity": "HUMAN_REVIEW_REQUIRED",
            "notes": [
                "overlap_equality ~0 is geometric identity (joint or hard-lock), not model skill",
                "generation_frontier is A last locked/own pixel vs B first free pixel",
                "do not use single adjacent-col MAE as v1-vs-v2 improvement alone",
            ],
        }
        print(json.dumps(out, indent=2))
        return 0

    return 2


if __name__ == "__main__":
    raise SystemExit(main())
