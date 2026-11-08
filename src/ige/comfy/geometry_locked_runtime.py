"""Comfy Cloud ↔ SHQ S2/S3/S4/S6 geometry-locked candidate bridge.

This submits one tile workflow to Comfy Cloud, requires exact tile/output
identity, then performs a real local core-only S6 compositor. It deliberately
leaves global-noise, Cloud weight-SHA and S7 acceptance gates blocked.
"""
from __future__ import annotations

import copy
import hashlib
import json
import os
import re
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Mapping

from PIL import Image

from .cloud_client import ComfyCloudClient
from .geometry_locked import (
    compose_core_only_master,
    sha256_file,
    validate_geometry_tile_plan,
)
from .workflow_runtime import audit_api_workflow_live, load_api_workflow

MANIFEST_SCHEMA = "ige-comfy-geometry-locked-run/0.1"
PERMISSION_SCHEMA = "ige-comfy-geometry-human-permission/0.1"
ALLOWED_DIAGNOSTIC_BLOCKERS = frozenset({
    "E_NOISE_FIELD_NOT_GLOBAL",
    "E_TILE_COMPOSITOR_MISSING",
    "E_CLOUD_MODEL_SHA_UNVERIFIED",
})


class GeometryLockedRuntimeError(RuntimeError):
    """Raised on missing proof, route ambiguity, backend failure or unsafe write."""


def _canonical_sha(value: Mapping[str, Any]) -> str:
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _resolve(base: Path, value: str) -> Path:
    candidate = Path(value).expanduser()
    return candidate.resolve() if candidate.is_absolute() else (base / candidate).resolve()


def _portable(path: Path, base: Path) -> str:
    try:
        return os.path.relpath(path, base)
    except ValueError:
        return str(path)


def _load_json(path: Path, label: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise GeometryLockedRuntimeError(f"cannot read {label} JSON {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise GeometryLockedRuntimeError(f"{label} JSON root must be an object")
    return value


def _file_record(path: str | Path, base: Path, label: str) -> dict[str, Any]:
    resolved = Path(path).expanduser().resolve()
    if not resolved.is_file():
        raise GeometryLockedRuntimeError(f"{label} file does not exist: {resolved}")
    return {"path": _portable(resolved, base), "sha256": sha256_file(resolved)}


def _validate_permission_receipt(
    path: str | Path,
    *,
    expected: Mapping[str, str],
) -> dict[str, Any]:
    permission_path = Path(path).expanduser().resolve()
    permission = _load_json(permission_path, "human permission")
    if permission.get("schema") != PERMISSION_SCHEMA:
        raise GeometryLockedRuntimeError(f"permission schema must be {PERMISSION_SCHEMA}")
    if permission.get("decision") != "APPROVED":
        raise GeometryLockedRuntimeError("S3 permission is not APPROVED; do not submit or compose")
    reviewer = permission.get("reviewer_ref")
    reviewed_at = permission.get("reviewed_at")
    if not isinstance(reviewer, str) or not reviewer.strip():
        raise GeometryLockedRuntimeError("S3 permission reviewer_ref is required")
    if not isinstance(reviewed_at, str) or not reviewed_at.strip():
        raise GeometryLockedRuntimeError("S3 permission reviewed_at is required")
    try:
        timestamp = datetime.fromisoformat(reviewed_at.replace("Z", "+00:00"))
    except ValueError as exc:
        raise GeometryLockedRuntimeError("S3 reviewed_at must be ISO-8601") from exc
    if timestamp.tzinfo is None:
        raise GeometryLockedRuntimeError("S3 reviewed_at must include an explicit timezone")
    if permission.get("review_scope") != "diagnostic_candidate_only":
        raise GeometryLockedRuntimeError("S3 permission scope must be diagnostic_candidate_only")
    mismatches = []
    for key, expected_value in expected.items():
        if permission.get(key) != expected_value:
            mismatches.append(key)
    if mismatches:
        raise GeometryLockedRuntimeError("S3 permission receipt SHA/frame binding mismatch: " + ",".join(mismatches))
    required_artifacts = {
        "source", "canvas", "geometry_contract", "approved_mask",
        "protected_mask", "tile_plan", "workflow"
    }
    artifacts = permission.get("reviewed_artifacts")
    if not isinstance(artifacts, list) or not required_artifacts.issubset(set(artifacts)):
        raise GeometryLockedRuntimeError(
            "S3 permission must confirm visual review of source, canvas, S2 contract, both masks, tile plan and workflow"
        )
    return {
        "path": str(permission_path),
        "sha256": sha256_file(permission_path),
        "reviewer_ref": reviewer,
        "reviewed_at": reviewed_at,
        "decision": "APPROVED",
        "evidence_grade": "human_attested_unverified_identity",
        "identity_cryptographically_verified": False,
        "review_scope": "diagnostic_candidate_only",
    }


def _validate_s2_geometry_contract(
    contract: Mapping[str, Any],
    *,
    source_sha256: str,
    canvas_sha256: str,
    source_size: tuple[int, int],
    canvas_size: tuple[int, int],
    contract_path: Path,
    expected_canvas_path: Path,
) -> None:
    """Validate the same S2 fields required by the Agent Driver, bound to these bytes."""
    required = (
        "source_sha256", "canvas_path", "canvas_sha256", "coordinate_frame",
        "geometry_human_verified", "object_transform", "model_scale",
        "tile_size", "tile_context",
    )
    missing = [key for key in required if key not in contract]
    if missing:
        raise GeometryLockedRuntimeError("S2 geometry contract missing: " + ",".join(missing))
    if str(contract.get("source_sha256", "")).lower() != source_sha256.lower():
        raise GeometryLockedRuntimeError("S2 geometry contract source_sha256 does not bind to the frozen source")
    if str(contract.get("canvas_sha256", "")).lower() != canvas_sha256.lower():
        raise GeometryLockedRuntimeError("S2 geometry contract canvas_sha256 does not bind to the frozen canvas")
    contract_canvas_path = contract.get("canvas_path")
    if not isinstance(contract_canvas_path, str) or not contract_canvas_path.strip():
        raise GeometryLockedRuntimeError("S2 geometry contract canvas_path is required")
    declared_canvas_path = Path(contract_canvas_path).expanduser()
    if not declared_canvas_path.is_absolute():
        declared_canvas_path = contract_path.parent / declared_canvas_path
    if declared_canvas_path.resolve() != expected_canvas_path.resolve():
        raise GeometryLockedRuntimeError("S2 geometry contract canvas_path does not resolve to the frozen canvas")
    if contract.get("geometry_human_verified") is not True:
        raise GeometryLockedRuntimeError("S2 geometry_human_verified must be explicitly true")
    if not isinstance(contract.get("coordinate_frame"), str) or not contract["coordinate_frame"].strip():
        raise GeometryLockedRuntimeError("S2 coordinate_frame is required")
    if not isinstance(contract.get("object_transform"), Mapping) or not contract["object_transform"]:
        raise GeometryLockedRuntimeError("S2 object_transform must be a non-empty object")
    scale = contract.get("model_scale")
    if isinstance(scale, bool) or not isinstance(scale, (int, float)) or scale <= 0:
        raise GeometryLockedRuntimeError("S2 model_scale must be positive numeric")
    tile_size = contract.get("tile_size")
    tile_context = contract.get("tile_context")
    if type(tile_size) is not int or tile_size < 32:
        raise GeometryLockedRuntimeError("S2 tile_size must be an integer >= 32")
    if type(tile_context) is not int or tile_context < 0 or tile_context >= tile_size:
        raise GeometryLockedRuntimeError("S2 tile_context must be in [0, tile_size)")
    expected = (source_size[0] * float(scale), source_size[1] * float(scale))
    if expected != (float(canvas_size[0]), float(canvas_size[1])):
        raise GeometryLockedRuntimeError(
            f"S2 model_scale does not map source dimensions {source_size} to canvas {canvas_size}"
        )


def _validate_manifest_files(manifest_path: str | Path) -> tuple[dict[str, Any], dict[str, Any]]:
    path = Path(manifest_path).expanduser().resolve()
    manifest = _load_json(path, "geometry-locked manifest")
    if manifest.get("schema") != MANIFEST_SCHEMA:
        raise GeometryLockedRuntimeError(f"manifest schema must be {MANIFEST_SCHEMA}")
    if manifest.get("diagnostic_only") is not True:
        raise GeometryLockedRuntimeError("Comfy geometry run manifest must be diagnostic_only=true")
    base_dir = path.parent
    records = {}
    for key in ("workflow", "source", "canvas", "geometry_contract"):
        value = manifest.get(key)
        if not isinstance(value, Mapping) or not isinstance(value.get("path"), str):
            raise GeometryLockedRuntimeError(f"manifest.{key}.path is required")
        file_path = _resolve(base_dir, value["path"])
        if not file_path.is_file():
            raise GeometryLockedRuntimeError(f"manifest {key} file not found: {file_path}")
        digest = sha256_file(file_path)
        if digest.lower() != str(value.get("sha256", "")).lower():
            raise GeometryLockedRuntimeError(f"manifest {key} SHA mismatch")
        records[key] = {"path": file_path, "sha256": digest}
    mask_records = manifest.get("masks")
    if not isinstance(mask_records, Mapping):
        raise GeometryLockedRuntimeError("manifest.masks is required")
    for key in ("approved", "protected"):
        value = mask_records.get(key)
        if not isinstance(value, Mapping) or not isinstance(value.get("path"), str):
            raise GeometryLockedRuntimeError(f"manifest.masks.{key}.path is required")
        file_path = _resolve(base_dir, value["path"])
        if not file_path.is_file() or sha256_file(file_path).lower() != str(value.get("sha256", "")).lower():
            raise GeometryLockedRuntimeError(f"manifest {key} mask missing or SHA mismatch")
        records[f"{key}_mask"] = {"path": file_path, "sha256": sha256_file(file_path)}

    try:
        with Image.open(records["canvas"]["path"]) as image:
            canvas_size = image.size
    except Exception as exc:
        raise GeometryLockedRuntimeError(f"cannot decode geometry canvas: {exc}") from exc
    canvas = manifest.get("canvas")
    if not isinstance(canvas, Mapping):
        raise GeometryLockedRuntimeError("manifest.canvas must be an object")
    if canvas.get("width") != canvas_size[0] or canvas.get("height") != canvas_size[1]:
        raise GeometryLockedRuntimeError("canvas width/height do not match the actual image")
    source_size = None
    try:
        with Image.open(records["source"]["path"]) as image:
            source_size = image.size
    except Exception as exc:
        raise GeometryLockedRuntimeError(f"cannot decode S0 source image: {exc}") from exc
    s2_contract = _load_json(records["geometry_contract"]["path"], "S2 geometry contract")
    _validate_s2_geometry_contract(
        s2_contract,
        source_sha256=records["source"]["sha256"],
        canvas_sha256=records["canvas"]["sha256"],
        source_size=source_size,
        canvas_size=canvas_size,
        contract_path=records["geometry_contract"]["path"],
        expected_canvas_path=records["canvas"]["path"],
    )
    from .geometry_locked import _load_binary_mask
    approved_mask = _load_binary_mask(records["approved_mask"]["path"], canvas_size, "approved edit")
    protected_mask = _load_binary_mask(
        records["protected_mask"]["path"], canvas_size, "protected", require_nonempty=False
    )
    import numpy as np
    if np.any((np.asarray(approved_mask) == 255) & (np.asarray(protected_mask) == 255)):
        raise GeometryLockedRuntimeError("approved and protected masks overlap")

    coordinate_frame = canvas.get("coordinate_frame")
    if not isinstance(coordinate_frame, str) or not coordinate_frame.strip():
        raise GeometryLockedRuntimeError("canvas.coordinate_frame is required")

    plan = manifest.get("tile_plan")
    if not isinstance(plan, Mapping):
        raise GeometryLockedRuntimeError("manifest.tile_plan must be an object")
    plan_hash = _canonical_sha(plan)
    if plan_hash.lower() != str(manifest.get("tile_plan_sha256", "")).lower():
        raise GeometryLockedRuntimeError("normalized tile plan SHA mismatch")
    if plan.get("coordinate_frame") != coordinate_frame:
        raise GeometryLockedRuntimeError("tile plan coordinate_frame does not match S2 canvas")
    if s2_contract.get("coordinate_frame") != coordinate_frame:
        raise GeometryLockedRuntimeError("tile plan coordinate_frame does not match the human-verified S2 contract")
    normalized_plan = validate_geometry_tile_plan(
        plan, canvas_size=canvas_size, canvas_sha256=records["canvas"]["sha256"]
    )
    workflow = load_api_workflow(records["workflow"]["path"])
    for tile in normalized_plan["tiles"]:
        node = workflow.get(tile["input_node_id"])
        if not isinstance(node, Mapping) or node.get("class_type") != "LoadImage":
            raise GeometryLockedRuntimeError(
                f"tile {tile['tile_id']} input_node_id {tile['input_node_id']} is not a LoadImage node"
            )
        input_record = tile.get("input")
        if not isinstance(input_record, Mapping) or not isinstance(input_record.get("path"), str):
            raise GeometryLockedRuntimeError(f"tile {tile['tile_id']} generated input record is missing")
        input_path = _resolve(base_dir, input_record["path"])
        if not input_path.is_file() or sha256_file(input_path).lower() != str(input_record.get("sha256", "")).lower():
            raise GeometryLockedRuntimeError(f"tile {tile['tile_id']} input crop missing or SHA mismatch")
        with Image.open(input_path) as image:
            read = tile["read_bounds"]
            if image.size != (read[2] - read[0], read[3] - read[1]):
                raise GeometryLockedRuntimeError(f"tile {tile['tile_id']} input crop size does not match read_bounds")
        tile["input_path_resolved"] = str(input_path)
        tile["input_sha256"] = input_record["sha256"]

    output_dir = _resolve(base_dir, str(manifest.get("output_dir", "")))
    if not isinstance(manifest.get("output_dir"), str) or not manifest["output_dir"].strip():
        raise GeometryLockedRuntimeError("manifest.output_dir is required")
    expected_permission = {
        "source_sha256": records["source"]["sha256"],
        "canvas_sha256": records["canvas"]["sha256"],
        "coordinate_frame": coordinate_frame,
        "approved_mask_sha256": records["approved_mask"]["sha256"],
        "protected_mask_sha256": records["protected_mask"]["sha256"],
        "tile_plan_sha256": plan_hash,
        "workflow_sha256": records["workflow"]["sha256"],
        "geometry_contract_sha256": records["geometry_contract"]["sha256"],
    }
    context = {
        "manifest_path": path,
        "manifest": manifest,
        "workflow": workflow,
        "plan": normalized_plan,
        "records": records,
        "canvas_size": canvas_size,
        "coordinate_frame": coordinate_frame,
        "output_dir": output_dir,
        "expected_permission": expected_permission,
        "s2_geometry": {
            "coordinate_frame": coordinate_frame,
            "canvas_sha256": records["canvas"]["sha256"],
            "geometry_contract_sha256": records["geometry_contract"]["sha256"],
            "model_scale": s2_contract["model_scale"],
            "tile_size": s2_contract["tile_size"],
            "tile_context": s2_contract["tile_context"],
            "object_transform": s2_contract["object_transform"],
        },
    }
    return context, expected_permission


def create_geometry_locked_comfy_manifest(
    *,
    workflow_path: str | Path,
    source_path: str | Path,
    canvas_path: str | Path,
    approved_mask_path: str | Path,
    protected_mask_path: str | Path,
    geometry_contract_path: str | Path,
    tile_plan_path: str | Path,
    manifest_path: str | Path,
    output_dir: str | Path,
    permission_template_path: str | Path | None = None,
    run_id: str | None = None,
    overwrite: bool = False,
) -> dict[str, Any]:
    """Freeze source/canvas/masks/plan and create exact read-crop PNGs for each tile."""
    manifest_target = Path(manifest_path).expanduser().resolve()
    base_dir = manifest_target.parent
    base_dir.mkdir(parents=True, exist_ok=True)
    workflow = Path(workflow_path).expanduser().resolve()
    source = Path(source_path).expanduser().resolve()
    canvas = Path(canvas_path).expanduser().resolve()
    approved = Path(approved_mask_path).expanduser().resolve()
    protected = Path(protected_mask_path).expanduser().resolve()
    geometry_contract_file = Path(geometry_contract_path).expanduser().resolve()
    if not all(x.is_file() for x in (workflow, source, canvas, approved, protected, geometry_contract_file)):
        missing = [str(x) for x in (workflow, source, canvas, approved, protected, geometry_contract_file) if not x.is_file()]
        raise GeometryLockedRuntimeError("required input file(s) missing: " + ", ".join(missing))
    raw_plan = _load_json(Path(tile_plan_path).expanduser().resolve(), "tile plan")
    with Image.open(canvas) as image:
        canvas_size = image.size
    canvas_sha = sha256_file(canvas)
    source_sha = sha256_file(source)
    with Image.open(source) as image:
        source_size = image.size
    s2_contract = _load_json(geometry_contract_file, "S2 geometry contract")
    _validate_s2_geometry_contract(
        s2_contract,
        source_sha256=source_sha,
        canvas_sha256=canvas_sha,
        source_size=source_size,
        canvas_size=canvas_size,
        contract_path=geometry_contract_file,
        expected_canvas_path=canvas,
    )
    normalized_plan = validate_geometry_tile_plan(
        raw_plan, canvas_size=canvas_size, canvas_sha256=canvas_sha
    )
    if normalized_plan["coordinate_frame"] != s2_contract.get("coordinate_frame"):
        raise GeometryLockedRuntimeError("tile plan coordinate_frame does not match the human-verified S2 contract")
    api_workflow = load_api_workflow(workflow)
    for tile in normalized_plan["tiles"]:
        node = api_workflow.get(tile["input_node_id"])
        if not isinstance(node, Mapping) or node.get("class_type") != "LoadImage":
            raise GeometryLockedRuntimeError(
                f"tile {tile['tile_id']} input node {tile['input_node_id']} is not LoadImage"
            )
    # Validate mask dimensions and binary values before any Cloud interaction.
    from .geometry_locked import _load_binary_mask
    _load_binary_mask(approved, canvas_size, "approved edit")
    _load_binary_mask(protected, canvas_size, "protected", require_nonempty=False)

    output_root = Path(output_dir).expanduser()
    output_root = output_root.resolve() if output_root.is_absolute() else (base_dir / output_root).resolve()
    input_root = output_root / "inputs"
    input_root.mkdir(parents=True, exist_ok=True)
    with Image.open(canvas) as opened:
        canvas_image = opened.convert("RGBA" if "A" in opened.getbands() else "RGB")
        for tile in normalized_plan["tiles"]:
            crop_path = input_root / f"{tile['tile_id']}.png"
            if crop_path.exists() and not overwrite:
                raise GeometryLockedRuntimeError(f"refusing to overwrite tile crop: {crop_path}")
            crop = canvas_image.crop(tuple(tile["read_bounds"]))
            crop.save(crop_path, format="PNG")
            tile["input"] = {
                "path": _portable(crop_path.resolve(), base_dir),
                "sha256": sha256_file(crop_path),
            }
    plan_sha = _canonical_sha(normalized_plan)
    manifest = {
        "schema": MANIFEST_SCHEMA,
        "run_id": run_id or f"comfy-shq-{uuid.uuid4().hex[:12]}",
        "workflow": _file_record(workflow, base_dir, "workflow"),
        "source": _file_record(source, base_dir, "source"),
        "geometry_contract": _file_record(geometry_contract_file, base_dir, "S2 geometry contract"),
        "canvas": {
            **_file_record(canvas, base_dir, "canvas"),
            "width": canvas_size[0],
            "height": canvas_size[1],
            "coordinate_frame": normalized_plan["coordinate_frame"],
        },
        "masks": {
            "approved": _file_record(approved, base_dir, "approved mask"),
            "protected": _file_record(protected, base_dir, "protected mask"),
        },
        "tile_plan": normalized_plan,
        "tile_plan_sha256": plan_sha,
        "output_dir": _portable(output_root, base_dir),
        "diagnostic_only": True,
        "execution_allowed": False,
        "candidate_accepted": False,
        "non_claims": [
            "Manifest creation performs no Comfy inference and grants no S3 edit permission.",
            "The human-verified S2 geometry contract must bind source and canvas before tile execution.",
            "Human S3 permission must be reviewed and supplied separately before submit.",
            "Tile crops are deterministic reads from the frozen canvas; output writes are not performed here.",
        ],
    }
    permission_template = {
        "schema": PERMISSION_SCHEMA,
        "decision": "PENDING_REVIEW",
        "reviewer_ref": "",
        "reviewed_at": "",
        "review_scope": "diagnostic_candidate_only",
        "reviewed_artifacts": [],
        **{
            "source_sha256": manifest["source"]["sha256"],
            "canvas_sha256": manifest["canvas"]["sha256"],
            "coordinate_frame": manifest["canvas"]["coordinate_frame"],
            "approved_mask_sha256": manifest["masks"]["approved"]["sha256"],
            "protected_mask_sha256": manifest["masks"]["protected"]["sha256"],
            "tile_plan_sha256": plan_sha,
            "workflow_sha256": manifest["workflow"]["sha256"],
            "geometry_contract_sha256": manifest["geometry_contract"]["sha256"],
        },
        "note": (
            "Inspect the source, output canvas, S2 geometry contract, approved/protected masks, tile plan and workflow manually. "
            "Set decision=APPROVED only after review. This JSON is a human attestation, not a cryptographic identity signature."
        ),
    }
    permission_target = Path(permission_template_path).expanduser().resolve() if permission_template_path else manifest_target.with_name(manifest_target.stem + ".permission-review.json")
    if permission_target.exists() and not overwrite:
        raise GeometryLockedRuntimeError(f"refusing to overwrite permission review template: {permission_target}")
    permission_target.parent.mkdir(parents=True, exist_ok=True)
    permission_target.write_text(json.dumps(permission_template, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    manifest["permission_template_path"] = _portable(permission_target, base_dir)
    if manifest_target.exists() and not overwrite:
        raise GeometryLockedRuntimeError(f"refusing to overwrite manifest: {manifest_target}")
    manifest_target.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return {
        "manifest_path": str(manifest_target),
        "manifest_sha256": sha256_file(manifest_target),
        "permission_template_path": str(permission_target),
        "permission_template_sha256": sha256_file(permission_target),
        "manifest": manifest,
        "status": "PREPARED_AWAITING_HUMAN_S3_REVIEW",
        "execution_allowed": False,
        "edit_permission": False,
    }


def _preflight_context(context: Mapping[str, Any], client: ComfyCloudClient) -> dict[str, Any]:
    live = client.health()
    models = client.model_inventory()
    audit = audit_api_workflow_live(
        context["workflow"],
        object_info=live["object_info"],
        model_inventory=models,
    )
    blockers = list(audit.get("blockers") or [])
    unexpected = [x for x in blockers if x not in ALLOWED_DIAGNOSTIC_BLOCKERS]
    if unexpected:
        raise GeometryLockedRuntimeError(
            "Comfy workflow has structural/model blockers beyond the explicitly diagnostic-only allowances: "
            + ",".join(unexpected)
        )
    plan = context["plan"]
    routes = audit.get("routed_tiles") or []
    by_id: dict[str, dict[str, Any]] = {}
    save_to_tile: dict[str, str] = {}
    for route in routes:
        tile_id = route.get("tile_id")
        if not isinstance(tile_id, str) or tile_id in by_id:
            raise GeometryLockedRuntimeError("Cloud workflow route contains missing or duplicate TILE ids")
        by_id[tile_id] = dict(route)
    expected_by_id = {tile["tile_id"]: tile for tile in plan["tiles"]}
    if set(by_id) != set(expected_by_id):
        raise GeometryLockedRuntimeError(
            f"workflow TILE ids {sorted(by_id)} do not equal tile-plan ids {sorted(expected_by_id)}"
        )
    for tile_id, tile in expected_by_id.items():
        route = by_id[tile_id]
        origin = route.get("origin_xy")
        read = tile["read_bounds"]
        if origin != [read[0], read[1]]:
            raise GeometryLockedRuntimeError(
                f"workflow tile {tile_id} global origin {origin} != read_bounds origin {[read[0], read[1]}"
            )
        if route.get("input_node_id") != tile["input_node_id"]:
            raise GeometryLockedRuntimeError(f"workflow tile {tile_id} input node is not bound to the planned LoadImage")
        save_nodes = route.get("save_node_ids") or []
        if len(save_nodes) != 1 or not isinstance(save_nodes[0], str):
            raise GeometryLockedRuntimeError(f"workflow tile {tile_id} must map to exactly one SaveImage node")
        save_node = save_nodes[0]
        if save_node in save_to_tile:
            raise GeometryLockedRuntimeError(f"SaveImage node {save_node} maps to multiple tiles")
        save_to_tile[save_node] = tile_id
    return {
        "schema": "ige-comfy-shq-geometry-preflight/0.1",
        "status": "READY_FOR_DIAGNOSTIC_ONLY_SUBMIT",
        "cloud": {
            "base_url": client.base_url,
            "status": live.get("status"),
            "node_count": live.get("node_count"),
            "model_folder_count": len(models.get("folders") or []),
        },
        "workflow_audit": audit,
        "tile_routes": [by_id[tile["tile_id"]] for tile in plan["tiles"]],
        "diagnostic_blockers_retained": blockers,
        "structural_blockers": [],
        "human_permission_receipt_required_for_submit": True,
        "execution_allowed": False,
        "candidate_accepted": False,
        "maturity_remains": "workflow_candidate",
        "non_claims": [
            "Preflight is live Cloud control-plane evidence, not GPU inference.",
            "Global coordinate-indexed diffusion noise remains unverified.",
            "Cloud model filename presence does not prove weight SHA or loaded tensor identity.",
            "No final master or S7 acceptance is produced by preflight.",
        ],
        "_save_to_tile": save_to_tile,
    }


def preflight_comfy_geometry_locked(
    manifest_path: str | Path,
    *,
    client: ComfyCloudClient | None = None,
) -> dict[str, Any]:
    context, _ = _validate_manifest_files(manifest_path)
    report = _preflight_context(context, client or ComfyCloudClient())
    report.pop("_save_to_tile", None)
    report["run_id"] = context["manifest"].get("run_id")
    report["manifest_sha256"] = sha256_file(context["manifest_path"])
    return report


def run_comfy_geometry_locked(
    manifest_path: str | Path,
    *,
    permission_path: str | Path,
    diagnostic_submit: bool = False,
    client: ComfyCloudClient | None = None,
    timeout_seconds: float = 1800,
    poll_interval_seconds: float = 2,
    overwrite: bool = False,
) -> dict[str, Any]:
    """Run diagnostic Cloud tile inference, then actual local S6 core-only compose."""
    if diagnostic_submit is not True:
        raise GeometryLockedRuntimeError("Cloud credits are not used unless --diagnostic-submit is explicitly supplied")
    context, expected_permission = _validate_manifest_files(manifest_path)
    permission = _validate_permission_receipt(permission_path, expected=expected_permission)
    client = client or ComfyCloudClient()
    preflight = _preflight_context(context, client)
    save_to_tile = preflight.pop("_save_to_tile")
    output_dir: Path = context["output_dir"]
    output_dir.mkdir(parents=True, exist_ok=True)
    prepared = copy.deepcopy(context["workflow"])
    input_receipts = []
    tile_by_id = {tile["tile_id"]: tile for tile in context["plan"]["tiles"]}
    for tile in context["plan"]["tiles"]:
        tile_path = Path(tile["input_path_resolved"])
        uploaded = client.upload_image(tile_path)
        prepared[tile["input_node_id"]]["inputs"]["image"] = uploaded["name"]
        input_receipts.append({
            "tile_id": tile["tile_id"],
            "node_id": tile["input_node_id"],
            "source_path": str(tile_path),
            "source_sha256": tile["input_sha256"],
            "uploaded_name": uploaded["name"],
            "uploaded_subfolder": uploaded.get("subfolder", ""),
        })

    prompt_id = client.submit_prompt(prepared)
    job = client.wait_for_job(
        prompt_id, timeout_seconds=timeout_seconds, poll_interval_seconds=poll_interval_seconds
    )
    image_records = client.collect_images(job)
    if not image_records:
        raise GeometryLockedRuntimeError(f"Cloud job {prompt_id} completed without image outputs")
    seen_tiles: set[str] = set()
    tile_outputs = []
    cloud_output_receipts = []
    cloud_output_dir = output_dir / "cloud_outputs"
    cloud_output_dir.mkdir(parents=True, exist_ok=True)
    for index, record in enumerate(image_records):
        node_id = record.get("node_id")
        if not isinstance(node_id, str) or node_id not in save_to_tile:
            raise GeometryLockedRuntimeError(
                "Cloud output has no unambiguous SaveImage node identity; refusing tile attribution"
            )
        tile_id = save_to_tile[node_id]
        if tile_id in seen_tiles:
            raise GeometryLockedRuntimeError(f"Cloud returned more than one image for tile {tile_id}")
        seen_tiles.add(tile_id)
        tile = tile_by_id[tile_id]
        safe_tile = re.sub(r"[^A-Za-z0-9_.-]+", "_", tile_id)
        destination = cloud_output_dir / f"{prompt_id}_{safe_tile}_{index:02d}.download"
        downloaded = client.download_output(record, destination)
        extension = {"PNG": ".png", "JPEG": ".jpg", "WEBP": ".webp"}.get(
            str(downloaded.get("image_format", "")).upper()
        )
        if extension is None:
            raise GeometryLockedRuntimeError(
                f"Cloud output for tile {tile_id} has unsupported format {downloaded.get('image_format')!r}"
            )
        final_output_path = destination.with_suffix(extension)
        if final_output_path.exists():
            raise GeometryLockedRuntimeError(f"refusing to overwrite Cloud tile output: {final_output_path}")
        destination.replace(final_output_path)
        downloaded["path"] = str(final_output_path.resolve())
        expected_size = (
            tile["read_bounds"][2] - tile["read_bounds"][0],
            tile["read_bounds"][3] - tile["read_bounds"][1],
        )
        actual_size = (downloaded.get("width"), downloaded.get("height"))
        if actual_size != expected_size:
            raise GeometryLockedRuntimeError(
                f"Cloud output for tile {tile_id} has size {actual_size}; expected {expected_size}; no implicit resize allowed"
            )
        downloaded.update({
            "tile_id": tile_id,
            "output_node_id": node_id,
            "read_bounds": tile["read_bounds"],
            "core_bounds": tile["core_bounds"],
            "tile_mapping_status": "BOUND_BY_SAVEIMAGE_NODE_AND_TILE_ID",
        })
        tile_outputs.append({
            "tile_id": tile_id,
            "path": downloaded["path"],
            "sha256": downloaded["sha256"],
        })
        cloud_output_receipts.append(downloaded)
    if seen_tiles != set(tile_by_id):
        raise GeometryLockedRuntimeError(
            f"Cloud output set incomplete; missing tiles={sorted(set(tile_by_id) - seen_tiles)}"
        )

    manifest = context["manifest"]
    records = context["records"]
    master_path = output_dir / f"{prompt_id}_geometry_locked_master.png"
    s6 = compose_core_only_master(
        base_canvas_path=records["canvas"]["path"],
        approved_mask_path=records["approved_mask"]["path"],
        protected_mask_path=records["protected_mask"]["path"],
        tile_plan=context["plan"],
        tile_outputs=tile_outputs,
        canvas_sha256=records["canvas"]["sha256"],
        output_path=master_path,
        overwrite=overwrite,
    )
    workflow_audit = preflight["workflow_audit"]
    receipt = {
        "schema": "ige-comfy-shq-geometry-locked-run-receipt/0.1",
        "run_id": manifest["run_id"],
        "prompt_id": prompt_id,
        "execution_kind": "comfy_cloud_job_plus_local_s6_compositor",
        "cloud_transport": f"{type(client).__module__}.{type(client).__qualname__}",
        "job_status": job.get("status") or job.get("state"),
        "workflow_sha256": records["workflow"]["sha256"],
        "source_sha256": records["source"]["sha256"],
        "canvas_sha256": records["canvas"]["sha256"],
        "geometry_contract_sha256": records["geometry_contract"]["sha256"],
        "coordinate_frame": context["coordinate_frame"],
        "permission": permission,
        "input_receipts": input_receipts,
        "cloud_output_receipts": cloud_output_receipts,
        "workflow_audit": workflow_audit,
        "s6_local_compositor": s6,
        "global_coordinate_noise_verified": False,
        "cloud_weight_sha_verified": False,
        "s7_status": "NOT_PERFORMED",
        "candidate_accepted": False,
        "execution_allowed": False,
        "edit_permission": False,
        "maturity_remains": "workflow_candidate",
        "production_blockers": [
            "E_NOISE_FIELD_NOT_GLOBAL: coordinate-indexed global diffusion noise and overlap equality are not verified",
            "E_CLOUD_MODEL_SHA_UNVERIFIED: Cloud catalogue does not prove weight SHA or loaded tensor identity",
            "E_S7_HUMAN_REVIEW_REQUIRED: independent reload and visual acceptance have not been performed",
        ],
        "non_claims": [
            "This receipt proves one real Comfy Cloud diagnostic job and downloaded tile image bytes only.",
            "S6 proves the local compositor pasted each disjoint core only through the approved binary mask.",
            "It does not prove that independently generated tiles share the same global diffusion noise field.",
            "Human permission is an attestation record; reviewer identity is not cryptographically verified.",
            "The result is a candidate master, not a production-accepted image or Registry maturity promotion.",
        ],
    }
    receipt_path = output_dir / f"{prompt_id}.comfy_geometry_receipt.json"
    if receipt_path.exists() and not overwrite:
        raise GeometryLockedRuntimeError(f"refusing to overwrite receipt: {receipt_path}")
    receipt["receipt_path"] = str(receipt_path.resolve())
    receipt_path.write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    receipt["receipt_sha256"] = sha256_file(receipt_path)
    return receipt
