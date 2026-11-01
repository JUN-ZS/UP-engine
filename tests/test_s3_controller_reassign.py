from __future__ import annotations

import time
from pathlib import Path

from PIL import Image

from ige.upscale.s3.controller import JobController
from ige.upscale.s3.registry import WorkerRegistry
from ige.upscale.s3.adapter_synthetic import SyntheticNearestAdapter


def test_reassign_when_worker_stale(tmp_path: Path):
    base = tmp_path / "base.png"
    Image.new("RGB", (64, 64), (1, 2, 3)).save(base)
    ctl = JobController(tmp_path / "job", lease_seconds=2, registry_stale_s=1.0)
    a = SyntheticNearestAdapter()
    man = ctl.init_job(
        base_path=base,
        mode="synthetic",
        model_id=a.model_id,
        weight_sha256=a.weight_sha256(),
        compute_core=64,
        compute_context=0,
        region=(0, 0, 64, 64),
        est_peak_rss_mib=100,
        job_id="t",
    )
    reg = ctl.registry
    # only dead worker registered then goes stale
    reg.report({
        "worker_id": "dead",
        "resources": {"ram_available_mib": 2000, "cpu_threads": 1},
        "devices": [{"device_id": "cpu", "kind": "cpu"}],
        "models": [{"model_id": a.model_id, "weight_sha256": a.weight_sha256(), "adapter_id": a.adapter_id}],
        "max_inflight": 2,
        "queue_depth": 0,
        "throughput_tiles_per_min_est": 10,
    })
    assignment = ctl.schedule_and_enqueue()
    assert all(v == "dead" for v in assignment.values() if v)
    time.sleep(1.2)  # stale
    # live worker appears
    reg.report({
        "worker_id": "live",
        "resources": {"ram_available_mib": 2000, "cpu_threads": 1},
        "devices": [{"device_id": "cpu", "kind": "cpu"}],
        "models": [{"model_id": a.model_id, "weight_sha256": a.weight_sha256(), "adapter_id": a.adapter_id}],
        "max_inflight": 2,
        "queue_depth": 0,
        "throughput_tiles_per_min_est": 10,
    })
    info = ctl.reassign_orphans()
    assert info["reassigned"] >= 1
    # pending tasks now assigned to live
    for p in (tmp_path / "job" / "queue" / "pending").glob("*.json"):
        import json
        d = json.loads(p.read_text())
        assert d["assigned_worker"] == "live"
