from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any


class FsLeaseTransport:
    """Filesystem lease transport.

    pending/ → lease/{worker}/ → done|failed/ with heartbeat JSON.
    Atomic rename for claim. Expired leases return to pending.
    """

    def __init__(self, root: str | Path, *, lease_seconds: float = 120.0):
        self.root = Path(root)
        self.lease_seconds = lease_seconds
        for sub in ("pending", "lease", "done", "failed", "heartbeats", "children"):
            (self.root / sub).mkdir(parents=True, exist_ok=True)

    def enqueue(self, task_id: str, payload: dict[str, Any]) -> Path:
        path = self.root / "pending" / f"{task_id}.json"
        if path.exists() or (self.root / "done" / f"{task_id}.json").exists():
            return path  # idempotent enqueue
        tmp = path.with_suffix(f".{os.getpid()}.tmp")
        tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        os.replace(tmp, path)
        return path

    def pending_count(self) -> int:
        return len(list((self.root / "pending").glob("*.json")))

    def done_count(self) -> int:
        return len(list((self.root / "done").glob("*.json")))

    def claim(self, worker_id: str) -> dict[str, Any] | None:
        self.requeue_expired()
        pending = self.root / "pending"
        lease_dir = self.root / "lease" / worker_id
        lease_dir.mkdir(parents=True, exist_ok=True)
        for path in sorted(pending.glob("*.json")):
            dest = lease_dir / path.name
            try:
                os.rename(path, dest)
            except FileNotFoundError:
                continue
            except OSError:
                continue
            data = json.loads(dest.read_text(encoding="utf-8"))
            data["_lease"] = {
                "worker_id": worker_id,
                "claimed_at": time.time(),
                "lease_seconds": self.lease_seconds,
                "path": str(dest),
            }
            dest.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            self.heartbeat(worker_id, data.get("child_id") or path.stem)
            return data
        return None

    def heartbeat(self, worker_id: str, task_id: str) -> None:
        hb = self.root / "heartbeats" / f"{worker_id}__{task_id}.json"
        tmp = hb.with_suffix(".tmp")
        tmp.write_text(
            json.dumps({"worker_id": worker_id, "task_id": task_id, "ts": time.time()}, indent=2) + "\n",
            encoding="utf-8",
        )
        os.replace(tmp, hb)

    def complete(self, worker_id: str, task_id: str, receipt: dict[str, Any]) -> Path:
        lease_dir = self.root / "lease" / worker_id
        src = self._find_lease(lease_dir, task_id)
        done = self.root / "done" / f"{task_id}.json"
        payload = {
            "task_id": task_id,
            "worker_id": worker_id,
            "receipt": receipt,
            "completed_at": time.time(),
        }
        tmp = done.with_suffix(".tmp")
        tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        os.replace(tmp, done)
        if src and src.exists():
            src.unlink()
        hb = self.root / "heartbeats" / f"{worker_id}__{task_id}.json"
        if hb.exists():
            hb.unlink()
        return done

    def fail(self, worker_id: str, task_id: str, error: str, *, requeue: bool = False) -> Path:
        lease_dir = self.root / "lease" / worker_id
        src = self._find_lease(lease_dir, task_id)
        if requeue and src is not None:
            data = json.loads(src.read_text(encoding="utf-8"))
            data.pop("_lease", None)
            data["last_error"] = error
            data["fail_count"] = int(data.get("fail_count") or 0) + 1
            dest = self.root / "pending" / f"{task_id}.json"
            tmp = dest.with_suffix(".tmp")
            tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            os.replace(tmp, dest)
            src.unlink(missing_ok=True)
            return dest
        failed = self.root / "failed" / f"{task_id}.json"
        payload = {
            "task_id": task_id,
            "worker_id": worker_id,
            "error": error,
            "failed_at": time.time(),
        }
        tmp = failed.with_suffix(".tmp")
        tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        os.replace(tmp, failed)
        if src and src.exists():
            src.unlink()
        hb = self.root / "heartbeats" / f"{worker_id}__{task_id}.json"
        if hb.exists():
            hb.unlink()
        return failed

    def list_receipts(self) -> list[dict[str, Any]]:
        out = []
        for p in sorted((self.root / "done").glob("*.json")):
            out.append(json.loads(p.read_text(encoding="utf-8")))
        return out

    def requeue_expired(self) -> int:
        now = time.time()
        n = 0
        lease_root = self.root / "lease"
        if not lease_root.is_dir():
            return 0
        for worker_dir in lease_root.iterdir():
            if not worker_dir.is_dir():
                continue
            for path in list(worker_dir.glob("*.json")):
                try:
                    data = json.loads(path.read_text(encoding="utf-8"))
                except Exception:
                    continue
                lease = data.get("_lease") or {}
                claimed_at = float(lease.get("claimed_at") or 0)
                ttl = float(lease.get("lease_seconds") or self.lease_seconds)
                task_id = data.get("child_id") or path.stem
                hb = self.root / "heartbeats" / f"{worker_dir.name}__{task_id}.json"
                last = claimed_at
                if hb.is_file():
                    try:
                        last = float(json.loads(hb.read_text(encoding="utf-8")).get("ts") or last)
                    except Exception:
                        pass
                if now - last > ttl:
                    dest = self.root / "pending" / path.name
                    data.pop("_lease", None)
                    data["requeued_from_expired_lease"] = True
                    tmp = dest.with_suffix(".tmp")
                    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
                    os.replace(tmp, dest)
                    path.unlink(missing_ok=True)
                    if hb.exists():
                        hb.unlink()
                    n += 1
        return n

    @staticmethod
    def _find_lease(lease_dir: Path, task_id: str) -> Path | None:
        if not lease_dir.is_dir():
            return None
        direct = lease_dir / f"{task_id}.json"
        if direct.is_file():
            return direct
        for c in lease_dir.glob("*.json"):
            try:
                body = json.loads(c.read_text(encoding="utf-8"))
            except Exception:
                continue
            if body.get("child_id") == task_id or c.stem == task_id:
                return c
        return None
