from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image

from .relations import RELATION_PREDICATES


class GeometryContractError(ValueError):
    """A generation packet would violate READ permissions or geometry evidence rules."""


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _safe_run_path(run_dir: Path, relative_path: str) -> Path:
    candidate = (run_dir / relative_path).resolve()
    root = run_dir.resolve()
    if not candidate.is_relative_to(root):
        raise GeometryContractError(f"READ manifest path escapes the run directory: {relative_path}")
    if not candidate.is_file():
        raise GeometryContractError(f"required READ artifact is missing: {relative_path}")
    return candidate


def compile_generation_packet(
    analysis_path: str | Path,
    output_dir: str | Path,
    *,
    objective: str,
    target_region_ids: list[str],
    base_image_path: str | Path | None = None,
    overwrite: bool = False,
) -> dict[str, Any]:
    """Compile a generation request from one READ run without granting extra pixels.

    Only explicitly human-marked editable regions can be targets. The task mask
    is the union of selected per-region masks, not the global READ editable mask.
    Every other BASE pixel is protected. Only human-verified relations enter locks.
    """
    source_analysis = Path(analysis_path)
    if not source_analysis.is_file():
        raise FileNotFoundError(source_analysis)
    run_dir = source_analysis.parent.resolve()
    destination = Path(output_dir)
    if destination.exists() and not destination.is_dir():
        raise NotADirectoryError(destination)
    if destination.exists() and any(destination.iterdir()) and not overwrite:
        raise FileExistsError(f"output directory is not empty: {destination}")

    analysis = json.loads(source_analysis.read_text(encoding="utf-8"))
    source = analysis.get("source", {})
    source_sha = source.get("sha256")
    width, height = source.get("width"), source.get("height")
    if not isinstance(source_sha, str) or len(source_sha) != 64:
        raise GeometryContractError("READ analysis has no valid source SHA-256")
    if not isinstance(width, int) or not isinstance(height, int) or width <= 0 or height <= 0:
        raise GeometryContractError("READ analysis has invalid source dimensions")
    if not isinstance(objective, str) or not objective.strip():
        raise GeometryContractError("objective must be non-empty")

    # Refuse stale analysis or an image that is no longer the exact READ parent.
    base_path_value = base_image_path or source.get("path")
    if not isinstance(base_path_value, str) or not base_path_value.strip():
        raise GeometryContractError("READ analysis does not record the parent image path")
    base_path = Path(base_path_value)
    if not base_path.is_file():
        raise GeometryContractError(
            f"the original BASE image is unavailable: {base_path}; provide --base with the exact parent image"
        )
    actual_base_sha = _sha256(base_path)
    if actual_base_sha != source_sha:
        raise GeometryContractError(
            "BASE SHA-256 does not match READ analysis; refusing to compile a task from a different image"
        )

    raw_targets = list(target_region_ids)
    if any(not isinstance(item, str) or not item.strip() for item in raw_targets):
        raise GeometryContractError("target_region_ids cannot contain blank entries")
    requested = list(dict.fromkeys(item.strip() for item in raw_targets))
    if not requested:
        raise GeometryContractError("at least one target_region_id is required")
    if len(requested) != len(raw_targets):
        raise GeometryContractError("target_region_ids cannot contain duplicates")

    region_rows = analysis.get("regions", [])
    if not isinstance(region_rows, list):
        raise GeometryContractError("READ analysis regions must be an array")
    regions: dict[str, dict[str, Any]] = {}
    for region in region_rows:
        if not isinstance(region, dict) or not isinstance(region.get("id"), str):
            raise GeometryContractError("READ analysis contains an invalid region record")
        if region["id"] in regions:
            raise GeometryContractError(f"duplicate region id in READ analysis: {region['id']}")
        regions[region["id"]] = region
    missing = sorted(set(requested) - set(regions))
    if missing:
        raise GeometryContractError(f"unknown target region IDs: {missing}")
    protected_targets = sorted(
        region_id for region_id in requested
        if regions[region_id].get("permission") != "editable"
    )
    if protected_targets:
        raise GeometryContractError(f"target regions are not human-approved editable: {protected_targets}")

    mask_rows = analysis.get("region_masks", [])
    if not isinstance(mask_rows, list):
        raise GeometryContractError("READ analysis region_masks must be an array")
    mask_by_id: dict[str, dict[str, Any]] = {}
    for row in mask_rows:
        if not isinstance(row, dict) or not isinstance(row.get("id"), str):
            raise GeometryContractError("READ analysis contains an invalid region-mask record")
        mask_by_id[row["id"]] = row

    generation_mask = np.zeros((height, width), dtype=np.uint8)
    target_mask_evidence: list[dict[str, Any]] = []
    for region_id in requested:
        mask_row = mask_by_id.get(region_id)
        if mask_row is None:
            raise GeometryContractError(f"READ analysis has no per-region mask for {region_id}")
        mask_rel = mask_row.get("mask")
        expected_mask_sha = mask_row.get("sha256")
        if not isinstance(mask_rel, str) or not isinstance(expected_mask_sha, str):
            raise GeometryContractError(
                f"READ analysis lacks a relative mask path or integrity hash for {region_id}"
            )
        mask_path = _safe_run_path(run_dir, mask_rel)
        actual_mask_sha = _sha256(mask_path)
        if actual_mask_sha != expected_mask_sha:
            raise GeometryContractError(f"region mask integrity check failed for {region_id}")
        with Image.open(mask_path) as opened:
            mask_image = opened.convert("L")
            if mask_image.size != (width, height):
                raise GeometryContractError(
                    f"region mask {region_id} size {mask_image.size} does not match BASE {(width, height)}"
                )
            mask = np.asarray(mask_image, dtype=np.uint8)
        if not np.any(mask):
            raise GeometryContractError(f"target region {region_id} has an empty mask")
        generation_mask = np.maximum(generation_mask, np.where(mask > 0, 255, 0).astype(np.uint8))
        target_mask_evidence.append({
            "region_id": region_id,
            "mask_source": mask_rel,
            "mask_sha256": actual_mask_sha,
        })

    editable_pixels = int(np.count_nonzero(generation_mask))
    if editable_pixels == 0:
        raise GeometryContractError("target union mask is empty")
    protected_mask = np.where(generation_mask > 0, 0, 255).astype(np.uint8)

    scene_graph = analysis.get("scene_graph", {})
    relations = scene_graph.get("relations", []) if isinstance(scene_graph, dict) else []
    if not isinstance(relations, list):
        raise GeometryContractError("READ scene_graph.relations must be an array")
    verified_relations: list[dict[str, Any]] = []
    candidate_relations: list[dict[str, Any]] = []
    part_of_graph: dict[str, set[str]] = {}
    for relation in relations:
        if not isinstance(relation, dict):
            raise GeometryContractError("READ relation entries must be objects")
        status = relation.get("status")
        if status == "candidate":
            candidate_relations.append(relation)
            continue
        if status == "rejected":
            continue
        if status != "human_verified":
            raise GeometryContractError("relation has an unknown verification status")
        if relation.get("source") != "human":
            raise GeometryContractError(
                "a model-originated relation cannot enter human-verified geometry locks"
            )
        subject = relation.get("subject_region_id")
        object_id = relation.get("object_region_id")
        predicate = relation.get("predicate")
        if subject not in regions or object_id not in regions or subject == object_id:
            raise GeometryContractError("human-verified relation has invalid region endpoints")
        if predicate not in RELATION_PREDICATES:
            raise GeometryContractError("human-verified relation has an unsupported predicate")
        if not str(relation.get("evidence", "")).strip():
            raise GeometryContractError("human-verified relation has no evidence")
        confidence = relation.get("confidence")
        if confidence is not None and (
            isinstance(confidence, bool) or not isinstance(confidence, (int, float))
            or not 0.0 <= float(confidence) <= 1.0
        ):
            raise GeometryContractError("human-verified relation confidence is invalid")
        evidence_region = relation.get("evidence_region_id")
        if evidence_region is not None and evidence_region not in regions:
            raise GeometryContractError("human-verified relation has an unknown evidence region")
        if predicate == "contacts_at":
            details = relation.get("details", {})
            if not isinstance(details, dict) or not str(details.get("subject_surface", "")).strip() or not str(details.get("object_surface", "")).strip():
                raise GeometryContractError("human-verified contacts_at relation must name both surfaces")
        if predicate == "part_of":
            part_of_graph.setdefault(subject, set()).add(object_id)
        verified_relations.append(relation)

    # Re-check hierarchy integrity even if analysis.json was edited after READ.
    visiting: set[str] = set()
    visited: set[str] = set()

    def visit_part(node: str) -> None:
        if node in visiting:
            raise GeometryContractError("human-verified part_of relations contain a cycle")
        if node in visited:
            return
        visiting.add(node)
        for parent in part_of_graph.get(node, ()):
            visit_part(parent)
        visiting.remove(node)
        visited.add(node)

    for node in part_of_graph:
        visit_part(node)

    destination.mkdir(parents=True, exist_ok=True)
    generation_path = destination / "generation_mask.png"
    protected_path = destination / "protected_mask.png"
    Image.fromarray(generation_mask, mode="L").save(generation_path)
    Image.fromarray(protected_mask, mode="L").save(protected_path)

    packet: dict[str, Any] = {
        "packet_version": "0.1.0",
        "task_id": destination.name,
        "objective": objective.strip(),
        "base": {
            "sha256": source_sha,
            "width": width,
            "height": height,
            "orientation": source.get("orientation"),
        },
        "targets": [
            {
                "region_id": region_id,
                "label": regions[region_id].get("label"),
                "semantic_type": regions[region_id].get("semantic_type"),
                "permission": "editable",
            }
            for region_id in requested
        ],
        "pixel_authorization": {
            "source": "human_region_annotation",
            "generation_mask": generation_path.name,
            "generation_mask_sha256": _sha256(generation_path),
            "protected_mask": protected_path.name,
            "protected_mask_sha256": _sha256(protected_path),
            "generation_pixels": editable_pixels,
            "protected_pixels": (width * height) - editable_pixels,
            "rule": "Only the union of selected human-approved editable region masks may change.",
            "target_mask_inputs": target_mask_evidence,
        },
        "geometry_locks": {
            "coordinate_space": "source_display_pixels",
            "dimensionality": "2d_image_plane_assertions_only",
            "relations": verified_relations,
            "protected_region_ids": sorted(
                region_id for region_id, region in regions.items()
                if region.get("permission") == "protected"
                or "identity_anchor" in region.get("tags", [])
            ),
            "candidate_relations_excluded": [relation.get("id") for relation in candidate_relations],
            "limitation": (
                "These are human-verified image-plane assertions, not metric 3D geometry. "
                "No hidden surface, physical force, or camera calibration is implied."
            ),
        },
        "acceptance_requirements": [
            "parent_source_sha256_matches",
            "no_pixel_writes_outside_generation_mask",
            "protected_mask_unchanged",
            "all_human_verified_relations_preserved",
            "candidate_relations_not_promoted_automatically",
            "identity_and_pose_gates_pass",
            "topology_gate_passes",
            "registration_gate_passes",
        ],
        "provenance": {
            "read_analysis_path": str(source_analysis.resolve()),
            "read_analysis_sha256": _sha256(source_analysis),
            "read_version": analysis.get("read_version"),
            "model_proposals_grant_no_permission": True,
        },
    }
    (destination / "generation_packet.json").write_text(
        json.dumps(packet, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return packet
