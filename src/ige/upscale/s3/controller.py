from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

from .capability import WorkerCapability
from .job_plan import plan_compute_children
from .rebuild import pixel_match_children, rebuild_from_receipts
from .registry import WorkerRegistry
from .scheduler import CapabilityScheduler, ChildTask
from .transport_fs import FsLeaseTransport, _atomic_write


class JobController:
    """S3.6 Job Controller: plan · schedule · enqueue · reassign · rebuild.

    Does not run model inference. Agents pull work from shared transport root.
    """

    def __init__(
        self,
        job_dir: str | Path,
        *,
        lease_seconds: float = 60.0,
        max_attempts: int = 5,
        registry_stale_s: float = 20.0,
    ):
        self.job_dir = Path(job_dir)
        self.job_dir.mkdir(parents=True, exist_ok=True)
        self.queue = self.job_dir / "queue"
        self.transport = FsLeaseTransport(
            self.queue,
            lease_seconds=lease_seconds,
            max_attempts=max_attempts,
            allow_unassigned=False,
        )
        self.registry = WorkerRegistry(self.job_dir, stale_after_s=registry_stale_s)
        self.lease_seconds = lease_seconds
        self.max_attempts = max_attempts
        self.manifest_path = self.job_dir / "job_manifest.json"

    def init_job(
        self,
        *,
        base_path: str | Path,
        mode: str,
        model_id: str,
        weight_sha256: str,
        compute_core: int,
        compute_context: int,
        region: tuple[int, int, int, int] | None,
        est_peak_rss_mib: float,
        job_id: str,
    ) -> dict[str, Any]:
        plan = plan_compute_children(
            base_path,
            compute_core=compute_core,
            compute_context=compute_context,
            region=region,
        )
        manifest = {
            "format": "ige.s3.job",
            "format_version": "1.0",
            "job_id": job_id,
            "mode": mode,
            "base_path": str(Path(base_path).resolve()),
            "model_id": model_id,
            "weight_sha256": weight_sha256,
            "est_peak_rss_mib": est_peak_rss_mib,
            "plan": plan,
            "children_dir": str((self.job_dir / "children").resolve()),
            "created_at": time.time(),
            "final_acceptance": False,
            "e3_speed_claim": False,
        }
        (self.job_dir / "children").mkdir(parents=True, exist_ok=True)
        _atomic_write(self.manifest_path, json.dumps(manifest, ensure_ascii=False, indent=2) + "\n")
        _atomic_write(self.job_dir / "plan.json", json.dumps(plan, indent=2) + "\n")
        return manifest

    def load_manifest(self) -> dict[str, Any]:
        return json.loads(self.manifest_path.read_text(encoding="utf-8"))

    def wait_for_workers(self, min_workers: int, timeout_s: float) -> list[dict[str, Any]]:
        t0 = time.time()
        while time.time() - t0 < timeout_s:
            live = [w for w in self.registry.list_live() if not w.get("_stale")]
            if len(live) >= min_workers:
                return live
            time.sleep(0.2)
        return [w for w in self.registry.list_live() if not w.get("_stale")]

    def schedule_and_enqueue(self, *, prefer_device: str = "cuda") -> dict[str, str | None]:
        man = self.load_manifest()
        plan = man["plan"]
        caps = self.registry.live_capabilities()
        if not caps:
            raise RuntimeError("no live workers in registry")
        sch = CapabilityScheduler(caps, prefer_device=prefer_device)
        tasks = [
            ChildTask(
                child_id=c["child_id"],
                model_id=man["model_id"],
                weight_sha256=man["weight_sha256"],
                est_peak_rss_mib=float(man["est_peak_rss_mib"]),
                payload=c,
            )
            for c in plan["children"]
        ]
        assignment = sch.assign_all(tasks, fill_all=True)

        for c in plan["children"]:
            wid = assignment.get(c["child_id"])
            if wid is None:
                continue
            payload = dict(c)
            payload["assigned_worker"] = wid
            payload["job_id"] = man["job_id"]
            payload["base_path"] = man["base_path"]
            payload["model_id"] = man["model_id"]
            payload["weight_sha256"] = man["weight_sha256"]
            self.transport.enqueue(c["child_id"], payload)
        _atomic_write(
            self.job_dir / "assignment.json",
            json.dumps(assignment, indent=2) + "\n",
        )
        return assignment

    def reassign_orphans(self) -> dict[str, Any]:
        """Reassign pending tasks whose assigned worker is offline/stale.

        Also requeue expired leases first so dead workers' work becomes pending.
        """
        expired = self.transport.requeue_expired()
        man = self.load_manifest()
        caps = self.registry.live_capabilities()
        if not caps:
            return {"expired_requeued": expired, "reassigned": 0, "reason": "no_live_workers"}
        sch = CapabilityScheduler(caps, prefer_device="cuda")
        # reset queue depths from live registry depths if present
        reassigned = 0
        details = []
        for path in sorted((self.queue / "pending").glob("*.json")):
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
            except Exception:
                continue
            assigned = data.get("assigned_worker")
            if assigned in (None, "", "*"):
                pass  # needs assignment
            elif self.registry.is_live(str(assigned)):
                continue
            # need new home
            task = ChildTask(
                child_id=data["child_id"],
                model_id=man["model_id"],
                weight_sha256=man["weight_sha256"],
                est_peak_rss_mib=float(man["est_peak_rss_mib"]),
                payload=data,
            )
            new_w = sch.assign_one(task)
            if new_w is None:
                details.append({"child_id": data["child_id"], "status": "unassigned"})
                continue
            old = assigned
            data["assigned_worker"] = new_w
            data["reassigned_from"] = old
            data["reassigned_at"] = time.time()
            _atomic_write(path, json.dumps(data, ensure_ascii=False, indent=2) + "\n")
            reassigned += 1
            details.append({"child_id": data["child_id"], "from": old, "to": new_w})
        return {"expired_requeued": expired, "reassigned": reassigned, "details": details}


    def reconcile_missing(self) -> dict[str, Any]:
        """Re-enqueue plan children that are neither done, pending, nor leased.

        Guards against lost tasks after stale-complete / FS races.
        """
        man = self.load_manifest()
        plan = man["plan"]
        done_ids = {p.stem for p in (self.queue / "done").glob("*.json")}
        pending_ids = {p.stem for p in (self.queue / "pending").glob("*.json")}
        lease_ids: set[str] = set()
        lease_root = self.queue / "lease"
        if lease_root.is_dir():
            for wd in lease_root.iterdir():
                if wd.is_dir():
                    for f in wd.glob("*.json"):
                        lease_ids.add(f.stem)
        known = done_ids | pending_ids | lease_ids
        caps = self.registry.live_capabilities()
        sch = CapabilityScheduler(caps, prefer_device="cuda") if caps else None
        restored = []
        for c in plan["children"]:
            cid = c["child_id"]
            if cid in known:
                continue
            payload = dict(c)
            payload["job_id"] = man["job_id"]
            payload["base_path"] = man["base_path"]
            payload["model_id"] = man["model_id"]
            payload["weight_sha256"] = man["weight_sha256"]
            payload["restored_missing"] = True
            if sch is not None:
                task = ChildTask(
                    child_id=cid,
                    model_id=man["model_id"],
                    weight_sha256=man["weight_sha256"],
                    est_peak_rss_mib=float(man["est_peak_rss_mib"]),
                    payload=payload,
                )
                wid = sch.assign_one(task, enforce_max_inflight=False)
            else:
                wid = None
            if wid is None and caps:
                wid = caps[0].worker_id
            if wid is None:
                continue
            payload["assigned_worker"] = wid
            # remove stale done race
            self.transport.enqueue(cid, payload)
            restored.append({"child_id": cid, "assigned_worker": wid})
        return {"restored": restored, "n": len(restored)}

    def wait_until_done(self, *, expected: int, timeout_s: float, reassign_every_s: float = 2.0) -> dict[str, Any]:
        t0 = time.time()
        last_reassign = 0.0
        reassign_log: list[dict[str, Any]] = []
        while time.time() - t0 < timeout_s:
            done = self.transport.done_count()
            if done >= expected:
                break
            if time.time() - last_reassign >= reassign_every_s:
                info = self.reassign_orphans()
                miss = self.reconcile_missing()
                if info.get("reassigned") or info.get("expired_requeued") or miss.get("n"):
                    reassign_log.append({**info, "missing": miss})
                last_reassign = time.time()
            time.sleep(0.25)
        return {
            "done": self.transport.done_count(),
            "pending": self.transport.pending_count(),
            "dead": self.transport.dead_count(),
            "expected": expected,
            "elapsed_s": round(time.time() - t0, 3),
            "reassign_log": reassign_log,
        }

    def rebuild(self) -> dict[str, Any]:
        man = self.load_manifest()
        plan = man["plan"]
        receipts = self.transport.list_receipts()
        out_w, out_h = plan["output_wh"]
        origin = tuple(plan["output_origin_hires"])
        primary = self.job_dir / "OUT_PRIMARY.png"
        rebuild = rebuild_from_receipts(
            receipts=receipts,
            output_path=primary,
            output_width=out_w,
            output_height=out_h,
            origin_hires=origin,
            min_bytes=100,
        )
        integrity = pixel_match_children(receipts, primary, origin_hires=origin)
        report = {
            "receipts_n": len(receipts),
            "rebuild": rebuild,
            "integrity": integrity,
            "ok": integrity.get("ok") is True and len(receipts) == plan["child_count"],
            "final_acceptance": False,
            "e3_speed_claim": False,
        }
        _atomic_write(self.job_dir / "controller_report.json", json.dumps(report, indent=2) + "\n")
        return report
