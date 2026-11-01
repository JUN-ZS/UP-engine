from __future__ import annotations

import json
import time
from pathlib import Path

from ige.upscale.s3.adapter_base import ChildRunSpec
from ige.upscale.s3.adapter_synthetic import SyntheticNearestAdapter
from ige.upscale.s3.controller import JobController
from ige.upscale.s3.transport_fs import FsLeaseTransport, StaleLeaseError


def test_kill_a_reassign_and_rebuild(tmp_path: Path, base_jpg: Path | None = None):
    base = base_jpg
    if base is None:
        from PIL import Image
        base = tmp_path / "base.png"
        Image.new("RGB", (128, 128), (3, 4, 5)).save(base)
    ctl = JobController(tmp_path / "job", lease_seconds=1.0, registry_stale_s=1.5)
    a0 = SyntheticNearestAdapter()
    man = ctl.init_job(
        base_path=base,
        mode="synthetic",
        model_id=a0.model_id,
        weight_sha256=a0.weight_sha256(),
        compute_core=64,
        compute_context=0,
        region=(0, 0, 128, 128),
        est_peak_rss_mib=50,
        job_id="kill",
    )
    for wid, thr in [("hostA_cpu", 20.0), ("hostB_cpu", 8.0)]:
        ctl.registry.report(
            {
                "worker_id": wid,
                "resources": {"ram_available_mib": 2000, "cpu_threads": 1},
                "devices": [{"device_id": "cpu", "kind": "cpu"}],
                "models": [
                    {
                        "model_id": a0.model_id,
                        "weight_sha256": a0.weight_sha256(),
                        "adapter_id": a0.adapter_id,
                    }
                ],
                "max_inflight": 64,
                "queue_depth": 0,
                "throughput_tiles_per_min_est": thr,
            }
        )
    assignment = ctl.schedule_and_enqueue(prefer_device="cpu")
    assert sum(1 for v in assignment.values() if v) == man["plan"]["child_count"]
    tr = FsLeaseTransport(tmp_path / "job" / "queue", lease_seconds=1.0, allow_unassigned=False)
    task = tr.claim("hostA_cpu")
    assert task is not None
    tok_dead = task["_fencing_token"]
    time.sleep(1.2)
    assert tr.requeue_expired() >= 1
    # only B remains live
    time.sleep(1.6)
    ctl.registry.report(
        {
            "worker_id": "hostB_cpu",
            "resources": {"ram_available_mib": 2000, "cpu_threads": 1},
            "devices": [{"device_id": "cpu", "kind": "cpu"}],
            "models": [
                {
                    "model_id": a0.model_id,
                    "weight_sha256": a0.weight_sha256(),
                    "adapter_id": a0.adapter_id,
                }
            ],
            "max_inflight": 64,
            "queue_depth": 0,
            "throughput_tiles_per_min_est": 8.0,
        }
    )
    info = ctl.reassign_orphans()
    assert info["reassigned"] >= 1
    children = tmp_path / "job" / "children"
    children.mkdir(exist_ok=True)
    while True:
        t = tr.claim("hostB_cpu")
        if t is None:
            break
        tok = t["_fencing_token"]
        spec = ChildRunSpec(
            child_id=t["child_id"],
            base_path=str(base),
            core_box_base=t["core_box_base"],
            input_box_base=t["input_box_base"],
            output_box_hires=t["output_box_hires"],
            extra={
                "out_uri": str(children / f"{t['child_id']}.png"),
                "job_id": man["job_id"],
                "worker_id": "hostB_cpu",
            },
        )
        tr.heartbeat("hostB_cpu", t["child_id"], tok)
        res = a0.run_child(spec)
        tr.complete("hostB_cpu", t["child_id"], tok, res.receipt)
    # stale complete rejected
    try:
        tr.complete("hostA_cpu", task["child_id"], tok_dead, {"status": "ok"})
        assert False, "expected stale"
    except StaleLeaseError:
        pass
    rep = ctl.rebuild()
    assert rep["ok"] is True
    return {
        "ok": True,
        "reassign": info,
        "rebuild": rep,
        "assignment": assignment,
        "stale_complete_rejected": True,
    }


if __name__ == "__main__":
    import tempfile
    from pathlib import Path as P

    with tempfile.TemporaryDirectory() as d:
        out = test_kill_a_reassign_and_rebuild(P(d))
    print(json.dumps(out, indent=2, default=str)[:500])
    # also write project evidence using real BASE if present
    base = P("runs/fair_e283/BASE.jpg")
    job = P("runs/s3_6_kill_evidence")
    import shutil

    if job.exists():
        shutil.rmtree(job)
    job.mkdir(parents=True)
    # use tmp style with real base
    with tempfile.TemporaryDirectory() as d:
        res = test_kill_a_reassign_and_rebuild(P(d), base if base.is_file() else None)
    P("docs/evidence/S3_6_DUAL_AGENT_KILL_A.json").write_text(
        json.dumps(
            {
                "program": "S3_6_DUAL_AGENT_PILOT",
                "scenario": "kill_a",
                "physical_dual_host": False,
                **res,
                "topology": {
                    "controller": "JobController",
                    "agents": "hostA crash + hostB takeover via reassign",
                    "note": "Physical dual-host not run; recovery interface proven",
                },
                "final_acceptance": False,
                "e3_speed_claim": False,
                "s21_quality": "INCONCLUSIVE_unchanged",
            },
            indent=2,
            default=str,
        )
        + "\n"
    )
    print("KILL_A_OK")
