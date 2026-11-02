#!/usr/bin/env python3
"""S3 multi-worker simulation with hard assignment + fencing (S3.5).

Does NOT claim quality PASS or E3 speed.
"""
from __future__ import annotations

import argparse
import json
import multiprocessing as mp
import os
import time
from pathlib import Path


def _worker_entry(args: dict) -> dict:
    import sys

    sys.path.insert(0, args["src"])
    os.environ.setdefault("OMP_NUM_THREADS", "1")
    os.environ.setdefault("MKL_NUM_THREADS", "1")
    os.environ.setdefault("TORCH_NUM_THREADS", "1")
    from ige.upscale.s3 import FsLeaseTransport, SyntheticNearestAdapter, SiaxAdapter, run_worker_loop

    transport = FsLeaseTransport(
        args["job_root"],
        lease_seconds=args["lease_seconds"],
        max_attempts=args.get("max_attempts", 3),
        allow_unassigned=False,
    )
    if args["mode"] == "synthetic":
        adapter = SyntheticNearestAdapter()
    else:
        adapter = SiaxAdapter(
            args["checkpoint"],
            device=args["device"],
            confirm_model_license_review=True,
        )
    return run_worker_loop(
        transport,
        adapter,
        worker_id=args["worker_id"],
        job_id=args["job_id"],
        base_path=args["base"],
        children_dir=args["children_dir"],
        max_tasks=args.get("max_tasks"),
        heartbeat_every_s=args.get("heartbeat_every_s", 1.0),
        device=args["device"],
    )


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--job-dir", type=Path, required=True)
    ap.add_argument("--base", type=Path, required=True)
    ap.add_argument("--mode", choices=("synthetic", "siax"), default="synthetic")
    ap.add_argument("--checkpoint", type=Path, default=Path("models/4x_NMKD-Siax_200k.pth"))
    ap.add_argument("--compute-core", type=int, default=64)
    ap.add_argument("--compute-context", type=int, default=0)
    ap.add_argument("--region", default="", help="x0,y0,x1,y1 optional")
    # id:kind:ram_mib:device
    ap.add_argument("--workers", default="w_cpu_a:cpu:1800:cpu,w_cpu_b:cpu:1200:cpu")
    ap.add_argument("--lease-seconds", type=float, default=60)
    ap.add_argument("--heartbeat-every-s", type=float, default=1.0)
    ap.add_argument("--max-attempts", type=int, default=3)
    ap.add_argument("--out-report", type=Path, required=True)
    ap.add_argument("--confirm-model-license-review", action="store_true")
    args = ap.parse_args()

    if args.mode == "siax" and not args.confirm_model_license_review:
        raise SystemExit("siax mode requires --confirm-model-license-review")

    src = str(Path(__file__).resolve().parents[1] / "src")
    import sys

    sys.path.insert(0, src)
    from ige.upscale.siax import file_sha256, MODEL_SHA256
    from ige.upscale.s3 import (
        CapabilityScheduler,
        ChildTask,
        FsLeaseTransport,
        WorkerCapability,
        plan_compute_children,
        rebuild_from_receipts,
        pixel_match_children,
    )
    from ige.upscale.s3.adapter_synthetic import SyntheticNearestAdapter

    job = Path(args.job_dir)
    if job.exists() and any(job.iterdir()):
        raise SystemExit(f"job-dir must be empty/new: {job}")
    job.mkdir(parents=True)
    children_dir = job / "children"
    children_dir.mkdir()

    region = None
    if args.region.strip():
        region = tuple(int(x) for x in args.region.split(","))

    plan = plan_compute_children(
        args.base,
        compute_core=args.compute_core,
        compute_context=args.compute_context,
        region=region,
    )
    (job / "plan.json").write_text(json.dumps(plan, indent=2) + "\n")

    if args.mode == "siax":
        model_id = "4x_NMKD-Siax_200k"
        weight_sha = MODEL_SHA256
        est_rss = 700.0
    else:
        adapter0 = SyntheticNearestAdapter()
        model_id = adapter0.model_id
        weight_sha = adapter0.weight_sha256()
        est_rss = 200.0

    worker_specs = []
    caps = []
    for part in args.workers.split(","):
        bits = part.strip().split(":")
        if len(bits) == 3:
            wid, kind, ram = bits
            device = kind if kind in ("cpu", "cuda") else "cpu"
        else:
            wid, kind, ram, device = bits
        worker_specs.append({"worker_id": wid, "kind": kind, "ram": float(ram), "device": device})
        caps.append(
            WorkerCapability.from_dict(
                {
                    "worker_id": wid,
                    "resources": {"ram_available_mib": float(ram), "cpu_threads": 1},
                    "devices": [{"device_id": device, "kind": kind if kind in ("cpu", "cuda") else "cpu"}],
                    "models": [
                        {
                            "model_id": model_id,
                            "weight_sha256": weight_sha,
                            "adapter_id": "siax.esgan.4x" if args.mode == "siax" else "synthetic.nearest.4x",
                        }
                    ],
                    "max_inflight": 64,
                    "queue_depth": 0,
                    "throughput_tiles_per_min_est": 30.0 if kind == "cuda" else 8.0,
                }
            )
        )

    sch = CapabilityScheduler(caps, prefer_device="cuda")
    tasks = [
        ChildTask(
            child_id=c["child_id"],
            model_id=model_id,
            weight_sha256=weight_sha,
            est_peak_rss_mib=est_rss,
            payload=c,
        )
        for c in plan["children"]
    ]
    assignment = sch.assign_all(tasks)
    assigned = {k: v for k, v in assignment.items() if v}
    unassigned = [k for k, v in assignment.items() if v is None]
    (job / "assignment.json").write_text(json.dumps(assignment, indent=2) + "\n")

    transport = FsLeaseTransport(
        job / "queue",
        lease_seconds=args.lease_seconds,
        max_attempts=args.max_attempts,
        allow_unassigned=False,
    )
    for c in plan["children"]:
        wid = assignment.get(c["child_id"])
        if wid is None:
            continue
        payload = dict(c)
        payload["assigned_worker"] = wid  # HARD assignment
        transport.enqueue(c["child_id"], payload)

    job_id = f"s3_{args.mode}_{int(time.time())}"
    t0 = time.perf_counter()
    procs = []
    ctx = mp.get_context("spawn")
    for spec in worker_specs:
        entry = {
            "src": src,
            "job_root": str(job / "queue"),
            "lease_seconds": args.lease_seconds,
            "max_attempts": args.max_attempts,
            "heartbeat_every_s": args.heartbeat_every_s,
            "mode": args.mode,
            "checkpoint": str(args.checkpoint),
            "device": spec["device"],
            "worker_id": spec["worker_id"],
            "job_id": job_id,
            "base": str(args.base),
            "children_dir": str(children_dir),
            "max_tasks": None,
        }
        p = ctx.Process(target=_worker_entry, args=(entry,))
        p.start()
        procs.append((spec["worker_id"], p))

    results = {}
    for wid, p in procs:
        p.join(timeout=3600)
        results[wid] = {"exitcode": p.exitcode, "alive": p.is_alive()}
        if p.is_alive():
            p.terminate()
            results[wid]["terminated"] = True

    wall = time.perf_counter() - t0
    receipts = transport.list_receipts()
    by_worker: dict[str, int] = {}
    for r in receipts:
        by_worker[r["worker_id"]] = by_worker.get(r["worker_id"], 0) + 1

    # assignment fidelity: actual completer must match assigned_worker
    mismatches = []
    for r in receipts:
        cid = r["task_id"]
        if assignment.get(cid) and assignment[cid] != r["worker_id"]:
            mismatches.append({"child_id": cid, "assigned": assignment[cid], "actual": r["worker_id"]})

    out_w, out_h = plan["output_wh"]
    origin = tuple(plan["output_origin_hires"])
    primary = job / "OUT_PRIMARY.png"
    rebuild = None
    integrity = None
    if receipts and not unassigned and len(receipts) == plan["child_count"]:
        rebuild = rebuild_from_receipts(
            receipts=receipts,
            output_path=primary,
            output_width=out_w,
            output_height=out_h,
            origin_hires=origin,
            min_bytes=100 if args.mode == "synthetic" else 1000,
        )
        integrity = pixel_match_children(receipts, primary, origin_hires=origin)

    report = {
        "program": "S3_MULTI_WORKER_SIM",
        "control_plane": "S3.5_hard_assignment_fencing",
        "mode": args.mode,
        "job_id": job_id,
        "base_sha256": file_sha256(args.base),
        "plan": {
            "child_count": plan["child_count"],
            "compute_core": plan["compute_core"],
            "region": plan["region"],
            "output_wh": plan["output_wh"],
        },
        "assignment": {
            "assigned_n": len(assigned),
            "unassigned": unassigned,
            "by_worker_hint": {wid: sum(1 for v in assignment.values() if v == wid) for wid, _ in procs},
            "assignment_mismatches": mismatches,
        },
        "execution": {
            "wall_s": round(wall, 3),
            "receipts_n": len(receipts),
            "by_worker_completed": by_worker,
            "process_exits": results,
            "pending_left": transport.pending_count(),
            "failed_n": len(list((job / "queue" / "failed").glob("*.json"))),
            "dead_n": transport.dead_count(),
            "rejects_n": len(list((job / "queue" / "rejects").glob("*.json"))),
        },
        "rebuild": rebuild,
        "integrity": integrity,
        "ok": (
            len(mismatches) == 0
            and integrity is not None
            and integrity.get("ok") is True
            and len(receipts) == plan["child_count"]
        ),
        "final_acceptance": False,
        "quality_qualified": False,
        "e3_speed_claim": False,
    }
    args.out_report.parent.mkdir(parents=True, exist_ok=True)
    args.out_report.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n")
    print(json.dumps({
        "ok": report["ok"],
        "assignment_mismatches": mismatches,
        "by_worker_completed": by_worker,
        "by_worker_assigned": report["assignment"]["by_worker_hint"],
        "integrity": integrity,
    }, indent=2))
    return 0 if report["ok"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
