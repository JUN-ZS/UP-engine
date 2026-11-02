from __future__ import annotations

import json
import os
import socket
import time
from pathlib import Path
from typing import Any

from .capability import WorkerCapability
from .transport_fs import _atomic_write


class WorkerRegistry:
    """Shared-FS worker capability + liveness registry.

    workers/{worker_id}.json written by agents; controller reads for scheduling/reassign.
    """

    def __init__(self, root: str | Path, *, stale_after_s: float = 30.0):
        self.root = Path(root)
        self.dir = self.root / "registry" / "workers"
        self.dir.mkdir(parents=True, exist_ok=True)
        self.stale_after_s = stale_after_s

    def report(self, capability: dict[str, Any]) -> Path:
        wid = str(capability["worker_id"])
        body = dict(capability)
        body["reported_at"] = time.time()
        body["reported_at_utc"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        body.setdefault("hostname", socket.gethostname())
        body.setdefault("pid", os.getpid())
        path = self.dir / f"{wid}.json"
        _atomic_write(path, json.dumps(body, ensure_ascii=False, indent=2) + "\n")
        return path

    def list_live(self) -> list[dict[str, Any]]:
        now = time.time()
        out = []
        for p in sorted(self.dir.glob("*.json")):
            try:
                data = json.loads(p.read_text(encoding="utf-8"))
            except Exception:
                continue
            ts = float(data.get("reported_at") or 0)
            data["_stale"] = (now - ts) > self.stale_after_s
            data["_age_s"] = round(now - ts, 3)
            out.append(data)
        return out

    def live_capabilities(self) -> list[WorkerCapability]:
        caps = []
        for d in self.list_live():
            if d.get("_stale"):
                continue
            caps.append(WorkerCapability.from_dict(d))
        return caps

    def is_live(self, worker_id: str) -> bool:
        for d in self.list_live():
            if d.get("worker_id") == worker_id and not d.get("_stale"):
                return True
        return False
