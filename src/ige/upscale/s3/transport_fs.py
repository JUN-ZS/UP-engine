from __future__ import annotations

import json
import os
import time
import uuid
from pathlib import Path
from typing import Any


class StaleLeaseError(RuntimeError):
    """Worker no longer holds a valid fencing token for this task."""


def _atomic_write(path: Path, text: str, retries: int = 8) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    last: Exception | None = None
    for i in range(retries):
        tmp = path.with_name(path.name + f".{os.getpid()}.{time.time_ns()}.{i}.tmp")
        try:
            tmp.write_text(text, encoding="utf-8")
            os.replace(tmp, path)
            return
        except OSError as exc:
            last = exc
            try:
                tmp.unlink(missing_ok=True)
            except Exception:
                pass
            time.sleep(0.02 * (i + 1))
    assert last is not None
    raise last


class FsLeaseTransport:
    """Filesystem lease transport with hard assignment + fencing tokens (S3.5)."""

    def __init__(
        self,
        root: str | Path,
        *,
        lease_seconds: float = 120.0,
        max_attempts: int = 3,
        allow_unassigned: bool = False,
    ):
        self.root = Path(root)
        self.lease_seconds = lease_seconds
        self.max_attempts = max_attempts
        self.allow_unassigned = allow_unassigned
        for sub in ("pending", "lease", "done", "failed", "dead", "heartbeats", "children", "rejects"):
            (self.root / sub).mkdir(parents=True, exist_ok=True)

    def enqueue(self, task_id: str, payload: dict[str, Any]) -> Path:
        path = self.root / "pending" / f"{task_id}.json"
        if path.exists() or (self.root / "done" / f"{task_id}.json").exists():
            return path
        body = dict(payload)
        body.setdefault("child_id", task_id)
        body.setdefault("attempt", 0)
        _atomic_write(path, json.dumps(body, ensure_ascii=False, indent=2) + "\n")
        return path

    def pending_count(self) -> int:
        return len(list((self.root / "pending").glob("*.json")))

    def done_count(self) -> int:
        return len(list((self.root / "done").glob("*.json")))

    def dead_count(self) -> int:
        return len(list((self.root / "dead").glob("*.json")))

    def claim(self, worker_id: str) -> dict[str, Any] | None:
        self.requeue_expired()
        pending = self.root / "pending"
        lease_dir = self.root / "lease" / worker_id
        lease_dir.mkdir(parents=True, exist_ok=True)
        for path in sorted(pending.glob("*.json")):
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
            except Exception:
                continue
            assigned = data.get("assigned_worker")
            if assigned not in (None, "", "*"):
                if assigned != worker_id:
                    continue
            elif not self.allow_unassigned:
                continue
            if (self.root / "done" / path.name).exists():
                path.unlink(missing_ok=True)
                continue
            dest = lease_dir / path.name
            try:
                os.rename(path, dest)
            except FileNotFoundError:
                continue
            except OSError:
                continue
            try:
                data = json.loads(dest.read_text(encoding="utf-8"))
            except Exception:
                continue
            fencing_token = str(uuid.uuid4())
            attempt = int(data.get("attempt") or 0) + 1
            data["attempt"] = attempt
            data["_lease"] = {
                "worker_id": worker_id,
                "fencing_token": fencing_token,
                "claimed_at": time.time(),
                "lease_seconds": self.lease_seconds,
                "path": str(dest),
                "attempt": attempt,
            }
            _atomic_write(dest, json.dumps(data, ensure_ascii=False, indent=2) + "\n")
            child_id = data.get("child_id") or path.stem
            self.heartbeat(worker_id, child_id, fencing_token)
            data["_fencing_token"] = fencing_token
            return data
        return None

    def heartbeat(self, worker_id: str, task_id: str, fencing_token: str) -> None:
        lease = self._load_lease(worker_id, task_id)
        if lease is None:
            raise StaleLeaseError(f"no lease for {worker_id}/{task_id}")
        tok = (lease.get("_lease") or {}).get("fencing_token")
        if tok != fencing_token:
            raise StaleLeaseError(f"fencing mismatch on heartbeat {task_id}")
        hb = self.root / "heartbeats" / f"{worker_id}__{task_id}.json"
        _atomic_write(
            hb,
            json.dumps(
                {
                    "worker_id": worker_id,
                    "task_id": task_id,
                    "fencing_token": fencing_token,
                    "ts": time.time(),
                },
                indent=2,
            )
            + "\n",
        )

    def complete(self, worker_id: str, task_id: str, fencing_token: str, receipt: dict[str, Any]) -> Path:
        try:
            self._assert_live_lease(worker_id, task_id, fencing_token)
        except StaleLeaseError as exc:
            self._reject(worker_id, task_id, fencing_token, f"stale_complete:{exc}")
            raise
        done = self.root / "done" / f"{task_id}.json"
        if done.exists():
            self._reject(worker_id, task_id, fencing_token, "already_done")
            raise StaleLeaseError(f"task {task_id} already completed")
        lease_dir = self.root / "lease" / worker_id
        src = self._find_lease(lease_dir, task_id)
        payload = {
            "task_id": task_id,
            "worker_id": worker_id,
            "fencing_token": fencing_token,
            "receipt": receipt,
            "completed_at": time.time(),
        }
        # exclusive create
        try:
            fd = os.open(str(done), os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o644)
        except FileExistsError:
            self._reject(worker_id, task_id, fencing_token, "race_already_done")
            raise StaleLeaseError(f"task {task_id} race already done") from None
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(json.dumps(payload, ensure_ascii=False, indent=2) + "\n")
        if src and src.exists():
            src.unlink(missing_ok=True)
        self._clear_hb(worker_id, task_id)
        return done

    def fail(
        self,
        worker_id: str,
        task_id: str,
        fencing_token: str,
        error: str,
        *,
        requeue: bool = False,
    ) -> Path:
        try:
            self._assert_live_lease(worker_id, task_id, fencing_token)
        except StaleLeaseError:
            self._reject(worker_id, task_id, fencing_token, f"stale_fail:{error}")
            raise
        lease_dir = self.root / "lease" / worker_id
        src = self._find_lease(lease_dir, task_id)
        if requeue and src is not None:
            data = json.loads(src.read_text(encoding="utf-8"))
            attempt = int(data.get("attempt") or 0)
            data.pop("_lease", None)
            data["last_error"] = error
            if attempt >= self.max_attempts:
                out = self._dead_letter(task_id, data, error)
                src.unlink(missing_ok=True)
                self._clear_hb(worker_id, task_id)
                return out
            dest = self.root / "pending" / f"{task_id}.json"
            _atomic_write(dest, json.dumps(data, ensure_ascii=False, indent=2) + "\n")
            src.unlink(missing_ok=True)
            self._clear_hb(worker_id, task_id)
            return dest
        failed = self.root / "failed" / f"{task_id}.json"
        payload = {
            "task_id": task_id,
            "worker_id": worker_id,
            "fencing_token": fencing_token,
            "error": error,
            "failed_at": time.time(),
        }
        _atomic_write(failed, json.dumps(payload, ensure_ascii=False, indent=2) + "\n")
        if src and src.exists():
            src.unlink(missing_ok=True)
        self._clear_hb(worker_id, task_id)
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
                worker_id = worker_dir.name
                last = claimed_at
                hb = self.root / "heartbeats" / f"{worker_id}__{task_id}.json"
                if hb.is_file():
                    try:
                        hb_data = json.loads(hb.read_text(encoding="utf-8"))
                        if hb_data.get("fencing_token") == lease.get("fencing_token"):
                            last = max(last, float(hb_data.get("ts") or last))
                    except Exception:
                        pass
                if now - last <= ttl:
                    continue
                attempt = int(data.get("attempt") or 0)
                expired_token = lease.get("fencing_token")
                data.pop("_lease", None)
                data["requeued_from_expired_lease"] = True
                data["expired_fencing_token"] = expired_token
                if attempt >= self.max_attempts:
                    self._dead_letter(task_id, data, "max_attempts_after_lease_expire")
                    path.unlink(missing_ok=True)
                    if hb.exists():
                        hb.unlink(missing_ok=True)
                    n += 1
                    continue
                dest = self.root / "pending" / path.name
                try:
                    _atomic_write(dest, json.dumps(data, ensure_ascii=False, indent=2) + "\n")
                    path.unlink(missing_ok=True)
                    if hb.exists():
                        hb.unlink(missing_ok=True)
                    n += 1
                except OSError:
                    continue
        return n

    def _assert_live_lease(self, worker_id: str, task_id: str, fencing_token: str) -> dict[str, Any]:
        lease = self._load_lease(worker_id, task_id)
        if lease is None:
            raise StaleLeaseError(f"lease missing for {worker_id}/{task_id}")
        tok = (lease.get("_lease") or {}).get("fencing_token")
        if tok != fencing_token:
            raise StaleLeaseError(f"fencing token mismatch for {task_id}")
        if (self.root / "done" / f"{task_id}.json").exists():
            raise StaleLeaseError(f"already done {task_id}")
        return lease

    def _load_lease(self, worker_id: str, task_id: str) -> dict[str, Any] | None:
        src = self._find_lease(self.root / "lease" / worker_id, task_id)
        if src is None or not src.is_file():
            return None
        try:
            return json.loads(src.read_text(encoding="utf-8"))
        except Exception:
            return None

    def _dead_letter(self, task_id: str, data: dict[str, Any], error: str) -> Path:
        dead = self.root / "dead" / f"{task_id}.json"
        payload = dict(data)
        payload["dead_error"] = error
        payload["dead_at"] = time.time()
        _atomic_write(dead, json.dumps(payload, ensure_ascii=False, indent=2) + "\n")
        return dead

    def _reject(self, worker_id: str, task_id: str, fencing_token: str, reason: str) -> None:
        p = self.root / "rejects" / f"{task_id}__{worker_id}__{int(time.time() * 1000)}.json"
        _atomic_write(
            p,
            json.dumps(
                {
                    "task_id": task_id,
                    "worker_id": worker_id,
                    "fencing_token": fencing_token,
                    "reason": reason,
                    "ts": time.time(),
                },
                indent=2,
            )
            + "\n",
        )

    def _clear_hb(self, worker_id: str, task_id: str) -> None:
        hb = self.root / "heartbeats" / f"{worker_id}__{task_id}.json"
        if hb.exists():
            hb.unlink(missing_ok=True)

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
