from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Optional

import numpy as np
from PIL import Image

from .motion import MotionDelta
from .state import FrameRef


@dataclass
class ValidationReport:
    ok: bool
    reasons: list[str] = field(default_factory=list)
    mae: Optional[float] = None
    flow_p50: Optional[float] = None
    static_note: str = "ddxx_static_gate_deferred_or_light"
    dynamic_note: str = "dynamic_anchors_not_overlocked_check_light"
    identity_note: str = "master_reanchor_policy_only"
    metrics: dict[str, Any] = field(default_factory=dict)
    ddxx: Optional[dict[str, Any]] = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class TemporalValidator:
    """C0.3 — temporal gates; optional C0.3.1 DDXX consecutive static gate."""

    def __init__(
        self,
        mae_min: float = 0.3,
        mae_max: float = 35.0,
        flow_p50_max: float = 8.0,
        require_different_sha: bool = True,
        enable_ddxx: bool = False,
        ddxx_hard: bool = False,
    ):
        self.mae_min = mae_min
        self.mae_max = mae_max
        self.flow_p50_max = flow_p50_max
        self.require_different_sha = require_different_sha
        self.enable_ddxx = enable_ddxx
        self.ddxx_hard = ddxx_hard

    def validate(
        self,
        prev: FrameRef,
        cand: FrameRef,
        master: FrameRef | None,
        delta: MotionDelta,
        size: tuple[int, int] = (1280, 720),
    ) -> ValidationReport:
        reasons: list[str] = []
        if self.require_different_sha and prev.sha256 == cand.sha256:
            reasons.append("candidate_sha_equals_prev (not a new still)")

        a = np.asarray(Image.open(prev.path).convert("RGB").resize(size, Image.Resampling.LANCZOS), np.float32)
        b = np.asarray(Image.open(cand.path).convert("RGB").resize(size, Image.Resampling.LANCZOS), np.float32)
        mae = float(np.mean(np.abs(a - b)))
        flow_p50 = None
        try:
            import cv2

            g0 = cv2.cvtColor(a.astype(np.uint8), cv2.COLOR_RGB2GRAY)
            g1 = cv2.cvtColor(b.astype(np.uint8), cv2.COLOR_RGB2GRAY)
            fl = cv2.calcOpticalFlowFarneback(g0, g1, None, 0.5, 3, 15, 3, 5, 1.2, 0)
            flow_p50 = float(np.median(np.sqrt(fl[..., 0] ** 2 + fl[..., 1] ** 2)))
        except Exception:
            flow_p50 = None

        if mae < self.mae_min:
            reasons.append(f"mae_too_low={mae:.3f}<{self.mae_min} (possible identity copy / no motion)")
        if mae > self.mae_max:
            reasons.append(f"mae_too_high={mae:.3f}>{self.mae_max} (possible reframe/semantic break)")
        if flow_p50 is not None and flow_p50 > self.flow_p50_max:
            reasons.append(f"flow_p50_too_high={flow_p50:.3f}>{self.flow_p50_max}")

        ddxx_dict = None
        static_note = "camera_lock_assumed; full DDXX static edge deferred to C0.3.1"
        if self.enable_ddxx:
            try:
                from .ddxx_gate import consecutive_ddxx_pair

                rep = consecutive_ddxx_pair(Path(prev.path), Path(cand.path), pair_id="prev_cand", size=size)
                ddxx_dict = rep.to_dict()
                static_note = f"ddxx_gate={rep.gate}; sim_p95={rep.sim_p95}; n_anchors={rep.n_anchors}"
                if self.ddxx_hard and not rep.ok:
                    reasons.extend([f"ddxx:{r}" for r in rep.reasons] or ["ddxx_hard_fail"])
            except Exception as exc:
                static_note = f"ddxx_error:{type(exc).__name__}"
                if self.ddxx_hard:
                    reasons.append(f"ddxx_error:{exc}")

        dynamic_note = f"allowed={delta.dynamic_allow}; do_not_force_align_all_body_anchors"
        identity_note = "periodic master re-anchor via TemporalState.should_reanchor"
        ok = len(reasons) == 0
        return ValidationReport(
            ok=ok,
            reasons=reasons,
            mae=mae,
            flow_p50=flow_p50,
            static_note=static_note,
            dynamic_note=dynamic_note,
            identity_note=identity_note,
            metrics={"mae": mae, "flow_p50": flow_p50, "delta": delta.to_dict()},
            ddxx=ddxx_dict,
        )
