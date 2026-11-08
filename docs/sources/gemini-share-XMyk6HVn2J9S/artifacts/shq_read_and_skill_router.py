#!/usr/bin/env python3
"""
SHQ Unified Architecture (PR #12 Normative Contract) — S0–S4 Layered Evidence `READ`,
S2/S3 Permission Compiler, & Dynamic `Method Registry` Skill Router (`shq_read_and_skill_router.py`)
====================================================================================================
Fixes the critical gap identified in PR #12 review:
  1. `route_skill_by_state()` NOW ACTUALLY LOADS AND VALIDATES `method_registry.json`
     via `validate_registry.validate()` at runtime! Every routed `method_id` is resolved
     dynamically from `method_registry.json` (never an unverified hardcoded string), returning
     its exact `implementation_status`, `capability`, `preconditions`, `failure_codes`,
     `allowed_claims`, and `forbidden_non_claims`.
  2. Conditional Four-State Route (`HOLE_FOUR_ANTI_EVIDENCE`):
     - `REMOVE -> DIFF -> HOLE` is a conditional method selected by S4 ONLY when
       `boundary_unknown_needs_empty_bg_diff == True`.
     - When `verified_closed_silhouette_available == True`, S4 skips `REMOVE -> DIFF` and
       uses the verified geometry directly!
     - Locks `DIFF != edit_permission`: candidate difference maps NEVER grant write authority!
  3. Five Independent Scale / Geometry / Tiling Variables (`Program Guidance §1–§7`):
     `model_scale != object_transform != tile_size != tile_context != delivery_transform`.
"""

from __future__ import annotations
import hashlib
import importlib.util
import json
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import cv2
import numpy as np


_HERE = Path(__file__).resolve().parent


def _load_validator():
    val_path = _HERE / "validate_registry.py"
    spec = importlib.util.spec_from_file_location("validate_registry", str(val_path))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_array(arr: np.ndarray) -> str:
    return hashlib.sha256(np.ascontiguousarray(arr).tobytes()).hexdigest()


def load_and_validate_method_registry(registry_path: Optional[Path] = None) -> Dict[str, Dict[str, object]]:
    """
    Loads `method_registry.json` from disk, runs `validate_registry.validate(data)`,
    and returns a dictionary mapping `method_id -> method_entry`.
    Fails closed (`RuntimeError`) if the registry file is missing or fails schema validation!
    """
    if registry_path is None:
        registry_path = _HERE / "method_registry.json"
    if not registry_path.exists():
        raise FileNotFoundError(f"E_REGISTRY_FILE_MISSING: {registry_path}")
    data = json.loads(registry_path.read_text(encoding="utf-8"))
    val_mod = _load_validator()
    errors = val_mod.validate(data)
    if errors:
        raise RuntimeError(f"E_REGISTRY_SCHEMA_INVALID: {errors}")
    return {m["method_id"]: m for m in data["methods"]}


# =============================================================================
# FIVE INDEPENDENT SCALE / GEOMETRY / TILING VARIABLES CONTRACT
# =============================================================================

@dataclass(frozen=True)
class IndependentScaleAndTilingContract:
    """
    Enforces PR #12's separation law:
      `model_scale != object_transform != tile_size != tile_context != delivery_transform`
    Never labels a resampled `delivery_canvas_wh` (e.g., 16 MP `5333x3000`) as an
    unmodified native `model_scale` master (e.g., 28.9 MP `7168x4032`)!
    """
    source_canvas_wh: Tuple[int, int]
    model_scale: int
    native_model_canvas_wh: Tuple[int, int]
    object_transform_matrix_2x3: List[List[float]]
    tile_size_core_wh: Tuple[int, int]
    tile_context_halo_px: int
    delivery_canvas_wh: Tuple[int, int]
    delivery_transform_scale_xy: Tuple[float, float]
    is_unmodified_native_model_master: bool
    claim_status: str


def build_independent_scale_and_tiling_contract(
    source_canvas_wh: Tuple[int, int],
    model_scale: int = 4,
    tile_size_core_wh: Tuple[int, int] = (256, 256),
    tile_context_halo_px: int = 32,
    delivery_canvas_wh: Optional[Tuple[int, int]] = None,
) -> IndependentScaleAndTilingContract:
    sw, sh = source_canvas_wh
    nw, nh = sw * model_scale, sh * model_scale
    if delivery_canvas_wh is None:
        dw, dh = nw, nh
    else:
        dw, dh = delivery_canvas_wh
    sx, sy = round(dw / float(nw), 6), round(dh / float(nh), 6)
    is_native = (dw == nw) and (dh == nh)
    eff_linear_scale = round(dw / float(sw), 4)
    claim_str = (
        f"native_{model_scale}x_master_{nw}x{nh}"
        if is_native
        else f"delivery_resampled_{dw}x{dh}_effective_{eff_linear_scale}x_NOT_unmodified_native_{model_scale}x"
    )
    return IndependentScaleAndTilingContract(
        source_canvas_wh=source_canvas_wh,
        model_scale=model_scale,
        native_model_canvas_wh=(nw, nh),
        object_transform_matrix_2x3=[[float(dw / sw), 0.0, 0.0], [0.0, float(dh / sh), 0.0]],
        tile_size_core_wh=tile_size_core_wh,
        tile_context_halo_px=tile_context_halo_px,
        delivery_canvas_wh=(dw, dh),
        delivery_transform_scale_xy=(sx, sy),
        is_unmodified_native_model_master=is_native,
        claim_status=claim_str,
    )


# =============================================================================
# S0 — BASE FREEZE & PAIRED-SOURCE REGISTRATION LEDGER
# =============================================================================

@dataclass(frozen=True)
class S0BaseFreezeRecord:
    image_id: str
    source_path: str
    source_file_sha256: str
    raw_pixel_sha256: str
    canvas_wh: Tuple[int, int]
    channels: int
    orientation: str
    frozen: bool = True


@dataclass(frozen=True)
class S0PairedSourceRegistrationRecord:
    """
    Explicitly records the coordinate transform between `L0` (Scene with object)
    and `L1` (Native Gemini empty-background counterpart) at S0 so `anti_diff`
    never performs an unrecorded/implicit resize!
    """
    l0_file_sha256: str
    l0_canvas_wh: Tuple[int, int]
    l1_original_file_sha256: str
    l1_original_canvas_wh: Tuple[int, int]
    registered_scale_ratio_xy: Tuple[float, float]
    registration_phase_shift_px: float
    l1_registered_pixel_sha256: str


def freeze_s0_base(image_path: Path, image_id: str = "") -> Tuple[S0BaseFreezeRecord, np.ndarray]:
    if not image_path.exists():
        raise FileNotFoundError(f"S0_BASE_MISSING: {image_path}")
    raw_bytes = image_path.read_bytes()
    bgr = cv2.imread(str(image_path), cv2.IMREAD_COLOR)
    if bgr is None:
        raise ValueError(f"S0_DECODE_FAILED: {image_path}")
    h, w, c = bgr.shape
    orient = "landscape" if w > h else ("portrait" if h > w else "square")
    rec = S0BaseFreezeRecord(
        image_id=image_id or image_path.stem,
        source_path=str(image_path),
        source_file_sha256=sha256_bytes(raw_bytes),
        raw_pixel_sha256=sha256_array(bgr),
        canvas_wh=(w, h),
        channels=c,
        orientation=orient,
        frozen=True,
    )
    return rec, bgr


def register_s0_paired_counterpart(
    l0_rec: S0BaseFreezeRecord,
    l0_bgr: np.ndarray,
    l1_path: Path,
    expected_scale_ratio: float = 2.0,
) -> Tuple[S0PairedSourceRegistrationRecord, np.ndarray]:
    """
    Explicitly validates and registers a known integer/exact scale counterpart `L1`
    (such as the `2752x1536` 2x Gemini Empty-BG counterpart to the `1376x768` 1x `L0` scene)
    in S0, emitting a cryptographic `S0PairedSourceRegistrationRecord`.
    """
    l1_bytes = l1_path.read_bytes()
    l1_raw = cv2.imread(str(l1_path), cv2.IMREAD_COLOR)
    h0, w0 = l0_bgr.shape[:2]
    h1, w1 = l1_raw.shape[:2]
    rx, ry = w1 / float(w0), h1 / float(h0)
    if abs(rx - expected_scale_ratio) > 1e-4 or abs(ry - expected_scale_ratio) > 1e-4:
        raise ValueError(f"E_S0_PAIRED_SCALE_UNEXPECTED: got {(rx, ry)}, expected {expected_scale_ratio}")

    l1_reg = cv2.resize(l1_raw, (w0, h0), interpolation=cv2.INTER_AREA) if (w1, h1) != (w0, h0) else l1_raw.copy()
    g0 = cv2.cvtColor(l0_bgr[:80, 450:800], cv2.COLOR_BGR2GRAY).astype(np.float32)
    g1 = cv2.cvtColor(l1_reg[:80, 450:800], cv2.COLOR_BGR2GRAY).astype(np.float32)
    (dx0, dy0), _ = cv2.phaseCorrelate(g0, g0)
    (dx, dy), _ = cv2.phaseCorrelate(g0, g1)
    shift_px = float(np.hypot(dx - dx0, dy - dy0))

    rec = S0PairedSourceRegistrationRecord(
        l0_file_sha256=l0_rec.source_file_sha256,
        l0_canvas_wh=(w0, h0),
        l1_original_file_sha256=sha256_bytes(l1_bytes),
        l1_original_canvas_wh=(w1, h1),
        registered_scale_ratio_xy=(round(rx, 4), round(ry, 4)),
        registration_phase_shift_px=round(shift_px, 4),
        l1_registered_pixel_sha256=sha256_array(l1_reg),
    )
    return rec, l1_reg


# =============================================================================
# S1 & S2 — LAYERED EVIDENCE `READ` & SCENE GRAPH (CANDIDATE ONLY!)
# =============================================================================

@dataclass(frozen=True)
class EvidenceBox:
    x0: int
    y0: int
    x1: int
    y1: int
    observable_basis: str
    measured_value: float


@dataclass(frozen=True)
class CandidateNode:
    node_id: str
    parent_id: Optional[str]
    semantic_label: str
    visibility_state: str
    bbox_xyxy: Tuple[int, int, int, int]
    closed_silhouette_sha256: str
    evidence: EvidenceBox
    status: str = "candidate"
    auto_contour_claimed_as_semantic_truth: bool = False
    edit_permission: bool = False
    geometry_lock: bool = False
    unobservable_3d_backface_status: str = "unknown"
    camera_extrinsics_status: str = "unknown"


@dataclass(frozen=True)
class CandidateRelation:
    subject_id: str
    predicate: str
    object_id: str
    evidence_bbox: Optional[Tuple[int, int, int, int]]
    observable_basis: str
    status: str = "candidate"


@dataclass(frozen=True)
class S1S2ReadReport:
    base_sha256: str
    nodes: List[CandidateNode]
    relations: List[CandidateRelation]
    unobservable_claims_rejected: List[str]
    all_outputs_marked_candidate: bool
    any_self_granted_edit_permission: bool
    any_bare_confidence_without_evidence_bbox: bool


def build_candidate_relation_with_anti_overreach(
    subj_id: str,
    obj_id: str,
    mask_a: np.ndarray,
    mask_b: np.ndarray,
    bbox_a: Tuple[int, int, int, int],
    bbox_b: Tuple[int, int, int, int],
    is_hierarchical_child: bool = False,
    Boundary_contact_visible: bool = True,
) -> CandidateRelation:
    ix0 = max(bbox_a[0], bbox_b[0])
    iy0 = max(bbox_a[1], bbox_b[1])
    ix1 = min(bbox_a[2], bbox_b[2])
    iy1 = min(bbox_a[3], bbox_b[3])

    if is_hierarchical_child:
        return CandidateRelation(
            subject_id=subj_id,
            predicate="part_of",
            object_id=obj_id,
            evidence_bbox=bbox_a,
            observable_basis="hierarchical_anatomical_subpart_containment_100pct",
            status="candidate",
        )

    if ix1 <= ix0 or iy1 <= iy0:
        return CandidateRelation(
            subject_id=subj_id,
            predicate="unknown",
            object_id=obj_id,
            evidence_bbox=None,
            observable_basis="disjoint_2d_bboxes_no_contact",
            status="candidate",
        )

    k3 = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
    dil_a = cv2.dilate(mask_a[iy0:iy1, ix0:ix1], k3, iterations=1)
    dil_b = cv2.dilate(mask_b[iy0:iy1, ix0:ix1], k3, iterations=1)
    seam = (dil_a > 0) & (dil_b > 0)
    seam_px = int(np.sum(seam))

    if seam_px > 0 and Boundary_contact_visible:
        ys, xs = np.where(seam)
        ev_box = (int(ix0 + xs.min()), int(iy0 + ys.min()), int(ix0 + xs.max() + 1), int(iy0 + ys.max() + 1))
        return CandidateRelation(
            subject_id=subj_id,
            predicate="contacts_at",
            object_id=obj_id,
            evidence_bbox=ev_box,
            observable_basis=f"shared_2d_boundary_seam_px={seam_px}",
            status="candidate",
        )
    elif seam_px > 0 and not Boundary_contact_visible:
        ys, xs = np.where(seam)
        ev_box = (int(ix0 + xs.min()), int(iy0 + ys.min()), int(ix0 + xs.max() + 1), int(iy0 + ys.max() + 1))
        return CandidateRelation(
            subject_id=subj_id,
            predicate="occludes",
            object_id=obj_id,
            evidence_bbox=ev_box,
            observable_basis=f"2d_projection_adjacency_across_depth_gap_px={seam_px}_contact_unknown",
            status="candidate",
        )
    else:
        return CandidateRelation(
            subject_id=subj_id,
            predicate="unknown",
            object_id=obj_id,
            evidence_bbox=(ix0, iy0, ix1, iy1),
            observable_basis="bbox_overlap_only_zero_silhouette_contact_seam",
            status="candidate",
        )


# =============================================================================
# S3 — HUMAN VERIFICATION & PERMISSION COMPILER (`DIFF != edit_permission`)
# =============================================================================

@dataclass(frozen=True)
class S3CompiledPermissions:
    base_sha256: str
    human_verified: bool
    diff_alone_granted_permission: bool
    verified_node_ids: List[str]
    approved_edit_mask_sha256: str
    protected_preserve_mask_sha256: str
    edit_and_preserve_disjoint: bool
    edit_and_preserve_partition_full_canvas: bool
    geometry_lock_granted: bool


def compile_s3_human_verification_and_permissions(
    base_rec: S0BaseFreezeRecord,
    read_report: S1S2ReadReport,
    approved_mask: np.ndarray,
    human_verified: bool = True,
) -> Tuple[S3CompiledPermissions, np.ndarray, np.ndarray]:
    w, h = base_rec.canvas_wh
    if approved_mask.shape[:2] != (h, w):
        raise ValueError(f"S3_MASK_SIZE_MISMATCH: got {approved_mask.shape[:2]}, expected {(h, w)}")

    edit_u8 = np.where(approved_mask >= 128, 255, 0).astype(np.uint8) if human_verified else np.zeros((h, w), dtype=np.uint8)
    preserve_u8 = np.where(edit_u8 == 255, 0, 255).astype(np.uint8)

    disjoint = bool(np.all((edit_u8 & preserve_u8) == 0))
    full_cov = bool(np.all((edit_u8 ^ preserve_u8) == 255))

    perm = S3CompiledPermissions(
        base_sha256=base_rec.raw_pixel_sha256,
        human_verified=human_verified,
        diff_alone_granted_permission=False,  # Hard PR #12 Law: DIFF != edit_permission!
        verified_node_ids=[n.node_id for n in read_report.nodes] if human_verified else [],
        approved_edit_mask_sha256=sha256_array(edit_u8),
        protected_preserve_mask_sha256=sha256_array(preserve_u8),
        edit_and_preserve_disjoint=disjoint,
        edit_and_preserve_partition_full_canvas=full_cov,
        geometry_lock_granted=human_verified,
    )
    return perm, edit_u8, preserve_u8


# =============================================================================
# S4 — DYNAMIC REGISTRY-BACKED SKILL ROUTER
#      `Method = f(Defect, Evidence, Geometry, Permission, History, Available_Backend)`
# =============================================================================

@dataclass(frozen=True)
class SkillRouterStateInput:
    topology_error: str                                   # "present" | "absent" | "unknown"
    identity_drift: str                                   # "present" | "absent" | "unknown"
    metal_detail_low: str                                 # "present" | "absent" | "unknown"
    skin_noise: str = "absent"                            # "present" | "absent" | "unknown"
    verified_closed_silhouette_available: bool = True     # If True, skips REMOVE->DIFF!
    boundary_unknown_needs_empty_bg_diff: bool = False    # Conditional trigger for HOLE_FOUR_ANTI_EVIDENCE
    hole_edit_requested: bool = False
    has_identity_reference: bool = False
    human_verified: bool = False
    has_4x_master: bool = False
    has_material_mask: bool = False
    same_coordinate_frame: bool = True
    available_backend: str = "siax_sr"                    # "siax_sr" | "flux_hr_tile" | "ai_donor_transfer" | "non_generative_hf_control"
    # Section 4: 5 Head/Part Detail States & Demoted INPAINT Role
    outer_shape_broken: str = "absent"                    # "present" -> Rollback to HOLE_FOUR_ANTI_EVIDENCE / OTL0; block DETAIL!
    surface_noise_excessive: str = "absent"               # "present" -> SKILL_C3_ATTENUATE_HF_DETAIL_LAYER
    structural_seams_mesh_cracks_missing: str = "absent"  # "present" -> SKILL_C2_NORMAL_DEPTH_STRUCTURAL_DETAIL
    material_blurry_texture_lacking: str = "absent"       # "present" -> SKILL_B_GEOMETRY_LOCKED_MATERIAL_GEN -> SKILL_C_MULTISCALE_DETAIL_SYNTHESIS
    shape_clear_pixels_low: str = "absent"                # "present" -> SKILL_A_NEURAL_SR_BASE_4X -> SKILL_B_GEOMETRY_LOCKED_MATERIAL_GEN
    missing_occlusion_hole_repair_needed: str = "absent"  # "present" -> INPAINT_HOLE_REPAIR_OPTIONAL (optional repair only!)


@dataclass(frozen=True)
class SkillRouterDecision:
    selected_skill_id: str
    registry_method_id: Optional[str]
    registry_loaded_and_validated: bool
    implementation_status: str
    capability: str
    execution_status: str
    four_state_remove_diff_skipped_because_mask_verified: bool
    diff_grants_edit_permission: bool
    blocked_downstream_skills: List[str]
    effective_identity_drift_state: str
    detail6_completion_allowed: bool
    allowed_claims: List[str]
    forbidden_non_claims: List[str]
    rationale: str


def route_skill_by_state(
    state: SkillRouterStateInput,
    registry_path: Optional[Path] = None,
) -> SkillRouterDecision:
    """
    Dynamically loads and validates `method_registry.json` and resolves the exact method
    according to:
      `Method = f(Defect, Evidence, Geometry, Permission, History, Available_Backend)`
    """
    reg_map = load_and_validate_method_registry(registry_path)

    def _pack_from_registry(
        mid: Optional[str],
        exec_status: str,
        blocked: List[str],
        eff_id: str,
        d6_ok: bool,
        rationale: str,
    ) -> SkillRouterDecision:
        if mid is None:
            return SkillRouterDecision(
                selected_skill_id="CANDIDATE_PLAN_ONLY" if exec_status == "review_required" else "BLOCKED_PRECONDITION",
                registry_method_id=None,
                registry_loaded_and_validated=True,
                implementation_status="candidate_or_blocked_no_mutation",
                capability="policy_gate",
                execution_status=exec_status,
                four_state_remove_diff_skipped_because_mask_verified=bool(state.verified_closed_silhouette_available and not state.boundary_unknown_needs_empty_bg_diff),
                diff_grants_edit_permission=False,
                blocked_downstream_skills=blocked,
                effective_identity_drift_state=eff_id,
                detail6_completion_allowed=d6_ok,
                allowed_claims=["enforces_fail_closed_s3_and_s4_preconditions"],
                forbidden_non_claims=["ai_self_authorizes_edit_permission"],
                rationale=rationale,
            )
        if mid not in reg_map:
            raise KeyError(f"E_UNREGISTERED_METHOD_ID: {mid} not found in method_registry.json")
        m_entry = reg_map[mid]
        return SkillRouterDecision(
            selected_skill_id=mid,
            registry_method_id=mid,
            registry_loaded_and_validated=True,
            implementation_status=str(m_entry["implementation_status"]),
            capability=str(m_entry["capability"]),
            execution_status=exec_status,
            four_state_remove_diff_skipped_because_mask_verified=bool(state.verified_closed_silhouette_available and not state.boundary_unknown_needs_empty_bg_diff),
            diff_grants_edit_permission=False,
            blocked_downstream_skills=blocked,
            effective_identity_drift_state=eff_id,
            detail6_completion_allowed=d6_ok,
            allowed_claims=list(m_entry.get("allowed_claims", [])),
            forbidden_non_claims=list(m_entry.get("forbidden_non_claims", [])),
            rationale=rationale,
        )

    eff_id_drift = state.identity_drift if state.has_identity_reference else "unknown"
    detail6_ok = bool(
        state.human_verified
        and state.topology_error == "absent"
        and state.has_4x_master
        and state.has_material_mask
    )

    # 1. Conditional 4-State Evidence Route: ONLY when boundary is unknown and paired empty-BG diff is needed!
    if state.boundary_unknown_needs_empty_bg_diff and not state.verified_closed_silhouette_available:
        if not state.same_coordinate_frame:
            return _pack_from_registry(
                mid="HOLE_FOUR_ANTI_EVIDENCE",
                exec_status="blocked_precondition",
                blocked=["HOLE_FOUR_ANTI_EVIDENCE", "FLUX_HR_TILE_IMG2IMG", "ALL24_AI_DONOR_MULTIBAND_TRANSFER"],
                eff_id=eff_id_drift,
                d6_ok=False,
                rationale="Precondition failed: same_coordinate_frame=False. Refusing REMOVE->DIFF across mismatched cameras.",
            )
        return _pack_from_registry(
            mid="HOLE_FOUR_ANTI_EVIDENCE",
            exec_status="candidate_evidence_only_requires_s3_review",
            blocked=["DETAIL6_MATERIAL_RESIDUAL"],
            eff_id=eff_id_drift,
            d6_ok=False,
            rationale="Boundary unknown -> run conditional REMOVE->DIFF->HOLE to produce candidate mask only (DIFF != edit_permission).",
        )

    # 2. Unverified candidate state -> hold at review_required
    if not state.human_verified:
        return _pack_from_registry(
            mid=None,
            exec_status="review_required",
            blocked=["OTL0_TOPOLOGY_REPAIR", "PATH1E_IDENTITY_ECC_LOCK", "SIAX4X_TILE_CORE_SR", "FLUX_HR_TILE_IMG2IMG", "DETAIL6_MATERIAL_RESIDUAL", "HOLE_SCALELOCK_HF_RESIDUAL"],
            eff_id=eff_id_drift,
            d6_ok=False,
            rationale="Model produced candidate understanding only; S3 human verification is required before granting edit_permission.",
        )

    # 3. Counterfactual Topology / Broken Outer Shape Priority Law
    if state.topology_error == "present" or state.outer_shape_broken == "present":
        return _pack_from_registry(
            mid="OTL0_TOPOLOGY_REPAIR",
            exec_status="execute_authorized",
            blocked=[
                "SIAX4X_TILE_CORE_SR", "FLUX_HR_TILE_IMG2IMG", "DETAIL6_MATERIAL_RESIDUAL",
                "ALL24_AI_DONOR_MULTIBAND_TRANSFER", "HOLE_SCALELOCK_HF_RESIDUAL",
                "SKILL_A_NEURAL_SR_BASE_4X", "SKILL_B_GEOMETRY_LOCKED_MATERIAL_GEN",
                "SKILL_C_MULTISCALE_DETAIL_SYNTHESIS", "SKILL_C2_NORMAL_DEPTH_STRUCTURAL_DETAIL",
                "INPAINT_HOLE_REPAIR_OPTIONAL",
            ],
            eff_id=eff_id_drift,
            d6_ok=False,
            rationale="Counterfactual Law (Section 4): outer_shape_broken/topology_error=present returns to EDIT 4-way anti-diff / OTL0 and strictly blocks all SR, Material, and Detail skills.",
        )

    # 3b. Section 4 State 5: Surface detail excessive / noisy -> attenuate H_detail layer only, keep geometry intact
    if state.surface_noise_excessive == "present":
        return _pack_from_registry(
            mid="SKILL_C3_ATTENUATE_HF_DETAIL_LAYER",
            exec_status="execute_authorized",
            blocked=["SKILL_C_MULTISCALE_DETAIL_SYNTHESIS", "INPAINT_HOLE_REPAIR_OPTIONAL"],
            eff_id=eff_id_drift,
            d6_ok=False,
            rationale="Section 4 State 5: surface_noise_excessive=present -> attenuate high-frequency H_detail layer while preserving L_base, M_material, and immutable 4x geometry.",
        )

    # 3c. Section 4 State 3: Structural seams / gold-mesh / cracks missing -> 3D/Normal/Depth-guided structural detail
    if state.structural_seams_mesh_cracks_missing == "present":
        return _pack_from_registry(
            mid="SKILL_C2_NORMAL_DEPTH_STRUCTURAL_DETAIL",
            exec_status="execute_authorized",
            blocked=["INPAINT_HOLE_REPAIR_OPTIONAL"],
            eff_id=eff_id_drift,
            d6_ok=detail6_ok,
            rationale="Section 4 State 3: structural_seams_mesh_cracks_missing=present -> route to 3D/Normal/Depth-guided structural detail synthesis inside locked M_hole.",
        )

    # 3d. Section 4 State 2: Material blurry / surface lacking texture -> Material Generation -> Detail Synthesis
    if state.material_blurry_texture_lacking == "present":
        return _pack_from_registry(
            mid="SKILL_B_GEOMETRY_LOCKED_MATERIAL_GEN",
            exec_status="execute_authorized",
            blocked=["INPAINT_HOLE_REPAIR_OPTIONAL"],
            eff_id=eff_id_drift,
            d6_ok=detail6_ok,
            rationale="Section 4 State 2: material_blurry_texture_lacking=present -> route to SKILL_B_GEOMETRY_LOCKED_MATERIAL_GEN followed by SKILL_C_MULTISCALE_DETAIL_SYNTHESIS (RGB only, zero Alpha authority).",
        )

    # 3e. Section 4 State 1: Shape clear but pixels too few -> Neural SR -> Material Detail
    if state.shape_clear_pixels_low == "present":
        return _pack_from_registry(
            mid="SKILL_A_NEURAL_SR_BASE_4X",
            exec_status="execute_authorized",
            blocked=["INPAINT_HOLE_REPAIR_OPTIONAL"],
            eff_id=eff_id_drift,
            d6_ok=detail6_ok,
            rationale="Section 4 State 1: shape_clear_pixels_low=present -> route to SKILL_A_NEURAL_SR_BASE_4X -> SKILL_B_GEOMETRY_LOCKED_MATERIAL_GEN -> SKILL_C_MULTISCALE_DETAIL_SYNTHESIS -> SKILL_D_IMMUTABLE_ALPHA_GEOMETRY_GUARD.",
        )

    # 3f. Demoted INPAINT: Optional hole completion ONLY when missing occlusion repair is explicitly needed
    if state.missing_occlusion_hole_repair_needed == "present":
        return _pack_from_registry(
            mid="INPAINT_HOLE_REPAIR_OPTIONAL",
            exec_status="execute_authorized",
            blocked=[],
            eff_id=eff_id_drift,
            d6_ok=False,
            rationale="Demoted INPAINT policy: routed strictly for optional missing-occlusion hole completion, never as the primary HD upscaler.",
        )

    # 4. Identity drift (with verified identity reference)
    if eff_id_drift == "present":
        return _pack_from_registry(
            mid="PATH1E_IDENTITY_ECC_LOCK",
            exec_status="execute_authorized",
            blocked=["DETAIL6_MATERIAL_RESIDUAL"],
            eff_id=eff_id_drift,
            d6_ok=False,
            rationale="identity_drift=present with verified identity reference -> resolved PATH1E_IDENTITY_ECC_LOCK from method_registry.json.",
        )

    # 5. Deterministic non-generative hole residual control
    if state.hole_edit_requested:
        if not state.same_coordinate_frame:
            return _pack_from_registry(
                mid="HOLE_SCALELOCK_HF_RESIDUAL",
                exec_status="blocked_precondition",
                blocked=["HOLE_SCALELOCK_HF_RESIDUAL"],
                eff_id=eff_id_drift,
                d6_ok=False,
                rationale="Blocked: same_coordinate_frame=False.",
            )
        return _pack_from_registry(
            mid="HOLE_SCALELOCK_HF_RESIDUAL",
            exec_status="execute_authorized",
            blocked=[],
            eff_id=eff_id_drift,
            d6_ok=detail6_ok,
            rationale="Resolved HOLE_SCALELOCK_HF_RESIDUAL (non-generative control) from method_registry.json.",
        )

    # 6. Material / mechanical detail low -> route by available backend & upstream state
    if state.metal_detail_low == "present":
        if state.available_backend == "flux_hr_tile":
            return _pack_from_registry(
                mid="FLUX_HR_TILE_IMG2IMG",
                exec_status="execute_authorized",
                blocked=[],
                eff_id=eff_id_drift,
                d6_ok=detail6_ok,
                rationale="Resolved FLUX_HR_TILE_IMG2IMG (Route B: High-Resolution Tile Diffusion) from method_registry.json.",
            )
        elif state.available_backend == "ai_donor_transfer":
            return _pack_from_registry(
                mid="ALL24_AI_DONOR_MULTIBAND_TRANSFER",
                exec_status="execute_authorized",
                blocked=[],
                eff_id=eff_id_drift,
                d6_ok=detail6_ok,
                rationale="Resolved ALL24_AI_DONOR_MULTIBAND_TRANSFER (Route C: External AI Donor Multiband Transfer) from method_registry.json.",
            )
        elif state.has_4x_master and state.has_material_mask:
            return _pack_from_registry(
                mid="DETAIL6_MATERIAL_RESIDUAL",
                exec_status="execute_authorized",
                blocked=[],
                eff_id=eff_id_drift,
                d6_ok=True,
                rationale="Topology clean + 4x Master & Material Mask verified -> resolved DETAIL6_MATERIAL_RESIDUAL from method_registry.json.",
            )
        else:
            return _pack_from_registry(
                mid="SIAX4X_TILE_CORE_SR",
                exec_status="execute_authorized",
                blocked=["DETAIL6_MATERIAL_RESIDUAL"],
                eff_id=eff_id_drift,
                d6_ok=False,
                rationale="metal_detail_low=present without 4x Master or Material Mask -> resolved SIAX4X_TILE_CORE_SR first; DETAIL6 blocked.",
            )

    return _pack_from_registry(
        mid="GEOMETRY_LOCKED_TILE_PLAN_RETURN",
        exec_status="execute_authorized",
        blocked=[],
        eff_id=eff_id_drift,
        d6_ok=detail6_ok,
        rationale="All defect states absent; resolved GEOMETRY_LOCKED_TILE_PLAN_RETURN from method_registry.json.",
    )