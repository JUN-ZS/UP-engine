#!/usr/bin/env python3
"""Fail-closed preflight for the IGE-SHQ Hub package and candidate bundles."""
from __future__ import annotations

import argparse
import cv2
import hashlib
import json
from pathlib import Path
import sys
from typing import Any

EXPECTED_ASSETS = {
    "assets/s0_battlefield_keep_1376x768.jpg": "f9f24da281878e6583ae17386b76593c9285e509d4feb7a1cea42f848944b90f",
    "assets/s0_battlefield_remove_empty_bg_1376x768.jpg": "98bf4fc0d69c2760bf2c66461111b8c90c3934c4155664434115dd48828a2ada",
    "assets/s1_battlefield_18part_locate_sheet_1376x768.jpg": "fb3a204b733189d3a1d2f88b9f8d2ec8cdbda267aaf09e033529a48634f3ebd0",
    "assets/s4_self_part_hr_b0_lower_legs_boots_1200x896.jpg": "e3da38cbbc89bc4bb7285c6f96f689dcd4308b0e209945e42c029f5d95df69d6",
    "assets/s4_self_part_hr_b0_upper_1200x896.jpg": "234b3eb7ad8bd672fe21d78a59c067a22262b211a47539b7c98dce9829061a3e",
    "assets/s4_self_part_hr_b1_lower_thighs_greaves_1200x896.jpg": "f5074e6bb585d881f11ca13e6a6b33e94f48c4895fbda78b73549629f0048e21",
    "assets/s4_self_part_hr_b1_upper_1200x896.jpg": "137e7ce6c13e14ff07863390251ab20207ab7d443c44815974c26315072f01b9",
    "assets/s4_self_part_hr_b2_full_siege_mecha_1200x896.jpg": "c389e0e439d86384487df952886cdd9f81b81a266b5b54ea54aaed3d17c13ffe",
    "assets/s4_skill_b_material_ref_sheet_1200x896.jpg": "5763ee281830d151c14bb29f282716af6d195430496adb571c3189d1f62ebed3",
    "assets/s4_skill_c_micro_detail_sheet_1200x896.jpg": "b03445fddf3f3c776f75f787474123ea731d579b9c7855acadfb9484608ea8b3",
}
REQUIRED_CODE = [
    "run_all_verifications.py",
    "preflight_check.py",
    "requirements.txt",
    "registry/method_registry.json",
    "registry/validate_registry.py",
    "tests/test_registry_schema.py",
    "src/ige_shq/l0_s0_four_way_anti_hole.py",
    "src/ige_shq/l1_s1_s2_part_hierarchy_and_geometry_lock.py",
    "src/ige_shq/l2_s3_s4_permission_and_registry_router.py",
    "src/ige_shq/l3_s4_self_part_dense_registration_and_3freq_engine.py",
    "src/ige_shq/l4_s5_s6_s7_rule01380_return_and_reverse_qa.py",
]
CANDIDATE_EXTRA_ASSETS = [
    "assets/s4_self_part_hr_b0_geometry_locked_1200x896.jpg",
    "assets/s4_self_part_hr_b2_geometry_locked_1200x896.jpg",
]
CANDIDATE_MANIFEST = "assets/geometry_locked_hr_manifest.json"
CANDIDATE_MANIFEST_SCHEMA = "ige-geometry-locked-hr-assets/1.0"
CANDIDATE_DIMENSIONS_WH = [1200, 896]


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def inspect(root: Path) -> dict[str, Any]:
    errors: list[str] = []
    missing_code = [p for p in REQUIRED_CODE if not (root / p).is_file()]
    if missing_code:
        errors.append("REQUIRED_CODE_MISSING: " + ", ".join(missing_code))

    asset_results: dict[str, dict[str, Any]] = {}
    for rel, expected in EXPECTED_ASSETS.items():
        path = root / rel
        if not path.is_file():
            asset_results[rel] = {"status": "MISSING", "expected_sha256": expected}
            errors.append(f"ASSET_MISSING: {rel}")
            continue
        actual = sha256_file(path)
        status = "PASS" if actual == expected else "HASH_MISMATCH"
        asset_results[rel] = {"status": status, "sha256": actual, "expected_sha256": expected}
        if status != "PASS":
            errors.append(f"ASSET_HASH_MISMATCH: {rel}")

    runner = root / "run_all_verifications.py"
    candidate_extra_required = False
    if runner.is_file():
        source = runner.read_text(encoding="utf-8", errors="replace")
        candidate_extra_required = "B0_GL" in source and "B2_GL" in source

    candidate_results: dict[str, dict[str, Any]] = {}
    if candidate_extra_required:
        manifest_path = root / CANDIDATE_MANIFEST
        manifest_assets: dict[str, Any] = {}
        if not manifest_path.is_file():
            errors.append(f"CANDIDATE_MANIFEST_MISSING: {CANDIDATE_MANIFEST}")
        else:
            try:
                manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
                if manifest.get("schema") != CANDIDATE_MANIFEST_SCHEMA:
                    errors.append("CANDIDATE_MANIFEST_SCHEMA_INVALID")
                manifest_assets = manifest.get("assets", {})
                if not isinstance(manifest_assets, dict):
                    errors.append("CANDIDATE_MANIFEST_ASSETS_INVALID")
                    manifest_assets = {}
            except Exception as exc:
                errors.append(f"CANDIDATE_MANIFEST_READ_ERROR: {exc}")

        for rel in CANDIDATE_EXTRA_ASSETS:
            path = root / rel
            if not path.is_file():
                candidate_results[rel] = {"status": "MISSING"}
                errors.append(f"CANDIDATE_REQUIRED_ASSET_MISSING: {rel}")
                continue

            record = manifest_assets.get(rel, {})
            expected_sha = record.get("sha256") if isinstance(record, dict) else None
            expected_wh = record.get("dimensions_wh") if isinstance(record, dict) else None
            actual_sha = sha256_file(path)
            image = cv2.imread(str(path), cv2.IMREAD_COLOR)
            actual_wh = [int(image.shape[1]), int(image.shape[0])] if image is not None else None

            status = "PASS"
            if not isinstance(expected_sha, str) or len(expected_sha) != 64:
                status = "MANIFEST_SHA_MISSING"
                errors.append(f"CANDIDATE_MANIFEST_SHA_MISSING: {rel}")
            elif actual_sha.lower() != expected_sha.lower():
                status = "HASH_MISMATCH"
                errors.append(f"CANDIDATE_ASSET_HASH_MISMATCH: {rel}")
            if expected_wh != CANDIDATE_DIMENSIONS_WH or actual_wh != CANDIDATE_DIMENSIONS_WH:
                status = "DIMENSIONS_INVALID"
                errors.append(
                    f"CANDIDATE_ASSET_DIMENSIONS_INVALID: {rel}: expected {CANDIDATE_DIMENSIONS_WH}, "
                    f"manifest={expected_wh}, actual={actual_wh}"
                )
            candidate_results[rel] = {
                "status": status,
                "sha256": actual_sha,
                "manifest_sha256": expected_sha,
                "dimensions_wh": actual_wh,
                "manifest_dimensions_wh": expected_wh,
            }

    return {
        "package_root": str(root),
        "profile": "geometry_locked_extension" if candidate_extra_required else "hub_five_plate_baseline",
        "status": "PASS" if not errors else "BLOCK",
        "expected_baseline_asset_count": len(EXPECTED_ASSETS),
        "baseline_asset_results": asset_results,
        "candidate_geometry_locked_asset_results": candidate_results,
        "required_code_missing": missing_code,
        "errors": errors,
        "policy": "No substitute assets, silent resize, or fallback; BLOCK until the exact required files are supplied.",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--root",
        type=Path,
        default=Path(__file__).resolve().parent,
        help="Package root containing assets/, registry/, src/, tests/, and run_all_verifications.py",
    )
    args = parser.parse_args()
    root = args.root.resolve()
    if not root.is_dir():
        result = {"status": "BLOCK", "package_root": str(root), "errors": ["PACKAGE_ROOT_NOT_FOUND"]}
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 2
    result = inspect(root)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["status"] == "PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
