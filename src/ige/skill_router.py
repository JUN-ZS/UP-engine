from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path
from typing import Any

from PIL import Image, ImageOps

from .method_registry import MethodRegistry
from .references import ReferenceCatalog
from .upscale.strategy_catalog import build_strategy_portfolio


OBSERVATIONS = {"identity_drift", "topology_error", "garment_pattern_error", "face_detail_low", "skin_noise", "metal_detail_low", "stone_detail_low", "text_detail_low", "fire_detail_low", "background_detail_low", "detail6_requested", "defocus_blur", "motion_blur", "compression_artifacts", "jpeg_blocks", "oversharpening_ringing", "color_noise", "low_resolution_undersampling"}
VALID_STATES = {"present", "absent", "unknown"}


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def inspect_source_image(path: str | Path) -> dict[str, Any]:
    source = Path(path)
    if not source.is_file():
        raise FileNotFoundError(source)
    with Image.open(source) as opened:
        image = ImageOps.exif_transpose(opened)
        width, height = image.size
        image_format, mode = opened.format, opened.mode
    return {"path": str(source.resolve()), "sha256": _sha256(source), "width": width, "height": height, "megapixels": round(width * height / 1_000_000, 4), "format": image_format, "mode": mode, "classification": "observed_raster_facts_only"}


def load_diagnosis(path: str | Path, image_path: str | Path) -> dict[str, Any]:
    diagnosis_path = Path(path)
    raw = json.loads(diagnosis_path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict) or raw.get("diagnosis_version") != "1.0":
        raise ValueError("diagnosis_version must be '1.0'")
    image_facts = inspect_source_image(image_path)
    claimed = raw.get("image", {})
    if claimed.get("sha256") and claimed["sha256"] != image_facts["sha256"]:
        raise ValueError("diagnosis source SHA-256 does not match the supplied image")
    observations = raw.get("observations")
    if not isinstance(observations, dict):
        raise ValueError("diagnosis observations must be an object")
    unknown_keys = set(observations) - OBSERVATIONS
    if unknown_keys:
        raise ValueError(f"unsupported diagnosis observations: {sorted(unknown_keys)}")
    normalized: dict[str, dict[str, Any]] = {}
    for name, item in observations.items():
        if not isinstance(item, dict):
            raise ValueError(f"observation {name} must be an object")
        state = item.get("state", "unknown")
        if state not in VALID_STATES:
            raise ValueError(f"observation {name}.state must be present, absent or unknown")
        evidence = str(item.get("evidence", "")).strip()
        source = str(item.get("source", "unknown")).strip()
        verification = str(item.get("verification", "unverified")).strip()
        if state == "present" and not evidence:
            raise ValueError(f"present observation {name} requires evidence")
        if source not in {"human", "grok_vision", "other_model", "instrument"}:
            raise ValueError(f"observation {name}.source is invalid")
        if verification not in {"human_verified", "candidate", "unverified"}:
            raise ValueError(f"observation {name}.verification is invalid")
        normalized[name] = {"state": state, "evidence": evidence, "source": source, "verification": verification}
    references = raw.get("references", [])
    if not isinstance(references, list) or any(not isinstance(item, dict) for item in references):
        raise ValueError("diagnosis references must be an array of objects")
    strategy_context = raw.get("strategy_context", {})
    if not isinstance(strategy_context, dict):
        raise ValueError("strategy_context must be an object")
    return {
        "diagnosis_version": "1.0",
        "image": image_facts,
        "observations": normalized,
        "references": references,
        "strategy_context": strategy_context,
        "diagnosis_source": str(diagnosis_path.resolve()),
        "note": "Semantic defects are not inferred from raster metrics; model observations remain candidates until human-verified."
    }


def plan_skills(image_path: str | Path, diagnosis_path: str | Path, *, catalog: ReferenceCatalog | None = None, checkpoint_path: str | Path | None = None, upscaled_path: str | Path | None = None, masks_path: str | Path | None = None, method_registry_path: str | Path | None = None, license_review_acknowledged: bool = False) -> dict[str, Any]:
    catalog = catalog or ReferenceCatalog.load()
    method_registry = MethodRegistry.load(method_registry_path)
    try:
        siax_adapter_available = (
            importlib.util.find_spec("torch") is not None
            and importlib.util.find_spec("spandrel") is not None
        )
    except (ImportError, ValueError, ModuleNotFoundError):
        siax_adapter_available = False
    diagnosis = load_diagnosis(diagnosis_path, image_path)
    observations = diagnosis["observations"]
    steps: list[dict[str, Any]] = []

    def present(name: str) -> bool:
        return observations.get(name, {}).get("state") == "present"

    def verified(name: str) -> bool:
        return observations.get(name, {}).get("verification") == "human_verified"

    def add(skill: str, reason: str, prerequisites: list[str], *, stop_downstream: bool = False) -> None:
        method = method_registry.resolve_skill(skill)
        maturity = method["maturity"]
        all_verified = all(verified(name) for name in prerequisites if name in observations)
        if maturity == "optional_runtime":
            if upscaled_path and Path(upscaled_path).is_file():
                status = "upscaled_master_available"
            else:
                status = "checkpoint_available_review_required" if checkpoint_path and Path(checkpoint_path).is_file() else "blocked_missing_checkpoint"
        elif maturity == "partial":
            status = "partial_not_full_legacy_skill"
        elif maturity == "experimental":
            status = "review_required_experimental"
        elif maturity == "candidate_only":
            status = "candidate_only"
        elif maturity in {"workflow_candidate", "research_only", "external_donor_research", "documented_only", "proxy_only", "contract_only"}:
            status = "blocked_not_imported"
        else:
            status = "blocked_unknown_maturity"
        if not all_verified:
            status = "review_required"
        refs = catalog.search(skill=skill, limit=8)

        topology = observations.get("topology_error", {})
        topology_verified = (
            isinstance(topology, dict)
            and topology.get("state") in {"absent", "resolved"}
            and topology.get("verification") == "human_verified"
        )
        checkpoint_hash_verified = False
        if skill == "SIAX4X" and checkpoint_path and Path(checkpoint_path).is_file():
            try:
                from .upscale.siax import MODEL_SHA256, file_sha256
                checkpoint_hash_verified = file_sha256(checkpoint_path) == MODEL_SHA256
            except (ImportError, OSError, ValueError):
                checkpoint_hash_verified = False
        verified_master = False
        if skill == "DETAIL6" and upscaled_path and Path(upscaled_path).is_file():
            sidecar = Path(upscaled_path).with_suffix(".upscale.json")
            if sidecar.is_file():
                try:
                    receipt = json.loads(sidecar.read_text(encoding="utf-8"))
                    verified_master = (
                        receipt.get("acceptance") == "candidate_only"
                        and receipt.get("output_sha256") == _sha256(Path(upscaled_path))
                        and receipt.get("scale") == 4
                    )
                except (OSError, json.JSONDecodeError):
                    verified_master = False

        # Skill planning has no S0 freeze, S2 human geometry contract or S3
        # source-bound human mask approval. File existence is not permission.
        method_context = {
            "s0_source_sha_verified": False,
            "topology_verified": topology_verified,
            "topology_state": topology.get("state", "unknown") if isinstance(topology, dict) else "unknown",
            "topology_human_verified": topology_verified,
            "geometry_contract_verified": False,
            "human_permission": False,
            "approved_masks_verified": False,
            "checkpoint_sha_verified": checkpoint_hash_verified,
            "license_acknowledged": bool(license_review_acknowledged),
            "verified_4x_master_available": verified_master,
            "backend_adapter_available": siax_adapter_available if skill == "SIAX4X" else False,
            "tile_plan_verified": False,
            "comfy_nodes_available": False,
            "backend_model_inventory_verified": False,
            "tile_conditioning_verified": False,
            "global_noise_field_verified": False,
            "identity_reference_bytes_verified": False,
            "donor_bytes_verified": False,
            "donor_backend_receipt_verified": False,
            "donor_part_mapping_verified": False,
            "paired_edit_provenance_verified": False,
        }
        method_decision = method_registry.evaluate(method["method_id"], method_context)
        steps.append({
            "skill": skill,
            "method_id": method["method_id"],
            "method_maturity": method["maturity"],
            "method_decision": method_decision,
            "registry_status": method_decision["status"],
            "registry_blockers": method_decision["blockers"],
            "execution_authorized": False,
            "stage": method["route_stage"],
            "reason": reason,
            "execution": maturity,
            "status": status,
            "required_observations": prerequisites,
            "references": [item["asset_id"] for item in refs],
            "source_section": method["source_section"],
            "stop_downstream": stop_downstream,
        })

    if present("topology_error"):
        add("OTL0", observations["topology_error"]["evidence"], ["topology_error"], stop_downstream=True)
        add("TEX4", "topology/garment reconstruction must be resolved before detail enhancement", ["topology_error"], stop_downstream=True)
    elif present("garment_pattern_error"):
        add("TEX4", observations["garment_pattern_error"]["evidence"], ["garment_pattern_error"], stop_downstream=True)

    if present("identity_drift"):
        add("PATH1E", observations["identity_drift"]["evidence"], ["identity_drift"])
        a8b = catalog.inspect("a8b78fe5-2654-4f6f-84e3-c1dfbee61004")
        steps[-1]["identity_reference"] = {"asset_id": a8b["asset_id"], "availability": a8b["availability"], "materialization": "not_checked"}

    detail_observations = [name for name in ("metal_detail_low", "stone_detail_low", "text_detail_low", "fire_detail_low", "background_detail_low") if present(name)]
    if detail_observations:
        all_verified = all(verified(name) for name in detail_observations)
        add("SIAX4X", "4x model detail reconstruction requested for: " + ", ".join(detail_observations), detail_observations)
        add("GRID_SIAX", "region-aware detail donor/hybrid stage after object and material masks", detail_observations)
        add("DETAIL6", "detail residual and high-quality delivery after accepted 4x master", detail_observations)
        steps[-1]["requires"] = ["verified 4x_NMKD-Siax_200k.pth output and sidecar", "metal/stone/text/fire masks", "face/skin/eye_white protection masks"]
        if not all_verified:
            steps[-1]["status"] = "review_required"
        elif not upscaled_path or not Path(upscaled_path).is_file() or not masks_path or not Path(masks_path).is_file():
            steps[-1]["status"] = "blocked_missing_4x_master_or_masks"
        else:
            steps[-1]["status"] = "partial_execution_review_required"

    if present("face_detail_low"):
        add("PATH1E", observations["face_detail_low"]["evidence"], ["face_detail_low"])
        add("SKIN_MAT", "same-composition face material plate; must not change identity", ["face_detail_low"])
    if present("skin_noise"):
        add("PIXEL_CTRL", observations["skin_noise"]["evidence"], ["skin_noise"])
    if present("detail6_requested") and not detail_observations:
        add("DETAIL6", observations["detail6_requested"]["evidence"], ["detail6_requested"])
        steps[-1]["status"] = "partial_execution_review_required" if upscaled_path and Path(upscaled_path).is_file() and masks_path and Path(masks_path).is_file() else "blocked_missing_4x_master_or_masks"

    if not steps:
        steps.append({"skill": None, "stage": "diagnosis", "status": "insufficient_semantic_evidence", "reason": "No verified defect observations selected a skill. Raster dimensions alone cannot identify face, topology or material defects."})
    if any(step.get("stop_downstream") for step in steps):
        for step in steps:
            if step["skill"] in {"SIAX4X", "GRID_SIAX", "DETAIL6", "SKIN_MAT"}:
                step["status"] = "blocked_by_upstream_topology"
    statuses = {step["status"] for step in steps}
    overall = "BLOCKED" if any(status.startswith("blocked") for status in statuses) else "REVIEW_REQUIRED" if any(status in {"review_required", "blocked_not_imported", "insufficient_semantic_evidence"} or status.startswith("partial") for status in statuses) else "READY_FOR_EXECUTION"
    strategy_portfolio = build_strategy_portfolio(
        diagnosis["observations"],
        references=diagnosis.get("references", []),
        context=diagnosis.get("strategy_context", {}),
        has_siax_checkpoint=bool(checkpoint_path and Path(checkpoint_path).is_file()),
        has_4x_master=bool(upscaled_path and Path(upscaled_path).is_file()),
        has_material_masks=bool(masks_path and Path(masks_path).is_file()),
    )
    return {
        "plan_version": "1.2",
        "method_registry": {
            "registry_schema": method_registry.payload["registry_schema"],
            "registry_id": method_registry.payload.get("registry_id"),
            "registry_version": method_registry.payload.get("registry_version"),
            "source": method_registry.source,
            "method_count": len(method_registry.methods),
        },
        "image": diagnosis["image"],
        "diagnosis_source": diagnosis["diagnosis_source"],
        "observations": diagnosis["observations"],
        "steps": steps,
        "strategy_portfolio": strategy_portfolio,
        "overall_status": overall,
        "execution_readiness": "BLOCKED_S0_S3_EVIDENCE_REQUIRED",
        "execution_authorized": False,
        "non_claims": [
            "Raster dimensions are observed; semantic defects require evidence-bearing diagnosis.",
            "Grok Vision candidates are not human_verified and cannot authorize irreversible skill execution.",
            "A reference UUID is not proof that its image bytes are locally available.",
            "A 4x file or large byte-size does not prove visual quality.",
            "The strategy portfolio lists distinct method families; it does not imply every runtime is installed.",
            "Strategy eligibility is not an empirical quality ranking.",
            "A skill plan is not an S0 freeze, S2 geometry contract, S3 human permission, or S7 acceptance.",
            "Registry method eligibility never grants pixel-edit permission; S3 permission remains independently required."
        ]
    }
