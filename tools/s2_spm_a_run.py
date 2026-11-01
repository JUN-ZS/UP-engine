#!/usr/bin/env python3
"""SPM-A: real Siax 4x on fixed 48x64 probes vs Lanczos base (P0).

This is true residual fingerprint path for probes — NOT full-frame acceptance.
"""
from __future__ import annotations
import argparse, json, os, time
from pathlib import Path
import numpy as np
from PIL import Image, ImageOps

def file_sha(p: Path) -> str:
    import hashlib
    d = hashlib.sha256()
    with p.open('rb') as f:
        for c in iter(lambda: f.read(1 << 20), b''):
            d.update(c)
    return d.hexdigest()

def laplacian_energy(y: np.ndarray) -> float:
    c = y[1:-1, 1:-1]
    lap = (-4 * c + y[:-2, 1:-1] + y[2:, 1:-1] + y[1:-1, :-2] + y[1:-1, 2:])
    return float(np.mean(np.abs(lap)))

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--base', type=Path, required=True)
    ap.add_argument('--bank', type=Path, required=True)
    ap.add_argument('--checkpoint', type=Path, required=True)
    ap.add_argument('--out', type=Path, required=True)
    ap.add_argument('--device', default='cpu')
    ap.add_argument('--limit', type=int, default=0, help='0=all probes')
    args = ap.parse_args()

    os.environ.setdefault('OMP_NUM_THREADS', '1')
    os.environ.setdefault('MKL_NUM_THREADS', '1')
    os.environ.setdefault('TORCH_NUM_THREADS', '1')

    import torch
    from spandrel import ImageModelDescriptor, ModelLoader
    from ige.upscale.siax import MODEL_SHA256, file_sha256

    torch.set_num_threads(1)
    if file_sha256(args.checkpoint) != MODEL_SHA256:
        raise SystemExit('checkpoint hash mismatch')

    bank = json.loads(args.bank.read_text())
    probes = bank['probes']
    if args.limit:
        probes = probes[: args.limit]

    with Image.open(args.base) as im:
        base = ImageOps.exif_transpose(im).convert('RGB')

    t0 = time.perf_counter()
    desc = ModelLoader(device=args.device).load_from_file(str(args.checkpoint))
    if not isinstance(desc, ImageModelDescriptor) or int(desc.scale) != 4:
        raise SystemExit('bad model')
    desc.eval()
    load_s = time.perf_counter() - t0

    rows = []
    with torch.inference_mode():
        for pr in probes:
            x0, y0, x1, y1 = pr['box_base']
            crop = base.crop((x0, y0, x1, y1))
            # Lanczos 4x reference
            lanc = crop.resize((crop.size[0] * 4, crop.size[1] * 4), Image.Resampling.LANCZOS)
            arr = np.asarray(crop, dtype=np.float32) / 255.0
            tensor = torch.from_numpy(arr).permute(2, 0, 1).unsqueeze(0)
            t1 = time.perf_counter()
            out = desc(tensor).float().cpu()
            wall = time.perf_counter() - t1
            pred = out[0].permute(1, 2, 0).numpy()
            pred_u8 = np.clip(pred * 255.0 + 0.5, 0, 255).astype(np.uint8)
            lanc_u8 = np.asarray(lanc, dtype=np.uint8)
            if pred_u8.shape != lanc_u8.shape:
                raise SystemExit(f"shape mismatch {pred_u8.shape} vs {lanc_u8.shape}")
            residual = pred_u8.astype(np.int16) - lanc_u8.astype(np.int16)
            y_res = residual.astype(np.float32).mean(axis=2)
            y_pred = pred_u8.astype(np.float32).mean(axis=2)
            row = {
                'probe_id': pr['probe_id'],
                'kind': pr['kind'],
                'box_base': pr['box_base'],
                'forward_wall_s': round(wall, 4),
                'mae_residual_vs_lanczos': float(np.mean(np.abs(residual))),
                'p95_abs_residual': float(np.percentile(np.abs(residual), 95)),
                'residual_hf': laplacian_energy(y_res),
                'siax_hf': laplacian_energy(y_pred),
                'output_sha256_prefix': __import__('hashlib').sha256(pred_u8.tobytes()).hexdigest()[:16],
            }
            rows.append(row)
            del tensor, out, pred, residual
            print(pr['probe_id'], row['mae_residual_vs_lanczos'], flush=True)

    maes = [r['mae_residual_vs_lanczos'] for r in rows]
    hfs = [r['residual_hf'] for r in rows]
    report = {
        'program': 'SIAX_S2_1_P0_SPM_A',
        'bank_sha256': bank.get('bank_sha256'),
        'n_probes': len(rows),
        'model_load_s': round(load_s, 3),
        'base_sha256': file_sha(args.base),
        'summary': {
            'mae_residual_p50': float(np.median(maes)),
            'mae_residual_p95': float(np.percentile(maes, 95)),
            'residual_hf_p50': float(np.median(hfs)),
            'residual_hf_p95': float(np.percentile(hfs, 95)),
        },
        'probes': rows,
        'final_acceptance': False,
        'note': 'SPM-A probe residual vs Lanczos only; not identity/topology; not full-frame S2 rank alone.',
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report['summary'], indent=2))

if __name__ == '__main__':
    main()
