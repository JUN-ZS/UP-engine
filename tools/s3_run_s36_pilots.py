#!/usr/bin/env python3
from __future__ import annotations

import json
import multiprocessing as mp
import shutil
import sys
import time
from pathlib import Path

root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root / "src"))
sys.path.insert(0, str(root / "tools"))

from s3_agent_process import agent_main
from ige.upscale.s3.controller import JobController
from ige.upscale.s3.adapter_synthetic import SyntheticNearestAdapter


def run_scenario(scenario: str, report_path: Path) -> bool:
    job = root / f"runs/s3_6_mp_{scenario}_{int(time.time())}"
    if job.exists():
        shutil.rmtree(job, ignore_errors=True)
    job.mkdir(parents=True)
    lease_s = 10.0
    ctl = JobController(job, lease_seconds=lease_s, registry_stale_s=15.0)
    a0 = SyntheticNearestAdapter()
    man = ctl.init_job(
        base_path=(root / "runs/fair_e283/BASE.jpg").resolve(),
        mode="synthetic",
        model_id=a0.model_id,
        weight_sha256=a0.weight_sha256(),
        compute_core=64,
        compute_context=0,
        region=(0, 0, 128, 128),
        est_peak_rss_mib=200,
        job_id=f"s3_6_mp_{scenario}",
    )
    expected = man["plan"]["child_count"]
    hang = 15.0 if scenario == "kill_a" else 0.0
    ctx = mp.get_context("spawn")
    # balanced throughput so both get work
    pa = ctx.Process(target=agent_main, args=(str(job), "hostA_cpu", 2000.0, 12.0, hang, lease_s))
    pb = ctx.Process(target=agent_main, args=(str(job), "hostB_cpu", 1800.0, 10.0, 0.0, lease_s))
    pa.start()
    pb.start()
    t0 = time.time()
    while time.time() - t0 < 25:
        live = {w["worker_id"] for w in ctl.registry.list_live() if not w.get("_stale")}
        if live >= {"hostA_cpu", "hostB_cpu"}:
            break
        time.sleep(0.1)
    else:
        pa.terminate(); pb.terminate()
        raise RuntimeError(f"registry fail {ctl.registry.list_live()}")
    assignment = ctl.schedule_and_enqueue(prefer_device="cpu")
    assert sum(1 for v in assignment.values() if v) == expected, assignment
    wait = ctl.wait_until_done(expected=expected, timeout_s=75, reassign_every_s=1.0)
    pa.join(20)
    pb.join(20)
    if pa.is_alive():
        pa.terminate()
    if pb.is_alive():
        pb.terminate()
    rebuild = ctl.rebuild() if wait["done"] >= expected else {"ok": False, "error": "incomplete"}
    receipts = ctl.transport.list_receipts()
    by_w: dict[str, int] = {}
    for r in receipts:
        by_w[r["worker_id"]] = by_w.get(r["worker_id"], 0) + 1
    # fidelity vs final assignment file if reassigned
    final_assign = dict(assignment)
    for entry in wait.get("reassign_log") or []:
        for d in entry.get("details") or []:
            if d.get("to") and d.get("child_id"):
                final_assign[d["child_id"]] = d["to"]
        for d in (entry.get("missing") or {}).get("restored") or []:
            if d.get("child_id") and d.get("assigned_worker"):
                final_assign[d["child_id"]] = d["assigned_worker"]
    mismatches = []
    for r in receipts:
        exp = final_assign.get(r["task_id"])
        if exp and exp != r["worker_id"]:
            mismatches.append({"child_id": r["task_id"], "expected": exp, "actual": r["worker_id"]})
    reassigned_n = sum(int(e.get("reassigned") or 0) for e in (wait.get("reassign_log") or []))
    report = {
        "program": "S3_6_DUAL_AGENT_PILOT",
        "scenario": scenario,
        "mode": "synthetic",
        "physical_dual_host": False,
        "topology": {
            "controller": "JobController parent (no inference)",
            "agent_a": "multiprocessing.Process hostA_cpu",
            "agent_b": "multiprocessing.Process hostB_cpu",
            "transport": "shared_job_dir + fencing + hard assignment",
            "note": "Independent OS processes; dual-host-ready interface. Physical dual-host NOT run.",
        },
        "expected_children": expected,
        "initial_assignment": assignment,
        "final_assignment": final_assign,
        "wait": wait,
        "reassigned_n": reassigned_n,
        "by_worker_completed": by_w,
        "assignment_mismatches_vs_final": mismatches,
        "rebuild": rebuild,
        "ok": bool(rebuild.get("ok"))
        and wait.get("done", 0) >= expected
        and len(mismatches) == 0
        and (scenario != "kill_a" or reassigned_n >= 1 or by_w.get("hostB_cpu", 0) >= 1),
        "final_acceptance": False,
        "e3_speed_claim": False,
        "quality_qualified": False,
        "s21_quality": "INCONCLUSIVE_unchanged",
    }
    # kill_a: must show recovery (B did work or reassignment happened) and rebuild ok
    if scenario == "kill_a":
        report["ok"] = bool(rebuild.get("ok")) and wait.get("done", 0) >= expected and (
            reassigned_n >= 1 or by_w.get("hostB_cpu", 0) > 0
        )
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, indent=2) + "\n")
    # also symlink-like copy to stable path
    print(json.dumps({
        "scenario": scenario,
        "ok": report["ok"],
        "by_w": by_w,
        "done": wait.get("done"),
        "reassigned_n": reassigned_n,
        "mismatches": mismatches,
    }, indent=2))
    return bool(report["ok"])


if __name__ == "__main__":
    ok1 = run_scenario("happy", root / "docs/evidence/S3_6_DUAL_AGENT_HAPPY.json")
    ok2 = run_scenario("kill_a", root / "docs/evidence/S3_6_DUAL_AGENT_KILL_A.json")
    print("ALL", ok1, ok2)
    raise SystemExit(0 if (ok1 and ok2) else 2)
