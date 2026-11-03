"""NEXT FRAME Engine (NFE) — still-unit temporal generation ALL framework.

F_{t+1} = G(F_t, F_{t-1}, K, ΔS_t, C_t)
G is I2I next-still only. I2V and optical-flow-as-generation are non-goals.
"""

from .framework import FrameworkManifest, bolt_check, resolve_tool
from .loop import NextFrameLoop, StepResult
from .motion import MotionCompiler, MotionDelta
from .state import FrameRef, TemporalState
from .stick import NfeStick, attach_stick, build_stick_from_state
from .validate import TemporalValidator, ValidationReport

__all__ = [
    "TemporalState",
    "FrameRef",
    "MotionCompiler",
    "MotionDelta",
    "TemporalValidator",
    "ValidationReport",
    "NextFrameLoop",
    "StepResult",
    "FrameworkManifest",
    "bolt_check",
    "resolve_tool",
    "NfeStick",
    "build_stick_from_state",
    "attach_stick",
]
