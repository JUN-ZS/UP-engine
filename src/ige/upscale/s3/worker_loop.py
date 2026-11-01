from __future__ import annotations

import threading
import time
from pathlib import Path
from typing import Any, Callable

from .adapter_base import ChildRunSpec, UpscaleAdapter
from .transport_fs import FsLeaseTransport, StaleLeaseError


class _HeartbeatThread(threading.Thread):
    def __init__(
        self,
        transport: FsLeaseTransport,
        worker_id: str,
        task_id: str,
        fencing_token: str,
        every_s: float,
    ):
        super().__init__(daemon=True)
        self.transport = transport
        self.worker_id = worker_id
        self.task_id = task_id
        self.fencing_token = fencing_token
        self.every_s = max(0.05, every_s)
        self._stop_event = threading.Event()
        self.error: Exception | None = None

    def stop(self) -> None:
        self._stop_event.set()

    def run(self) -> None:
        while not self._stop_event.is_set():
            try:
                self.transport.heartbeat(self.worker_id, self.task_id, self.fencing_token)
            except Exception as exc:  # StaleLeaseError or IO
                self.error = exc
                break
            self._stop_event.wait(self.every_s)


def run_worker_loop(
    transport: FsLeaseTransport,
    adapter: UpscaleAdapter,
    *,
    worker_id: str,
    job_id: str,
    base_path: str | Path,
    children_dir: str | Path,
    max_tasks: int | None = None,
    heartbeat_every_s: float = 2.0,
    idle_sleep_s: float = 0.05,
    device: str | None = None,
    on_task: Callable[[dict[str, Any]], None] | None = None,
) -> dict[str, Any]:
    """Claim (assignment-filtered) → heartbeat during run → fenced complete."""
    children_dir = Path(children_dir)
    children_dir.mkdir(parents=True, exist_ok=True)
    done = 0
    failed = 0
    stale = 0
    task_ids: list[str] = []
    while max_tasks is None or done < max_tasks:
        task = transport.claim(worker_id)
        if task is None:
            # Exit if no pending work assigned to this worker
            pending_for_us = False
            for pp in (transport.root / "pending").glob("*.json"):
                try:
                    d = __import__("json").loads(pp.read_text(encoding="utf-8"))
                except Exception:
                    continue
                aw = d.get("assigned_worker")
                if aw == worker_id or (aw in (None, "", "*") and transport.allow_unassigned):
                    pending_for_us = True
                    break
            if not pending_for_us:
                break
            time.sleep(idle_sleep_s)
            continue
        child_id = task["child_id"]
        fencing_token = task.get("_fencing_token") or (task.get("_lease") or {}).get("fencing_token")
        if not fencing_token:
            failed += 1
            continue
        hb_thread = _HeartbeatThread(
            transport, worker_id, child_id, fencing_token, heartbeat_every_s
        )
        hb_thread.start()
        try:
            out_uri = children_dir / f"{child_id}.png"
            extra = {
                "out_uri": str(out_uri),
                "job_id": job_id,
                "worker_id": worker_id,
                "simulate_s": task.get("simulate_s", 0),
                "fencing_token": fencing_token,
            }
            if device is not None:
                extra["device"] = device
            spec = ChildRunSpec(
                child_id=child_id,
                base_path=str(base_path),
                core_box_base=list(task["core_box_base"]),
                input_box_base=list(task["input_box_base"]),
                output_box_hires=list(task["output_box_hires"]),
                extra=extra,
            )
            result = adapter.run_child(spec)
            if hb_thread.error is not None:
                raise StaleLeaseError(f"heartbeat failed: {hb_thread.error}")
            receipt = dict(result.receipt)
            receipt["fencing_token"] = fencing_token
            receipt["worker_id"] = worker_id
            transport.complete(worker_id, child_id, fencing_token, receipt)
            done += 1
            task_ids.append(child_id)
            if on_task:
                on_task({"child_id": child_id, "worker_id": worker_id, "status": "ok", "fencing_token": fencing_token})
        except StaleLeaseError as exc:
            stale += 1
            if on_task:
                on_task({"child_id": child_id, "worker_id": worker_id, "status": "stale", "error": str(exc)})
        except Exception as exc:
            failed += 1
            try:
                transport.fail(
                    worker_id,
                    child_id,
                    fencing_token,
                    f"{type(exc).__name__}: {exc}",
                    requeue=False,
                )
            except StaleLeaseError:
                stale += 1
            if on_task:
                on_task({"child_id": child_id, "worker_id": worker_id, "status": "failed", "error": str(exc)})
        finally:
            hb_thread.stop()
            hb_thread.join(timeout=2.0)
    return {
        "worker_id": worker_id,
        "device": device,
        "tasks_completed": done,
        "tasks_failed": failed,
        "tasks_stale": stale,
        "task_ids": task_ids,
        "final_acceptance": False,
        "e3_speed_claim": False,
    }
