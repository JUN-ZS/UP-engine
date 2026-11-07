#!/usr/bin/env python3
"""
SHQ Unified Architecture Step 1 — Layered Evidence `READ` (S0–S3) & State-Dependent
`Skill Router` (S4) (`shq_read_and_skill_router.py`)
===================================================================================
Integrates PR #2–#5's Layered Evidence Reasoning & Skill Router with PR #15's
Method Registry (`SHQ_METHOD_REGISTRY_V1.json`):

1. S0 — BASE Freeze:
   Locks `source_sha256`, `width`, `height`, `orientation`, and raw pixel buffer.
2. S1 & S2 — Layered Evidence `READ` & Scene Graph (`part_of`, `occludes`, `contacts_at`):
   Enforces the 6-Layer Anti-Overreach Constitution:
     - Semantic Layer: Never claims auto-contours as semantic truth (`status = "candidate"`).
     - Relation Layer: Never conflates 2D bbox overlap with `contacts_at`; requires observable
       boundary contact evidence (`evidence_bbox`). Unobservable 3D back-faces, occluded joints,
       or missing references MUST be reported as `"unknown"`.
     - Evidence Layer: Every claim must carry a concrete `evidence_bbox` and observable metric
       (never a bare confidence score!).
     - Permission Layer: AI candidate output ALWAYS has `edit_permission = False` and
       `geometry_lock = False`.
3. S3 — Human Verification & Permission Compiler:
   Explicitly compiles human-verified facts and generates the binary `approved_edit_mask`
   and `protected_preserve_mask` (`approved_edit_mask & protected_preserve_mask == 0`).
4. S4 — State-Dependent `Skill Router`:
   `Skill = f(Defect, Evidence, Verification, Upstream_State, Available_Assets)`
   (NEVER `Skill = f(Image_Size)`!).
"""

from __future__ import annotations
import hashlib
import json
from dataclasses import dataclass, asdict, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import cv2
import numpy as np


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_array(arr: np.ndarray) -> str:
    return hashlib.sha256(np.ascontiguousarray(arr).tobytes()).hexdigest()


# =============================================================================
# S0 — BASE FREEZE
# =============================================================================

@dataclass(frozen=True)
class S0BaseFreezeRecord:
    image_id: str
    source_path: str
    source_file_sha256: str
    raw_pixel_sha256: str
    canvas_wh: Tuple[int, int]
    channels: int
    orientation: str  # "landscape" | "portrait" | "square"
    frozen: bool = True


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


# =============================================================================
# S1 & S2 — LAYERED EVIDENCE `READ` & SCENE GRAPH (CANDIDATE ONLY!)
# =============================================================================

@dataclass(frozen=True)
class EvidenceBox:
    x0: int
    y0: int
    x1: int
    y1: int
    observable_basis: str  # e.g., "reverse_clipping_energy_E_med=105.75", "shared_contour_edge_px=42"
    measured_value: float


@dataclass(frozen=True)
class CandidateNode:
    node_id: str
    parent_id: Optional[str]
    semantic_label: str          # "candidate_label" or "unknown"
    visibility_state: str        # "observable_2d" | "partially_occluded" | "unknown"
    bbox_xyxy: Tuple[int, int, int, int]
    closed_silhouette_sha256: str
    evidence: EvidenceBox
    # Hard Anti-Overreach Locks (reasoner_prompt.py / reasoning.py):
    status: str = "candidate"
    auto_contour_claimed_as_semantic_truth: bool = False
    edit_permission: bool = False
    geometry_lock: bool = False
    unobservable_3d_backface_status: str = "unknown"
    camera_extrinsics_status: str = "unknown"


@dataclass(frozen=True)
class CandidateRelation:
    subject_id: str
    predicate: str               # "part_of" | "occludes" | "contacts_at" | "unknown"
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
    """
    Enforces PR #2–#5 Relation & Evidence Anti-Overreach Rules:
    1. Never conflates 2D bounding-box overlap with physical contact (`contacts_at`)!
    2. `contacts_at` is emitted ONLY if `mask_a` and `mask_b` share a 1-2px dilated boundary
       seam with visible contact evidence (`evidence_bbox`).
    3. If bboxes overlap but the boundary seam is occluded or separated in depth, emits
       `occludes` or `unknown` — never `contacts_at`!
    """
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

    # Check actual 2D contour boundary contact inside intersection window
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
        # BBoxes/silhouettes project next to each other in 2D (e.g., U0 White Mecha claw vs U1 Pilot sleeve),
        # but they are at different depth planes in 3D hangar space — MUST NOT claim `contacts_at`!
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
# S3 — HUMAN VERIFICATION & PERMISSION COMPILER
# =============================================================================

@dataclass(frozen=True)
class S3CompiledPermissions:
    base_sha256: str
    human_verified: bool
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
    """
    Compiles S1/S2 candidate masks into an explicit S3 Permission Contract:
    - If `human_verified == False`, `geometry_lock_granted` is `False` and no pixel
      is authorized for final mutation (`review_required`).
    - Enforces `approved_edit_mask ^ protected_preserve_mask == 255` across the entire canvas.
    """
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
        verified_node_ids=[n.node_id for n in read_report.nodes] if human_verified else [],
        approved_edit_mask_sha256=sha256_array(edit_u8),
        protected_preserve_mask_sha256=sha256_array(preserve_u8),
        edit_and_preserve_disjoint=disjoint,
        edit_and_preserve_partition_full_canvas=full_cov,
        geometry_lock_granted=human_verified,
    )
    return perm, edit_u8, preserve_u8


# =============================================================================
# S4 — STATE-DEPENDENT SKILL ROUTER (`Skill = f(Defect, Evidence, Verification, Upstream, Assets)`)
# =============================================================================

@dataclass(frozen=True)
class SkillRouterStateInput:
    topology_error: str           # "present" | "absent" | "unknown"
    identity_drift: str           # "present" | "absent" | "unknown"
    metal_detail_low: str         # "present" | "absent" | "unknown"
    skin_noise: str               # "present" | "absent" | "unknown"
    hole_edit_requested: bool = False
    has_identity_reference: bool = False
    human_verified: bool = False
    has_4x_master: bool = False
    has_material_mask: bool = False
    same_coordinate_frame: bool = True


@dataclass(frozen=True)
class SkillRouterDecision:
    selected_skill_id: str
    execution_status: str         # "execute_authorized" | "review_required" | "blocked_precondition" | "blocked_counterfactual"
    blocked_downstream_skills: List[str]
    effective_identity_drift_state: str
    detail6_completion_allowed: bool
    rationale: str
    registry_method_id: Optional[str]


def route_skill_by_state(
    state: SkillRouterStateInput,
    registry_path: Optional[Path] = None,
) -> SkillRouterDecision:
    """
    Implements PR #5's State-Dependent `skill_router.py` law:
      `Skill = f(Defect, Evidence, Verification, Upstream State, Available Assets)`
    1. Missing identity reference -> `effective_identity_drift_state` MUST be forced to `"unknown"`!
    2. Candidate only (`human_verified == False`) -> `execution_status = "review_required"`,
       blocks mutating execution and outputs candidate plan only.
    3. `topology_error == "present"` -> routes to `OTL0_TOPOLOGY_REPAIR` (`OTL0/TEX4`) and
       HARD-BLOCKS `SIAX4X`, `GRID_SIAX`, `DETAIL6`, and `HOLE_SCALELOCK_HF` (Counterfactual Law:
       enhancing detail on broken topology makes wrong structure sharper!).
    4. `identity_drift == "present"` (with `has_identity_reference == True`) -> routes to
       `PATH1E_IDENTITY_ECC_LOCK`.
    5. `skin_noise == "present"` -> routes to `PIXEL_CTRL_SKIN_DENOISE`.
    6. `hole_edit_requested == True` -> routes to `HOLE_SCALELOCK_HF` (requires `same_coordinate_frame`).
    7. `metal_detail_low == "present"` ->
       - If `has_4x_master` and `has_material_mask`: routes to `DETAIL6_MATERIAL_ENHANCE` (`detail6_completion_allowed = True`).
       - Otherwise: routes to `SIAX4X_TILE_CORE_SR` first (`detail6_completion_allowed = False`!).
    """
    # Rule 1: Without an identity reference, identity_drift CANNOT be claimed as "present" or "absent"
    eff_id_drift = state.identity_drift if state.has_identity_reference else "unknown"
    detail6_ok = bool(
        state.human_verified
        and state.topology_error == "absent"
        and state.has_4x_master
        and state.has_material_mask
    )

    # Rule 2: Unverified candidate state -> hold at review_required
    if not state.human_verified:
        return SkillRouterDecision(
            selected_skill_id="CANDIDATE_PLAN_ONLY",
            execution_status="review_required",
            blocked_downstream_skills=["OTL0_TOPOLOGY_REPAIR", "PATH1E_IDENTITY_ECC_LOCK", "SIAX4X_TILE_CORE_SR", "DETAIL6_MATERIAL_ENHANCE", "HOLE_SCALELOCK_HF"],
            effective_identity_drift_state=eff_id_drift,
            detail6_completion_allowed=False,
            rationale="Model produced candidate understanding only; human verification (S3) is required before granting edit_permission.",
            registry_method_id=None,
        )

    # Rule 3: Counterfactual Topology Priority Law — topology error blocks all detail upscalers!
    if state.topology_error == "present":
        return SkillRouterDecision(
            selected_skill_id="OTL0_TOPOLOGY_REPAIR",
            execution_status="execute_authorized",
            blocked_downstream_skills=["SIAX4X_TILE_CORE_SR", "GRID_SIAX", "DETAIL6_MATERIAL_ENHANCE", "HOLE_SCALELOCK_HF"],
            effective_identity_drift_state=eff_id_drift,
            detail6_completion_allowed=False,
            rationale="Counterfactual Law: topology_error=present blocks DETAIL6/SIAX4X so broken object geometry is never sharpened into false structure.",
            registry_method_id="OTL0_TOPOLOGY_REPAIR",
        )

    # Rule 4: Identity drift (when identity reference is available)
    if eff_id_drift == "present":
        return SkillRouterDecision(
            selected_skill_id="PATH1E_IDENTITY_ECC_LOCK",
            execution_status="execute_authorized",
            blocked_downstream_skills=["DETAIL6_MATERIAL_ENHANCE"],
            effective_identity_drift_state=eff_id_drift,
            detail6_completion_allowed=False,
            rationale="identity_drift=present with verified identity reference -> route to PATH1E before detail enhancement.",
            registry_method_id="PATH1E_IDENTITY_ECC_LOCK",
        )

    # Rule 5: Skin noise control
    if state.skin_noise == "present":
        return SkillRouterDecision(
            selected_skill_id="PIXEL_CTRL_SKIN_DENOISE",
            execution_status="execute_authorized",
            blocked_downstream_skills=[],
            effective_identity_drift_state=eff_id_drift,
            detail6_completion_allowed=detail6_ok,
            rationale="skin_noise=present -> route to PIXEL_CTRL zero-phase edge-preserving skin denoise.",
            registry_method_id="PIXEL_CTRL_SKIN_DENOISE",
        )

    # Rule 6: Hole / Anti-Hole scale-locked detail synthesis
    if state.hole_edit_requested:
        if not state.same_coordinate_frame:
            return SkillRouterDecision(
                selected_skill_id="BLOCKED_COORD_MISMATCH",
                execution_status="blocked_precondition",
                blocked_downstream_skills=["HOLE_SCALELOCK_HF"],
                effective_identity_drift_state=eff_id_drift,
                detail6_completion_allowed=False,
                rationale="Precondition failed: same_coordinate_frame=False. Refusing to diff or paste across mismatched cameras.",
                registry_method_id="HOLE_SCALELOCK_HF",
            )
        return SkillRouterDecision(
            selected_skill_id="HOLE_SCALELOCK_HF",
            execution_status="execute_authorized",
            blocked_downstream_skills=[],
            effective_identity_drift_state=eff_id_drift,
            detail6_completion_allowed=detail6_ok,
            rationale="Verified hole in same coordinate frame -> execute HOLE_SCALELOCK_HF.",
            registry_method_id="HOLE_SCALELOCK_HF",
        )

    # Rule 7: Metal / mechanical detail low
    if state.metal_detail_low == "present":
        if state.has_4x_master and state.has_material_mask:
            return SkillRouterDecision(
                selected_skill_id="DETAIL6_MATERIAL_ENHANCE",
                execution_status="execute_authorized",
                blocked_downstream_skills=[],
                effective_identity_drift_state=eff_id_drift,
                detail6_completion_allowed=True,
                rationale="Topology clean + 4x Master & Material Mask verified -> execute DETAIL6_MATERIAL_ENHANCE.",
                registry_method_id="DETAIL6_MATERIAL_ENHANCE",
            )
        else:
            return SkillRouterDecision(
                selected_skill_id="SIAX4X_TILE_CORE_SR",
                execution_status="execute_authorized",
                blocked_downstream_skills=["DETAIL6_MATERIAL_ENHANCE"],
                effective_identity_drift_state=eff_id_drift,
                detail6_completion_allowed=False,
                rationale="metal_detail_low=present but 4x Master or Material Mask is missing -> route to SIAX4X_TILE_CORE_SR first; DETAIL6 cannot claim completion.",
                registry_method_id="SIAX4X_TILE_CORE_SR",
            )

    return SkillRouterDecision(
        selected_skill_id="NO_OP_ACCEPT_READY",
        execution_status="execute_authorized",
        blocked_downstream_skills=[],
        effective_identity_drift_state=eff_id_drift,
        detail6_completion_allowed=detail6_ok,
        rationale="All defect states absent; ready for S7 independent acceptance.",
        registry_method_id=None,
    )