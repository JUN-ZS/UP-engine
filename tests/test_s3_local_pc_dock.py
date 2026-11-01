"""S3 local PC dock v1.1 — runnable order (single-host pull).

Does not claim physical dual-host, quality PASS, or E3.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import threading
import time
from pathlib import Path

import pytest
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
SRC = str(ROOT / "src")
PY = sys.executable


def _run(cmd: list[str], *, env: dict | None = None, timeout: float = 120) -> subprocess.CompletedProcess:
    e = os.environ.copy()
    e["PYTHONPATH"] = SRC + os.pathsep + e.get("PYTHONPATH", "")
    e["PYTHONUNBUFFERED"] = "1"
    if env:
        e.update(env)
    return subprocess.run(
        cmd,
        cwd=str(ROOT),
        env=e,
        capture_output=True,
        text=True,
        timeout=timeout,
    )


def test_handshake_print_only(tmp_path: Path):
    job = tmp_path / "job"
    r = _run(
        [
            PY,
            str(ROOT / "tools" / "s3_dock_local_pc.py"),
            "--job-dir",
            str(job),
            "--print-handshake-only",
        ]
    )
    assert r.returncode == 0, r.stderr
    hs = json.loads(r.stdout)
    assert hs["format"] == "ige.s3.dock_handshake"
    assert hs["format_version"] == "1.1"
    assert hs["physical_dual_host"] is False
    assert hs["claims"]["handshake_not_used_by_scheduler"] is True
    assert (job / "dock" / "local_pc_handshake.json").is_file()
    assert hs["resources"]["cpu_threads"] >= 1
    assert hs["resources"]["ram_available_mib"] >= 456  # synthetic schedule threshold margin on CI hosts


def test_init_allows_dock_and_registry_bootstrap(tmp_path: Path):
    job = tmp_path / "job"
    (job / "dock").mkdir(parents=True)
    (job / "registry" / "workers").mkdir(parents=True)
    (job / "dock" / "local_pc_handshake.json").write_text("{}", encoding="utf-8")
    (job / "registry" / "workers" / "w1.json").write_text(
        json.dumps({"worker_id": "w1", "reported_at": time.time()}),
        encoding="utf-8",
    )
    (job / "queue").mkdir()
    (job / "children").mkdir()
    base = tmp_path / "base.png"
    Image.new("RGB", (64, 64), (9, 9, 9)).save(base)
    r = _run(
        [
            PY,
            str(ROOT / "tools" / "s3_controller.py"),
            "init",
            "--job-dir",
            str(job),
            "--base",
            str(base),
            "--mode",
            "synthetic",
            "--region",
            "0,0,64,64",
            "--compute-core",
            "64",
            "--lease-seconds",
            "15",
        ]
    )
    assert r.returncode == 0, r.stdout + r.stderr
    assert (job / "job_manifest.json").is_file()


def test_worker_first_then_init_schedule_wait_rebuild(tmp_path: Path):
    """handshake → worker first → init → schedule → wait → rebuild (synthetic pull)."""
    job = tmp_path / "job_pull"
    base = tmp_path / "base.png"
    Image.new("RGB", (128, 128), (10, 20, 30)).save(base)
    lease = "20"
    worker_id = "localpc_test"

    # start worker first (waits for manifest)
    agent_cmd = [
        PY,
        str(ROOT / "tools" / "s3_dock_local_pc.py"),
        "--job-dir",
        str(job),
        "--worker-id",
        worker_id,
        "--mode",
        "synthetic",
        "--device",
        "cpu",
        "--ram-mib",
        "2048",
        "--cpu-threads",
        "4",
        "--lease-seconds",
        lease,
        "--wait-manifest-s",
        "60",
        "--idle-exit-s",
        "20",
        "--registry-every-s",
        "0.5",
    ]
    proc = subprocess.Popen(
        agent_cmd,
        cwd=str(ROOT),
        env={
            **os.environ,
            "PYTHONPATH": SRC + os.pathsep + os.environ.get("PYTHONPATH", ""),
            "PYTHONUNBUFFERED": "1",
        },
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    try:
        # wait until registry has live worker
        reg = job / "registry" / "workers" / f"{worker_id}.json"
        t0 = time.time()
        while time.time() - t0 < 15:
            if reg.is_file():
                try:
                    d = json.loads(reg.read_text(encoding="utf-8"))
                    if int((d.get("resources") or {}).get("cpu_threads") or 0) == 4:
                        break
                except Exception:
                    pass
            time.sleep(0.2)
        else:
            out = proc.stdout.read() if proc.stdout else ""
            raise AssertionError(f"registry not ready: {out}")

        cap = json.loads(reg.read_text(encoding="utf-8"))
        assert cap["resources"]["cpu_threads"] == 4
        assert cap["resources"]["ram_available_mib"] == 2048

        r_init = _run(
            [
                PY,
                str(ROOT / "tools" / "s3_controller.py"),
                "init",
                "--job-dir",
                str(job),
                "--base",
                str(base),
                "--mode",
                "synthetic",
                "--region",
                "0,0,128,128",
                "--compute-core",
                "64",
                "--lease-seconds",
                lease,
            ]
        )
        assert r_init.returncode == 0, r_init.stdout + r_init.stderr

        r_sched = _run(
            [
                PY,
                str(ROOT / "tools" / "s3_controller.py"),
                "schedule",
                "--job-dir",
                str(job),
                "--wait-workers",
                "1",
                "--wait-timeout-s",
                "30",
                "--lease-seconds",
                lease,
            ]
        )
        assert r_sched.returncode == 0, r_sched.stdout + r_sched.stderr
        sched = json.loads(r_sched.stdout)
        assert sched["ok"] is True
        assert sched["assigned"] >= 1

        r_wait = _run(
            [
                PY,
                str(ROOT / "tools" / "s3_controller.py"),
                "wait",
                "--job-dir",
                str(job),
                "--timeout-s",
                "90",
                "--reassign-every-s",
                "1",
                "--lease-seconds",
                lease,
            ],
            timeout=120,
        )
        assert r_wait.returncode == 0, r_wait.stdout + r_wait.stderr
        wait = json.loads(r_wait.stdout)
        assert wait["ok"] is True

        r_reb = _run(
            [
                PY,
                str(ROOT / "tools" / "s3_controller.py"),
                "rebuild",
                "--job-dir",
                str(job),
                "--lease-seconds",
                lease,
            ]
        )
        assert r_reb.returncode == 0, r_reb.stdout + r_reb.stderr
        reb = json.loads(r_reb.stdout)
        assert reb["ok"] is True
        assert reb["final_acceptance"] is False
        assert reb["e3_speed_claim"] is False
        assert (job / "OUT_PRIMARY.png").is_file()
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except Exception:
            proc.kill()
