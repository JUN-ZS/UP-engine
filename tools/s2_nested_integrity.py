#!/usr/bin/env python3
"""Strict Nested integrity: schema-ish required fields, fail-closed SHA, pixel match.

Proves each native child PNG is byte-identical to the corresponding primary crop,
coverage is complete, and no overlaps exist.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
from PIL import Image


REQUIRED_CHILD = ("child_id", "parent_id", "uri", "sha256", "core_box_base", "output_box_hires")


def file_sha(p: Path) -> str:
    d = hashlib.sha256()
    with p.open("rb") as f:
        for c in iter(lambda: f.read(1 << 20), b""):
            d.update(c)
    return d.hexdigest()


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--job-dir", type=Path, required=True)
    ap.add_argument("--expected-primary-sha256", required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--scale", type=int, default=4)
    ap.add_argument("--pixel-check", action="store_true", default=True)
    ap.add_argument("--no-pixel-check", action="store_false", dest="pixel_check")
    args = ap.parse_args()

    job = args.job_dir
    vm_path = job / "manifests" / "virtual_master.json"
    primary = job / "OUT_NESTED_PRIMARY.png"
    errors: list[str] = []

    if not vm_path.is_file():
        errors.append("missing virtual_master.json")
    if not primary.is_file():
        errors.append("missing OUT_NESTED_PRIMARY.png")
    if errors:
        report = {"ok": False, "errors": errors, "final_acceptance": False, "quality_qualified": False}
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(report, indent=2) + "\n")
        print(json.dumps(report, indent=2))
        return 2

    vm = json.loads(vm_path.read_text())
    for key in ("manifest_version", "master_id", "base_sha256", "scale", "logical_grid", "children", "primary_policy"):
        if key not in vm:
            errors.append(f"vm missing required key: {key}")

    primary_sha = file_sha(primary)
    if primary_sha != args.expected_primary_sha256:
        errors.append(f"primary sha mismatch got={primary_sha}")

    with Image.open(primary) as im:
        canvas = np.asarray(im.convert("RGB"), dtype=np.uint8)
    oh, ow = canvas.shape[0], canvas.shape[1]
    if ow % args.scale or oh % args.scale:
        errors.append(f"primary dims not multiple of scale: {ow}x{oh}")
    bw, bh = ow // args.scale, oh // args.scale

    children = vm.get("children") or []
    coverage = np.zeros((bh, bw), dtype=np.uint16)
    verified = 0
    pixel_mismatches = 0
    missing_sha = 0

    for ch in children:
        cid = ch.get("child_id", "<unknown>")
        for k in REQUIRED_CHILD:
            if k not in ch or ch[k] in (None, ""):
                errors.append(f"{cid} missing required field {k}")
                if k == "sha256":
                    missing_sha += 1
        if "sha256" not in ch or not ch.get("sha256"):
            continue  # already recorded; fail closed via missing_sha/errors
        if len(str(ch.get("sha256", ""))) != 64:
            errors.append(f"{cid} sha256 not 64 hex")
            continue

        uri = Path(str(ch["uri"]))
        if not uri.is_file():
            uri = job / "children" / Path(str(ch["uri"])).name
        if not uri.is_file():
            errors.append(f"{cid} missing file")
            continue

        actual = file_sha(uri)
        if actual != ch["sha256"]:
            errors.append(f"{cid} file sha mismatch")
            continue

        try:
            x0, y0, x1, y1 = [int(v) for v in ch["output_box_hires"]]
        except Exception:
            errors.append(f"{cid} bad output_box_hires")
            continue
        if x0 < 0 or y0 < 0 or x1 > ow or y1 > oh or x1 <= x0 or y1 <= y0:
            errors.append(f"{cid} box out of primary bounds")
            continue
        if (x0 % args.scale) or (y0 % args.scale) or (x1 % args.scale) or (y1 % args.scale):
            errors.append(f"{cid} box not scale-aligned")
            continue

        bx0, by0, bx1, by1 = x0 // args.scale, y0 // args.scale, x1 // args.scale, y1 // args.scale
        if np.any(coverage[by0:by1, bx0:bx1]):
            errors.append(f"{cid} overlap")
            continue
        coverage[by0:by1, bx0:bx1] = 1

        with Image.open(uri) as im:
            tile = np.asarray(im.convert("RGB"), dtype=np.uint8)
        if tile.shape != (y1 - y0, x1 - x0, 3):
            errors.append(f"{cid} shape {tile.shape} != box")
            continue

        if args.pixel_check:
            region = canvas[y0:y1, x0:x1]
            if not np.array_equal(region, tile):
                pixel_mismatches += 1
                # count differing pixels for triage
                diff = int(np.count_nonzero(region != tile))
                errors.append(f"{cid} pixel mismatch vs primary crop (diff_channels={diff})")
                continue

        verified += 1

    missing_px = int(coverage.size - np.count_nonzero(coverage))
    ok = (
        len(errors) == 0
        and missing_sha == 0
        and pixel_mismatches == 0
        and missing_px == 0
        and verified == len(children)
        and primary_sha == args.expected_primary_sha256
        and len(children) > 0
    )

    report = {
        "program": "SIAX_S2_1_P1_NESTED_INTEGRITY_STRICT",
        "primary_sha256": primary_sha,
        "expected_primary_sha256": args.expected_primary_sha256,
        "primary_bytes": primary.stat().st_size,
        "primary_dimensions": [ow, oh],
        "children_in_vm": len(children),
        "children_verified": verified,
        "missing_base_pixels": missing_px,
        "coverage_complete": missing_px == 0,
        "missing_sha_fields": missing_sha,
        "pixel_mismatches": pixel_mismatches,
        "pixel_check_enabled": args.pixel_check,
        "errors_n": len(errors),
        "errors_sample": errors[:30],
        "ok": ok,
        "fail_closed": True,
        "final_acceptance": False,
        "quality_qualified": False,
        "note": "Fail-closed on missing SHA; pixel equality primary[crop]==child PNG when pixel_check enabled.",
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n")
    print(json.dumps({k: report[k] for k in report if k != "errors_sample"}, indent=2))
    if errors:
        print("errors_sample:", errors[:10])
    return 0 if ok else 2


if __name__ == "__main__":
    raise SystemExit(main())
