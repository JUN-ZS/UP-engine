from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
NODE_PACKAGE = ROOT / "docs" / "handoff" / "comfy-siax-return" / "packages" / "ComfyUI_IGE_GlobalLogicCoordinator"
if str(NODE_PACKAGE) not in sys.path:
    sys.path.insert(0, str(NODE_PACKAGE))

from ige_logic.core import ContractError, compile_contract, load_json  # noqa: E402


def _links(workflow: dict[str, Any]) -> dict[int, list[Any]]:
    return {int(link[0]): link for link in workflow.get("links", [])}


def _nodes(workflow: dict[str, Any]) -> dict[int, dict[str, Any]]:
    return {int(node["id"]): node for node in workflow.get("nodes", [])}


def _source_node(node: dict[str, Any], input_name: str, links: dict[int, list[Any]]) -> int | None:
    slots = [slot for slot in node.get("inputs", []) if slot.get("name") == input_name]
    if len(slots) != 1 or slots[0].get("link") is None:
        return None
    link = links.get(int(slots[0]["link"]))
    return int(link[1]) if link else None


def _output_targets(node: dict[str, Any], output_name: str, links: dict[int, list[Any]]) -> list[int]:
    slots = [slot for slot in node.get("outputs", []) if slot.get("name") == output_name]
    if len(slots) != 1:
        raise ValueError(f"Node {node.get('id')} must have exactly one output named {output_name}")
    targets = []
    for link_id in slots[0].get("links") or []:
        link = links.get(int(link_id))
        if link is None:
            raise ValueError(f"Node {node.get('id')} output references missing link {link_id}")
        targets.append(int(link[3]))
    return targets


def _ancestors(start_id: int, nodes: dict[int, dict[str, Any]], links: dict[int, list[Any]]) -> set[int]:
    seen: set[int] = set()
    todo = [int(start_id)]
    while todo:
        current = todo.pop()
        if current in seen or current not in nodes:
            continue
        seen.add(current)
        for slot in nodes[current].get("inputs", []):
            link_id = slot.get("link")
            if link_id is not None and int(link_id) in links:
                todo.append(int(links[int(link_id)][1]))
    return seen


def _pixel_sha(rgb: np.ndarray) -> str:
    quantized = np.round(np.clip(rgb.astype(np.float32) / 255.0, 0.0, 1.0) * 255.0).astype(np.uint8)
    return hashlib.sha256(np.ascontiguousarray(quantized).tobytes()).hexdigest()


def inspect_stage2_preflight(
    workflow_path: str | Path,
    source_image_path: str | Path,
    geometry_path: str | Path,
    policy_path: str | Path,
) -> dict[str, Any]:
    workflow_path = Path(workflow_path).expanduser().resolve()
    source_image_path = Path(source_image_path).expanduser().resolve()
    geometry_path = Path(geometry_path).expanduser().resolve()
    policy_path = Path(policy_path).expanduser().resolve()

    for label, path in (
        ("workflow", workflow_path),
        ("stage1 source image", source_image_path),
        ("geometry", geometry_path),
        ("policy", policy_path),
    ):
        if not path.is_file():
            raise FileNotFoundError(f"{label} file not found: {path}")

    workflow = json.loads(workflow_path.read_text(encoding="utf-8"))
    geometry = load_json(geometry_path)
    policy = load_json(policy_path)
    nodes, links = _nodes(workflow), _links(workflow)

    if workflow.get("extra", {}).get("ige_siax_staging", {}).get("stage") != "STAGE_2_IGE_FLUX_CANDIDATE":
        raise ValueError("Workflow is not marked as an IGE Stage 2 candidate")
    canvas_node = nodes.get(34)
    if not canvas_node or canvas_node.get("type") != "LoadImage":
        raise ValueError("Stage 2 Node 34 must be the LoadImage for the Stage 1 canvas")
    selected_name = str((canvas_node.get("widgets_values") or [""])[0]).replace("\\", "/").split("/")[-1]
    if selected_name != source_image_path.name:
        raise ValueError(
            f"Node 34 selects {selected_name!r}, but preflight image is {source_image_path.name!r}"
        )

    compiler = nodes.get(300)
    ttp = nodes.get(36)
    if not compiler or compiler.get("type") != "IGE_GlobalLogicCompiler":
        raise ValueError("Stage 2 Node 300 IGE_GlobalLogicCompiler is missing")
    if not ttp or ttp.get("type") != "TTP_Image_Tile_Batch":
        raise ValueError("Stage 2 Node 36 TTP_Image_Tile_Batch is missing")
    compiler_source = _source_node(compiler, "source_image", links)
    ttp_source = _source_node(ttp, "image", links)
    if compiler_source != 34:
        raise ValueError(f"Node 300 source_image is not bound directly to Stage 2 canvas Node 34: {compiler_source}")
    if ttp_source is None or 34 not in _ancestors(ttp_source, nodes, links):
        raise ValueError("TTP Node 36 does not descend from the same Stage 2 canvas Node 34")

    sampler_reports = []
    for sampler in [n for n in nodes.values() if n.get("type") == "SamplerCustomAdvanced"]:
        sampler_id = int(sampler["id"])
        latent_source = _source_node(sampler, "latent_image", links)
        gate = nodes.get(latent_source) if latent_source is not None else None
        if not gate or gate.get("type") != "IGE_ExecutionAuthorizationGate":
            raise ValueError(f"Sampler {sampler_id} latent path is not directly behind IGE execution gate")
        gate_contract = _source_node(gate, "global_contract", links)
        if gate_contract != 300:
            raise ValueError(f"Sampler {sampler_id} execution gate is not bound to Node 300 contract")
        widget_values = gate.get("widgets_values") or []
        authorization_default = widget_values[0] if widget_values else None
        if authorization_default != "{}":
            raise ValueError(f"Sampler {sampler_id} authorization default must remain empty BLOCK")

        barrier_targets = _output_targets(sampler, "output", links)
        barriers = [nodes[node_id] for node_id in barrier_targets if node_id in nodes and nodes[node_id].get("type") == "IGE_LatentMemoryBarrier"]
        if len(barriers) != 1:
            raise ValueError(f"Sampler {sampler_id} must feed exactly one IGE_LatentMemoryBarrier")
        barrier = barriers[0]
        if _source_node(barrier, "latent", links) != sampler_id:
            raise ValueError(f"Memory barrier {barrier['id']} is not bound to sampler {sampler_id}")
        barrier_values = barrier.get("widgets_values") or []
        if barrier_values[:3] != [True, True, True]:
            raise ValueError(f"Memory barrier {barrier['id']} must release models, clear CUDA cache and synchronize")
        barrier_decoder_targets = _output_targets(barrier, "LATENT", links)
        decoders = [nodes[node_id] for node_id in barrier_decoder_targets if node_id in nodes and nodes[node_id].get("type") == "VAEDecodeTiled"]
        if len(decoders) != 1:
            raise ValueError(f"Memory barrier {barrier['id']} must feed exactly one VAEDecodeTiled")
        sampler_reports.append({
            "sampler_node_id": sampler_id,
            "gate_node_id": int(gate["id"]),
            "branch_id": widget_values[1] if len(widget_values) > 1 else None,
            "authorization_default": authorization_default,
            "memory_barrier_node_id": int(barrier["id"]),
            "vae_decode_node_id": int(decoders[0]["id"]),
            "release_models_before_vae_decode": True,
            "status": "BLOCKED_PENDING_EXPLICIT_AUTHORIZATION",
        })

    with Image.open(source_image_path) as image:
        rgb_image = image.convert("RGB")
        width, height = rgb_image.size
        rgb = np.asarray(rgb_image, dtype=np.uint8)
    file_sha = hashlib.sha256(source_image_path.read_bytes()).hexdigest()
    pixel_sha = _pixel_sha(rgb)
    expected_width = geometry.get("source", {}).get("width")
    expected_height = geometry.get("source", {}).get("height")
    dimensions_match = (expected_width, expected_height) == (width, height)

    report: dict[str, Any] = {
        "schema_version": "ige-comfy-siax-stage2-preflight/0.1",
        "status": "BLOCKED_CANVAS_DIMENSION_MISMATCH",
        "workflow_path": str(workflow_path),
        "workflow_sha256": hashlib.sha256(workflow_path.read_bytes()).hexdigest(),
        "source_image_path": str(source_image_path),
        "source_image_sha256": file_sha,
        "source_pixel_sha256_for_ige_compiler": pixel_sha,
        "source_dimensions": {"width": width, "height": height},
        "geometry_reference": {
            "filename": geometry.get("source", {}).get("filename"),
            "sha256": geometry.get("source", {}).get("sha256"),
            "dimensions": {"width": expected_width, "height": expected_height},
            "geometry_status": geometry.get("geometry_status"),
            "operator_confirmation": geometry.get("provenance", {}).get("operator_confirmation"),
        },
        "geometry_dimensions_match": dimensions_match,
        "geometry_reference_sha_matches_stage1_output": (
            str(geometry.get("source", {}).get("sha256", "")).lower() == file_sha.lower()
        ),
        "policy_source_alignment_status": policy.get("source_alignment_status"),
        "compiler_and_ttp_same_canvas_node": True,
        "samplers": sampler_reports,
        "execution_allowed": False,
        "queue_submission": False,
    }
    if dimensions_match:
        try:
            compiled = compile_contract((height, width), geometry, policy, pixel_sha, None)
            report["compiler_contract_status"] = "COMPILE_CONTRACT_PASS"
            report["contract_id"] = compiled["contract"]["contract_id"]
        except ContractError as exc:
            report["compiler_contract_status"] = "BLOCKED"
            report["compiler_error"] = str(exc)
        geometry_confirmed = geometry.get("geometry_status") == "operator_confirmed"
        operator_confirmed = geometry.get("provenance", {}).get("operator_confirmation") in (
            True, "operator_confirmed", "confirmed", "ACCEPTED"
        )
        alignment_confirmed = policy.get("source_alignment_status") == "operator_confirmed"
        pixel_reference_match = report["geometry_reference_sha_matches_stage1_output"]
        if (
            report["compiler_contract_status"] == "COMPILE_CONTRACT_PASS"
            and geometry_confirmed and operator_confirmed
            and alignment_confirmed and pixel_reference_match
        ):
            report["status"] = "DIMENSIONS_AND_REFERENCE_BIND_PASS_PENDING_SEPARATE_EXECUTION_AUTHORIZATION"
        else:
            report["status"] = "BLOCKED_PENDING_HUMAN_GEOMETRY_AND_SOURCE_REGISTRATION"
        report["acceptance_gates"] = {
            "geometry_status_operator_confirmed": geometry_confirmed,
            "operator_confirmation": operator_confirmed,
            "policy_source_alignment_operator_confirmed": alignment_confirmed,
            "stage1_pixels_match_geometry_reference_sha": pixel_reference_match,
        }
    else:
        report["compiler_contract_status"] = "NOT_RUN_DIMENSION_MISMATCH"
        report["dimension_ratio_geometry_over_source"] = {
            "sx": (float(expected_width) / width) if width else None,
            "sy": (float(expected_height) / height) if height else None,
        }
        report["explicit_transform_required"] = True

    report["non_claims"] = [
        "This tool is CPU-only and never queues a ComfyUI prompt.",
        "Dimension equality is not proof that provisional polygons/landmarks are registered to the actual Siax pixels.",
        "A matching geometry reference SHA is stronger evidence but does not replace human geometry review.",
        "This preflight never sets execution_allowed=true.",
    ]
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description="CPU-only geometry preflight for the staged Siax → IGE workflow.")
    parser.add_argument("--workflow", required=True, help="Stage 2 UI workflow after selecting the Stage 1 image in Node 34")
    parser.add_argument("--source-image", required=True, help="Exact Stage 1 PNG copied to ComfyUI/input and selected in Node 34")
    parser.add_argument("--geometry", required=True)
    parser.add_argument("--policy", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    report = inspect_stage2_preflight(args.workflow, args.source_image, args.geometry, args.policy)
    target = Path(args.output)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    # Only a dimension + registration ready result returns 0. It still does not authorize execution.
    return 0 if report["status"] == "DIMENSIONS_AND_REFERENCE_BIND_PASS_PENDING_SEPARATE_EXECUTION_AUTHORIZATION" else 2


if __name__ == "__main__":
    raise SystemExit(main())
