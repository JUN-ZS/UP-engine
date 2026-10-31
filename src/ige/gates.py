from __future__ import annotations

from dataclasses import dataclass


HARD_GATE_NAMES = (
    "identity", "pose", "topology", "mask_leakage", "registration",
    "protected_region_preservation", "native_resolution",
)


@dataclass(frozen=True)
class GateResult:
    name: str
    passed: bool
    evidence_uri: str | None = None
    note: str = ""


@dataclass(frozen=True)
class AcceptanceReport:
    hard_gates: tuple[GateResult, ...]
    quality_scores: dict[str, float]

    @property
    def accepted(self) -> bool:
        required = set(HARD_GATE_NAMES)
        observed = {gate.name for gate in self.hard_gates}
        return required.issubset(observed) and all(
            gate.passed for gate in self.hard_gates if gate.name in required
        )

    def validate_scores(self) -> None:
        for name, score in self.quality_scores.items():
            if not 0.0 <= score <= 1.0:
                raise ValueError(f"quality score {name!r} must be within [0, 1]")
