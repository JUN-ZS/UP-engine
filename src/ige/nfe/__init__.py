"""Next Frame Engine (NFE) — temporal I2I still chain, not I2V."""

from .framework import FrameworkManifest, TOOL_REGISTRY, MODULE_REGISTRY, bolt_check, resolve_tool
from .loop import NextFrameLoop, StepResult
from .motion import MotionCompiler, MotionDelta
from .state import FrameRef, TemporalState, sha256_file
from .stick import attach_stick
from .validate import TemporalValidator, ValidationReport
from .ddxx_gate import consecutive_ddxx_pair, chain_ddxx_reports, PairDDXXReport
from .frameback import densify_frameback

__all__ = [
    "FrameworkManifest",
    "TOOL_REGISTRY",
    "MODULE_REGISTRY",
    "bolt_check",
    "resolve_tool",
    "NextFrameLoop",
    "StepResult",
    "MotionCompiler",
    "MotionDelta",
    "FrameRef",
    "TemporalState",
    "sha256_file",
    "attach_stick",
    "TemporalValidator",
    "ValidationReport",
    "consecutive_ddxx_pair",
    "chain_ddxx_reports",
    "PairDDXXReport",
    "densify_frameback",
]
