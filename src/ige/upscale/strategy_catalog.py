from __future__ import annotations

from typing import Any


# Strategy family != checkpoint/model. The registry is deliberately broader than the
# handful of legacy skills that have already been migrated into executable code.
UPSCALE_STRATEGIES: tuple[dict[str, Any], ...] = (
    {
        "strategy_id": "RESAMPLE_CONTROL",
        "family": "deterministic_resampling",
        "mechanism": "Lanczos/bicubic pixel interpolation",
        "purpose": "dimension-only control and delivery resize",
        "detail_recovery": "none",
        "risk": "low",
        "implementation": "available_via_pillow",
        "requirements": [],
        "limitations": ["Does not recover missing detail; never report as super-resolution."],
    },
    {
        "strategy_id": "CLASSICAL_RESTORATION",
        "family": "inverse_problem_restoration",
        "mechanism": "deblur, deconvolution, denoise, deblock and deringing before/around scaling",
        "purpose": "remove known degradations rather than invent texture",
        "detail_recovery": "limited_by_observed_signal",
        "risk": "low_to_medium",
        "implementation": "not_imported",
        "requirements": ["degradation diagnosis", "noise/blur/compression estimate"],
        "limitations": ["Cannot recover detail fully destroyed by blur, clipping or downsampling."],
    },
    {
        "strategy_id": "MULTISCALE_FREQUENCY_ENHANCEMENT",
        "family": "multi_scale_frequency_domain_enhancement",
        "mechanism": "wavelet/Laplacian-pyramid band separation with locally bounded high-frequency and contrast adjustment",
        "purpose": "recover visible microcontrast from existing signal without a generative model",
        "detail_recovery": "existing_signal_only",
        "risk": "low_to_medium",
        "implementation": "not_imported",
        "model_candidates": ["wavelet detail bands", "Laplacian pyramid", "local edge-aware contrast"],
        "requirements": ["noise/edge assessment", "protected face/skin/eye masks where applicable"],
        "limitations": ["Cannot create true missing resolution; can amplify noise, ringing and compression artifacts."],
    },
    {
        "strategy_id": "CNN_GAN_SR",
        "family": "learned_feed_forward_super_resolution",
        "mechanism": "ESRGAN-family learned image prior",
        "purpose": "single-image 2x/4x perceptual detail reconstruction",
        "detail_recovery": "model_prior",
        "risk": "medium_to_high",
        "implementation": "partial_model_adapter_available",
        "model_candidates": ["4x_NMKD-Siax_200k", "Real-ESRGAN family"],
        "requirements": ["checkpoint", "model hash/provenance", "native model scale"],
        "limitations": ["May invent plausible texture; checkpoint choice is content-dependent."],
    },
    {
        "strategy_id": "TRANSFORMER_SR",
        "family": "transformer_image_restoration",
        "mechanism": "window/global-attention restoration and super-resolution",
        "purpose": "preserve broader context while reconstructing repeated fine structures",
        "detail_recovery": "model_prior",
        "risk": "medium",
        "implementation": "not_imported",
        "model_candidates": ["SwinIR", "HAT"],
        "requirements": ["model checkpoint", "task/degradation-compatible weights"],
        "limitations": ["Not inherently identity-safe; model training domain matters."],
    },
    {
        "strategy_id": "DIFFUSION_SR",
        "family": "generative_diffusion_restoration",
        "mechanism": "conditional diffusion restoration / generative super-resolution",
        "purpose": "recover perceptually rich texture in severely degraded or AI-generated images",
        "detail_recovery": "strong_generative_prior",
        "risk": "high",
        "implementation": "not_imported",
        "model_candidates": ["SUPIR", "DiffBIR", "SeeSR", "ResShift", "GuideSR-family"],
        "requirements": ["conditioning profile", "low-strength structural guidance", "identity/geometry review"],
        "limitations": ["Can hallucinate features, alter faces, seams, text and object topology."],
    },
    {
        "strategy_id": "IDENTITY_GUIDED_FACE_RESTORATION",
        "family": "identity_conditioned_face_reconstruction",
        "mechanism": "canonical face reference + aligned face plate/ROI + protected eye/face compositing",
        "purpose": "restore facial detail while constraining identity to the canonical a8b reference",
        "detail_recovery": "identity_reference_conditioned",
        "risk": "medium_to_high",
        "implementation": "documented_only",
        "model_candidates": ["PATH1E plate/ECC", "identity-conditioned face restoration"],
        "requirements": ["actual canonical identity image bytes", "face ROI", "alignment and landmark/feature checks", "protected eyes and face boundary"],
        "limitations": ["An identity embedding alone does not prove pixel or geometric identity; misalignment can create face seams."],
    },
    {
        "strategy_id": "REFERENCE_GUIDED_SR",
        "family": "retrieval_and_reference_guided_reconstruction",
        "mechanism": "retrieve and align semantically/structurally matching high-resolution donor patches",
        "purpose": "recover subject- or material-specific detail from verified references",
        "detail_recovery": "reference_evidence_plus_model",
        "risk": "medium_to_high",
        "implementation": "not_imported",
        "model_candidates": ["iRAG", "RefGC-SR2", "feature/patch-matching RefSR"],
        "requirements": ["actual donor image bytes", "donor role/material compatibility", "registration", "occlusion/change mask"],
        "limitations": ["A face identity reference is not automatically a metal/cloth texture donor; incorrect references cause texture leakage."],
    },
    {
        "strategy_id": "NATIVE_GENERATIVE_REDETAIL",
        "family": "image_to_image_generative_reconstruction",
        "mechanism": "native image-edit/re-render with composition, identity and part constraints",
        "purpose": "synthesize coherent details when source information is insufficient",
        "detail_recovery": "generative_prior",
        "risk": "very_high",
        "implementation": "external_candidate_workflow_available",
        "model_candidates": ["Grok Imagine HERE", "other controlled image-to-image generators"],
        "requirements": ["BASE", "prompt/strength record", "identity reference when needed", "registration and geometry review"],
        "limitations": ["Not pixel restoration; may alter geometry, pose, material boundaries and facial identity."],
    },
    {
        "strategy_id": "ROI_HYBRID",
        "family": "region_specialist_ensemble",
        "mechanism": "segment regions, route each to a specialist method, then compose with protected zones",
        "purpose": "use different restoration/generation methods for face, skin, metal, cloth, text and environment",
        "detail_recovery": "mixed",
        "risk": "medium_to_very_high",
        "implementation": "partial_foundation_available",
        "model_candidates": ["GRID x SIAX", "face plate/ECC", "material-specific SR or re-detail"],
        "requirements": ["reviewed region masks", "BASE coordinate registration", "face/eye/identity protection", "per-zone proof"],
        "limitations": ["Mask errors and boundary seams can damage identity or topology."],
    },
    {
        "strategy_id": "TEMPORAL_MULTI_FRAME_SR",
        "family": "multi_frame_evidence_fusion",
        "mechanism": "align and fuse sub-pixel detail across multiple compatible frames",
        "purpose": "recover information not present in one frame by using independent observations",
        "detail_recovery": "observed_multi_frame_evidence",
        "risk": "medium",
        "implementation": "not_imported",
        "model_candidates": ["burst/temporal SR and optical-flow fusion"],
        "requirements": ["2+ same-state frames", "registration", "motion/occlusion rejection"],
        "limitations": ["Different pose, contact state, lighting or deformation cannot be naively fused."],
    },
    {
        "strategy_id": "GEOMETRY_GUIDED_SR",
        "family": "depth_normal_mesh_conditioned_reconstruction",
        "mechanism": "condition detail reconstruction on depth, normals, segmentation or 3D mesh",
        "purpose": "keep surface orientation, edge flow and object-part structure coherent",
        "detail_recovery": "geometry_conditioned_prior",
        "risk": "medium_to_high",
        "implementation": "not_imported",
        "model_candidates": ["depth/normal/mesh-conditioned diffusion or restoration"],
        "requirements": ["reviewed depth/normal/mesh", "camera/coordinate consistency"],
        "limitations": ["Estimated depth is uncertain; 2D depth maps are not metric 3D proof."],
    },
)


def _present(observations: dict[str, Any], name: str) -> bool:
    return observations.get(name, {}).get("state") == "present"


def _verified(observations: dict[str, Any], name: str) -> bool:
    return observations.get(name, {}).get("verification") == "human_verified"


def _context_value(context: dict[str, Any], key: str, default: Any) -> Any:
    return context.get(key, default)


def build_strategy_portfolio(
    observations: dict[str, Any],
    *,
    references: list[dict[str, Any]] | None = None,
    context: dict[str, Any] | None = None,
    has_siax_checkpoint: bool = False,
    has_4x_master: bool = False,
    has_material_masks: bool = False,
) -> dict[str, Any]:
    """Build a state-dependent method portfolio; it proposes alternatives, it does not execute them."""
    references = references or []
    context = context or {}
    topology_present = _present(observations, "topology_error") or _present(observations, "garment_pattern_error")
    topology_verified = (
        _verified(observations, "topology_error") and _present(observations, "topology_error")
    ) or (
        _verified(observations, "garment_pattern_error") and _present(observations, "garment_pattern_error")
    )
    detail_names = ("face_detail_low", "metal_detail_low", "stone_detail_low", "text_detail_low",
                    "fire_detail_low", "background_detail_low")
    detail_present = any(_present(observations, key) for key in detail_names + ("low_resolution_undersampling",))
    degradation_present = any(_present(observations, key) for key in (
        "skin_noise", "defocus_blur", "motion_blur", "compression_artifacts",
        "jpeg_blocks", "oversharpening_ringing", "color_noise"
    ))
    donor_refs = [
        ref for ref in references
        if ref.get("role") in {
            "material_texture_donor", "garment_texture_donor",
            "armor_detail_donor", "scene_detail_donor", "matched_hr_donor"
        } and (
            ref.get("availability") in {"local_verified", "materialized_verified"}
            or ref.get("materialization") == "local_verified"
            or (ref.get("path") and ref.get("sha256"))
        )
    ]
    identity_refs = [
        ref for ref in references
        if ref.get("role") == "identity_reference"
        and (
            ref.get("availability") in {"local_verified", "materialized_verified"}
            or ref.get("materialization") == "local_verified"
            or (ref.get("path") and ref.get("sha256"))
        )
    ]
    frame_count = int(_context_value(context, "frame_count", 1))
    aligned_frames = bool(_context_value(context, "frames_registered", False))
    depth_available = bool(_context_value(context, "depth_map_verified", False))
    normals_available = bool(_context_value(context, "normal_map_verified", False))
    mesh_available = bool(_context_value(context, "mesh_verified", False))
    allow_native = bool(_context_value(context, "allow_native_generative_redetail", True))
    target_scale = _context_value(context, "target_scale", 4)

    rows: list[dict[str, Any]] = []

    def add(strategy_id: str, eligibility: str, reasons: list[str], *, blocked_by_topology: bool = True,
            extra_requirements: list[str] | None = None) -> None:
        definition = next(x for x in UPSCALE_STRATEGIES if x["strategy_id"] == strategy_id)
        status = eligibility
        if topology_verified and blocked_by_topology and strategy_id not in {"RESAMPLE_CONTROL"}:
            status = "blocked_until_topology_repaired"
            reasons = reasons + ["Human-verified topology defect blocks detail enhancement."]
        elif topology_present and blocked_by_topology and strategy_id not in {"RESAMPLE_CONTROL"}:
            status = "review_topology_candidate_first"
            reasons = reasons + ["A topology defect was reported but is not yet human-verified."]
        if extra_requirements:
            reasons = reasons + extra_requirements
        rows.append({
            "strategy_id": strategy_id,
            "family": definition["family"],
            "mechanism": definition["mechanism"],
            "purpose": definition["purpose"],
            "detail_recovery": definition.get("detail_recovery", "not_specified"),
            "eligibility": status,
            "reasons": reasons,
            "implementation": definition["implementation"],
            "model_candidates": definition.get("model_candidates", []),
            "requirements": definition["requirements"],
            "risk": definition["risk"],
            "limitations": definition["limitations"],
            "target_scale": target_scale,
            "execution_performed": False,
            "final_acceptance": False,
        })

    add("RESAMPLE_CONTROL", "control_only", [
        "Keep a dimension-only resize as a low-risk control; it is not detail recovery."
    ], blocked_by_topology=False)

    if degradation_present:
        add("CLASSICAL_RESTORATION", "candidate_after_review", [
            "One or more blur/noise/compression/ringing observations are present."
        ])
    else:
        add("CLASSICAL_RESTORATION", "conditional_not_selected", [
            "No confirmed degradation subtype currently selects this branch; do not denoise/sharpen by default."
        ])

    if bool(_context_value(context, "local_contrast_deficit", False)):
        add("MULTISCALE_FREQUENCY_ENHANCEMENT", "candidate_after_review", [
            "The diagnosis context declares local microcontrast loss; verify that noise/ringing is not being amplified."
        ])
    else:
        add("MULTISCALE_FREQUENCY_ENHANCEMENT", "conditional_not_selected", [
            "Use only when genuine microcontrast loss is identified and noise/ringing is controlled."
        ])

    if detail_present:
        add("CNN_GAN_SR", "candidate_model_comparison", [
            "At least one subject/material detail deficit is reported."
        ], extra_requirements=(
            ["Siax checkpoint is present; run the pinned adapter and record its sidecar."]
            if has_siax_checkpoint and not has_4x_master else
            ["A 4x master path is supplied; verify its sidecar/hash before DETAIL6 and reuse it instead of running Siax again."]
            if has_4x_master else
            ["Siax adapter exists but weights are not established; no inference is claimed."]
        ))
        add("TRANSFORMER_SR", "candidate_not_imported", [
            "Compare a context-aware transformer SR family against the CNN/GAN baseline."
        ])
        add("DIFFUSION_SR", "candidate_not_imported_high_risk", [
            "A generative restoration branch may reconstruct richer texture; use a conservative structure condition and compare face/topology separately."
        ])
        add("NATIVE_GENERATIVE_REDETAIL", "candidate_external_generation" if allow_native else "disabled_by_context", [
            "The supplied workflow includes native re-detail outputs; treat them as generative reconstruction, not pixel-faithful SR."
        ])
        add("ROI_HYBRID", "candidate_partial_foundation" if has_material_masks else "blocked_missing_reviewed_masks", [
            "Material-specific deficits support routing different methods by region."
        ], extra_requirements=[] if has_material_masks else ["Generate/review region masks before execution."])
    else:
        for strategy_id in ("CNN_GAN_SR", "TRANSFORMER_SR", "DIFFUSION_SR", "NATIVE_GENERATIVE_REDETAIL", "ROI_HYBRID"):
            add(strategy_id, "conditional_not_selected", [
                "No detail-loss observation currently selects this branch; retain it in the portfolio instead of running every model."
            ])

    if identity_refs and (_present(observations, "face_detail_low") or _present(observations, "identity_drift")):
        add("IDENTITY_GUIDED_FACE_RESTORATION", "candidate_not_imported", [
            "A canonical identity reference is supplied and face detail/identity repair is reported."
        ])
    elif identity_refs:
        add("IDENTITY_GUIDED_FACE_RESTORATION", "conditional_not_selected", [
            "A canonical identity reference is supplied, but no face-detail/identity defect currently selects this branch."
        ])
    else:
        add("IDENTITY_GUIDED_FACE_RESTORATION", "blocked_no_identity_reference", [
            "No canonical identity reference image is supplied; identity-guided face reconstruction cannot be grounded."
        ])

    if donor_refs:
        add("REFERENCE_GUIDED_SR", "candidate_not_imported", [
            f"{len(donor_refs)} material/scene donor reference(s) are locally verified and role-compatible."
        ])
    else:
        add("REFERENCE_GUIDED_SR", "blocked_no_verified_detail_donor", [
            "No locally verified material/garment/scene detail donor is present. An identity-only a8b reference is not counted as a texture donor."
        ])

    if frame_count >= 2 and aligned_frames:
        add("TEMPORAL_MULTI_FRAME_SR", "candidate_not_imported", [
            f"{frame_count} frames are declared and registration is marked verified."
        ])
    elif frame_count >= 2:
        add("TEMPORAL_MULTI_FRAME_SR", "blocked_frames_not_registered", [
            f"{frame_count} frames are declared, but same-state registration has not been verified."
        ])
    else:
        add("TEMPORAL_MULTI_FRAME_SR", "conditional_need_2plus_compatible_frames", [
            "A single source image cannot provide temporal/sub-pixel evidence."
        ])

    if depth_available or normals_available or mesh_available:
        add("GEOMETRY_GUIDED_SR", "candidate_requires_geometry_review", [
            "At least one verified depth/normal/mesh input is available."
        ])
    else:
        add("GEOMETRY_GUIDED_SR", "conditional_need_verified_geometry", [
            "No verified depth, normal map or mesh was supplied."
        ])

    eligible = [row for row in rows if row["eligibility"].startswith("candidate")]
    return {
        "portfolio_version": "1.0",
        "selection_mode": "state_dependent_portfolio_not_single_fixed_method",
        "context": {
            "detail_deficit_observed": detail_present,
            "degradation_observed": degradation_present,
            "topology_defect_reported": topology_present,
            "topology_defect_human_verified": topology_verified,
            "identity_reference_count": len(identity_refs),
            "verified_detail_donor_count": len(donor_refs),
            "frame_count": frame_count,
            "frames_registered": aligned_frames,
            "verified_geometry_available": depth_available or normals_available or mesh_available,
            "has_siax_checkpoint": has_siax_checkpoint,
            "has_4x_master": has_4x_master,
            "has_material_masks": has_material_masks,
        },
        "eligible_candidate_count": len(eligible),
        "strategies": rows,
        "comparison_protocol": [
            "Use the identical BASE SHA for every single-image branch.",
            "Keep target dimensions and crop identical when comparing model families.",
            "Record checkpoint/model revision, parameters, seed, runtime, output SHA and output dimensions.",
            "Use identity/geometry/topology gates separately from perceptual detail scoring.",
            "Keep a dimension-only control; do not label interpolation as recovered detail.",
            "Do not rank a strategy until the same BASE has been replayed through competing families.",
        ],
        "non_claims": [
            "A listed method is not necessarily installed or executable in this environment.",
            "Candidate eligibility is not a quality ranking.",
            "A high-frequency or file-size increase is not proof of improved clarity.",
            "Identity references are not automatically texture donors.",
            "No strategy in this portfolio is marked final_acceptance.",
        ],
    }
