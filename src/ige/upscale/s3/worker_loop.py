from __future__ import annotations

import time
import traceback
from pathlib import Path
from typing import Any, Callable

from .adapter_base import ChildRunSpec, UpscaleAdapter
from .transport_fs import FsLeaseTransport


def run_worker_loop(
    transport: FsLeaseTransport,
    adapter: UpscaleAdapter,
    *,
    worker_id: str,
    job_id: str,
    base_path: str | Path,
    children_dir: str | Path,
    max_tasks: int | None = None,
    heartbeat_every_s: float = 5.0,
    idle_sleep_s: float = 0.05,
    on_task: Callable[[dict[str, Any]], None] | None = None,
) -> dict[str, Any]:
    """Claim → run_child → complete until no pending or max_tasks."""
    children_dir = Path(children_dir)
    children_dir.mkdir(parents=True, exist_ok=True)
    done = 0
    failed = 0
    task_ids: list[str] = []
    while max_tasks is None or done < max_tasks:
        task = transport.claim(worker_id)
        if task is None:
            if transport.pending_count() == 0:
                break
            time.sleep(idle_sleep_s)
            continue
        child_id = task["child_id"]
        try:
            transport.heartbeat(worker_id, child_id)
            out_uri = children_dir / f"{child_id}.png"
            spec = ChildRunSpec(
                child_id=child_id,
                base_path=str(base_path),
                core_box_base=list(task["core_box_base"]),
                input_box_base=list(task["input_box_base"]),
                output_box_hires=list(task["output_box_hires"]),
                extra={
                    "out_uri": str(out_uri),
                    "job_id": job_id,
                    "worker_id": worker_id,
                    "simulate_s": task.get("simulate_s", 0),
                },
            )
            result = adapter.run_child(spec)
            transport.heartbeat(worker_id, child_id)
            transport.complete(worker_id, child_id, result.receipt)
            done += 1
            task_ids.append(child_id)
            if on_task:
                on_task({"child_id": child_id, "worker_id": worker_id, "status": "ok"})
        except Exception as exc:
            failed += 1
            transport.fail(worker_id, child_id, f"{type(exc).__name__}: {exc}", requeue=False)
            if on_task:
                on_task({"child_id": child_id, "worker_id": worker_id, "status": "failed", "error": str(exc)})
    return {
        "worker_id": worker_id,
        "tasks_completed": done,
        "tasks_failed": failed,
        "task_ids": task_ids,
        "final_acceptance": False,
        "e3_speed_claim": False,
    }
