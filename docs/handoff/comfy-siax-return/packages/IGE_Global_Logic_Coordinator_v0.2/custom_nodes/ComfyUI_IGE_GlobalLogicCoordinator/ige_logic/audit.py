from __future__ import annotations
import numpy as np
from .core import ACTIONS, ContractError


def audit_candidate(source: np.ndarray, candidate: np.ndarray, subsets: dict,
                    observations: dict | None = None) -> dict:
    src=np.asarray(source,dtype=np.float32); out=np.asarray(candidate,dtype=np.float32)
    if src.ndim==4: src=src[0]
    if out.ndim==4: out=out[0]
    if src.shape != out.shape: raise ContractError(f"Source/candidate shape mismatch: {src.shape} vs {out.shape}")
    h,w=src.shape[:2]
    if (w,h)!=tuple(subsets["original_size"]): raise ContractError("Audit canvas differs from TTP original_size")
    cover=subsets["coverage_count"]>0
    blocked=np.zeros((h,w),dtype=bool)
    if "global_action_map" in subsets:
        action=subsets["global_action_map"]
        blocked=np.isin(action,[ACTIONS['PRESERVE'],ACTIONS['REJECT']])
    outside=~cover
    outside_diff=np.any(src!=out,axis=-1)
    blocked_diff=np.any(src!=out,axis=-1) & blocked
    observations=observations or {}
    contract=subsets["contract"]
    geom_status=contract.get("geometry_status","unknown")
    tol=contract.get("geometry_tolerances",{})
    required=("silhouette_iou", "bbox_iou", "landmark_max_px")
    threshold_keys={"silhouette_iou":"silhouette_iou_min", "bbox_iou":"bbox_iou_min", "landmark_max_px":"landmark_max_px"}
    checks={}
    valid_metrics={}
    for name in required:
        raw=observations.get(name)
        valid=False
        numeric=None
        if name in observations:
            try:
                numeric=float(raw)
                valid=bool(np.isfinite(numeric))
            except (TypeError, ValueError):
                valid=False
        valid_metrics[name]=valid
        checks[name]={"provided":name in observations,"valid_numeric":valid,"value":numeric if valid else raw,
                      "threshold":tol.get(threshold_keys[name])}
    checks["operator_confirmed"]={"provided":bool(observations.get("operator_confirmed",False)),"value":bool(observations.get("operator_confirmed",False))}
    geometry_metrics_present=all(valid_metrics.values())
    geometry_values_pass=False
    if geometry_metrics_present:
        siou=checks["silhouette_iou"]["value"]; biou=checks["bbox_iou"]["value"]; lm=checks["landmark_max_px"]["value"]
        geometry_values_pass=(siou>=float(tol.get("silhouette_iou_min",0.85)) and
                              biou>=float(tol.get("bbox_iou_min",0.90)) and
                              lm<=float(tol.get("landmark_max_px",12.0)))
    violations=[]; warnings=[]
    source_alignment_pass=contract.get("source_alignment_status")=="operator_confirmed"
    if outside_diff[outside].any(): violations.append("pixels_outside_ttp_coverage_changed")
    if blocked_diff.any(): violations.append("preserve_or_reject_region_changed")
    if not geometry_metrics_present: warnings.append("geometry_observations_missing")
    if not checks['operator_confirmed']['value']: warnings.append("operator_geometry_confirmation_missing")
    if geom_status != "operator_confirmed": warnings.append("geometry_contract_not_operator_confirmed")
    if not source_alignment_pass: warnings.append("geometry_coordinates_not_registered_to_current_siax_output")
    if geometry_metrics_present and not geometry_values_pass: violations.append("geometry_observations_outside_tolerance")
    has_reconcile_report=bool(subsets.get("reconcile_report"))
    if not has_reconcile_report:
        warnings.append("reconcile_report_not_attached")
    rr=subsets.get("reconcile_report",{})
    max_conflict=float(rr.get("maximum_overlap_conflict_fraction",0.05))
    conflict_fraction=float(rr.get("overlap_conflict_fraction",0.0))
    overlap_conflict_pass=conflict_fraction <= max_conflict
    p95_pass=bool(rr.get("overlap_p95_threshold_pass",True))
    overlap_consensus_pass=bool(has_reconcile_report and overlap_conflict_pass and p95_pass)
    failed_subsets = list(rr.get("failed_subsets", []))
    if not overlap_conflict_pass:
        warnings.append("overlap_conflict_fraction_above_configured_limit")
    if failed_subsets:
        warnings.append("one_or_more_tile_subsets_failed_overlap_consensus")
    if not p95_pass:
        warnings.append("overlap_p95_spread_above_configured_limit")
    exec_groups=subsets.get("execution_groups",{})
    if exec_groups and not exec_groups.get("single_shared_sampler_batch_compatible", True):
        warnings.append("subset_conditioning_groups_require_separate_execution_or_verified_batch_adapter")
    # Acceptance is intentionally stricter than pixel plumbing.
    conditioning_compatible=(not subsets.get("execution_groups") or subsets["execution_groups"].get("single_shared_sampler_batch_compatible",True))
    geometry_accept=(geometry_metrics_present and geometry_values_pass and checks['operator_confirmed']['value'] and geom_status=="operator_confirmed" and source_alignment_pass and conditioning_compatible)
    acceptance_pass=bool(geometry_accept and overlap_consensus_pass and conditioning_compatible)
    if violations:
        status="FAIL"
    elif not overlap_consensus_pass and not geometry_accept:
        status="BLOCKED_PENDING_GEOMETRY_AND_CONSENSUS"
    elif not overlap_consensus_pass:
        status="BLOCKED_PENDING_OVERLAP_CONSENSUS"
    elif not geometry_accept:
        status="BLOCKED_PENDING_GEOMETRY_ACCEPTANCE"
    else:
        status="PASS_TECHNICAL_AND_GEOMETRY_GATES"
    return {
      "schema_version":"ige-global-audit/0.2","status":status,
      "canvas_wh":[w,h],"source_candidate_exact_match_outside_coverage":int(np.count_nonzero(outside_diff & outside))==0,
      "outside_coverage_changed_pixels":int(np.count_nonzero(outside_diff & outside)),
      "preserve_reject_changed_pixels":int(blocked_diff.sum()),
      "geometry_status":geom_status,"source_alignment_status":contract.get("source_alignment_status"),"geometry_observations":checks,
      "geometry_observations_pass":geometry_values_pass,
      "operator_confirmation_pass":bool(checks['operator_confirmed']['value']),
      "geometry_acceptance_pass":geometry_accept,"overlap_consensus_pass":overlap_consensus_pass,
      "acceptance_pass":acceptance_pass,"conditioning_groups_compatible_with_single_batch":conditioning_compatible,
      "reconcile":rr,"violations":violations,"warnings":warnings,
      "failed_subsets":failed_subsets,
      "explicit_non_claims":["No identity detector was run.","RGB similarity is not proof of semantic identity.",
                             "The tile gate does not hard-constrain the diffusion sampler."]
    }
