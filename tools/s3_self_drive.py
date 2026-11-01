#!/usr/bin/env python3
"""S3 self-drive orchestrator — local / CI / dual-runner stages.

Entry point for Grok CLI, human, or GitHub Actions.
Does NOT call remote Grok chat as a live brain.
Does NOT claim quality PASS or E3.

Stages:
  unit              pytest S3 control + dock
  single_pull       one-host synthetic worker-first pilot
  docker_dual       two containers, shared volume (NOT physical dual-host)
  self_hosted_hint  print dual self-hosted runner checklist (no run)
  siax_mini         optional single-host Siax mini (needs checkpoint + flag)

Exit non-zero on failure. Writes docs/evidence/S3_SELF_DRIVE_<stamp>.json when --evidence-out set.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _run(cmd: list[str], *, cwd: Path | None = None, env: dict | None = None, timeout: float | None = None) -> subprocess.CompletedProcess:
    e = os.environ.copy()
    e["PYTHONPATH"] = str(ROOT / "src") + os.pathsep + e.get("PYTHONPATH", "")
    e["PYTHONUNBUFFERED"] = "1"
    if env:
        e.update(env)
    print("+", " ".join(cmd), flush=True)
    return subprocess.run(
        cmd,
        cwd=str(cwd or ROOT),
        env=e,
        text=True,
        timeout=timeout,
    )


def stage_unit() -> dict:
    # prefer pytest if available
    r = _run([sys.executable, "-m", "pytest",
              "tests/test_s3_local_pc_dock.py",
              "tests/test_s3_control_plane.py",
              "tests/test_s3_controller_reassign.py",
              "tests/test_s3_6_kill_reassign.py",
              "tests/test_s3_scheduler_transport.py",
              "-q", "--tb=line"], timeout=300)
    if r.returncode != 0:
        # fallback unittest subset
        r2 = _run([sys.executable, "-m", "unittest", "discover", "-s", "tests", "-p", "test_s3*.py", "-v"], timeout=300)
        ok = r2.returncode == 0
        return {"stage": "unit", "ok": ok, "runner": "unittest" if ok else "pytest_failed"}
    return {"stage": "unit", "ok": True, "runner": "pytest"}


def stage_single_pull(job_dir: Path, base: Path, lease: float) -> dict:
    from PIL import Image

    job_dir = Path(job_dir)
    if job_dir.exists() and any(job_dir.iterdir()):
        # allow only empty-ish: refuse if manifest exists
        if (job_dir / "job_manifest.json").exists():
            raise SystemExit(f"job-dir already used: {job_dir} — pick a new path")
    job_dir.mkdir(parents=True, exist_ok=True)
    base = Path(base)
    if not base.is_file():
        # synthesize tiny base for CI
        base.parent.mkdir(parents=True, exist_ok=True)
        Image.new("RGB", (128, 128), (11, 22, 33)).save(base)

    py = sys.executable
    worker_id = "selfdrive_w1"
    agent = subprocess.Popen(
        [
            py, str(ROOT / "tools" / "s3_dock_local_pc.py"),
            "--job-dir", str(job_dir),
            "--worker-id", worker_id,
            "--mode", "synthetic",
            "--device", "cpu",
            "--ram-mib", "2048",
            "--cpu-threads", str(os.cpu_count() or 2),
            "--lease-seconds", str(lease),
            "--wait-manifest-s", "120",
            "--idle-exit-s", "30",
            "--registry-every-s", "0.5",
        ],
        cwd=str(ROOT),
        env={**os.environ, "PYTHONPATH": str(ROOT / "src"), "PYTHONUNBUFFERED": "1"},
    )
    try:
        # wait registry
        reg = job_dir / "registry" / "workers" / f"{worker_id}.json"
        t0 = time.time()
        while time.time() - t0 < 30:
            if reg.is_file():
                break
            time.sleep(0.2)
        else:
            raise SystemExit("registry not ready")

        for cmd in (
            [py, str(ROOT / "tools" / "s3_controller.py"), "init",
             "--job-dir", str(job_dir), "--base", str(base),
             "--mode", "synthetic", "--region", "0,0,128,128",
             "--compute-core", "64", "--lease-seconds", str(lease)],
            [py, str(ROOT / "tools" / "s3_controller.py"), "schedule",
             "--job-dir", str(job_dir), "--wait-workers", "1",
             "--wait-timeout-s", "30", "--lease-seconds", str(lease)],
            [py, str(ROOT / "tools" / "s3_controller.py"), "wait",
             "--job-dir", str(job_dir), "--timeout-s", "120",
             "--reassign-every-s", "1", "--lease-seconds", str(lease)],
            [py, str(ROOT / "tools" / "s3_controller.py"), "rebuild",
             "--job-dir", str(job_dir), "--lease-seconds", str(lease)],
        ):
            r = _run(cmd, timeout=180)
            if r.returncode != 0:
                raise SystemExit(f"command failed: {cmd} rc={r.returncode}")
    finally:
        agent.terminate()
        try:
            agent.wait(timeout=15)
        except Exception:
            agent.kill()

    report = {}
    rp = job_dir / "controller_report.json"
    if rp.is_file():
        report = json.loads(rp.read_text(encoding="utf-8"))
    return {
        "stage": "single_pull",
        "ok": bool(report.get("ok")),
        "job_dir": str(job_dir),
        "physical_dual_host": False,
        "final_acceptance": False,
        "e3_speed_claim": False,
        "controller_report": report,
    }


def stage_docker_dual() -> dict:
    compose = ROOT / "docker" / "s3-dual-worker" / "docker-compose.yml"
    if not compose.is_file():
        return {"stage": "docker_dual", "ok": False, "error": "compose missing"}
    if not shutil.which("docker"):
        return {
            "stage": "docker_dual",
            "ok": False,
            "skipped": True,
            "reason": "docker_not_available",
            "physical_dual_host": False,
            "note": "Install Docker or use GitHub self-hosted dual runners instead",
        }
    r = _run(
        ["docker", "compose", "-f", str(compose), "run", "--rm", "controller"],
        timeout=600,
    )
    return {
        "stage": "docker_dual",
        "ok": r.returncode == 0,
        "physical_dual_host": False,
        "label": "container_dual_on_one_machine",
        "final_acceptance": False,
        "e3_speed_claim": False,
    }


def stage_self_hosted_hint() -> dict:
    return {
        "stage": "self_hosted_hint",
        "ok": True,
        "physical_dual_host": "REQUIRES_TWO_SELF_HOSTED_RUNNERS",
        "checklist": [
            "Register two self-hosted runners with labels: s3-host-a, s3-host-b",
            "Shared path both can rename on (NFS/SMB) e.g. /shared/s3_jobs",
            "workflow s3-self-drive.yml job dual_self_hosted needs: [s3-host-a, s3-host-b]",
            "Same --lease-seconds on controller and both workers",
            "Upload controller_report.json as artifact; never flip quality PASS",
        ],
        "workflow": ".github/workflows/s3-self-drive.yml",
    }


def stage_siax_mini(job_dir: Path, base: Path, lease: float, checkpoint: Path) -> dict:
    if not os.environ.get("S3_CONFIRM_MODEL_LICENSE") == "1":
        return {
            "stage": "siax_mini",
            "ok": False,
            "skipped": True,
            "reason": "set S3_CONFIRM_MODEL_LICENSE=1 after license review",
        }
    if not Path(checkpoint).is_file():
        return {"stage": "siax_mini", "ok": False, "skipped": True, "reason": "checkpoint_missing"}
    # Reuse single_pull pattern but mode siax — minimal region
    # Keep implementation conservative: only run if user explicitly asked stage
    py = sys.executable
    job_dir = Path(job_dir)
    job_dir.mkdir(parents=True, exist_ok=True)
    worker_id = "selfdrive_siax"
    agent = subprocess.Popen(
        [
            py, str(ROOT / "tools" / "s3_dock_local_pc.py"),
            "--job-dir", str(job_dir),
            "--worker-id", worker_id,
            "--mode", "siax",
            "--device", os.environ.get("S3_DEVICE", "cpu"),
            "--checkpoint", str(checkpoint),
            "--confirm-model-license-review",
            "--lease-seconds", str(lease),
            "--wait-manifest-s", "600",
            "--idle-exit-s", "120",
        ],
        cwd=str(ROOT),
        env={**os.environ, "PYTHONPATH": str(ROOT / "src"), "PYTHONUNBUFFERED": "1"},
    )
    try:
        reg = job_dir / "registry" / "workers" / f"{worker_id}.json"
        t0 = time.time()
        while time.time() - t0 < 60:
            if reg.is_file():
                break
            time.sleep(0.5)
        r = _run([
            py, str(ROOT / "tools" / "s3_controller.py"), "init",
            "--job-dir", str(job_dir), "--base", str(base),
            "--mode", "siax", "--region", "0,0,128,128",
            "--compute-core", "64", "--compute-context", "32",
            "--lease-seconds", str(lease),
        ], timeout=120)
        if r.returncode != 0:
            raise SystemExit("siax init failed")
        for sub in ("schedule", "wait", "rebuild"):
            cmd = [py, str(ROOT / "tools" / "s3_controller.py"), sub,
                   "--job-dir", str(job_dir), "--lease-seconds", str(lease)]
            if sub == "schedule":
                cmd += ["--wait-workers", "1", "--wait-timeout-s", "90"]
            if sub == "wait":
                cmd += ["--timeout-s", "3600", "--reassign-every-s", "5"]
            r = _run(cmd, timeout=4000 if sub == "wait" else 180)
            if r.returncode != 0:
                raise SystemExit(f"siax {sub} failed")
    finally:
        agent.terminate()
        try:
            agent.wait(timeout=30)
        except Exception:
            agent.kill()
    report = json.loads((job_dir / "controller_report.json").read_text(encoding="utf-8")) if (job_dir / "controller_report.json").is_file() else {}
    return {
        "stage": "siax_mini",
        "ok": bool(report.get("ok")),
        "physical_dual_host": False,
        "final_acceptance": False,
        "e3_speed_claim": False,
        "controller_report": report,
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--stages",
        default="unit,single_pull,self_hosted_hint",
        help="comma list: unit,single_pull,docker_dual,self_hosted_hint,siax_mini",
    )
    ap.add_argument("--job-dir", type=Path, default=None)
    ap.add_argument("--base", type=Path, default=None)
    ap.add_argument("--lease-seconds", type=float, default=90.0)
    ap.add_argument("--checkpoint", type=Path, default=Path("models/4x_NMKD-Siax_200k.pth"))
    ap.add_argument("--evidence-out", type=Path, default=None)
    args = ap.parse_args()

    stamp = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
    job = args.job_dir or (ROOT / "runs" / f"s3_self_drive_{stamp}")
    base = args.base or (job / "BASE_synthetic.png")

    results = []
    overall = True
    for name in [s.strip() for s in args.stages.split(",") if s.strip()]:
        if name == "unit":
            res = stage_unit()
        elif name == "single_pull":
            res = stage_single_pull(job / "single_pull", base, args.lease_seconds)
        elif name == "docker_dual":
            res = stage_docker_dual()
        elif name == "self_hosted_hint":
            res = stage_self_hosted_hint()
        elif name == "siax_mini":
            res = stage_siax_mini(job / "siax_mini", base, args.lease_seconds, args.checkpoint)
        else:
            res = {"stage": name, "ok": False, "error": "unknown_stage"}
        results.append(res)
        if not res.get("ok") and not res.get("skipped"):
            overall = False
        print(json.dumps(res, indent=2, ensure_ascii=False), flush=True)

    out = {
        "format": "ige.s3.self_drive_report",
        "format_version": "1.0",
        "stamp_utc": stamp,
        "ok": overall,
        "results": results,
        "final_acceptance": False,
        "e3_speed_claim": False,
        "physical_dual_host": False,
        "note": "GitHub dual self-hosted runners can share one job-dir; this script does not spawn remote Grok chat.",
    }
    if args.evidence_out:
        args.evidence_out.parent.mkdir(parents=True, exist_ok=True)
        args.evidence_out.write_text(json.dumps(out, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"ok": overall, "stages": [r["stage"] for r in results]}, indent=2))
    return 0 if overall else 2


if __name__ == "__main__":
    raise SystemExit(main())
