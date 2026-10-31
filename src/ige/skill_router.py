from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from PIL import Image, ImageOps

from .references import ReferenceCatalog


OBSERVATIONS = {"identity_drift", "topology_error", "garment_pattern_error", "face_detail_low", "skin_noise", "metal_detail_low", "stone_detail_low", "text_detail_low", "fire_detail_low", "background_detail_low", "detail6_requested"}
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
    return {"diagnosis_version": "1.0", "image": image_facts, "observations": normalized, "diagnosis_source": str(diagnosis_path.resolve()), "note": "Semantic defects are not inferred from raster metrics; model observations remain candidates until human-verified."}


SKILL_REGISTRY: dict[str, dict[str, Any]] = {
    "OTL0": {"stage": "topology", "execution": "contract_only", "source_section": "BOUNDARY_WALKER_UNIFIED_RULES.md §0.12.31", "purpose": "lock object topology, part count and connectivity before enhancement"},
    "TEX4": {"stage": "reconstruction", "execution": "documented_only", "source_section": "FOUR_SKILL_TEX_ALIGN.md §0.12.50", "purpose": "combine IP donor, virtual fitting, RRT topology correction and P_G mapping"},
    "PATH1E": {"stage": "identity", "execution": "documented_only", "source_section": "PATH1E_PLATE_ECC_LAW.md §0.12.17", "purpose": "a8b-derived face plate, ECC alignment and protected identity composite"},
    "PIXEL_CTRL": {"stage": "pixel_protection", "execution": "documented_only", "source_section": "PIXEL_CTRL_LAW.md §0.12.16", "purpose": "pixel-class protection; sclera is restored from the structural base"},
    "SIAX4X": {"stage": "super_resolution", "execution": "implemented_optional_runtime", "source_section": "GRID_SIAX_CORRECT_PROCESS.md §0.12.15", "purpose": "4x_NMKD-Siax_200k.pth true 4x model inference"},
    "GRID_SIAX": {"stage": "detail_hybrid", "execution": "documented_only", "source_section": "GRID_SIAX_CORRECT_PROCESS.md §0.12.15–18", "purpose": "multi-region detail donor and hybrid composition with pixel-class protection"},
    "DETAIL6": {"stage": "detail_delivery", "execution": "partial", "source_section": "BOUNDARY_WALKER_UNIFIED_RULES.md §0.12.19", "purpose": "detail-only residual on approved material zones plus high-quality 4:4:4 delivery"},
    "SKIN_MAT": {"stage": "skin_material", "execution": "documented_only", "source_section": "BOUNDARY_WALKER_UNIFIED_RULES.md §0.12.20", "purpose": "same-composition pore plate, plate-dominant reconstruction and face-zone proof"},
}


def plan_skills(image_path: str | Path, diagnosis_path: str | Path, *, catalog: ReferenceCatalog | None = None, checkpoint_path: str | Path | None = None, upscaled_path: str | Path | None = None, masks_path: str | Path | None = None) -> dict[str, Any]:
    catalog = catalog or ReferenceCatalog.load()
    diagnosis = load_diagnosis(diagnosis_path, image_path)
    observations = diagnosis["observations"]
    steps: list[dict[str, Any]] = []

    def present(name: str) -> bool:
        return observations.get(name, {}).get("state") == "present"

    def verified(name: str) -> bool:
        return observations.get(name, {}).get("verification") == "human_verified"

    def add(skill: str, reason: str, prerequisites: list[str], *, stop_downstream: bool = False) -> None:
        definition = SKILL_REGISTRY[skill]
        all_verified = all(verified(name) for name in prerequisites if name in observations)
        status = "ready" if definition["execution"] == "implemented" else "partial_not_full_legacy_skill" if definition["execution"] == "partial" else "blocked_not_imported"
        if definition["execution"] == "implemented_optional_runtime":
            status = "ready" if checkpoint_path and Path(checkpoint_path).is_file() else "blocked_missing_checkpoint"
        if not all_verified:
            status = "review_required"
        refs = catalog.search(skill=skill, limit=8)
        steps.append({"skill": skill, "stage": definition["stage"], "reason": reason, "execution": definition["execution"], "status": status, "required_observations": prerequisites, "references": [item["asset_id"] for item in refs], "source_section": definition["source_section"], "stop_downstream": stop_downstream})

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
    return {"plan_version": "1.0", "image": diagnosis["image"], "diagnosis_source": diagnosis["diagnosis_source"], "observations": diagnosis["observations"], "steps": steps, "overall_status": overall, "non_claims": ["Raster dimensions are observed; semantic defects require evidence-bearing diagnosis.", "Grok Vision candidates are not human_verified and cannot authorize irreversible skill execution.", "A reference UUID is not proof that its image bytes are locally available.", "A 4x file or large MB count alone does not prove visual quality."]}
