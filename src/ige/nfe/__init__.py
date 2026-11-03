"""NEXT FRAME Engine (NFE) — still-unit temporal generation.

F_{t+1} = G(F_t, F_{t-1}, K, ΔS_t, C_t)
G is I2I next-still only. I2V and optical-flow-as-generation are non-goals.
"""

from .state import TemporalState, FrameRef
from .motion import MotionCompiler, MotionDelta
from .validate import TemporalValidator, ValidationReport
from .loop import NextFrameLoop, StepResult

__all__ = [
    "TemporalState",
    "FrameRef",
    "MotionCompiler",
    "MotionDelta",
    "TemporalValidator",
    "ValidationReport",
    "NextFrameLoop",
    "StepResult",
]
