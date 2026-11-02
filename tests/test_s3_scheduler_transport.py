from __future__ import annotations

import time
from pathlib import Path

from PIL import Image

from ige.upscale.s3.capability import WorkerCapability
from ige.upscale.s3.scheduler import CapabilityScheduler, ChildTask
from ige.upscale.s3.transport_fs import FsLeaseTransport
from ige.upscale.s3.job_plan import plan_compute_children
from ige.upscale.s3.adapter_synthetic import SyntheticNearestAdapter
from ige.upscale.s3.rebuild import rebuild_from_receipts, pixel_match_children
from ige.upscale.s3.worker_loop import run_worker_loop


MODEL = "4x_NMKD-Siax_200k"
SHA = "560424d9f68625713fc47e9e7289a98aabe1d744e1cd6a9ae5a35e9957fd127e"


def test_scheduler_prefers_gpu_and_respects_ram():
    gpu = WorkerCapability.from_dict(
        {
            "worker_id": "gpu-1",
            "resources": {"ram_available_mib": 16000, "cpu_threads": 8},
            "devices": [{"device_id": "cuda:0", "kind": "cuda", "vram_mib": 12000}],
            "models": [{"model_id": MODEL, "weight_sha256": SHA, "adapter_id": "siax.esgan.4x"}],
            "max_inflight": 2,
            "queue_depth": 0,
            "throughput_tiles_per_min_est": 30,
        }
    )
    weak = WorkerCapability.from_dict(
        {
            "worker_id": "weak-1",
            "resources": {"ram_available_mib": 400, "cpu_threads": 2},
            "devices": [{"device_id": "cpu", "kind": "cpu"}],
            "models": [{"model_id": MODEL, "weight_sha256": SHA, "adapter_id": "siax.esgan.4x"}],
            "max_inflight": 1,
            "queue_depth": 0,
            "throughput_tiles_per_min_est": 2,
        }
    )
    sch = CapabilityScheduler([gpu, weak], prefer_device="cuda")
    t = ChildTask("c1", MODEL, SHA, est_peak_rss_mib=700, payload={})
    assert sch.assign_one(t) == "gpu-1"
    sch2 = CapabilityScheduler([weak], prefer_device="cuda")
    assert sch2.assign_one(t) is None


def test_fs_lease_claim_complete_and_expire(tmp_path: Path):
    tr = FsLeaseTransport(tmp_path / "job", lease_seconds=0.3, allow_unassigned=False)
    tr.enqueue("childA", {"child_id": "childA", "assigned_worker": "w1", "n": 1})
    claimed = tr.claim("w1")
    assert claimed is not None
    tok = claimed["_fencing_token"]
    tr.complete("w1", "childA", tok, {"status": "ok", "sha256": "x" * 64})
    assert (tmp_path / "job" / "done" / "childA.json").is_file()
    tr.enqueue("childB", {"child_id": "childB", "assigned_worker": "w1"})
    claimed = tr.claim("w1")
    assert claimed is not None
    time.sleep(0.35)
    n = tr.requeue_expired()
    assert n >= 1
    again = tr.claim("w1")
    assert again is not None and again["child_id"] == "childB"


def test_plan_rebuild_synthetic(tmp_path: Path):
    base = tmp_path / "base.png"
    Image.new("RGB", (128, 128), (20, 40, 60)).save(base)
    plan = plan_compute_children(base, compute_core=64, compute_context=0, region=(0, 0, 128, 128))
    assert plan["child_count"] == 4
    transport = FsLeaseTransport(tmp_path / "q", lease_seconds=30, allow_unassigned=False)
    children_dir = tmp_path / "children"
    for i, c in enumerate(plan["children"]):
        c["assigned_worker"] = "w1" if i < 2 else "w2"
        transport.enqueue(c["child_id"], c)
    adapter = SyntheticNearestAdapter()
    r1 = run_worker_loop(
        transport, adapter, worker_id="w1", job_id="j", base_path=base, children_dir=children_dir
    )
    r2 = run_worker_loop(
        transport, adapter, worker_id="w2", job_id="j", base_path=base, children_dir=children_dir
    )
    assert r1["tasks_completed"] + r2["tasks_completed"] == 4
    receipts = transport.list_receipts()
    primary = tmp_path / "out.png"
    rep = rebuild_from_receipts(
        receipts=receipts,
        output_path=primary,
        output_width=512,
        output_height=512,
        origin_hires=(0, 0),
        min_bytes=100,
    )
    integ = pixel_match_children(receipts, primary)
    assert integ["ok"] is True
    assert rep["n_placed"] == 4
