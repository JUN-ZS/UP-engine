"""Importable agent entry for multiprocessing spawn (S3.6)."""
from __future__ import annotations

import json
import os
import time
from pathlib import Path


def agent_main(job_dir: str, worker_id: str, ram: float, thr: float, hang_s: float, lease_s: float):
    os.environ.setdefault("OMP_NUM_THREADS", "1")
    os.environ.setdefault("PYTHONUNBUFFERED", "1")
    job = Path(job_dir)
    for _ in range(100):
        if (job / "job_manifest.json").is_file():
            break
        time.sleep(0.05)
    man = json.loads((job / "job_manifest.json").read_text())
    from ige.upscale.s3.adapter_synthetic import SyntheticNearestAdapter
    from ige.upscale.s3.registry import WorkerRegistry
    from ige.upscale.s3 import FsLeaseTransport, run_worker_loop, StaleLeaseError

    adapter = SyntheticNearestAdapter()
    reg = WorkerRegistry(job, stale_after_s=20)
    transport = FsLeaseTransport(job / "queue", lease_seconds=lease_s, max_attempts=5, allow_unassigned=False)

    def publish():
        reg.report(
            {
                "worker_id": worker_id,
                "resources": {"ram_available_mib": ram, "cpu_threads": 1},
                "devices": [{"device_id": "cpu", "kind": "cpu"}],
                "models": [
                    {
                        "model_id": adapter.model_id,
                        "weight_sha256": adapter.weight_sha256(),
                        "adapter_id": adapter.adapter_id,
                    }
                ],
                "max_inflight": 64,
                "queue_depth": 0,
                "throughput_tiles_per_min_est": thr,
            }
        )

    publish()
    if hang_s > 0:
        t0 = time.time()
        while time.time() - t0 < 30:
            publish()
            try:
                task = transport.claim(worker_id)
            except StaleLeaseError:
                time.sleep(0.05)
                continue
            if task:
                time.sleep(hang_s)
                return
            time.sleep(0.1)
        return

    import threading

    stop = threading.Event()

    def reg_loop():
        while not stop.is_set():
            try:
                publish()
            except Exception:
                pass
            stop.wait(0.8)

    th = threading.Thread(target=reg_loop, daemon=True)
    th.start()
    expected = int(man["plan"]["child_count"])
    idle0 = time.time()
    while time.time() - idle0 < 60:
        if transport.done_count() >= expected:
            break
        try:
            res = run_worker_loop(
                transport,
                adapter,
                worker_id=worker_id,
                job_id=man["job_id"],
                base_path=man["base_path"],
                children_dir=job / "children",
                max_tasks=1,
                heartbeat_every_s=0.3,
                device="cpu",
            )
        except StaleLeaseError:
            time.sleep(0.05)
            continue
        if res.get("tasks_completed"):
            idle0 = time.time()
        else:
            time.sleep(0.1)
    stop.set()
