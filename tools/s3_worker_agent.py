#!/usr/bin/env python3
"""S3.6 Worker Agent — independent process that registers capability and pulls work.

Intended to run on each host. Uses shared job directory (NFS/SMB/local).
Does not claim quality PASS or E3 speed.

v1.1: wait for job_manifest with continuous registry heartbeat (default 600s);
      publish real --cpu-threads into registry resources.
"""
from __future__ import annotations

import argparse
import json
import os
import socket
import sys
import time
from pathlib import Path


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--job-dir", type=Path, required=True)
    ap.add_argument("--worker-id", required=True)
    ap.add_argument("--mode", choices=("synthetic", "siax"), default="synthetic")
    ap.add_argument("--checkpoint", type=Path, default=Path("models/4x_NMKD-Siax_200k.pth"))
    ap.add_argument("--device", default="cpu")
    ap.add_argument("--ram-mib", type=float, default=1800)
    ap.add_argument("--cpu-threads", type=int, default=0, help="0 = os.cpu_count()")
    ap.add_argument("--throughput-est", type=float, default=8.0)
    ap.add_argument("--lease-seconds", type=float, default=60)
    ap.add_argument("--heartbeat-every-s", type=float, default=1.0)
    ap.add_argument("--registry-every-s", type=float, default=2.0)
    ap.add_argument("--max-tasks", type=int, default=None)
    ap.add_argument("--idle-exit-s", type=float, default=15.0, help="exit if no work for this long")
    ap.add_argument(
        "--wait-manifest-s",
        type=float,
        default=600.0,
        help="seconds to wait for job_manifest.json while heartbeating (v1.1 dock)",
    )
    ap.add_argument("--confirm-model-license-review", action="store_true")
    ap.add_argument("--simulate-hang-s", type=float, default=0.0, help="test only: hang after claim without HB")
    args = ap.parse_args()

    src = str(Path(__file__).resolve().parents[1] / "src")
    sys.path.insert(0, src)
    cpu_threads = int(args.cpu_threads) if args.cpu_threads > 0 else int(os.cpu_count() or 1)
    os.environ.setdefault("OMP_NUM_THREADS", str(max(1, min(4, cpu_threads))))
    os.environ.setdefault("MKL_NUM_THREADS", os.environ["OMP_NUM_THREADS"])
    os.environ.setdefault("TORCH_NUM_THREADS", os.environ["OMP_NUM_THREADS"])

    from ige.upscale.s3 import (
        FsLeaseTransport,
        SiaxAdapter,
        SyntheticNearestAdapter,
        run_worker_loop,
    )
    from ige.upscale.s3.registry import WorkerRegistry
    from ige.upscale.siax import MODEL_SHA256

    job = Path(args.job_dir)
    queue = job / "queue"
    children = job / "children"
    children.mkdir(parents=True, exist_ok=True)
    queue.mkdir(parents=True, exist_ok=True)

    if args.mode == "siax":
        if not args.confirm_model_license_review:
            raise SystemExit("siax requires --confirm-model-license-review")
        model_id = "4x_NMKD-Siax_200k"
        weight_sha = MODEL_SHA256
        adapter_id = "siax.esgan.4x"
        adapter = SiaxAdapter(
            args.checkpoint,
            device=args.device,
            confirm_model_license_review=True,
        )
    else:
        adapter = SyntheticNearestAdapter()
        model_id = adapter.model_id
        weight_sha = adapter.weight_sha256()
        adapter_id = adapter.adapter_id

    registry = WorkerRegistry(job, stale_after_s=max(10.0, args.registry_every_s * 3))
    transport = FsLeaseTransport(
        queue,
        lease_seconds=args.lease_seconds,
        max_attempts=5,
        allow_unassigned=False,
    )

    def publish() -> None:
        cap = {
            "worker_id": args.worker_id,
            "hostname": socket.gethostname(),
            "pid": os.getpid(),
            "resources": {
                "ram_available_mib": float(args.ram_mib),
                "cpu_threads": int(cpu_threads),
            },
            "devices": [
                {
                    "device_id": args.device,
                    "kind": "cuda" if args.device.startswith("cuda") else (
                        "mps" if args.device == "mps" else "cpu"
                    ),
                    "name": args.device,
                }
            ],
            "models": [
                {
                    "model_id": model_id,
                    "weight_sha256": weight_sha,
                    "adapter_id": adapter_id,
                }
            ],
            "max_inflight": 64,
            "queue_depth": 0,
            "throughput_tiles_per_min_est": args.throughput_est,
        }
        registry.report(cap)

    publish()

    # v1.1: wait for controller init while heartbeating (worker-first dock order)
    man_path = job / "job_manifest.json"
    man: dict = {}
    t_wait0 = time.time()
    while time.time() - t_wait0 < float(args.wait_manifest_s):
        publish()
        if man_path.is_file():
            try:
                man = json.loads(man_path.read_text(encoding="utf-8"))
            except Exception:
                man = {}
            if man.get("base_path"):
                break
        time.sleep(min(0.5, args.registry_every_s))
    else:
        raise SystemExit(
            f"job_manifest.json not ready after {args.wait_manifest_s}s — "
            "start controller init on the same job-dir (worker may start first)"
        )

    job_id = man.get("job_id", "unknown")
    base_path = man.get("base_path")
    if not base_path:
        raise SystemExit("job_manifest.json missing base_path")

    # Optional hang mode for recovery tests: claim one then die without heartbeat
    if args.simulate_hang_s > 0:
        publish()
        t0 = time.time()
        while time.time() - t0 < 30:
            publish()
            task = transport.claim(args.worker_id)
            if task:
                time.sleep(args.simulate_hang_s)
                raise SystemExit(99)
            time.sleep(0.1)
        raise SystemExit("hang mode: no task claimed")

    import threading

    stop = threading.Event()

    def reg_loop() -> None:
        while not stop.is_set():
            try:
                publish()
            except Exception:
                pass
            stop.wait(args.registry_every_s)

    th = threading.Thread(target=reg_loop, daemon=True)
    th.start()

    idle_start = time.time()
    completed = 0
    total_result = {
        "worker_id": args.worker_id,
        "tasks_completed": 0,
        "task_ids": [],
        "tasks_stale": 0,
        "tasks_failed": 0,
        "cpu_threads": cpu_threads,
        "ram_mib": float(args.ram_mib),
    }
    while True:
        remaining = None if args.max_tasks is None else max(0, args.max_tasks - completed)
        if remaining == 0:
            break
        res = run_worker_loop(
            transport,
            adapter,
            worker_id=args.worker_id,
            job_id=job_id,
            base_path=base_path,
            children_dir=children,
            max_tasks=1 if remaining is None else min(1, remaining),
            heartbeat_every_s=args.heartbeat_every_s,
            device=args.device,
        )
        completed += res["tasks_completed"]
        total_result["tasks_completed"] = completed
        total_result["task_ids"].extend(res.get("task_ids") or [])
        total_result["tasks_stale"] += res.get("tasks_stale") or 0
        total_result["tasks_failed"] += res.get("tasks_failed") or 0
        if res["tasks_completed"] == 0 and res.get("tasks_failed", 0) == 0:
            pending_for_us = False
            for p in (queue / "pending").glob("*.json"):
                try:
                    d = json.loads(p.read_text(encoding="utf-8"))
                except Exception:
                    continue
                if d.get("assigned_worker") == args.worker_id:
                    pending_for_us = True
                    break
            if not pending_for_us:
                plan_remaining = False
                try:
                    plan = man.get("plan") or {}
                    done_n = transport.done_count()
                    total = int(plan.get("child_count") or 0)
                    if total and done_n < total:
                        plan_remaining = True
                except Exception:
                    pass
                if plan_remaining:
                    idle_start = time.time()
                    time.sleep(0.3)
                    continue
                if time.time() - idle_start >= args.idle_exit_s:
                    break
                time.sleep(0.2)
            else:
                idle_start = time.time()
                time.sleep(0.1)
        else:
            idle_start = time.time()

    stop.set()
    th.join(timeout=2)
    publish()
    out = job / "agent_reports" / f"{args.worker_id}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    total_result["hostname"] = socket.gethostname()
    total_result["pid"] = os.getpid()
    total_result["device"] = args.device
    total_result["mode"] = args.mode
    total_result["final_acceptance"] = False
    total_result["e3_speed_claim"] = False
    out.write_text(json.dumps(total_result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(total_result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
