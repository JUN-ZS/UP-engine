#!/usr/bin/env python3
"""N1.gen v2: build A-locked continuation kit for tile B.

Given plan, pair indices or tile ids, and an existing A tile PNG (frozen):
  - write overlap anchor strip from A's right
  - write B canvas with left overlap pre-pasted from A (mask guide)
  - write job JSON for B continuation (PENDING_GENERATOR)

Does not claim seam PASS. Does not regenerate A.
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
    ap.add_argument("--tile-a", required=True)
    ap.add_argument("--tile-b", required=True)
    ap.add_argument("--tile-a-png", type=Path, required=True, help="frozen A output (exact expect_wh)")
    ap.add_argument("--out-dir", type=Path, default=Path("runs/n1/gen_v2"))
    ap.add_argument("--global-ref", type=Path, default=None)
    args = ap.parse_args()

    plan = CanvasPlan.load(args.plan)
    by = {t["tile_id"]: t for t in plan.tiles}
    if args.tile_a not in by or args.tile_b not in by:
        raise SystemExit("unknown tile id")
    a, b = by[args.tile_a], by[args.tile_b]
    if a["y0"] != b["y0"] or b["x0"] < a["x0"]:
        raise SystemExit("v2 horizontal: B must be right of A on same row")

    ov = plan.overlap
    aw, ah = a["x1"] - a["x0"], a["y1"] - a["y0"]
    bw, bh = b["x1"] - b["x0"], b["y1"] - b["y0"]

    a_im = Image.open(args.tile_a_png).convert("RGB")
    if a_im.size != (aw, ah):
        raise SystemExit(f"A png size {a_im.size} != expect {(aw, ah)}")

    # overlap in canvas: region [b.x0, b.x0+ov) should match A's right strip at same canvas x
    # In A local coords, canvas x maps to local x = canvas_x - a.x0
    # strip on A: x from (b.x0 - a.x0) to (b.x0 - a.x0 + ov)
    x_on_a0 = b["x0"] - a["x0"]
    x_on_a1 = x_on_a0 + ov
    if x_on_a0 < 0 or x_on_a1 > aw:
        raise SystemExit(f"overlap strip not fully inside A local: {x_on_a0}:{x_on_a1} aw={aw}")

    strip = a_im.crop((x_on_a0, 0, x_on_a1, ah))
    out = Path(args.out_dir)
    (out / "anchors").mkdir(parents=True, exist_ok=True)
    (out / "guides").mkdir(parents=True, exist_ok=True)
    (out / "jobs").mkdir(parents=True, exist_ok=True)
    (out / "tiles").mkdir(parents=True, exist_ok=True)

    strip_path = out / "anchors" / f"{args.tile_a}_right_overlap_{ov}px.png"
    strip.save(strip_path)

    # B guide: black canvas, paste strip on left 0:ov
    guide = Image.new("RGB", (bw, bh), (20, 20, 24))
    # optional: paste global-ref crop of B region under free area for layout (not as success)
    if args.global_ref and args.global_ref.is_file():
        base = Image.open(args.global_ref).convert("RGB")
        W, H = plan.width, plan.height
        scale = min(W / base.size[0], H / base.size[1])
        nw, nh = max(1, int(base.size[0] * scale)), max(1, int(base.size[1] * scale))
        xoff, yoff = (W - nw) // 2, (H - nh) // 2
        canvas = Image.new("RGB", (W, H), (16, 16, 16))
        canvas.paste(base.resize((nw, nh), Image.Resampling.LANCZOS), (xoff, yoff))
        b_ref = canvas.crop((b["x0"], b["y0"], b["x1"], b["y1"]))
        guide.paste(b_ref, (0, 0))
    guide.paste(strip, (0, 0))  # lock left overlap from A
    guide_path = out / "guides" / f"{args.tile_b}_continuation_guide.png"
    guide.save(guide_path)

    # mask: white = free (generate), black = locked
    mask = Image.new("L", (bw, bh), 255)
    from PIL import ImageDraw
    ImageDraw.Draw(mask).rectangle([0, 0, ov - 1, bh - 1], fill=0)
    mask_path = out / "guides" / f"{args.tile_b}_mask.png"
    mask.save(mask_path)

    # freeze A into tiles dir for stitch later
    a_out = out / "tiles" / f"{args.tile_a}.png"
    a_im.save(a_out)

    job_b = {
        "format": "ige.native4k.n1_gen_v2_continuation_job",
        "format_version": "1.0",
        "mechanism": "neighbor_conditioned_continuation",
        "tile_a": args.tile_a,
        "tile_b": args.tile_b,
        "tile_a_sha256": sha256(args.tile_a_png),
        "overlap_px": ov,
        "anchor_strip": str(strip_path),
        "guide": str(guide_path),
        "mask": str(mask_path),
        "expect_wh": [bw, bh],
        "locked_left_band": [0, 0, ov, bh],
        "output_tile_png": str(out / "tiles" / f"{args.tile_b}.png"),
        "status": "PENDING_GENERATOR",
        "instructions": (
            "Generate tile B at expect_wh. Left overlap band must match anchor strip from frozen A. "
            "Prefer inpaint/outpaint with mask (black=locked). Do not independently recompose B from BASE only. "
            "Do not regenerate A."
        ),
        "n1_seam_continuity_ok": False,
        "not_siax_4x_upscale": True,
    }
    (out / "jobs" / f"{args.tile_b}_continuation.json").write_text(
        json.dumps(job_b, indent=2) + "\n", encoding="utf-8"
    )

    man = {
        "format": "ige.native4k.n1_gen_v2_kit",
        "status": "A_FROZEN_B_PENDING",
        "tile_a": args.tile_a,
        "tile_b": args.tile_b,
        "tile_a_sha256": job_b["tile_a_sha256"],
        "baseline_seam": "N1_GEN_DUAL_HERE independent gen FAIL",
        "labels": {
            "N1_GEN_PILOT_OK": "limited_pass_v1",
            "N1_SEAM_CONTINUITY_OK": False,
            "NATIVE_4K_PILOT_OK": False,
        },
        "stitch_cmd": (
            f"python tools/n1_stitch.py --plan {args.plan} --tiles-dir {out / 'tiles'} "
            f"--require-tiles {args.tile_a},{args.tile_b} --run-id v2 "
            f"--out {out / 'OUT_DUAL.png'}"
        ),
    }
    (out / "v2_manifest.json").write_text(json.dumps(man, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(man, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
