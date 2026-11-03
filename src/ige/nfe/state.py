from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Optional


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


@dataclass
class FrameRef:
    path: str
    sha256: str
    t_index: int
    frame_origin: str = "unknown"  # i2i_next_still | procedural_cv | extracted_from_video | i2v_source | master
    asset_id: Optional[str] = None

    @classmethod
    def from_path(cls, path: Path, t_index: int, frame_origin: str = "unknown", asset_id: str | None = None) -> "FrameRef":
        p = Path(path)
        return cls(path=str(p), sha256=sha256_file(p), t_index=t_index, frame_origin=frame_origin, asset_id=asset_id)


@dataclass
class TemporalState:
    """C0 — temporal memory for next-still generation."""

    format: str = "ige.nfe.temporal_state"
    format_version: str = "0.1"
    job_id: str = ""
    t_index: int = 0
    master_k: Optional[FrameRef] = None
    current_f: Optional[FrameRef] = None
    prev_f: Optional[FrameRef] = None
    history: list[dict[str, Any]] = field(default_factory=list)
    camera: dict[str, Any] = field(default_factory=lambda: {"model": "locked", "note": "static anchors only"})
    phase: str = "init"
    delta_s: dict[str, Any] = field(default_factory=dict)
    not_image_to_video: bool = True
    frame_origin_policy: str = "declare_every_frame_origin"
    quality_qualified: bool = False
    final_acceptance: bool = False
    reanchor_every: int = 4

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        return d

    def save(self, path: Path) -> None:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self.to_dict(), indent=2), encoding="utf-8")

    @classmethod
    def load(cls, path: Path) -> "TemporalState":
        raw = json.loads(Path(path).read_text(encoding="utf-8"))
        def fr(x):
            return None if x is None else FrameRef(**x)
        return cls(
            format=raw.get("format", "ige.nfe.temporal_state"),
            format_version=raw.get("format_version", "0.1"),
            job_id=raw.get("job_id", ""),
            t_index=int(raw.get("t_index", 0)),
            master_k=fr(raw.get("master_k")),
            current_f=fr(raw.get("current_f")),
            prev_f=fr(raw.get("prev_f")),
            history=list(raw.get("history") or []),
            camera=dict(raw.get("camera") or {}),
            phase=raw.get("phase", "init"),
            delta_s=dict(raw.get("delta_s") or {}),
            not_image_to_video=bool(raw.get("not_image_to_video", True)),
            frame_origin_policy=raw.get("frame_origin_policy", "declare_every_frame_origin"),
            quality_qualified=False,
            final_acceptance=False,
            reanchor_every=int(raw.get("reanchor_every", 4)),
        )

    def bootstrap(self, master: Path, job_id: str, asset_id: str | None = None) -> None:
        k = FrameRef.from_path(master, t_index=0, frame_origin="master", asset_id=asset_id)
        self.job_id = job_id
        self.t_index = 0
        self.master_k = k
        self.current_f = k
        self.prev_f = None
        self.history = [asdict(k)]
        self.phase = "f0_ready"

    def should_reanchor(self) -> bool:
        return self.t_index > 0 and (self.t_index % max(self.reanchor_every, 1) == 0)

    def advance_accept(self, new_f: FrameRef, delta_s: dict[str, Any]) -> None:
        self.prev_f = self.current_f
        self.current_f = new_f
        self.t_index = new_f.t_index
        self.delta_s = delta_s
        self.history.append(asdict(new_f))
        self.phase = f"accepted_t{self.t_index}"
