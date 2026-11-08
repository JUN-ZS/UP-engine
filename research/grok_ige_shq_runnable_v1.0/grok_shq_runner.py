#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Grok-safe launcher and evidence helper for the IGE-SHQ toolkit.

This wrapper deliberately does NOT execute the original method/recipe entrypoints
while the toolkit still hard-codes human_verified=True in its shared pipeline.
It provides safe inventory, preflight, registry, readiness, donor registration,
and output verification. It never upgrades a tool-generated PASS receipt into
independent algorithm acceptance.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

HERE = Path(__file__).resolve().parent
CANDIDATES = [
    HERE / "source" / "IGE_SHQ_GitHub_Verifiable_Package_v1.0",
    HERE / "IGE_SHQ_GitHub_Verifiable_Package_v1.0",
    HERE,
]
PKG = next((p for p in CANDIDATES if (p / "preflight_check.py").is_file()), None)
if PKG is None:
    raise SystemExit("BLOCK: Cannot locate IGE_SHQ_GitHub_Verifiable_Package_v1.0")
RUN_DIR = PKG / "outputs" / "grok_runs"
RUN_DIR.mkdir(parents=True, exist_ok=True)


def stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def write_json(path: Path, data: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def run_command(label: str, args: List[str]) -> Dict[str, Any]:
    started = datetime.now(timezone.utc).isoformat()
    p = subprocess.run(args, cwd=PKG, text=True, capture_output=True)
    ended = datetime.now(timezone.utc).isoformat()
    prefix = f"{stamp()}_{label}"
    (RUN_DIR / f"{prefix}.stdout.txt").write_text(p.stdout or "", encoding="utf-8")
    (RUN_DIR / f"{prefix}.stderr.txt").write_text(p.stderr or "", encoding="utf-8")
    return {
        "label": label,
        "argv": args,
        "started_utc": started,
        "ended_utc": ended,
        "exit_code": p.returncode,
        "status": "PASS_COMMAND_EXIT_0" if p.returncode == 0 else "FAIL_COMMAND_EXIT_NONZERO",
        "stdout_file": str((RUN_DIR / f"{prefix}.stdout.txt").relative_to(PKG)),
        "stderr_file": str((RUN_DIR / f"{prefix}.stderr.txt").relative_to(PKG)),
        "stdout_tail": (p.stdout or "")[-3000:],
        "stderr_tail": (p.stderr or "")[-2000:],
    }


def inspect_execution_gate() -> Dict[str, Any]:
    common = PKG / "methods" / "common_runtime.py"
    src = common.read_text(encoding="utf-8") if common.exists() else ""
    hardcoded = "human_verified=True" in src.replace(" ", "")
    # The source currently auto-grants S3 permission in the shared runtime.
    blockers = []
    if hardcoded:
        blockers.append("S3 permission is hard-coded to human_verified=True in methods/common_runtime.py")
    if "permission_artifact" not in src.lower() and "approval_artifact" not in src.lower():
        blockers.append("No visible signed human-approval artifact verifier is wired into the shared runtime")
    rep = PKG / "outputs" / "SHQ_GITHUB_LAYERED_TRACEABILITY_REPORT.json"
    master = PKG / "outputs" / "SHQ_BATTLEFIELD_SELF_PARTS_4X_MASTER_5504x3072.png"
    if rep.exists() or master.exists():
        blockers.append("Existing master/report artifact path may be reused as a cache pair without content-addressed source validation")
    return {
        "status": "BLOCKED" if blockers else "READY_FOR_REVIEW_NOT_ACCEPTANCE",
        "blockers": blockers,
        "method_execution_allowed_by_launcher": not bool(blockers),
        "note": "A launcher-side flag cannot substitute for signed human review. Repair the S3 gate in source before enabling write methods.",
    }


def cmd_doctor() -> int:
    checks: Dict[str, Any] = {
        "python": sys.version,
        "package_root": str(PKG),
        "numpy_available": False,
        "cv2_available": False,
        "execution_gate": inspect_execution_gate(),
    }
    try:
        import numpy  # type: ignore
        checks["numpy_available"] = True
        checks["numpy_version"] = numpy.__version__
    except Exception as e:
        checks["numpy_error"] = str(e)
    try:
        import cv2  # type: ignore
        checks["cv2_available"] = True
        checks["opencv_version"] = cv2.__version__
    except Exception as e:
        checks["cv2_error"] = str(e)
    checks["status"] = "BLOCKED" if not checks["numpy_available"] or not checks["cv2_available"] or checks["execution_gate"]["status"] == "BLOCKED" else "READY_FOR_READ_ONLY_CHECKS"
    path = RUN_DIR / f"{stamp()}_doctor.json"
    write_json(path, checks)
    print(json.dumps(checks, ensure_ascii=False, indent=2))
    print(f"REPORT: {path}")
    return 0 if checks["numpy_available"] and checks["cv2_available"] else 2


def cmd_preflight() -> int:
    res = run_command("preflight", [sys.executable, "preflight_check.py"])
    print(json.dumps(res, ensure_ascii=False, indent=2))
    return res["exit_code"]


def cmd_registry() -> int:
    res = run_command("registry", [sys.executable, "registry/validate_registry.py", "registry/method_registry.json"])
    print(json.dumps(res, ensure_ascii=False, indent=2))
    return res["exit_code"]


def cmd_audit() -> int:
    report: Dict[str, Any] = {
        "schema": "grok-ige-shq-readonly-audit/1.0",
        "started_utc": datetime.now(timezone.utc).isoformat(),
        "source_package": str(PKG),
        "scope": "read-only asset and registry checks; no method/recipe image-write execution",
        "steps": [],
    }
    for label, args in [
        ("preflight", [sys.executable, "preflight_check.py"]),
        ("registry", [sys.executable, "registry/validate_registry.py", "registry/method_registry.json"]),
    ]:
        step = run_command(label, args)
        report["steps"].append(step)
        if step["exit_code"] != 0:
            report["status"] = "FAIL_CLOSED"
            break
    else:
        report["status"] = "READ_ONLY_CHECKS_PASS_EXECUTION_BLOCKED" if inspect_execution_gate()["status"] == "BLOCKED" else "READ_ONLY_CHECKS_PASS"
    report["execution_gate"] = inspect_execution_gate()
    report["finished_utc"] = datetime.now(timezone.utc).isoformat()
    out = RUN_DIR / f"{stamp()}_readonly_audit.json"
    write_json(out, report)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    print(f"REPORT: {out}")
    return 0 if all(s["exit_code"] == 0 for s in report["steps"]) else 2


def cmd_catalog() -> int:
    p = subprocess.run([sys.executable, "invoke_method.py", "--list"], cwd=PKG, text=True)
    return p.returncode


def cmd_info(key: str) -> int:
    p = subprocess.run([sys.executable, "invoke_method.py", "--info", key], cwd=PKG, text=True)
    return p.returncode


def cmd_register_donor(src_arg: str, label: str) -> int:
    src = Path(src_arg).expanduser().resolve()
    if not src.is_file():
        print(f"BLOCK: donor file not found: {src}", file=sys.stderr)
        return 2
    digest = sha256(src)
    donor_dir = PKG / "assets" / "imagine_donors"
    donor_dir.mkdir(parents=True, exist_ok=True)
    safe_name = "".join(c if c.isalnum() or c in "-_." else "_" for c in src.name)
    dest = donor_dir / f"{digest[:12]}_{safe_name}"
    if not dest.exists():
        shutil.copy2(src, dest)
    try:
        import cv2  # type: ignore
        im = cv2.imread(str(dest), cv2.IMREAD_UNCHANGED)
        dimensions = [int(im.shape[1]), int(im.shape[0])] if im is not None else None
        channels = int(im.shape[2]) if im is not None and len(im.shape) > 2 else 1 if im is not None else None
    except Exception:
        dimensions, channels = None, None
    rec = {
        "schema": "grok-imagine-donor/1.0",
        "label": label,
        "source_file": str(src),
        "registered_file": str(dest.relative_to(PKG)),
        "sha256": digest,
        "dimensions_wh": dimensions,
        "channels": channels,
        "status": "REGISTERED_NOT_PIPELINE_WIRED",
        "geometry_authority": False,
        "note": "This file is an auxiliary donor only. Current M12/M13 source code does not automatically consume assets/imagine_donors; do not replace canonical assets or treat the donor as geometry truth.",
    }
    manifest = donor_dir / "imagine_donor_manifest.json"
    existing = []
    if manifest.exists():
        try:
            existing = json.loads(manifest.read_text(encoding="utf-8")).get("donors", [])
        except Exception:
            existing = []
    existing = [x for x in existing if x.get("sha256") != digest]
    existing.append(rec)
    write_json(manifest, {"schema": "grok-imagine-donor-manifest/1.0", "donors": existing})
    print(json.dumps(rec, ensure_ascii=False, indent=2))
    return 0


def cmd_verify_master() -> int:
    master = PKG / "outputs" / "SHQ_BATTLEFIELD_SELF_PARTS_4X_MASTER_5504x3072.png"
    if not master.exists():
        print("BLOCK: master PNG does not exist", file=sys.stderr)
        return 2
    try:
        import cv2  # type: ignore
        im = cv2.imread(str(master), cv2.IMREAD_UNCHANGED)
        if im is None:
            raise RuntimeError("OpenCV could not decode master")
        dims = [int(im.shape[1]), int(im.shape[0])]
        channels = int(im.shape[2]) if len(im.shape) > 2 else 1
    except Exception as e:
        print(f"BLOCK: image decode failed: {e}", file=sys.stderr)
        return 2
    rec = {
        "file": str(master.relative_to(PKG)),
        "sha256": sha256(master),
        "bytes": master.stat().st_size,
        "dimensions_wh": dims,
        "channels": channels,
        "expected_dimensions_wh": [5504, 3072],
        "dimension_check": "PASS" if dims == [5504, 3072] else "FAIL",
        "scope": "file integrity and dimensions only; not semantic quality, independent acceptance, or live Imagine/Siax/Flux inference",
    }
    out = RUN_DIR / f"{stamp()}_master_file_check.json"
    write_json(out, rec)
    print(json.dumps(rec, ensure_ascii=False, indent=2))
    print(f"REPORT: {out}")
    return 0 if rec["dimension_check"] == "PASS" else 2


def main() -> int:
    ap = argparse.ArgumentParser(description="Grok-safe IGE-SHQ launcher (read-only checks + evidence helpers)")
    group = ap.add_mutually_exclusive_group(required=True)
    group.add_argument("--doctor", action="store_true", help="Check runtime dependencies and execution blockers")
    group.add_argument("--preflight", action="store_true", help="Verify the 13 canonical source assets")
    group.add_argument("--registry", action="store_true", help="Validate method registry schema")
    group.add_argument("--audit", action="store_true", help="Run read-only preflight + registry checks and write evidence JSON")
    group.add_argument("--catalog", action="store_true", help="List methods and recipes")
    group.add_argument("--info", metavar="METHOD_OR_RECIPE", help="Show M01..M22 or R01..R03 metadata")
    group.add_argument("--register-donor", metavar="IMAGE_PATH", help="Register an Imagine output as an auxiliary donor; not auto-wired")
    group.add_argument("--verify-master", action="store_true", help="Check saved master PNG dimensions and SHA-256")
    group.add_argument("--run", metavar="Mxx", help="Intentionally blocked until source S3 approval and cache guards are repaired")
    group.add_argument("--recipe", metavar="Rxx", help="Intentionally blocked until source S3 approval and cache guards are repaired")
    ap.add_argument("--label", default="grok_imagine_donor", help="Label for a registered Imagine donor")
    args = ap.parse_args()
    if args.doctor: return cmd_doctor()
    if args.preflight: return cmd_preflight()
    if args.registry: return cmd_registry()
    if args.audit: return cmd_audit()
    if args.catalog: return cmd_catalog()
    if args.info: return cmd_info(args.info)
    if args.register_donor: return cmd_register_donor(args.register_donor, args.label)
    if args.verify_master: return cmd_verify_master()
    if args.run or args.recipe:
        gate = inspect_execution_gate()
        action = f"method {args.run}" if args.run else f"recipe {args.recipe}"
        print(json.dumps({"status": "BLOCKED", "requested": action, "execution_gate": gate, "reason": "Current source auto-sets human_verified=True and may reuse stale cached output. The launcher refuses to write images until these source-level issues are fixed and re-audited."}, ensure_ascii=False, indent=2))
        return 3
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
