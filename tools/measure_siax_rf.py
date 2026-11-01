#!/usr/bin/env python3
"""Measure Siax effective context / edge influence for Nested Compute (P1).

Method (OBSERVED diagnostics, not theoretical RF formula):
  1) Context sweep: fixed core C on BASE; vary margin m; compare core 4x output
     against a large-margin reference. MAE vs m → required compute_context.
  2) Shift overlap: two windows shifted by s px; compare aligned overlap interior.

final_acceptance always false.
"""
from __future__ import annotations

import argparse
import gc
import json
import os
import time
from pathlib import Path

import numpy as np
from PIL import Image, ImageOps


def rss_mb() -> float:
    try:
        for line in Path("/proc/self/status").read_text().splitlines():
            if line.startswith("VmRSS:"):
                return int(line.split()[1]) / 1024.0
    except OSError:
        pass
    return 0.0


def run_core(
    descriptor,
    torch,
    base_rgb: np.ndarray,
    *,
    x0: int,
    y0: int,
    x1: int,
    y1: int,
    margin: int,
) -> np.ndarray:
    """Upscale core [x0:x1,y0:y1] with margin context; return uint8 core at 4x."""
    h, w, _ = base_rgb.shape
    ex0, ey0 = max(0, x0 - margin), max(0, y0 - margin)
    ex1, ey1 = min(w, x1 + margin), min(h, y1 + margin)
    crop = base_rgb[ey0:ey1, ex0:ex1]
    arr = crop.astype(np.float32) / 255.0
    tensor = torch.from_numpy(arr).permute(2, 0, 1).unsqueeze(0)
    with torch.inference_mode():
        out = descriptor(tensor).float().cpu()
    pred = out[0].permute(1, 2, 0).numpy()
    pred_u8 = np.clip(pred * 255.0 + 0.5, 0, 255).astype(np.uint8)
    # extract core relative to expanded crop
    left = (x0 - ex0) * 4
    top = (y0 - ey0) * 4
    right = left + (x1 - x0) * 4
    bottom = top + (y1 - y0) * 4
    core = pred_u8[top:bottom, left:right].copy()
    del tensor, out, pred, pred_u8
    return core


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", type=Path, required=True)
    ap.add_argument("--checkpoint", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--core", type=int, default=64, help="compute core side on BASE")
    ap.add_argument("--margins", default="0,8,16,24,32,40,48,64")
    ap.add_argument("--device", default="cpu")
    ap.add_argument("--centers", default="", help="optional cy,cx;cy,cx list")
    args = ap.parse_args()

    os.environ.setdefault("OMP_NUM_THREADS", "1")
    os.environ.setdefault("MKL_NUM_THREADS", "1")
    os.environ.setdefault("TORCH_NUM_THREADS", "1")

    import torch
    from spandrel import ImageModelDescriptor, ModelLoader
    from ige.upscale.siax import MODEL_SHA256, file_sha256

    torch.set_num_threads(1)
    if file_sha256(args.checkpoint) != MODEL_SHA256:
        raise SystemExit("checkpoint hash mismatch")

    with Image.open(args.base) as im:
        base = np.asarray(ImageOps.exif_transpose(im).convert("RGB"), dtype=np.uint8)
    H, W, _ = base.shape
    C = args.core
    margins = [int(x) for x in args.margins.split(",") if x.strip() != ""]
    margins = sorted(set(margins))
    ref_m = max(margins)

    if args.centers.strip():
        centers = []
        for part in args.centers.split(";"):
            cy, cx = part.split(",")
            centers.append((int(cy), int(cx)))
    else:
        # three fixed centers: mid, upper-left detail-ish, lower-right
        centers = [
            (H // 2, W // 2),
            (H // 3, W // 3),
            (2 * H // 3, 2 * W // 3),
        ]

    t0 = time.perf_counter()
    desc = ModelLoader(device=args.device).load_from_file(str(args.checkpoint))
    if not isinstance(desc, ImageModelDescriptor) or int(desc.scale) != 4:
        raise SystemExit("bad model")
    desc.eval()
    load_s = time.perf_counter() - t0
    model_rss = rss_mb()

    center_reports = []
    for cy, cx in centers:
        x0 = max(0, min(W - C, cx - C // 2))
        y0 = max(0, min(H - C, cy - C // 2))
        x1, y1 = x0 + C, y0 + C
        # need room for ref margin
        if x0 < ref_m or y0 < ref_m or x1 + ref_m > W or y1 + ref_m > H:
            # shift inward
            x0 = max(ref_m, min(W - C - ref_m, x0))
            y0 = max(ref_m, min(H - C - ref_m, y0))
            x1, y1 = x0 + C, y0 + C

        print(f"center core=({x0},{y0})-({x1},{y1}) ref_m={ref_m}", flush=True)
        ref = run_core(desc, torch, base, x0=x0, y0=y0, x1=x1, y1=y1, margin=ref_m)
        rows = []
        for m in margins:
            gc.collect()
            t1 = time.perf_counter()
            core = run_core(desc, torch, base, x0=x0, y0=y0, x1=x1, y1=y1, margin=m)
            wall = time.perf_counter() - t1
            if core.shape != ref.shape:
                raise SystemExit(f"shape {core.shape} vs {ref.shape}")
            mae = float(np.mean(np.abs(core.astype(np.int16) - ref.astype(np.int16))))
            # border vs interior mae (outer 4px ring vs inner)
            bh = min(8, core.shape[0] // 4)
            if bh > 0 and core.shape[0] > 2 * bh:
                border = np.concatenate(
                    [
                        np.abs(core[:bh].astype(np.int16) - ref[:bh].astype(np.int16)).ravel(),
                        np.abs(core[-bh:].astype(np.int16) - ref[-bh:].astype(np.int16)).ravel(),
                        np.abs(core[:, :bh].astype(np.int16) - ref[:, :bh].astype(np.int16)).ravel(),
                        np.abs(core[:, -bh:].astype(np.int16) - ref[:, -bh:].astype(np.int16)).ravel(),
                    ]
                )
                inner = np.abs(
                    core[bh:-bh, bh:-bh].astype(np.int16) - ref[bh:-bh, bh:-bh].astype(np.int16)
                )
                border_mae = float(np.mean(border))
                inner_mae = float(np.mean(inner))
            else:
                border_mae = mae
                inner_mae = mae
            rows.append(
                {
                    "margin": m,
                    "mae_vs_ref": mae,
                    "border_mae_vs_ref": border_mae,
                    "inner_mae_vs_ref": inner_mae,
                    "wall_s": round(wall, 3),
                    "rss_mb": round(rss_mb(), 2),
                    "input_wh": [ (x1 - x0) + 2 * m, (y1 - y0) + 2 * m ],
                }
            )
            print(f"  m={m} mae={mae:.4f} inner={inner_mae:.4f} border={border_mae:.4f}", flush=True)
            del core
            gc.collect()

        # recommend smallest m where mae <= 0.5 and <= 1.05 * min_mae (or mae < 0.25)
        maes = [(r["margin"], r["mae_vs_ref"]) for r in rows if r["margin"] < ref_m]
        min_mae = min((r["mae_vs_ref"] for r in rows if r["margin"] < ref_m), default=0.0)
        # also relative to almost-ref
        rec = None
        for r in rows:
            if r["margin"] >= ref_m:
                continue
            if r["mae_vs_ref"] <= max(0.35, min_mae * 1.1) and r["inner_mae_vs_ref"] <= max(0.35, min_mae * 1.1):
                rec = r["margin"]
                break
        if rec is None:
            # fallback: first m with mae < 1.0
            for r in rows:
                if r["margin"] < ref_m and r["mae_vs_ref"] < 1.0:
                    rec = r["margin"]
                    break
        center_reports.append(
            {
                "center_xy": [x0 + C // 2, y0 + C // 2],
                "core_box": [x0, y0, x1, y1],
                "ref_margin": ref_m,
                "rows": rows,
                "recommended_compute_context": rec,
                "min_mae_vs_ref_nonref": min_mae,
            }
        )
        del ref
        gc.collect()

    recs = [c["recommended_compute_context"] for c in center_reports if c["recommended_compute_context"] is not None]
    recommended = int(max(recs)) if recs else None

    # shift overlap test at recommended or 32
    shift_m = recommended if recommended is not None else 32
    shift_reports = []
    cy, cx = centers[0]
    x0 = max(shift_m + 16, min(W - C - shift_m - 16, cx - C // 2))
    y0 = max(shift_m + 16, min(H - C - shift_m - 16, cy - C // 2))
    x1, y1 = x0 + C, y0 + C
    for shift in (8, 16, 32):
        if x1 + shift + shift_m > W:
            continue
        a = run_core(desc, torch, base, x0=x0, y0=y0, x1=x1, y1=y1, margin=shift_m)
        b = run_core(
            desc, torch, base, x0=x0 + shift, y0=y0, x1=x1 + shift, y1=y1, margin=shift_m
        )
        # overlap in output space: a right part vs b left part
        ov = (C - shift) * 4
        if ov <= 8:
            continue
        a_ov = a[:, shift * 4 :]
        b_ov = b[:, :ov]
        # use interior of overlap
        pad = 4
        if a_ov.shape[1] > 2 * pad:
            a_i = a_ov[:, pad:-pad]
            b_i = b_ov[:, pad:-pad]
        else:
            a_i, b_i = a_ov, b_ov
        mae = float(np.mean(np.abs(a_i.astype(np.int16) - b_i.astype(np.int16))))
        shift_reports.append({"shift_base_px": shift, "margin": shift_m, "overlap_mae": mae})
        print(f"shift={shift} overlap_mae={mae:.4f}", flush=True)
        del a, b, a_ov, b_ov
        gc.collect()

    report = {
        "program": "SIAX_S2_1_P1_RF_MEASURE",
        "final_acceptance": False,
        "core": C,
        "margins": margins,
        "model_load_s": round(load_s, 3),
        "model_rss_mb": round(model_rss, 2),
        "centers": center_reports,
        "recommended_compute_context": recommended,
        "shift_overlap": shift_reports,
        "guidance": {
            "logical_256_32": {
                "logical_core": 256,
                "logical_halo": 32,
                "suggested_compute_core": C,
                "suggested_compute_context": recommended,
                "note": "Nested cell is a NEW config id; not auto-equivalent to single-forward 256/32.",
            }
        },
        "evidence_grade": "OBSERVED",
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({"recommended_compute_context": recommended, "shifts": shift_reports}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
