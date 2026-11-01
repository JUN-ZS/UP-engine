#!/usr/bin/env python3
"""Verify Nested Virtual Master: 448 children SHA, coverage, no overlap, primary SHA."""
from __future__ import annotations
import argparse, json, hashlib
from pathlib import Path
import numpy as np
from PIL import Image

def file_sha(p: Path) -> str:
    d = hashlib.sha256()
    with p.open('rb') as f:
        for c in iter(lambda: f.read(1<<20), b''):
            d.update(c)
    return d.hexdigest()

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--job-dir', type=Path, required=True)
    ap.add_argument('--expected-primary-sha256', required=True)
    ap.add_argument('--out', type=Path, required=True)
    ap.add_argument('--scale', type=int, default=4)
    args = ap.parse_args()
    job = args.job_dir
    vm = json.loads((job/'manifests/virtual_master.json').read_text())
    primary = job/'OUT_NESTED_PRIMARY.png'
    primary_sha = file_sha(primary)
    children = vm['children']
    errors = []
    if primary_sha != args.expected_primary_sha256:
        errors.append(f'primary sha mismatch {primary_sha}')
    with Image.open(primary) as im:
        ow, oh = im.size
    bw = ow // args.scale
    bh = oh // args.scale
    coverage = np.zeros((bh, bw), dtype=np.uint16)
    child_ok = 0
    for ch in children:
        uri = Path(ch['uri'])
        if not uri.is_file():
            # try relative to job
            uri = job / 'children' / Path(ch['uri']).name
        if not uri.is_file():
            errors.append(f'missing {ch["child_id"]}')
            continue
        actual = file_sha(uri)
        if ch.get('sha256') and actual != ch['sha256']:
            errors.append(f'sha mismatch {ch["child_id"]}')
            continue
        x0,y0,x1,y1 = ch['output_box_hires']
        bx0,by0,bx1,by1 = x0//args.scale, y0//args.scale, x1//args.scale, y1//args.scale
        if np.any(coverage[by0:by1, bx0:bx1]):
            errors.append(f'overlap {ch["child_id"]}')
            continue
        coverage[by0:by1, bx0:bx1] = 1
        with Image.open(uri) as im:
            if im.size != (x1-x0, y1-y0):
                errors.append(f'size {ch["child_id"]} {im.size} != {(x1-x0,y1-y0)}')
                continue
        child_ok += 1
    missing_px = int(coverage.size - np.count_nonzero(coverage))
    report = {
        'program': 'SIAX_S2_1_P1_NESTED_INTEGRITY',
        'primary_sha256': primary_sha,
        'primary_bytes': primary.stat().st_size,
        'primary_dimensions': [ow, oh],
        'children_in_vm': len(children),
        'children_verified': child_ok,
        'missing_base_pixels': missing_px,
        'coverage_complete': missing_px == 0,
        'errors_n': len(errors),
        'errors_sample': errors[:20],
        'ok': len(errors)==0 and missing_px==0 and child_ok==len(children) and primary_sha==args.expected_primary_sha256,
        'final_acceptance': False,
        'quality_qualified': False,
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2)+'\n')
    print(json.dumps(report, indent=2))
    return 0 if report['ok'] else 2

if __name__ == '__main__':
    raise SystemExit(main())
