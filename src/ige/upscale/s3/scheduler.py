from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable

from .capability import WorkerCapability, score_worker_for_child


@dataclass
class ChildTask:
    child_id: str
    model_id: str
    weight_sha256: str
    est_peak_rss_mib: float
    payload: dict[str, Any]


class CapabilityScheduler:
    """Greedy capability-aware assignment (v0).

    Does **not** average-split. Re-score after each assignment using updated queue_depth.
    """

    def __init__(self, workers: Iterable[WorkerCapability], *, prefer_device: str = "cuda"):
        self.workers = {w.worker_id: w for w in workers}
        self.prefer_device = prefer_device

    def assign_one(self, task: ChildTask) -> str | None:
        best_id: str | None = None
        best_score: float | None = None
        for wid, w in self.workers.items():
            s = score_worker_for_child(
                w,
                model_id=task.model_id,
                weight_sha256=task.weight_sha256,
                est_peak_rss_mib=task.est_peak_rss_mib,
                prefer_device=self.prefer_device,
            )
            if s is None:
                continue
            if best_score is None or s > best_score:
                best_score = s
                best_id = wid
        if best_id is None:
            return None
        self.workers[best_id].queue_depth += 1
        return best_id

    def assign_all(self, tasks: list[ChildTask]) -> dict[str, str | None]:
        return {t.child_id: self.assign_one(t) for t in tasks}
