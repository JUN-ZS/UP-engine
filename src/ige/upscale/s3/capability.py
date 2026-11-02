from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class WorkerCapability:
    worker_id: str
    ram_available_mib: float
    cpu_threads: int = 1
    devices: list[dict[str, Any]] = field(default_factory=list)
    models: list[dict[str, Any]] = field(default_factory=list)
    max_inflight: int = 1
    queue_depth: int = 0
    throughput_tiles_per_min_est: float | None = None
    raw: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "WorkerCapability":
        res = data.get("resources") or {}
        return cls(
            worker_id=str(data["worker_id"]),
            ram_available_mib=float(res.get("ram_available_mib") or 0),
            cpu_threads=int(res.get("cpu_threads") or 1),
            devices=list(data.get("devices") or []),
            models=list(data.get("models") or []),
            max_inflight=int(data.get("max_inflight") or 1),
            queue_depth=int(data.get("queue_depth") or 0),
            throughput_tiles_per_min_est=(
                float(data["throughput_tiles_per_min_est"])
                if data.get("throughput_tiles_per_min_est") is not None
                else None
            ),
            raw=data,
        )

    def supports_model(self, model_id: str, weight_sha256: str) -> bool:
        for m in self.models:
            if m.get("model_id") == model_id and m.get("weight_sha256") == weight_sha256:
                return True
        return False

    def has_device_kind(self, kind: str) -> bool:
        return any(d.get("kind") == kind for d in self.devices)


def score_worker_for_child(
    worker: WorkerCapability,
    *,
    model_id: str,
    weight_sha256: str,
    est_peak_rss_mib: float,
    prefer_device: str = "cuda",
    enforce_max_inflight: bool = False,
) -> float | None:
    """Higher is better. None = ineligible.

    max_inflight is concurrent claim capacity, not total job share.
    Batch schedule uses enforce_max_inflight=False.
    """
    if not worker.supports_model(model_id, weight_sha256):
        return None
    if enforce_max_inflight and worker.queue_depth >= worker.max_inflight:
        return None
    if worker.ram_available_mib < est_peak_rss_mib + 256:
        return None
    score = 0.0
    if worker.has_device_kind(prefer_device):
        score += 100.0
    elif worker.has_device_kind("cpu"):
        score += 10.0
    thr = worker.throughput_tiles_per_min_est or 1.0
    score += thr
    score -= 5.0 * worker.queue_depth
    if worker.queue_depth >= max(1, worker.max_inflight):
        score -= 2.0 * (worker.queue_depth - worker.max_inflight + 1)
    score += min(worker.ram_available_mib, 65536) / 1024.0
    return score
