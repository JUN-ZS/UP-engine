#!/usr/bin/env python3
"""SPM-A candidate evaluation on an existing 4x PNG (S2.1.5).

Does NOT re-run Siax. Crops the candidate at fixed BASE probe boxes * 4,
compares residual vs Lanczos upscale of the same BASE crop.

Optional --reference-spm-a: P0 fingerprint report for per-probe delta distribution
(reference only — not a pass/fail gate).
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
from PIL import Image, ImageOps


def file_sha(p: Path) -> str:
    d = hashlib.sha256()
    with p.open("rb") as f:
        for c in iter(lambda: f.read(1 << 20), b""):
            d.update(c)
    return d.hexdigest()


def laplacian_energy(y: np.ndarray) -> float:
    c = y[1:-1, 1:-1]
    lap = (-4 * c + y[:-2, 1:-1] + y[2:, 1:-1] + y[1:-1, :-2] + y[1:-1, 2:])
    return float(np.mean(np.abs(lap)))


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--base", type=Path, required=True)
    ap.add_argument("--candidate", type=Path, required=True)
    ap.add_argument("--bank", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--expected-sha256", type=str, default="")
    ap.add_argument("--reference-spm-a", type=Path, default=None,
                    help="optional P0 probe residual report for per-probe delta reference")
    ap.add_argument("--scale", type=int, default=4)
    args = ap.parse_args()

    if args.scale != 4:
        raise SystemExit("only scale=4 supported")

    cand_sha = file_sha(args.candidate)
    if args.expected_sha256 and cand_sha != args.expected_sha256:
        raise SystemExit(f"candidate sha mismatch: got {cand_sha}, expected {args.expected_sha256}")

    bank = json.loads(args.bank.read_text())
    probes = bank["probes"]
    probe_hw = bank.get("probe_hw") or [64, 48]  # [w,h] or [h,w]? bank says 48x64 probes in docs
    # bank probe_hw from builder
    with Image.open(args.base) as im:
        base = ImageOps.exif_transpose(im).convert("RGB")
    bw, bh = base.size
    with Image.open(args.candidate) as im:
        cand = im.convert("RGB")
    cw, ch = cand.size
    if cw != bw * args.scale or ch != bh * args.scale:
        raise SystemExit(f"candidate {cw}x{ch} != base {bw}x{bh} * {args.scale}")

    ref_by_id = {}
    if args.reference_spm_a and args.reference_spm_a.is_file():
        ref = json.loads(args.reference_spm_a.read_text())
        for row in ref.get("probes") or []:
            ref_by_id[row["probe_id"]] = row

    rows = []
    for pr in probes:
        x0, y0, x1, y1 = [int(v) for v in pr["box_base"]]
        if x0 < 0 or y0 < 0 or x1 > bw or y1 > bh or x1 <= x0 or y1 <= y0:
            raise SystemExit(f"bad probe box {pr['probe_id']}: {pr['box_base']}")
        crop = base.crop((x0, y0, x1, y1))
        lanc = crop.resize((crop.size[0] * args.scale, crop.size[1] * args.scale), Image.Resampling.LANCZOS)
        ox0, oy0, ox1, oy1 = x0 * args.scale, y0 * args.scale, x1 * args.scale, y1 * args.scale
        cand_crop = cand.crop((ox0, oy0, ox1, oy1))
        pred_u8 = np.asarray(cand_crop, dtype=np.uint8)
        lanc_u8 = np.asarray(lanc, dtype=np.uint8)
        if pred_u8.shape != lanc_u8.shape:
            raise SystemExit(f"{pr['probe_id']} shape {pred_u8.shape} vs {lanc_u8.shape}")
        residual = pred_u8.astype(np.int16) - lanc_u8.astype(np.int16)
        y_res = residual.astype(np.float32).mean(axis=2)
        y_pred = pred_u8.astype(np.float32).mean(axis=2)
        row = {
            "probe_id": pr["probe_id"],
            "kind": pr.get("kind"),
            "box_base": pr["box_base"],
            "box_hires": [ox0, oy0, ox1, oy1],
            "mae_residual_vs_lanczos": float(np.mean(np.abs(residual))),
            "p95_abs_residual": float(np.percentile(np.abs(residual), 95)),
            "residual_hf": laplacian_energy(y_res),
            "candidate_hf": laplacian_energy(y_pred),
            "patch_sha256_prefix": hashlib.sha256(pred_u8.tobytes()).hexdigest()[:16],
        }
        if pr["probe_id"] in ref_by_id:
            r0 = ref_by_id[pr["probe_id"]]
            row["ref_mae_residual_vs_lanczos"] = r0.get("mae_residual_vs_lanczos")
            row["delta_mae_vs_ref_fingerprint"] = (
                row["mae_residual_vs_lanczos"] - float(r0["mae_residual_vs_lanczos"])
                if r0.get("mae_residual_vs_lanczos") is not None
                else None
            )
            row["ref_note"] = "P0 single-forward probe fingerprint; context may differ from nested child"
        rows.append(row)

    maes = [r["mae_residual_vs_lanczos"] for r in rows]
    hfs = [r["residual_hf"] for r in rows]
    deltas = [r["delta_mae_vs_ref_fingerprint"] for r in rows if r.get("delta_mae_vs_ref_fingerprint") is not None]

    report = {
        "program": "SIAX_S2_1_P1_SPM_A_CANDIDATE",
        "method": "crop_candidate_4x_at_fixed_probes_vs_lanczos_base; no re-inference",
        "bank_sha256": bank.get("bank_sha256"),
        "n_probes": len(rows),
        "base_sha256": file_sha(args.base),
        "candidate_path": str(args.candidate.resolve()),
        "candidate_sha256": cand_sha,
        "candidate_dimensions": [cw, ch],
        "summary": {
            "mae_residual_p50": float(np.median(maes)),
            "mae_residual_p95": float(np.percentile(maes, 95)),
            "residual_hf_p50": float(np.median(hfs)),
            "residual_hf_p95": float(np.percentile(hfs, 95)),
        },
        "reference_fingerprint": {
            "path": str(args.reference_spm_a) if args.reference_spm_a else None,
            "delta_mae_p50": float(np.median(deltas)) if deltas else None,
            "delta_mae_p95": float(np.percentile(deltas, 95)) if deltas else None,
            "n_matched": len(deltas),
            "use": "distribution reference only; not pass/fail gate",
        },
        "probes": rows,
        "quality_qualified": False,
        "final_acceptance": False,
        "note": (
            "Candidate SPM-A on Nested primary only. "
            "Not identity/topology. Not original 256/32 single-forward claim. "
            "P0 ref deltas are advisory (different model context)."
        ),
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n")
    print(json.dumps({"summary": report["summary"], "reference_fingerprint": report["reference_fingerprint"], "candidate_sha256": cand_sha}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
