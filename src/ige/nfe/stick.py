"""NFE STICK — attachable evolve pack for generation sessions.

STICK = sticky context card bolted onto each next-still generation:
  identity lock, scene lock, motion delta, reject rules, provenance.
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from .motion import MotionCompiler, MotionDelta
from .state import TemporalState


STICK_FORMAT = "ige.nfe.stick_evolve"
STICK_VERSION = "1.0"


@dataclass
class NfeStick:
    """Attach to I2I / Comfy / CLI for evolutionary next-frame generation."""

    format: str = STICK_FORMAT
    format_version: str = STICK_VERSION
    skill_code: str = "NFE"
    skill_name_zh: str = "逐幀延生"
    formula: str = "F_{t+1}=G(F_t,F_{t-1},K,ΔS_t,C_t)"
    generator_G: str = "i2i_next_still_only"
    forbidden: list[str] = field(
        default_factory=lambda: [
            "i2v",
            "image_to_video",
            "optical_flow_as_generation",
            "spatial_extend_as_time",
            "claim_360_next_frames_from_5_keys_plus_flow",
        ]
    )
    job_id: str = ""
    t_target: int = 1
    paths: dict[str, Optional[str]] = field(default_factory=dict)
    delta_s: dict[str, Any] = field(default_factory=dict)
    prompt: str = ""
    reanchor_to_K: bool = False
    accept_rules: dict[str, Any] = field(
        default_factory=lambda: {
            "require_new_sha": True,
            "mae_min": 0.3,
            "mae_max": 35.0,
            "flow_p50_max": 8.0,
            "static_anchors": "camera_ground_horizon",
            "dynamic_anchors": "track_not_force_align",
        }
    )
    provenance: dict[str, Any] = field(
        default_factory=lambda: {
            "frame_origin_required": True,
            "not_image_to_video_this_step": True,
            "never_touched_by_i2v_in_lineage": None,
        }
    )
    evolve: dict[str, Any] = field(
        default_factory=lambda: {
            "mode": "sequential_accept_only",
            "on_reject": "retry_same_t_do_not_advance",
            "max_retries": 2,
            "periodic_master_reanchor_every": 4,
        }
    )
    quality_qualified: bool = False
    final_acceptance: bool = False
    cinematic_product: bool = False
    created_at_utc: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def save(self, path: Path) -> Path:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        if not self.created_at_utc:
            self.created_at_utc = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        path.write_text(json.dumps(self.to_dict(), indent=2, ensure_ascii=False), encoding="utf-8")
        return path


def build_stick_from_state(
    state: TemporalState,
    phase: str | None = None,
    never_touched_by_i2v: bool | None = None,
) -> NfeStick:
    delta = MotionCompiler().compile(state.t_index + 1, phase)
    reanchor = state.should_reanchor() or ((state.t_index + 1) % max(state.reanchor_every, 1) == 0)
    prompt = delta.scene_lock_prompt()
    if reanchor and state.master_k:
        prompt = (
            prompt
            + " Strongly re-anchor identity and armor pattern to the master reference K. "
            "Do not drift face or gold mesh design."
        )
    stick = NfeStick(
        job_id=state.job_id,
        t_target=state.t_index + 1,
        paths={
            "f_t": state.current_f.path if state.current_f else None,
            "f_tm1": state.prev_f.path if state.prev_f else None,
            "k": state.master_k.path if state.master_k else None,
        },
        delta_s=delta.to_dict(),
        prompt=prompt,
        reanchor_to_K=reanchor,
    )
    stick.provenance["never_touched_by_i2v_in_lineage"] = never_touched_by_i2v
    stick.evolve["periodic_master_reanchor_every"] = state.reanchor_every
    return stick


def attach_stick(state_path: Path, out_path: Path | None = None, phase: str | None = None) -> Path:
    state = TemporalState.load(Path(state_path))
    stick = build_stick_from_state(state, phase=phase)
    out = Path(out_path) if out_path else Path(state_path).parent / f"STICK_t{stick.t_target}.json"
    stick.save(out)
    # also write human prompt snippet
    prompt_path = out.with_suffix(".prompt.txt")
    prompt_path.write_text(stick.prompt + "\n", encoding="utf-8")
    return out
