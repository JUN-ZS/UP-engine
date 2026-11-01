from __future__ import annotations

import json
import time
from pathlib import Path

from ige.upscale.s3.capability import WorkerCapability
from ige.upscale.s3.scheduler import CapabilityScheduler, ChildTask
from ige.upscale.s3.transport_fs import FsLeaseTransport


MODEL = "4x_NMKD-Siax_200k"
SHA = "560424d9f68625713fc47e9e7289a98aabe1d744e1cd6a9ae5a35e9957fd127e"


def test_scheduler_prefers_gpu_and_respects_ram(tmp_path: Path | None = None):
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
    cpu = WorkerCapability.from_dict(
        {
            "worker_id": "cpu-1",
            "resources": {"ram_available_mib": 2000, "cpu_threads": 4},
            "devices": [{"device_id": "cpu", "kind": "cpu"}],
            "models": [{"model_id": MODEL, "weight_sha256": SHA, "adapter_id": "siax.esgan.4x"}],
            "max_inflight": 1,
            "queue_depth": 0,
            "throughput_tiles_per_min_est": 4,
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
    sch = CapabilityScheduler([gpu, cpu, weak], prefer_device="cuda")
    t = ChildTask("c1", MODEL, SHA, est_peak_rss_mib=700, payload={})
    assert sch.assign_one(t) == "gpu-1"
    # weak cannot take 700+256 peak
    sch2 = CapabilityScheduler([weak], prefer_device="cuda")
    assert sch2.assign_one(t) is None


def test_fs_lease_claim_complete_and_expire(tmp_path: Path):
    tr = FsLeaseTransport(tmp_path / "job", lease_seconds=0.3)
    tr.enqueue("childA", {"child_id": "childA", "n": 1})
    claimed = tr.claim("w1")
    assert claimed is not None
    assert claimed["child_id"] == "childA"
    # second claim empty
    assert tr.claim("w2") is None
    tr.complete("w1", "childA", {"status": "ok", "sha256": "x" * 64})
    assert (tmp_path / "job" / "done" / "childA.json").is_file()
    # expire path
    tr.enqueue("childB", {"child_id": "childB"})
    claimed = tr.claim("w1")
    assert claimed is not None
    time.sleep(0.35)
    n = tr.requeue_expired()
    assert n >= 1
    again = tr.claim("w2")
    assert again is not None and again["child_id"] == "childB"
