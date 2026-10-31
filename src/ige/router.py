from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class RuntimeState:
    available_vram_gb: float | None = None
    available_ram_gb: float | None = None
    latency_budget_seconds: float | None = None
    offline_only: bool = False
    geometry_risk: float = 0.5
    mask_complexity: float = 0.5
    source_resolution_mp: float | None = None
    history_drift_risk: float = 0.5


@dataclass(frozen=True)
class ModelProfile:
    model_id: str
    supported_tasks: frozenset[str]
    supports_masks: bool
    supports_multi_reference: bool
    max_resolution_mp: float | None
    estimated_vram_gb: float | None
    estimated_latency_seconds: float | None
    local: bool
    license_status: str  # approved | review_required | prohibited
    validation_status: str  # untested | benchmarked | production
    strengths: frozenset[str] = frozenset()


@dataclass(frozen=True)
class RouteDecision:
    selected_model_id: str | None
    eligible_model_ids: tuple[str, ...]
    rejected: dict[str, str]
    reason: str


def route(task_type: str, state: RuntimeState, profiles: list[ModelProfile],
          *, needs_mask: bool = True, needs_multi_reference: bool = False) -> RouteDecision:
    """Fail-closed routing. It does not promote untested models to production."""
    eligible: list[ModelProfile] = []
    rejected: dict[str, str] = {}
    for model in profiles:
        reason = None
        if task_type not in model.supported_tasks:
            reason = "task_not_supported"
        elif model.license_status != "approved":
            reason = "license_not_approved"
        elif model.validation_status not in {"benchmarked", "production"}:
            reason = "not_benchmarked"
        elif needs_mask and not model.supports_masks:
            reason = "mask_support_missing"
        elif needs_multi_reference and not model.supports_multi_reference:
            reason = "multi_reference_support_missing"
        elif state.offline_only and not model.local:
            reason = "offline_only"
        elif (state.available_vram_gb is not None and model.estimated_vram_gb is not None
              and model.estimated_vram_gb > state.available_vram_gb):
            reason = "insufficient_vram"
        elif (state.source_resolution_mp is not None and model.max_resolution_mp is not None
              and state.source_resolution_mp > model.max_resolution_mp):
            reason = "resolution_exceeds_model_limit"
        elif (state.latency_budget_seconds is not None and model.estimated_latency_seconds is not None
              and model.estimated_latency_seconds > state.latency_budget_seconds):
            reason = "latency_budget_exceeded"
        if reason:
            rejected[model.model_id] = reason
        else:
            eligible.append(model)

    if not eligible:
        return RouteDecision(None, (), rejected, "No model passed hard capability, license, and validation filters.")

    # Ranking is state-dependent and deliberately subordinate to hard eligibility.
    def score(model: ModelProfile) -> float:
        value = 0.0
        if state.geometry_risk >= 0.7 and "geometry_control" in model.strengths:
            value += 3.0
        if state.history_drift_risk >= 0.7 and "consistency" in model.strengths:
            value += 2.0
        if state.mask_complexity >= 0.7 and "local_editing" in model.strengths:
            value += 1.5
        if "task_quality" in model.strengths:
            value += 1.0
        if model.validation_status == "production":
            value += 0.25
        return value

    ranked = sorted(eligible, key=lambda m: (score(m), m.model_id), reverse=True)
    return RouteDecision(ranked[0].model_id, tuple(m.model_id for m in ranked), rejected,
                         "Selected from eligible models using task-state risk and benchmarked strengths.")
