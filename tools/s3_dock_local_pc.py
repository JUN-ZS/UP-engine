#!/usr/bin/env python3
"""S3 Local-PC dock launcher v1.1 for Grok CLI / human dual-host.

Runs on YOUR machine. Uses YOUR CPU/RAM via s3_worker_agent.
Does NOT open a reverse shell to the remote Grok sandbox.
Coordination is via shared job-dir (or paste of handshake JSON into chat).

v1.1 fixes:
  - physical_dual_host defaults false; only --claim-physical-dual-host sets true
  - pass --cpu-threads into worker registry
  - worker waits for manifest up to --wait-manifest-s (default 600)
  - handshake is NOT used by scheduler (registry is)
"""
from __future__ import annotations

import argparse
import json
import os
import platform
import socket
import subprocess
import sys
import time
from pathlib import Path


def detect_resources() -> dict:
    cpu = os.cpu_count() or 1
    ram_total = None
    ram_avail = None
    try:
        if sys.platform == "win32":
            import ctypes

            class MEMORYSTATUSEX(ctypes.Structure):
                _fields_ = [
                    ("dwLength", ctypes.c_ulong),
                    ("dwMemoryLoad", ctypes.c_ulong),
                    ("ullTotalPhys", ctypes.c_ulonglong),
                    ("ullAvailPhys", ctypes.c_ulonglong),
                    ("ullTotalPageFile", ctypes.c_ulonglong),
                    ("ullAvailPageFile", ctypes.c_ulonglong),
                    ("ullTotalVirtual", ctypes.c_ulonglong),
                    ("ullAvailVirtual", ctypes.c_ulonglong),
                    ("sullAvailExtendedVirtual", ctypes.c_ulonglong),
                ]

            stat = MEMORYSTATUSEX()
            stat.dwLength = ctypes.sizeof(MEMORYSTATUSEX)
            ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(stat))
            ram_total = stat.ullTotalPhys / (1024 * 1024)
            ram_avail = stat.ullAvailPhys / (1024 * 1024)
        else:
            if Path("/proc/meminfo").is_file():
                info = {}
                for line in Path("/proc/meminfo").read_text().splitlines():
                    if ":" in line:
                        k, v = line.split(":", 1)
                        info[k.strip()] = v.strip()

                def kib(key: str):
                    raw = info.get(key, "")
                    parts = raw.split()
                    if not parts:
                        return None
                    return float(parts[0]) / 1024.0

                ram_total = kib("MemTotal")
                ram_avail = kib("MemAvailable") or kib("MemFree")
            else:
                try:
                    total = int(
                        subprocess.check_output(["sysctl", "-n", "hw.memsize"], text=True).strip()
                    )
                    ram_total = total / (1024 * 1024)
                    ram_avail = ram_total * 0.6
                except Exception:
                    pass
    except Exception:
        pass
    if ram_total is None:
        ram_total = 8192.0
    if ram_avail is None:
        ram_avail = max(1024.0, ram_total * 0.5)
    safe_avail = max(512.0, ram_avail - 512.0)
    return {
        "ram_total_mib": round(ram_total, 1),
        "ram_available_mib": round(safe_avail, 1),
        "cpu_threads": int(cpu),
        "platform": platform.platform(),
        "python": sys.version.split()[0],
    }


def write_handshake(
    path: Path,
    *,
    worker_id: str,
    job_dir: Path,
    resources: dict,
    device: str,
    dock_mode: str,
    status: str,
    note: str = "",
    claim_physical_dual_host: bool = False,
) -> dict:
    body = {
        "format": "ige.s3.dock_handshake",
        "format_version": "1.1",
        "role": "local_pc_worker",
        "worker_id": worker_id,
        "hostname": socket.gethostname(),
        "pid": os.getpid(),
        "reported_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "resources": {
            "ram_available_mib": resources["ram_available_mib"],
            "ram_total_mib": resources["ram_total_mib"],
            "cpu_threads": resources["cpu_threads"],
        },
        "devices": [
            {
                "device_id": device,
                "kind": "cuda"
                if device.startswith("cuda")
                else ("mps" if device == "mps" else "cpu"),
                "name": device,
            }
        ],
        "dock_mode": dock_mode,
        "job_dir": str(job_dir.resolve()),
        "shared_root": str(job_dir.resolve()),
        "status": status,
        "note": note
        or (
            "Handshake is offline announcement only. Scheduler reads "
            "registry/workers/<id>.json, not this file."
        ),
        "platform": resources.get("platform"),
        "python": resources.get("python"),
        "final_acceptance": False,
        "e3_speed_claim": False,
        # Operator claim only — never inferred from dock_mode alone (v1.1).
        "physical_dual_host": bool(claim_physical_dual_host),
        "claims": {
            "uses_local_cpu_ram": True,
            "remote_grok_sandbox_cannot_steal_local_ram": True,
            "realtime": "fs_pull_heartbeat_not_websocket",
            "scheduler_reads": "registry/workers/<id>.json",
            "handshake_not_used_by_scheduler": True,
        },
        "controller_where": "unknown",
        "sync": "unknown",
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(body, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    tmp.replace(path)
    return body


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--job-dir", type=Path, required=True)
    ap.add_argument("--worker-id", default="")
    ap.add_argument("--mode", choices=("synthetic", "siax"), default="synthetic")
    ap.add_argument("--device", default="cpu")
    ap.add_argument("--checkpoint", type=Path, default=Path("models/4x_NMKD-Siax_200k.pth"))
    ap.add_argument("--ram-mib", type=float, default=0, help="0 = auto-detect available")
    ap.add_argument("--cpu-threads", type=int, default=0, help="0 = auto")
    ap.add_argument("--throughput-est", type=float, default=0, help="0 = heuristic from cpu")
    ap.add_argument("--lease-seconds", type=float, default=90)
    ap.add_argument("--heartbeat-every-s", type=float, default=1.0)
    ap.add_argument("--registry-every-s", type=float, default=2.0)
    ap.add_argument("--idle-exit-s", type=float, default=120)
    ap.add_argument("--wait-manifest-s", type=float, default=600.0)
    ap.add_argument(
        "--dock-mode",
        choices=("shared_fs", "rsync_pull", "manual_paste", "http_pull_future"),
        default="shared_fs",
    )
    ap.add_argument(
        "--claim-physical-dual-host",
        action="store_true",
        help="operator declaration only; default false even if dock_mode=shared_fs",
    )
    ap.add_argument("--handshake-out", type=Path, default=None)
    ap.add_argument("--print-handshake-only", action="store_true")
    ap.add_argument("--confirm-model-license-review", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    root = Path(__file__).resolve().parents[1]
    agent = root / "tools" / "s3_worker_agent.py"
    if not agent.is_file():
        raise SystemExit(f"missing {agent}")

    resources = detect_resources()
    if args.ram_mib > 0:
        resources["ram_available_mib"] = float(args.ram_mib)
    if args.cpu_threads > 0:
        resources["cpu_threads"] = int(args.cpu_threads)
    thr = args.throughput_est
    if thr <= 0:
        thr = max(2.0, min(60.0, resources["cpu_threads"] * 2.5))

    worker_id = args.worker_id or f"localpc_{socket.gethostname().replace(' ', '_')}"
    job = args.job_dir
    job.mkdir(parents=True, exist_ok=True)
    hs_path = args.handshake_out or (job / "dock" / "local_pc_handshake.json")
    hs = write_handshake(
        hs_path,
        worker_id=worker_id,
        job_dir=job,
        resources=resources,
        device=args.device,
        dock_mode=args.dock_mode,
        status="online",
        note="Paste this JSON into Grok chat if shared FS is not yet wired. "
        "Scheduler ignores handshake; it needs registry after agent starts.",
        claim_physical_dual_host=args.claim_physical_dual_host,
    )
    print(json.dumps(hs, indent=2, ensure_ascii=False), flush=True)
    if args.print_handshake_only:
        return 0

    cmd = [
        sys.executable,
        str(agent),
        "--job-dir",
        str(job),
        "--worker-id",
        worker_id,
        "--mode",
        args.mode,
        "--device",
        args.device,
        "--ram-mib",
        str(resources["ram_available_mib"]),
        "--cpu-threads",
        str(int(resources["cpu_threads"])),
        "--throughput-est",
        str(thr),
        "--lease-seconds",
        str(args.lease_seconds),
        "--heartbeat-every-s",
        str(args.heartbeat_every_s),
        "--registry-every-s",
        str(args.registry_every_s),
        "--idle-exit-s",
        str(args.idle_exit_s),
        "--wait-manifest-s",
        str(args.wait_manifest_s),
    ]
    if args.mode == "siax":
        if not args.confirm_model_license_review:
            raise SystemExit("siax requires --confirm-model-license-review")
        cmd += ["--confirm-model-license-review", "--checkpoint", str(args.checkpoint)]

    env = os.environ.copy()
    env["PYTHONPATH"] = str(root / "src") + os.pathsep + env.get("PYTHONPATH", "")
    env["PYTHONUNBUFFERED"] = "1"
    env["OMP_NUM_THREADS"] = str(max(1, min(4, resources["cpu_threads"])))
    env["MKL_NUM_THREADS"] = env["OMP_NUM_THREADS"]
    env["TORCH_NUM_THREADS"] = env["OMP_NUM_THREADS"]

    print("+", " ".join(cmd), flush=True)
    if args.dry_run:
        return 0
    write_handshake(
        hs_path,
        worker_id=worker_id,
        job_dir=job,
        resources=resources,
        device=args.device,
        dock_mode=args.dock_mode,
        status="working",
        claim_physical_dual_host=args.claim_physical_dual_host,
    )
    rc = 1
    try:
        rc = subprocess.call(cmd, env=env)
    finally:
        write_handshake(
            hs_path,
            worker_id=worker_id,
            job_dir=job,
            resources=resources,
            device=args.device,
            dock_mode=args.dock_mode,
            status="idle" if rc == 0 else "error",
            note=f"agent_exit={rc}",
            claim_physical_dual_host=args.claim_physical_dual_host,
        )
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
