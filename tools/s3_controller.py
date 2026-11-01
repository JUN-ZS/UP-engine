#!/usr/bin/env python3
"""S3.6 Job Controller CLI — plan, schedule, reassign, wait, rebuild.

Does not run inference. Does not claim quality PASS or E3.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    sub = ap.add_subparsers(dest="cmd", required=True)

    p_init = sub.add_parser("init")
    p_init.add_argument("--job-dir", type=Path, required=True)
    p_init.add_argument("--base", type=Path, required=True)
    p_init.add_argument("--mode", choices=("synthetic", "siax"), default="synthetic")
    p_init.add_argument("--region", default="")
    p_init.add_argument("--compute-core", type=int, default=64)
    p_init.add_argument("--compute-context", type=int, default=0)
    p_init.add_argument("--lease-seconds", type=float, default=30)
    p_init.add_argument("--job-id", default="")

    p_sched = sub.add_parser("schedule")
    p_sched.add_argument("--job-dir", type=Path, required=True)
    p_sched.add_argument("--wait-workers", type=int, default=1)
    p_sched.add_argument("--wait-timeout-s", type=float, default=60)
    p_sched.add_argument("--lease-seconds", type=float, default=30)

    p_wait = sub.add_parser("wait")
    p_wait.add_argument("--job-dir", type=Path, required=True)
    p_wait.add_argument("--timeout-s", type=float, default=600)
    p_wait.add_argument("--lease-seconds", type=float, default=30)
    p_wait.add_argument("--reassign-every-s", type=float, default=2.0)

    p_rebuild = sub.add_parser("rebuild")
    p_rebuild.add_argument("--job-dir", type=Path, required=True)
    p_rebuild.add_argument("--lease-seconds", type=float, default=30)

    p_status = sub.add_parser("status")
    p_status.add_argument("--job-dir", type=Path, required=True)

    args = ap.parse_args()
    src = str(Path(__file__).resolve().parents[1] / "src")
    sys.path.insert(0, src)

    from ige.upscale.s3.controller import JobController
    from ige.upscale.s3.adapter_synthetic import SyntheticNearestAdapter
    from ige.upscale.siax import MODEL_SHA256

    if args.cmd == "init":
        if args.job_dir.exists() and any(args.job_dir.iterdir()):
            raise SystemExit(f"job-dir must be empty: {args.job_dir}")
        ctl = JobController(args.job_dir, lease_seconds=args.lease_seconds)
        region = None
        if args.region.strip():
            region = tuple(int(x) for x in args.region.split(","))
        if args.mode == "siax":
            model_id, weight_sha, est = "4x_NMKD-Siax_200k", MODEL_SHA256, 700.0
        else:
            a = SyntheticNearestAdapter()
            model_id, weight_sha, est = a.model_id, a.weight_sha256(), 200.0
        job_id = args.job_id or f"s3_{args.mode}_{int(time.time())}"
        man = ctl.init_job(
            base_path=args.base,
            mode=args.mode,
            model_id=model_id,
            weight_sha256=weight_sha,
            compute_core=args.compute_core,
            compute_context=args.compute_context,
            region=region,
            est_peak_rss_mib=est,
            job_id=job_id,
        )
        print(json.dumps({"ok": True, "job_id": job_id, "child_count": man["plan"]["child_count"]}, indent=2))
        return 0

    if args.cmd == "schedule":
        ctl = JobController(args.job_dir, lease_seconds=args.lease_seconds)
        live = ctl.wait_for_workers(args.wait_workers, args.wait_timeout_s)
        if len(live) < args.wait_workers:
            print(json.dumps({"ok": False, "live": live, "error": "not_enough_workers"}, indent=2))
            return 2
        assignment = ctl.schedule_and_enqueue()
        print(json.dumps({
            "ok": True,
            "live_workers": [w["worker_id"] for w in live],
            "assigned": sum(1 for v in assignment.values() if v),
            "assignment": assignment,
        }, indent=2))
        return 0

    if args.cmd == "wait":
        ctl = JobController(args.job_dir, lease_seconds=args.lease_seconds)
        man = ctl.load_manifest()
        expected = int(man["plan"]["child_count"])
        result = ctl.wait_until_done(
            expected=expected,
            timeout_s=args.timeout_s,
            reassign_every_s=args.reassign_every_s,
        )
        result["ok"] = result["done"] >= expected
        print(json.dumps(result, indent=2))
        return 0 if result["ok"] else 2

    if args.cmd == "rebuild":
        ctl = JobController(args.job_dir, lease_seconds=args.lease_seconds)
        rep = ctl.rebuild()
        print(json.dumps(rep, indent=2))
        return 0 if rep.get("ok") else 2

    if args.cmd == "status":
        ctl = JobController(args.job_dir)
        live = ctl.registry.list_live()
        print(json.dumps({
            "live": live,
            "pending": ctl.transport.pending_count(),
            "done": ctl.transport.done_count(),
            "dead": ctl.transport.dead_count(),
        }, indent=2, default=str))
        return 0

    return 1


if __name__ == "__main__":
    raise SystemExit(main())
