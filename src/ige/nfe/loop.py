from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Callable, Optional

from .motion import MotionCompiler, MotionDelta
from .state import FrameRef, TemporalState
from .validate import TemporalValidator, ValidationReport


@dataclass
class StepResult:
    accepted: bool
    t_index: int
    candidate: Optional[FrameRef]
    validation: Optional[ValidationReport]
    delta: Optional[MotionDelta]
    retries: int = 0
    note: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "accepted": self.accepted,
            "t_index": self.t_index,
            "candidate": asdict(self.candidate) if self.candidate else None,
            "validation": self.validation.to_dict() if self.validation else None,
            "delta": self.delta.to_dict() if self.delta else None,
            "retries": self.retries,
            "note": self.note,
        }


# Generator callback: (state, delta, out_path) -> FrameRef
GeneratorFn = Callable[[TemporalState, MotionDelta, Path], FrameRef]


class NextFrameLoop:
    """C0 + C0.1 + C0.2 + C0.3 + C0.4 orchestration."""

    def __init__(
        self,
        state: TemporalState,
        generator: GeneratorFn,
        validator: TemporalValidator | None = None,
        motion: MotionCompiler | None = None,
        max_retries: int = 2,
    ):
        self.state = state
        self.generator = generator
        self.validator = validator or TemporalValidator()
        self.motion = motion or MotionCompiler()
        self.max_retries = max_retries

    def step(self, out_dir: Path, phase_name: str | None = None) -> StepResult:
        out_dir = Path(out_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        assert self.state.current_f is not None
        next_t = self.state.t_index + 1
        delta = self.motion.compile(next_t, phase_name)
        retries = 0
        last_val: ValidationReport | None = None
        last_cand: FrameRef | None = None

        while retries <= self.max_retries:
            out_path = out_dir / f"F{next_t:04d}_try{retries}.png"
            cand = self.generator(self.state, delta, out_path)
            # force t_index
            cand.t_index = next_t
            last_cand = cand
            val = self.validator.validate(
                self.state.current_f,
                cand,
                self.state.master_k,
                delta,
            )
            last_val = val
            if val.ok:
                self.state.advance_accept(cand, delta.to_dict())
                # re-anchor note
                note = "accepted"
                if self.state.should_reanchor():
                    note += "; reanchor_window"
                return StepResult(True, next_t, cand, val, delta, retries, note)
            retries += 1

        return StepResult(
            False,
            next_t,
            last_cand,
            last_val,
            delta,
            retries - 1,
            "rejected_after_retries; t not advanced",
        )
