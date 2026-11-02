#!/usr/bin/env python3
"""S2 · rough SPM-logic diagnostics for Siax tile/halo ranking.

SPM (§0.12.39 SIAX 探針匹配) is documented-only full stack.
This is an approximate diagnostic only:
  - probe size defaults 48×64 on BASE coords → 192×256 on 4× output
  - near-seam probes vs interior probes of similar size
  - across-seam MAE, HF residual energy, near/interior HF ratio
  - NOT an acceptance gate; NOT full SPM residual peep match
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
from PIL import Image


def file_sha256(path: Path) -> str:
    import hashlib
    d = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            d.update(chunk)
    return d.hexdigest()


def laplacian_energy(patch: np.ndarray) -> float:
    """Mean abs Laplacian on luminance — rough HF residual proxy."""
    y = patch.astype(np.float32).mean(axis=2)
    # 3x3 laplacian kernel
    c = y[1:-1, 1:-1]
    lap = (
        -4.0 * c
        + y[:-2, 1:-1]
        + y[2:, 1:-1]
        + y[1:-1, :-2]
        + y[1:-1, 2:]
    )
    return float(np.mean(np.abs(lap)))


def edge_mae(a: np.ndarray, b: np.ndarray) -> float:
    return float(np.mean(np.abs(a.astype(np.int16) - b.astype(np.int16))))


def sample_vertical_seam_probes(
    canvas: np.ndarray,
    *,
    seam_x: int,
    probe_h: int,
    probe_w: int,
    n_samples: int,
) -> list[dict]:
    H, W, _ = canvas.shape
    half = probe_w // 2
    if seam_x < half + 1 or seam_x + half + 1 >= W:
        return []
    ys = np.linspace(probe_h, H - probe_h - 1, num=max(n_samples, 1), dtype=int)
    out = []
    for y0 in ys:
        y0 = int(np.clip(y0, 0, H - probe_h))
        left = canvas[y0 : y0 + probe_h, seam_x - half : seam_x]
        right = canvas[y0 : y0 + probe_h, seam_x : seam_x + half]
        if left.shape != right.shape:
            continue
        # 1-px strip MAE across seam
        strip_l = canvas[y0 : y0 + probe_h, seam_x - 1]
        strip_r = canvas[y0 : y0 + probe_h, seam_x]
        band = canvas[y0 : y0 + probe_h, max(0, seam_x - half) : min(W, seam_x + half)]
        out.append(
            {
                "y0": y0,
                "across_strip_mae": edge_mae(strip_l, strip_r),
                "left_right_probe_mae": edge_mae(left, right),
                "band_hf": laplacian_energy(band),
                "left_hf": laplacian_energy(left),
                "right_hf": laplacian_energy(right),
            }
        )
    return out


def sample_horizontal_seam_probes(
    canvas: np.ndarray,
    *,
    seam_y: int,
    probe_h: int,
    probe_w: int,
    n_samples: int,
) -> list[dict]:
    H, W, _ = canvas.shape
    half = probe_h // 2
    if seam_y < half + 1 or seam_y + half + 1 >= H:
        return []
    xs = np.linspace(probe_w, W - probe_w - 1, num=max(n_samples, 1), dtype=int)
    out = []
    for x0 in xs:
        x0 = int(np.clip(x0, 0, W - probe_w))
        top = canvas[seam_y - half : seam_y, x0 : x0 + probe_w]
        bot = canvas[seam_y : seam_y + half, x0 : x0 + probe_w]
        if top.shape != bot.shape:
            continue
        strip_t = canvas[seam_y - 1, x0 : x0 + probe_w]
        strip_b = canvas[seam_y, x0 : x0 + probe_w]
        band = canvas[max(0, seam_y - half) : min(H, seam_y + half), x0 : x0 + probe_w]
        out.append(
            {
                "x0": x0,
                "across_strip_mae": edge_mae(strip_t, strip_b),
                "top_bot_probe_mae": edge_mae(top, bot),
                "band_hf": laplacian_energy(band),
                "top_hf": laplacian_energy(top),
                "bot_hf": laplacian_energy(bot),
            }
        )
    return out


def sample_interior_probes(
    canvas: np.ndarray,
    *,
    tile_out: int,
    pad_out: int,
    probe_h: int,
    probe_w: int,
    n_samples: int,
) -> list[dict]:
    """Probes centered away from tile boundaries by > pad+probe margin."""
    H, W, _ = canvas.shape
    margin = pad_out + max(probe_h, probe_w) + 8
    # candidate centers: tile interiors
    centers = []
    for y0 in range(0, H, tile_out):
        for x0 in range(0, W, tile_out):
            cy = y0 + tile_out // 2
            cx = x0 + tile_out // 2
            if cy - probe_h // 2 < margin or cy + probe_h // 2 >= H - margin:
                continue
            if cx - probe_w // 2 < margin or cx + probe_w // 2 >= W - margin:
                continue
            # distance to nearest vertical/horizontal tile boundary
            vx = min(cx % tile_out, tile_out - (cx % tile_out))
            hy = min(cy % tile_out, tile_out - (cy % tile_out))
            if vx < margin or hy < margin:
                continue
            centers.append((cy, cx))
    if not centers:
        # fallback: random-ish grid
        for cy in np.linspace(margin, H - margin - 1, 4, dtype=int):
            for cx in np.linspace(margin, W - margin - 1, 4, dtype=int):
                centers.append((int(cy), int(cx)))
    rng = np.random.default_rng(42)
    if len(centers) > n_samples:
        idx = rng.choice(len(centers), size=n_samples, replace=False)
        centers = [centers[i] for i in idx]
    out = []
    for cy, cx in centers:
        y0 = int(np.clip(cy - probe_h // 2, 0, H - probe_h))
        x0 = int(np.clip(cx - probe_w // 2, 0, W - probe_w))
        patch = canvas[y0 : y0 + probe_h, x0 : x0 + probe_w]
        out.append({"y0": y0, "x0": x0, "hf": laplacian_energy(patch)})
    return out


def analyze(
    image_path: Path,
    *,
    tile_size: int,
    tile_pad: int,
    scale: int = 4,
    probe_base_h: int = 48,
    probe_base_w: int = 64,
    samples_per_seam: int = 6,
    interior_samples: int = 24,
) -> dict:
    with Image.open(image_path) as im:
        canvas = np.asarray(im.convert("RGB"), dtype=np.uint8)
    H, W, _ = canvas.shape
    if H % scale or W % scale:
        raise ValueError(f"output not multiple of scale: {W}x{H}")
    base_h, base_w = H // scale, W // scale
    tile_out = tile_size * scale
    pad_out = tile_pad * scale
    probe_h = probe_base_h * scale  # 192
    probe_w = probe_base_w * scale  # 256

    grid_w = (base_w + tile_size - 1) // tile_size
    grid_h = (base_h + tile_size - 1) // tile_size

    # classic seam means (same spirit as stitcher)
    v_seams, h_seams = [], []
    for col in range(1, grid_w):
        bx = min(col * tile_size, base_w) * scale
        if 0 < bx < W:
            d = np.abs(canvas[:, bx - 1].astype(np.int16) - canvas[:, bx].astype(np.int16))
            v_seams.append(float(d.mean()))
    for row in range(1, grid_h):
        by = min(row * tile_size, base_h) * scale
        if 0 < by < H:
            d = np.abs(canvas[by - 1].astype(np.int16) - canvas[by].astype(np.int16))
            h_seams.append(float(d.mean()))

    # SPM-style probes
    v_probes, h_probes = [], []
    for col in range(1, grid_w):
        bx = min(col * tile_size, base_w) * scale
        v_probes.extend(
            sample_vertical_seam_probes(
                canvas, seam_x=bx, probe_h=probe_h, probe_w=probe_w, n_samples=samples_per_seam
            )
        )
    for row in range(1, grid_h):
        by = min(row * tile_size, base_h) * scale
        h_probes.extend(
            sample_horizontal_seam_probes(
                canvas, seam_y=by, probe_h=probe_h, probe_w=probe_w, n_samples=samples_per_seam
            )
        )
    interior = sample_interior_probes(
        canvas,
        tile_out=tile_out,
        pad_out=pad_out,
        probe_h=probe_h,
        probe_w=probe_w,
        n_samples=interior_samples,
    )

    def mean_key(items, key):
        vals = [float(x[key]) for x in items if key in x]
        return float(np.mean(vals)) if vals else None

    seam_strip_mae = []
    if v_probes:
        seam_strip_mae.extend(x["across_strip_mae"] for x in v_probes)
    if h_probes:
        seam_strip_mae.extend(x["across_strip_mae"] for x in h_probes)
    seam_band_hf = []
    if v_probes:
        seam_band_hf.extend(x["band_hf"] for x in v_probes)
    if h_probes:
        seam_band_hf.extend(x["band_hf"] for x in h_probes)
    interior_hf = [x["hf"] for x in interior]

    mean_seam_hf = float(np.mean(seam_band_hf)) if seam_band_hf else None
    mean_int_hf = float(np.mean(interior_hf)) if interior_hf else None
    ratio = (
        (mean_seam_hf / mean_int_hf)
        if mean_seam_hf is not None and mean_int_hf and mean_int_hf > 1e-6
        else None
    )

    # composite rank score: lower better (diagnostic only)
    # weight: strip MAE + excess HF at seam
    strip_m = float(np.mean(seam_strip_mae)) if seam_strip_mae else 999.0
    excess_hf = (ratio - 1.0) if ratio is not None else 0.0
    rank_score = strip_m + 10.0 * max(0.0, excess_hf)

    return {
        "status": "diagnostic_only_spm_approx_not_acceptance",
        "spm_note": "Rough SPM-logic probes only. Full §0.12.39 residual peep match NOT imported.",
        "image": str(image_path),
        "sha256": file_sha256(image_path),
        "output_dims": {"width": W, "height": H},
        "tile_size": tile_size,
        "tile_pad": tile_pad,
        "grid": [grid_w, grid_h],
        "probe_base_px": [probe_base_h, probe_base_w],
        "probe_out_px": [probe_h, probe_w],
        "classic_seam": {
            "vertical_mean_abs_boundary_delta": float(np.mean(v_seams)) if v_seams else None,
            "horizontal_mean_abs_boundary_delta": float(np.mean(h_seams)) if h_seams else None,
            "vertical_count": len(v_seams),
            "horizontal_count": len(h_seams),
        },
        "spm_probes": {
            "vertical_probe_count": len(v_probes),
            "horizontal_probe_count": len(h_probes),
            "interior_probe_count": len(interior),
            "mean_across_seam_strip_mae": float(np.mean(seam_strip_mae)) if seam_strip_mae else None,
            "p95_across_seam_strip_mae": float(np.percentile(seam_strip_mae, 95)) if seam_strip_mae else None,
            "mean_near_seam_band_hf": mean_seam_hf,
            "mean_interior_hf": mean_int_hf,
            "near_seam_over_interior_hf_ratio": ratio,
            "mean_vertical_left_right_probe_mae": mean_key(v_probes, "left_right_probe_mae"),
            "mean_horizontal_top_bot_probe_mae": mean_key(h_probes, "top_bot_probe_mae"),
        },
        "rank_score_lower_better": round(rank_score, 4),
        "interpretation": {
            "strip_mae": "1px across-seam absolute RGB mean; lower → softer boundary jump",
            "hf_ratio": "near-seam / interior Laplacian energy; ~1.0 preferred; >>1 may mark seam emphasis or >1 detail",
            "rank_score": "strip_mae + 10*max(0, hf_ratio-1); lower better; diagnostic only",
            "do_not": "Do not treat as final_acceptance or identity/topology gold",
        },
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--image", type=Path, required=True)
    ap.add_argument("--tile-size", type=int, required=True)
    ap.add_argument("--tile-pad", type=int, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--probe-h", type=int, default=48)
    ap.add_argument("--probe-w", type=int, default=64)
    args = ap.parse_args()
    report = analyze(
        args.image,
        tile_size=args.tile_size,
        tile_pad=args.tile_pad,
        probe_base_h=args.probe_h,
        probe_base_w=args.probe_w,
    )
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
