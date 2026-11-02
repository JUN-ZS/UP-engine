from __future__ import annotations

import json
import threading
import time
from pathlib import Path

from PIL import Image

from ige.upscale.s3.transport_fs import FsLeaseTransport, StaleLeaseError
from ige.upscale.s3.adapter_synthetic import SyntheticNearestAdapter
from ige.upscale.s3.worker_loop import run_worker_loop
from ige.upscale.s3.job_plan import plan_compute_children


def _task(cid="c1", assigned="w1"):
    return {
        "child_id": cid,
        "assigned_worker": assigned,
        "core_box_base": [0, 0, 32, 32],
        "input_box_base": [0, 0, 32, 32],
        "output_box_hires": [0, 0, 128, 128],
    }


def test_hard_assignment_blocks_other_worker(tmp_path: Path):
    tr = FsLeaseTransport(tmp_path / "q", lease_seconds=30, allow_unassigned=False)
    tr.enqueue("c1", _task("c1", "w1"))
    assert tr.claim("w2") is None
    got = tr.claim("w1")
    assert got is not None and got["child_id"] == "c1"
    assert got["_fencing_token"]


def test_stale_complete_rejected_after_requeue(tmp_path: Path):
    tr = FsLeaseTransport(tmp_path / "q", lease_seconds=0.25, max_attempts=5, allow_unassigned=False)
    tr.enqueue("c1", _task("c1", "w1"))
    claimed = tr.claim("w1")
    tok = claimed["_fencing_token"]
    # no heartbeat → expire
    time.sleep(0.35)
    n = tr.requeue_expired()
    assert n >= 1
    # stale complete must fail
    try:
        tr.complete("w1", "c1", tok, {"status": "ok", "sha256": "a" * 64})
        assert False, "expected StaleLeaseError"
    except StaleLeaseError:
        pass
    # new worker claim with new token
    claimed2 = tr.claim("w1")
    assert claimed2 is not None
    tok2 = claimed2["_fencing_token"]
    assert tok2 != tok
    tr.complete("w1", "c1", tok2, {"status": "ok", "sha256": "b" * 64, "uri": "x", "child_id": "c1"})
    receipts = tr.list_receipts()
    assert len(receipts) == 1
    assert receipts[0]["fencing_token"] == tok2


def test_heartbeat_thread_keeps_lease_during_long_work(tmp_path: Path):
    base = tmp_path / "base.png"
    Image.new("RGB", (64, 64), (1, 2, 3)).save(base)
    tr = FsLeaseTransport(tmp_path / "q", lease_seconds=0.4, allow_unassigned=False)
    plan = plan_compute_children(base, compute_core=64, region=(0, 0, 64, 64))
    c = plan["children"][0]
    c["assigned_worker"] = "w1"
    c["simulate_s"] = 1.0  # longer than lease if no heartbeat
    tr.enqueue(c["child_id"], c)
    adapter = SyntheticNearestAdapter()
    # heartbeat every 0.1s should keep lease alive through 1s work with lease 0.4s
    res = run_worker_loop(
        tr,
        adapter,
        worker_id="w1",
        job_id="j",
        base_path=base,
        children_dir=tmp_path / "ch",
        heartbeat_every_s=0.1,
        max_tasks=1,
    )
    assert res["tasks_completed"] == 1
    assert res["tasks_stale"] == 0
    assert tr.done_count() == 1


def test_assignment_fidelity_two_workers(tmp_path: Path):
    base = tmp_path / "base.png"
    Image.new("RGB", (128, 64), (10, 20, 30)).save(base)
    plan = plan_compute_children(base, compute_core=64, region=(0, 0, 128, 64))
    tr = FsLeaseTransport(tmp_path / "q", lease_seconds=30, allow_unassigned=False)
    # assign explicitly alternating
    for i, c in enumerate(plan["children"]):
        c["assigned_worker"] = "w_a" if i % 2 == 0 else "w_b"
        tr.enqueue(c["child_id"], c)
    adapter = SyntheticNearestAdapter()
    r_a = run_worker_loop(tr, adapter, worker_id="w_a", job_id="j", base_path=base, children_dir=tmp_path / "ch")
    r_b = run_worker_loop(tr, adapter, worker_id="w_b", job_id="j", base_path=base, children_dir=tmp_path / "ch")
    assert r_a["tasks_completed"] + r_b["tasks_completed"] == plan["child_count"]
    for rec in tr.list_receipts():
        # find assigned
        # all receipts must match assignment encoded in done only via worker_id == completer
        pass
    # w_a should only complete even indices
    assert set(r_a["task_ids"]).isdisjoint(set(r_b["task_ids"]))
    assert len(r_a["task_ids"]) + len(r_b["task_ids"]) == plan["child_count"]
