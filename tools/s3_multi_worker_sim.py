#!/usr/bin/env python3
"""S3 multi-worker synthetic (or mini Siax) simulation.

Validates: capability schedule · FS lease claim · multi-process workers ·
rebuild · pixel integrity. Does NOT claim quality PASS or E3 speed.
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

    transport = FsLeaseTransport(args["job_root"], lease_seconds=args["lease_seconds"])
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
    ap.add_argument("--workers", default="w_cpu_a:cpu:1800,w_cpu_b:cpu:1200")
    ap.add_argument("--lease-seconds", type=float, default=60)
    ap.add_argument("--device", default="cpu")
    ap.add_argument("--out-report", type=Path, required=True)
    ap.add_argument("--confirm-model-license-review", action="store_true")
    args = ap.parse_args()

    if args.mode == "siax" and not args.confirm_model_license_review:
        raise SystemExit("siax mode requires --confirm-model-license-review")

    src = str(Path(__file__).resolve().parents[1] / "src")
    import sys

    sys.path.insert(0, src)
    from ige.upscale.siax import file_sha256
    from ige.upscale.s3 import (
        CapabilityScheduler,
        ChildTask,
        FsLeaseTransport,
        WorkerCapability,
        plan_compute_children,
        rebuild_from_receipts,
        pixel_match_children,
    )
    from ige.upscale.s3.adapter_siax import SiaxAdapter
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
        assert len(region) == 4

    plan = plan_compute_children(
        args.base,
        compute_core=args.compute_core,
        compute_context=args.compute_context,
        region=region,
    )
    (job / "plan.json").write_text(json.dumps(plan, indent=2) + "\n")

    if args.mode == "siax":
        model_id = SiaxAdapter.model_id
        # weight sha without loading full adapter twice
        from ige.upscale.siax import MODEL_SHA256

        weight_sha = MODEL_SHA256
        est_rss = 700.0
    else:
        adapter0 = SyntheticNearestAdapter()
        model_id = adapter0.model_id
        weight_sha = adapter0.weight_sha256()
        est_rss = 200.0

    # parse workers: id:kind:ram_mib
    caps = []
    for part in args.workers.split(","):
        wid, kind, ram = part.strip().split(":")
        caps.append(
            WorkerCapability.from_dict(
                {
                    "worker_id": wid,
                    "resources": {"ram_available_mib": float(ram), "cpu_threads": 1},
                    "devices": [{"device_id": kind, "kind": kind if kind in ("cpu", "cuda") else "cpu"}],
                    "models": [
                        {
                            "model_id": model_id,
                            "weight_sha256": weight_sha,
                            "adapter_id": "siax.esgan.4x" if args.mode == "siax" else "synthetic.nearest.4x",
                        }
                    ],
                    "max_inflight": 8,
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

    transport = FsLeaseTransport(job / "queue", lease_seconds=args.lease_seconds)
    for c in plan["children"]:
        if c["child_id"] in unassigned:
            continue
        payload = dict(c)
        payload["assigned_worker_hint"] = assignment[c["child_id"]]
        transport.enqueue(c["child_id"], payload)

    job_id = f"s3_{args.mode}_{int(time.time())}"
    t0 = time.perf_counter()
    procs = []
    ctx = mp.get_context("spawn")
    for cap in caps:
        entry = {
            "src": src,
            "job_root": str(job / "queue"),
            "lease_seconds": args.lease_seconds,
            "mode": args.mode,
            "checkpoint": str(args.checkpoint),
            "device": args.device,
            "worker_id": cap.worker_id,
            "job_id": job_id,
            "base": str(args.base),
            "children_dir": str(children_dir),
            "max_tasks": None,
        }
        p = ctx.Process(target=_worker_entry, args=(entry,))
        p.start()
        procs.append((cap.worker_id, p))

    results = {}
    for wid, p in procs:
        p.join(timeout=3600)
        results[wid] = {"exitcode": p.exitcode, "alive": p.is_alive()}
        if p.is_alive():
            p.terminate()
            results[wid]["terminated"] = True

    wall = time.perf_counter() - t0
    receipts = transport.list_receipts()
    # rebuild only the planned region canvas
    out_w, out_h = plan["output_wh"]
    origin = tuple(plan["output_origin_hires"])
    primary = job / "OUT_PRIMARY.png"
    rebuild = rebuild_from_receipts(
        receipts=receipts,
        output_path=primary,
        output_width=out_w,
        output_height=out_h,
        origin_hires=origin,
        min_bytes=100 if args.mode == "synthetic" else 1000,
    )
    integrity = pixel_match_children(receipts, primary, origin_hires=origin)

    by_worker: dict[str, int] = {}
    for r in receipts:
        by_worker[r["worker_id"]] = by_worker.get(r["worker_id"], 0) + 1

    report = {
        "program": "S3_MULTI_WORKER_SIM",
        "mode": args.mode,
        "job_id": job_id,
        "base": str(args.base),
        "base_sha256": file_sha256(args.base),
        "plan": {
            "child_count": plan["child_count"],
            "compute_core": plan["compute_core"],
            "compute_context": plan["compute_context"],
            "region": plan["region"],
            "output_wh": plan["output_wh"],
        },
        "assignment": {
            "assigned_n": len(assigned),
            "unassigned": unassigned,
            "by_worker_hint": {
                wid: sum(1 for v in assignment.values() if v == wid) for wid in results
            },
        },
        "execution": {
            "wall_s": round(wall, 3),
            "receipts_n": len(receipts),
            "by_worker_completed": by_worker,
            "process_exits": results,
            "pending_left": transport.pending_count(),
            "failed_n": len(list((job / "queue" / "failed").glob("*.json"))),
        },
        "rebuild": rebuild,
        "integrity": integrity,
        "ok": integrity.get("ok") is True and len(receipts) == plan["child_count"] - len(unassigned),
        "final_acceptance": False,
        "quality_qualified": False,
        "e3_speed_claim": False,
        "note": "S3 dispatch/rebuild smoke only; not S2.1 quality flip; not E3",
    }
    args.out_report.parent.mkdir(parents=True, exist_ok=True)
    args.out_report.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n")
    print(json.dumps({k: report[k] for k in ("mode", "ok", "execution", "integrity", "rebuild") if k in report}, indent=2))
    # slim print rebuild sha
    print("output_sha256", rebuild.get("output_sha256"))
    print("ok", report["ok"])
    return 0 if report["ok"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
