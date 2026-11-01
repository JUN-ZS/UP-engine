#!/usr/bin/env python3
"""Matched seam vs non-seam controls with FIXED sample geometry across tile cells (P0)."""
from __future__ import annotations
import argparse, json
from pathlib import Path
import numpy as np
from PIL import Image

def edge_mae(a, b):
    return float(np.mean(np.abs(a.astype(np.int16) - b.astype(np.int16))))

def lap_energy(patch):
    y = patch.astype(np.float32).mean(axis=2)
    c = y[1:-1, 1:-1]
    lap = -4*c + y[:-2,1:-1] + y[2:,1:-1] + y[1:-1,:-2] + y[1:-1,2:]
    return float(np.mean(np.abs(lap)))

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--image', type=Path, required=True)
    ap.add_argument('--tile-size', type=int, required=True)
    ap.add_argument('--tile-pad', type=int, required=True)
    ap.add_argument('--base-w', type=int, default=1792)
    ap.add_argument('--base-h', type=int, default=1008)
    ap.add_argument('--out', type=Path, required=True)
    ap.add_argument('--samples-per-seam', type=int, default=8)
    args = ap.parse_args()

    scale = 4
    with Image.open(args.image) as im:
        canvas = np.asarray(im.convert('RGB'), dtype=np.uint8)
    H, W, _ = canvas.shape
    assert W == args.base_w * scale and H == args.base_h * scale

    tile = args.tile_size
    pad = args.tile_pad
    grid_w = (args.base_w + tile - 1) // tile
    grid_h = (args.base_h + tile - 1) // tile
    tile_out = tile * scale
    # FIXED sample fractions along each seam (same for all configs)
    fracs = np.linspace(0.12, 0.88, args.samples_per_seam)

    # control offset: mid-tile interior in output pixels, away from boundaries
    control_off = max(tile_out // 2, pad * scale * 4 + 32)

    v_pairs = []
    for col in range(1, grid_w):
        seam_x = min(col * tile, args.base_w) * scale
        for f in fracs:
            y = int(f * (H - 1))
            y0 = max(0, min(H - 64, y - 32))
            # seam strip
            strip_l = canvas[y0:y0+64, seam_x-1]
            strip_r = canvas[y0:y0+64, seam_x]
            band = canvas[y0:y0+64, max(0, seam_x-32):min(W, seam_x+32)]
            # control: same y, shifted into tile interior left
            cx = seam_x - control_off
            if cx < 33 or cx >= W - 33:
                cx = seam_x + control_off
            if cx < 33 or cx >= W - 33:
                continue
            c_l = canvas[y0:y0+64, cx-1]
            c_r = canvas[y0:y0+64, cx]
            c_band = canvas[y0:y0+64, cx-32:cx+32]
            v_pairs.append({
                'seam_x': seam_x, 'y0': y0, 'control_x': cx,
                'seam_strip_mae': edge_mae(strip_l, strip_r),
                'control_strip_mae': edge_mae(c_l, c_r),
                'seam_band_hf': lap_energy(band),
                'control_band_hf': lap_energy(c_band),
            })

    h_pairs = []
    for row in range(1, grid_h):
        seam_y = min(row * tile, args.base_h) * scale
        for f in fracs:
            x = int(f * (W - 1))
            x0 = max(0, min(W - 64, x - 32))
            strip_t = canvas[seam_y-1, x0:x0+64]
            strip_b = canvas[seam_y, x0:x0+64]
            band = canvas[max(0, seam_y-32):min(H, seam_y+32), x0:x0+64]
            cy = seam_y - control_off
            if cy < 33 or cy >= H - 33:
                cy = seam_y + control_off
            if cy < 33 or cy >= H - 33:
                continue
            c_t = canvas[cy-1, x0:x0+64]
            c_b = canvas[cy, x0:x0+64]
            c_band = canvas[cy-32:cy+32, x0:x0+64]
            h_pairs.append({
                'seam_y': seam_y, 'x0': x0, 'control_y': cy,
                'seam_strip_mae': edge_mae(strip_t, strip_b),
                'control_strip_mae': edge_mae(c_t, c_b),
                'seam_band_hf': lap_energy(band),
                'control_band_hf': lap_energy(c_band),
            })

    def summarize(pairs, prefix):
        if not pairs:
            return None
        s_mae = [p['seam_strip_mae'] for p in pairs]
        c_mae = [p['control_strip_mae'] for p in pairs]
        s_hf = [p['seam_band_hf'] for p in pairs]
        c_hf = [p['control_band_hf'] for p in pairs]
        excess_mae = [a - b for a, b in zip(s_mae, c_mae)]
        return {
            f'{prefix}_n': len(pairs),
            f'{prefix}_seam_strip_mae_p50': float(np.median(s_mae)),
            f'{prefix}_seam_strip_mae_p95': float(np.percentile(s_mae, 95)),
            f'{prefix}_control_strip_mae_p50': float(np.median(c_mae)),
            f'{prefix}_excess_strip_mae_p50': float(np.median(excess_mae)),
            f'{prefix}_excess_strip_mae_p95': float(np.percentile(excess_mae, 95)),
            f'{prefix}_seam_hf_p50': float(np.median(s_hf)),
            f'{prefix}_control_hf_p50': float(np.median(c_hf)),
            f'{prefix}_hf_excess_p50': float(np.median([a - b for a, b in zip(s_hf, c_hf)])),
        }

    vsum = summarize(v_pairs, 'v') or {}
    hsum = summarize(h_pairs, 'h') or {}
    # composite diagnostic (not acceptance): higher excess → worse seam vs control
    excess_all = []
    for p in v_pairs:
        excess_all.append(p['seam_strip_mae'] - p['control_strip_mae'])
    for p in h_pairs:
        excess_all.append(p['seam_strip_mae'] - p['control_strip_mae'])
    rank = float(np.median(excess_all)) if excess_all else None
    rank_p95 = float(np.percentile(excess_all, 95)) if excess_all else None

    report = {
        'program': 'SIAX_S2_1_P0_SEAM_CONTROLS',
        'tile_size': args.tile_size,
        'tile_pad': args.tile_pad,
        'image': str(args.image),
        'sample_fracs': list(map(float, fracs)),
        'control_offset_px': control_off,
        'vertical': vsum,
        'horizontal': hsum,
        'matched_excess_strip_mae_p50': rank,
        'matched_excess_strip_mae_p95': rank_p95,
        'n_pairs': len(v_pairs) + len(h_pairs),
        'final_acceptance': False,
        'note': 'Matched seam vs non-seam controls with fixed fracs. Natural edges still possible; excess p50 is diagnostic only.',
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps({k: report[k] for k in report if k not in ('vertical', 'horizontal')}, indent=2))

if __name__ == '__main__':
    main()
