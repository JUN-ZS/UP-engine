#!/usr/bin/env python3
"""Build a fixed 48-probe bank on BASE (deterministic, shared by all S2.1 cells)."""
from __future__ import annotations
import argparse, json, hashlib
from pathlib import Path
from PIL import Image, ImageOps

PROBE_H, PROBE_W = 48, 64  # §0.12.39 default A

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--base', type=Path, required=True)
    ap.add_argument('--out', type=Path, required=True)
    ap.add_argument('--n', type=int, default=48)
    args = ap.parse_args()
    with Image.open(args.base) as im:
        base = ImageOps.exif_transpose(im).convert('RGB')
    W, H = base.size
    # Lattice + edge-biased + center-biased fixed samples (no semantic labels yet)
    probes = []
    # 4x6 lattice interior (24)
    for i, fy in enumerate([0.15, 0.35, 0.55, 0.75]):
        for j, fx in enumerate([0.12, 0.28, 0.44, 0.60, 0.76, 0.90]):
            cy, cx = int(fy * H), int(fx * W)
            probes.append(('lattice', cy, cx))
    # vertical edge band (8)
    for k, fy in enumerate([0.1, 0.22, 0.34, 0.46, 0.58, 0.70, 0.82, 0.92]):
        probes.append(('edge_v', int(fy * H), int(0.05 * W)))
        if len(probes) >= args.n:
            break
    # horizontal edge + mid detail (fill to 48)
    for fy, fx in [
        (0.08, 0.5), (0.92, 0.5), (0.5, 0.08), (0.5, 0.92),
        (0.25, 0.25), (0.25, 0.75), (0.75, 0.25), (0.75, 0.75),
        (0.4, 0.35), (0.4, 0.65), (0.6, 0.35), (0.6, 0.65),
        (0.18, 0.42), (0.18, 0.58), (0.82, 0.42), (0.82, 0.58),
    ]:
        if len(probes) >= args.n:
            break
        probes.append(('focus', int(fy * H), int(fx * W)))
    probes = probes[: args.n]
    bank = []
    for idx, (kind, cy, cx) in enumerate(probes):
        y0 = max(0, min(H - PROBE_H, cy - PROBE_H // 2))
        x0 = max(0, min(W - PROBE_W, cx - PROBE_W // 2))
        y1, x1 = y0 + PROBE_H, x0 + PROBE_W
        bank.append({
            'probe_id': f'p{idx:02d}',
            'kind': kind,
            'box_base': [x0, y0, x1, y1],  # x0,y0,x1,y1
            'center_base': [cx, cy],
        })
    doc = {
        'format': 'ige.siax.spm_a_probe_bank',
        'format_version': '1.0',
        'base_path': str(args.base),
        'base_wh': [W, H],
        'probe_hw': [PROBE_H, PROBE_W],
        'n_probes': len(bank),
        'probes': bank,
        'note': 'Fixed geometry for all tile cells; not material-labeled yet. final_acceptance false.',
        'final_acceptance': False,
    }
    # content hash of probe boxes only
    h = hashlib.sha256(json.dumps(bank, sort_keys=True).encode()).hexdigest()
    doc['bank_sha256'] = h
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(doc, indent=2) + '\n')
    print(json.dumps({'n': len(bank), 'bank_sha256': h, 'base_wh': [W, H]}, indent=2))

if __name__ == '__main__':
    main()
