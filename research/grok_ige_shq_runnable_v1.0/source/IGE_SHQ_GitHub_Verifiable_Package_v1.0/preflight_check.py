#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
preflight_check.py
==================
Step 1 (Preflight Gate) of the HUB PR #12 Step-by-Step Runbook (`b0c7dee4`):
  - Verifies `assets/asset_manifest.json` exists and lists all 13 required image assets.
  - Verifies every image asset exists on disk, decodes cleanly via OpenCV, matches its
    exact `[width, height]` dimensions, and matches its exact `SHA-256` digest.
  - Strictly enforces the Geometry-Locked Donor Anti-Spoofing Rule:
      * `s4_self_part_hr_b0_geometry_locked_1200x896.jpg` (`B0_GL`) must exist and MUST NOT
        have the same SHA-256 as `s4_self_part_hr_b0_upper_1200x896.jpg` (`B0_UPPER`).
      * `s4_self_part_hr_b2_geometry_locked_1200x896.jpg` (`B2_GL`) must exist and MUST NOT
        have the same SHA-256 as `s4_self_part_hr_b2_full_siege_mecha_1200x896.jpg` (`B2_FULL`).
  - Verifies required companion files (`requirements.txt`, `SHQ_OTHER_AI_STEP_BY_STEP_RUNBOOK.md`,
    `SHQ_AI_USAGE_GUIDE.md`, `SHQ_INDEX.md`, `registry/method_registry.json`, `registry/validate_registry.py`,
    and all 5 layer modules `l0`..`l4`).
  - Returns `status = "BLOCK"` and exits with `exit code 2` if ANY check fails!
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path
from typing import Dict, List

import cv2

_PKG_ROOT = Path(__file__).resolve().parent


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run_preflight(pkg_root: Path = _PKG_ROOT) -> Dict[str, object]:
    errors: List[str] = []
    checks: Dict[str, str] = {}

    required_files = [
        "README.md",
        "requirements.txt",
        "preflight_check.py",
        "SHQ_OTHER_AI_STEP_BY_STEP_RUNBOOK.md",
        "SHQ_AI_USAGE_GUIDE.md",
        "SHQ_INDEX.md",
        "run_all_verifications.py",
        "registry/method_registry.json",
        "registry/validate_registry.py",
        "assets/asset_manifest.json",
        "src/ige_shq/__init__.py",
        "src/ige_shq/l0_s0_four_way_anti_hole.py",
        "src/ige_shq/l1_s1_s2_part_hierarchy_and_geometry_lock.py",
        "src/ige_shq/l2_s3_s4_permission_and_registry_router.py",
        "src/ige_shq/l3_s4_self_part_dense_registration_and_3freq_engine.py",
        "src/ige_shq/l4_s5_s6_s7_rule01380_return_and_reverse_qa.py",
        "tests/test_registry_schema.py",
    ]
    for rel in required_files:
        p = pkg_root / rel
        if not p.exists():
            errors.append(f"MISSING_REQUIRED_FILE: {rel}")
            checks[rel] = "MISSING"
        else:
            checks[rel] = "PASS"

    manifest_path = pkg_root / "assets" / "asset_manifest.json"
    asset_results = {}
    if manifest_path.exists():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        assets_list = manifest.get("assets", [])
        if len(assets_list) < 13:
            errors.append(f"MANIFEST_INCOMPLETE: expected 13 assets, got {len(assets_list)}")

        sha_map = {}
        for entry in assets_list:
            fname = entry["file_name"]
            expected_sha = entry["sha256"]
            expected_wh = entry["dimensions_wh"]
            ap = pkg_root / "assets" / fname
            if not ap.exists():
                errors.append(f"ASSET_MISSING: assets/{fname}")
                asset_results[fname] = "MISSING"
                continue
            actual_sha = sha256_file(ap)
            sha_map[fname] = actual_sha
            img = cv2.imread(str(ap), cv2.IMREAD_COLOR)
            if img is None:
                errors.append(f"ASSET_DECODE_FAIL: assets/{fname}")
                asset_results[fname] = "DECODE_FAIL"
                continue
            actual_wh = [int(img.shape[1]), int(img.shape[0])]
            if actual_sha != expected_sha:
                errors.append(f"ASSET_SHA_MISMATCH: {fname} expected {expected_sha}, got {actual_sha}")
                asset_results[fname] = "SHA_MISMATCH"
            elif actual_wh != expected_wh:
                errors.append(f"ASSET_DIM_MISMATCH: {fname} expected {expected_wh}, got {actual_wh}")
                asset_results[fname] = "DIM_MISMATCH"
            else:
                asset_results[fname] = "PASS"

        # Anti-spoofing check: B0_GL != B0_UPPER and B2_GL != B2_FULL
        b0_gl = sha_map.get("s4_self_part_hr_b0_geometry_locked_1200x896.jpg")
        b0_up = sha_map.get("s4_self_part_hr_b0_upper_1200x896.jpg")
        b2_gl = sha_map.get("s4_self_part_hr_b2_geometry_locked_1200x896.jpg")
        b2_full = sha_map.get("s4_self_part_hr_b2_full_siege_mecha_1200x896.jpg")
        if not b0_gl:
            errors.append("B0_GL_MISSING: s4_self_part_hr_b0_geometry_locked_1200x896.jpg")
        elif b0_gl == b0_up:
            errors.append("SPOOF_DETECTED: B0_UPPER substituted for B0_GL")
        if not b2_gl:
            errors.append("B2_GL_MISSING: s4_self_part_hr_b2_geometry_locked_1200x896.jpg")
        elif b2_gl == b2_full:
            errors.append("SPOOF_DETECTED: B2_FULL substituted for B2_GL")

    passed = len(errors) == 0
    return {
        "status": "PASS" if passed else "BLOCK",
        "exit_code": 0 if passed else 2,
        "total_assets_verified": sum(1 for v in asset_results.values() if v == "PASS"),
        "b0_gl_status": asset_results.get("s4_self_part_hr_b0_geometry_locked_1200x896.jpg", "MISSING"),
        "b2_gl_status": asset_results.get("s4_self_part_hr_b2_geometry_locked_1200x896.jpg", "MISSING"),
        "geometry_locked_asset_manifest": checks.get("assets/asset_manifest.json", "MISSING"),
        "preflight_and_requirements_bundled": bool(
            checks.get("preflight_check.py") == "PASS" and checks.get("requirements.txt") == "PASS"
        ),
        "live_siax_ncnn_or_comfyui_flux_invoked_at_runtime": False,
        "asset_results": asset_results,
        "required_file_checks": checks,
        "errors": errors,
    }


if __name__ == "__main__":
    res = run_preflight()
    print(json.dumps(res, indent=2, ensure_ascii=False))
    sys.exit(res["exit_code"])
