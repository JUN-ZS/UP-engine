from __future__ import annotations

import copy
import hashlib
import json
import re
import os
import uuid
from pathlib import Path
from typing import Any, Mapping, Sequence

from .cloud_client import ComfyCloudClient, ComfyCloudError


RUNTIME_AUDIT_SCHEMA = "ige-comfy-live-runtime-audit/0.1"
RUN_RECEIPT_SCHEMA = "ige-comfy-cloud-run-receipt/0.1"

REQUIRED_CLASSES = {
    "UNETLoader", "VAELoader", "DualCLIPLoader", "RandomNoise",
    "SamplerCustomAdvanced", "BasicGuider", "FluxGuidance",
    "CLIPTextEncode", "VAEEncode", "VAEDecodeTiled",
    "LoadImage", "SaveImage",
}
MODEL_INPUTS = {
    "UNETLoader": ("unet_name", "diffusion_models"),
    "VAELoader": ("vae_name", "vae"),
    "DualCLIPLoader": ("clip_name1", "clip"),
}
EXPECTED_MODELS = {
    "unet_name": "flux1-dev.safetensors",
    "vae_name": "ae.safetensors",
    "clip_name1": "t5xxl_fp16.safetensors",
    "clip_name2": "clip_l.safetensors",
}
FAIL_NOISE = "E_NOISE_FIELD_NOT_GLOBAL"
FAIL_TILE_RETURN = "E_TILE_COMPOSITOR_MISSING"
FAIL_MODEL_SHA = "E_CLOUD_MODEL_SHA_UNVERIFIED"
FAIL_NODE_CLASS = "E_COMFY_LIVE_NODE_MISSING"
FAIL_CONDITIONING = "E_TILE_CONDITIONING_UNROUTED"


class ComfyWorkflowError(ValueError):
    pass


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_file(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_api_workflow(path: str | Path) -> dict[str, Any]:
    try:
        value = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ComfyWorkflowError(f"cannot read API workflow {path}: {exc}") from exc
    if not isinstance(value, dict) or not value:
        raise ComfyWorkflowError("API workflow must be a non-empty node map")
    for node_id, node in value.items():
        if not isinstance(node, dict) or not isinstance(node.get("class_type"), str):
            raise ComfyWorkflowError(f"invalid API node {node_id!r}")
        if not isinstance(node.get("inputs"), dict):
            raise ComfyWorkflowError(f"API node {node_id!r} inputs must be an object")
    return value


def _node(workflow: Mapping[str, Any], node_id: Any) -> Mapping[str, Any] | None:
    if not isinstance(node_id, str):
        return None
    value = workflow.get(node_id)
    return value if isinstance(value, Mapping) else None


def _link(value: Any, workflow: Mapping[str, Any]) -> tuple[str, int] | None:
    if (
        isinstance(value, (list, tuple))
        and len(value) == 2
        and isinstance(value[0], str)
        and type(value[1]) is int
        and value[0] in workflow
    ):
        return value[0], value[1]
    return None


def _input_link(node: Mapping[str, Any], key: str, workflow: Mapping[str, Any]) -> tuple[str, int] | None:
    inputs = node.get("inputs")
    return _link(inputs.get(key), workflow) if isinstance(inputs, Mapping) else None


def _resolve_all_links(
    workflow: Mapping[str, Any],
    object_info: Mapping[str, Any],
) -> list[dict[str, Any]]:
    """Validate node references and output slot bounds against Cloud object_info."""
    errors: list[dict[str, Any]] = []
    for node_id, node in workflow.items():
        inputs = node.get("inputs", {})
        if not isinstance(inputs, Mapping):
            errors.append({"node_id": node_id, "error": "inputs_not_object"})
            continue
        for input_name, value in inputs.items():
            # A Comfy link is precisely [node_id: str, output_slot: int].
            if not (isinstance(value, (list, tuple)) and len(value) == 2 and isinstance(value[0], str)):
                continue
            source_id, slot = value
            if type(slot) is not int or slot < 0:
                errors.append({
                    "node_id": node_id, "input": input_name,
                    "error": "invalid_output_slot", "target_node": source_id, "slot": slot,
                })
                continue
            source_node = workflow.get(source_id)
            if not isinstance(source_node, Mapping):
                errors.append({
                    "node_id": node_id, "input": input_name,
                    "error": "dangling_node_reference", "target_node": source_id,
                })
                continue
            source_class = source_node.get("class_type")
            source_info = object_info.get(source_class) if isinstance(source_class, str) else None
            output_types = source_info.get("output") if isinstance(source_info, Mapping) else None
            if not isinstance(output_types, list):
                errors.append({
                    "node_id": node_id, "input": input_name,
                    "error": "source_output_schema_missing", "target_node": source_id,
                    "source_class": source_class,
                })
            elif slot >= len(output_types):
                errors.append({
                    "node_id": node_id, "input": input_name,
                    "error": "output_slot_out_of_range", "target_node": source_id,
                    "source_class": source_class, "slot": slot,
                    "output_count": len(output_types),
                })
                continue
            target_class = node.get("class_type")
            target_info = object_info.get(target_class) if isinstance(target_class, str) else None
            target_inputs = target_info.get("input") if isinstance(target_info, Mapping) else None
            input_spec = None
            if isinstance(target_inputs, Mapping):
                for group_name in ("required", "optional", "hidden"):
                    group = target_inputs.get(group_name)
                    if isinstance(group, Mapping) and input_name in group:
                        input_spec = group[input_name]
                        break
            source_type = output_types[slot] if isinstance(output_types, list) and slot < len(output_types) else None
            expected_type = input_spec[0] if isinstance(input_spec, (list, tuple)) and input_spec else None
            if isinstance(source_type, str) and isinstance(expected_type, str) and source_type != expected_type:
                errors.append({
                    "node_id": node_id, "input": input_name,
                    "error": "link_type_mismatch", "target_node": source_id,
                    "source_type": source_type, "expected_type": expected_type,
                })
    return errors


def _tile_prompt_metadata(text: Any) -> dict[str, Any]:
    if not isinstance(text, str):
        return {"valid": False, "tile_id": None, "origin_xy": None}
    tile_match = re.search(r"\bTILE:\s*([A-Za-z0-9_-]+)", text, re.IGNORECASE)
    origin_match = re.search(
        r"GLOBAL TILE ORIGIN:\s*\[\s*(-?\d+)\s*,\s*(-?\d+)\s*\]",
        text,
        re.IGNORECASE,
    )
    return {
        "valid": bool(tile_match and origin_match),
        "tile_id": tile_match.group(1) if tile_match else None,
        "origin_xy": [int(origin_match.group(1)), int(origin_match.group(2))] if origin_match else None,
    }


def _model_names(inventory: Mapping[str, Any]) -> set[str]:
    result: set[str] = set()
    folders = inventory.get("models_by_folder")
    if not isinstance(folders, Mapping):
        return result
    for entries in folders.values():
        if not isinstance(entries, list):
            continue
        for entry in entries:
            if isinstance(entry, str):
                name = entry
            elif isinstance(entry, Mapping):
                name = entry.get("name") or entry.get("filename") or entry.get("model_name") or entry.get("path")
            else:
                continue
            if isinstance(name, str) and name:
                result.add(Path(name.replace("\\", "/")).name)
    return result


def audit_api_workflow_live(
    workflow: Mapping[str, Any],
    *,
    object_info: Mapping[str, Any],
    model_inventory: Mapping[str, Any],
) -> dict[str, Any]:
    """Audit runtime node registration, model availability and the actual API graph.

    This is a pre-submit audit, not a geometry or inference acceptance.
    """
    checks: list[dict[str, Any]] = []
    blockers: list[str] = []
    class_counts: dict[str, int] = {}
    for node in workflow.values():
        cls = node.get("class_type")
        class_counts[cls] = class_counts.get(cls, 0) + 1

    missing_required = sorted(cls for cls in REQUIRED_CLASSES if cls not in object_info)
    workflow_classes = sorted(set(class_counts))
    missing_live_classes = sorted(cls for cls in workflow_classes if cls not in object_info)
    if missing_required or missing_live_classes:
        blockers.append(FAIL_NODE_CLASS)
        checks.append({
            "code": FAIL_NODE_CLASS,
            "status": "FAIL",
            "missing_required": missing_required,
            "missing_workflow_classes": missing_live_classes,
        })
    else:
        checks.append({
            "code": FAIL_NODE_CLASS,
            "status": "PASS",
            "required_registered": sorted(REQUIRED_CLASSES),
            "workflow_classes_registered": len(workflow_classes),
        })

    dangling = _resolve_all_links(workflow, object_info)
    if dangling:
        blockers.append("E_COMFY_API_GRAPH_INVALID")
    checks.append({
        "code": "E_COMFY_API_GRAPH_INVALID",
        "status": "FAIL" if dangling else "PASS",
        "errors": dangling,
    })

    available_models = _model_names(model_inventory)
    model_results: list[dict[str, Any]] = []
    model_contracts = {
        "UNETLoader": {"unet_name": EXPECTED_MODELS["unet_name"]},
        "VAELoader": {"vae_name": EXPECTED_MODELS["vae_name"]},
        "DualCLIPLoader": {
            "clip_name1": EXPECTED_MODELS["clip_name1"],
            "clip_name2": EXPECTED_MODELS["clip_name2"],
        },
    }
    for node_id, node in workflow.items():
        cls = node.get("class_type")
        inputs = node.get("inputs", {})
        expected_fields = model_contracts.get(cls)
        if expected_fields is None:
            continue
        for field, expected_name in expected_fields.items():
            model_name = inputs.get(field)
            normalized = Path(model_name.replace(chr(92), "/")).name if isinstance(model_name, str) else None
            exists = normalized in available_models
            matches_contract = normalized == expected_name
            model_results.append({
                "node_id": node_id,
                "class_type": cls,
                "input": field,
                "model": model_name,
                "expected": expected_name,
                "available": exists,
                "matches_contract": matches_contract,
            })
    if "UNETLoader" in class_counts:
        for node_id, node in workflow.items():
            if node.get("class_type") == "UNETLoader":
                model_results.append({
                    "node_id": node_id,
                    "class_type": "UNETLoader",
                    "input": "weight_dtype",
                    "model": node.get("inputs", {}).get("weight_dtype"),
                    "expected": "fp8_e4m3fn_fast",
                    "available": node.get("inputs", {}).get("weight_dtype") == "fp8_e4m3fn_fast",
                    "matches_contract": node.get("inputs", {}).get("weight_dtype") == "fp8_e4m3fn_fast",
                })
    if "DualCLIPLoader" in class_counts:
        for node_id, node in workflow.items():
            if node.get("class_type") == "DualCLIPLoader":
                clip_type_ok = node.get("inputs", {}).get("type") == "flux"
                model_results.append({
                    "node_id": node_id,
                    "class_type": "DualCLIPLoader",
                    "input": "type",
                    "model": node.get("inputs", {}).get("type"),
                    "expected": "flux",
                    "available": clip_type_ok,
                    "matches_contract": clip_type_ok,
                })
    bad_models = [x for x in model_results if not x["available"] or not x["matches_contract"]]
    if not model_results or bad_models:
        blockers.append("E_COMFY_MODEL_CONTRACT_MISMATCH")
    checks.append({
        "code": "E_COMFY_MODEL_CONTRACT_MISMATCH",
        "status": "PASS" if model_results and not bad_models else "FAIL",
        "models": model_results,
        "available_model_count": len(available_models),
        "model_names_only": True,
    })

    samplers = [
        (node_id, node) for node_id, node in workflow.items()
        if node.get("class_type") == "SamplerCustomAdvanced"
    ]
    routed_tiles: list[dict[str, Any]] = []
    route_errors: list[str] = []
    for sampler_id, sampler in samplers:
        guider_ref = _input_link(sampler, "guider", workflow)
        noise_ref = _input_link(sampler, "noise", workflow)
        latent_ref = _input_link(sampler, "latent_image", workflow)
        sampler_select_ref = _input_link(sampler, "sampler", workflow)
        scheduler_ref = _input_link(sampler, "sigmas", workflow)
        if not guider_ref or not noise_ref or not latent_ref or not sampler_select_ref or not scheduler_ref:
            route_errors.append(f"sampler {sampler_id} has missing guider/noise/latent/sampler/sigmas links")
            continue
        guider = _node(workflow, guider_ref[0])
        if not guider or guider.get("class_type") != "BasicGuider":
            route_errors.append(f"sampler {sampler_id} is not connected to BasicGuider")
            continue
        guidance_ref = _input_link(guider, "conditioning", workflow)
        model_ref = _input_link(guider, "model", workflow)
        if not guidance_ref or not model_ref:
            route_errors.append(f"sampler {sampler_id} guider route is incomplete")
            continue
        model_node = _node(workflow, model_ref[0])
        if not model_node or model_node.get("class_type") != "UNETLoader":
            route_errors.append(f"sampler {sampler_id} guider model is not a UNETLoader")
        scheduler = _node(workflow, scheduler_ref[0])
        if not scheduler or scheduler.get("class_type") != "BasicScheduler":
            route_errors.append(f"sampler {sampler_id} sigmas source is not BasicScheduler")
        elif _input_link(scheduler, "model", workflow) != model_ref:
            route_errors.append(f"sampler {sampler_id} guider and scheduler use different model sources")
        sampler_select = _node(workflow, sampler_select_ref[0])
        if not sampler_select or sampler_select.get("class_type") != "KSamplerSelect":
            route_errors.append(f"sampler {sampler_id} sampler source is not KSamplerSelect")
        guidance = _node(workflow, guidance_ref[0])
        if not guidance or guidance.get("class_type") != "FluxGuidance":
            route_errors.append(f"sampler {sampler_id} is not connected through FluxGuidance")
            continue
        clip_ref = _input_link(guidance, "conditioning", workflow)
        if not clip_ref:
            route_errors.append(f"sampler {sampler_id} FluxGuidance has no CLIPTextEncode source")
            continue
        clip = _node(workflow, clip_ref[0])
        if not clip or clip.get("class_type") != "CLIPTextEncode":
            route_errors.append(f"sampler {sampler_id} conditioning source is not CLIPTextEncode")
            continue
        clip_model_ref = _input_link(clip, "clip", workflow)
        clip_model = _node(workflow, clip_model_ref[0]) if clip_model_ref else None
        if not clip_model or clip_model.get("class_type") != "DualCLIPLoader":
            route_errors.append(f"sampler {sampler_id} CLIPTextEncode source is not DualCLIPLoader")
        prompt_meta = _tile_prompt_metadata(clip.get("inputs", {}).get("text"))
        if not prompt_meta["valid"]:
            route_errors.append(f"sampler {sampler_id} conditioning lacks explicit tile id/global origin")
        latent = _node(workflow, latent_ref[0])
        if not latent or latent.get("class_type") != "VAEEncode":
            route_errors.append(f"sampler {sampler_id} latent source is not VAEEncode")
        tile_input_ref = _input_link(latent, "pixels", workflow) if latent else None
        tile_input_node = _node(workflow, tile_input_ref[0]) if tile_input_ref else None
        if not tile_input_node or tile_input_node.get("class_type") != "LoadImage":
            route_errors.append(f"sampler {sampler_id} VAEEncode pixels are not from LoadImage")
        vae_ref = _input_link(latent, "vae", workflow) if latent else None
        vae_node = _node(workflow, vae_ref[0]) if vae_ref else None
        if not vae_node or vae_node.get("class_type") != "VAELoader":
            route_errors.append(f"sampler {sampler_id} VAEEncode is not connected to VAELoader")
        decoders = [
            (decode_id, decode) for decode_id, decode in workflow.items()
            if decode.get("class_type") == "VAEDecodeTiled"
            and _input_link(decode, "samples", workflow) == (sampler_id, 0)
        ]
        if len(decoders) != 1:
            route_errors.append(f"sampler {sampler_id} must feed exactly one VAEDecodeTiled")
        save_nodes_for_sampler: list[str] = []
        for decode_id, decode in decoders:
            if _input_link(decode, "vae", workflow) != vae_ref:
                route_errors.append(f"sampler {sampler_id} decode and encode use different VAE loaders")
            save_nodes_for_sampler.extend([
                save_id for save_id, save in workflow.items()
                if save.get("class_type") == "SaveImage"
                and _input_link(save, "images", workflow) == (decode_id, 0)
            ])
        if len(save_nodes_for_sampler) != 1:
            route_errors.append(f"sampler {sampler_id} must feed exactly one per-tile SaveImage")
        noise = _node(workflow, noise_ref[0])
        if not noise or noise.get("class_type") != "RandomNoise":
            route_errors.append(f"sampler {sampler_id} noise source is not RandomNoise or approved global-noise node")
        routed_tiles.append({
            "sampler_id": sampler_id,
            "guider_id": guider_ref[0],
            "guidance_id": guidance_ref[0],
            "conditioning_id": clip_ref[0],
            "clip_model_id": clip_model_ref[0] if clip_model_ref else None,
            "model_id": model_ref[0],
            "scheduler_id": scheduler_ref[0],
            "sampler_select_id": sampler_select_ref[0],
            "noise_id": noise_ref[0],
            "latent_id": latent_ref[0],
            "input_node_id": tile_input_ref[0] if tile_input_ref else None,
            "vae_id": vae_ref[0] if vae_ref else None,
            "decoder_ids": [x[0] for x in decoders],
            "save_node_ids": save_nodes_for_sampler,
            **prompt_meta,
        })

    conditioning_ids = [x["conditioning_id"] for x in routed_tiles]
    if len(samplers) < 1 or route_errors or len(set(conditioning_ids)) != len(conditioning_ids):
        blockers.append(FAIL_CONDITIONING)
    checks.append({
        "code": FAIL_CONDITIONING,
        "status": "PASS" if samplers and not route_errors and len(set(conditioning_ids)) == len(conditioning_ids) else "FAIL",
        "sampler_count": len(samplers),
        "routes": routed_tiles,
        "errors": route_errors,
    })

    noise_ids = [x["noise_id"] for x in routed_tiles]
    shared_noise = len(noise_ids) > 1 and len(set(noise_ids)) == 1
    noise_classes = {
        _node(workflow, noise_id).get("class_type")
        for noise_id in set(noise_ids)
        if _node(workflow, noise_id) is not None
    }
    # A shared RandomNoise node/seed is explicitly not a coordinate-indexed global field.
    if shared_noise or noise_classes == {"RandomNoise"}:
        blockers.append(FAIL_NOISE)
        noise_status = "FAIL_SHARED_SEED_ONLY"
    elif not noise_ids or "RandomNoise" in noise_classes:
        blockers.append(FAIL_NOISE)
        noise_status = "FAIL_NOT_COORDINATE_INDEXED"
    else:
        # Unknown custom NOISE implementations remain unverified until a live probe receipt
        # and node implementation identity are bound by a subsequent adapter version.
        blockers.append(FAIL_NOISE)
        noise_status = "UNKNOWN_CUSTOM_NOISE_IMPLEMENTATION"
    checks.append({
        "code": FAIL_NOISE,
        "status": "FAIL",
        "detail": "API graph does not carry a verifiable live coordinate-indexed noise implementation and overlap probe",
        "noise_ids": noise_ids,
        "noise_classes": sorted(noise_classes),
        "noise_status": noise_status,
    })

    save_nodes = [
        node_id for node_id, node in workflow.items()
        if node.get("class_type") == "SaveImage"
    ]
    decode_nodes = [
        node_id for node_id, node in workflow.items()
        if node.get("class_type") == "VAEDecodeTiled"
    ]
    if len(save_nodes) < len(samplers) or len(decode_nodes) < len(samplers):
        blockers.append(FAIL_TILE_RETURN)
        return_status = "FAIL_NO_PER_TILE_DECODE_SAVE"
    else:
        # The candidate API fixture only saves each decoded tile independently.
        # A production S6 requires a verified core-only compositor and final master.
        blockers.append(FAIL_TILE_RETURN)
        return_status = "FAIL_NO_CORE_ONLY_MASTER_COMPOSITOR"
    checks.append({
        "code": FAIL_TILE_RETURN,
        "status": "FAIL",
        "detail": "API workflow emits per-tile SaveImage outputs but no verified exact-once core compositor/final master",
        "save_nodes": save_nodes,
        "decode_nodes": decode_nodes,
        "return_status": return_status,
    })

    blockers.append(FAIL_MODEL_SHA)
    checks.append({
        "code": FAIL_MODEL_SHA,
        "status": "UNKNOWN",
        "detail": "Comfy Cloud model catalogue confirms filenames only; this API preflight has no weight-file SHA or loaded-tensor hash proof",
        "model_sha_verified": False,
    })

    unique_blockers = list(dict.fromkeys(blockers))
    return {
        "schema": RUNTIME_AUDIT_SCHEMA,
        "method_id": "FLUX_HR_TILE_IMG2IMG",
        "maturity_remains": "workflow_candidate",
        "overall_status": "BLOCKED_WORKFLOW_CANDIDATE" if unique_blockers else "READY_FOR_DIAGNOSTIC_ONLY",
        "blockers": unique_blockers,
        "checks": checks,
        "workflow_node_count": len(workflow),
        "workflow_class_counts": dict(sorted(class_counts.items())),
        "live_node_count": len(object_info),
        "live_model_name_count": len(available_models),
        "routed_tiles": routed_tiles,
        "execution_allowed": False,
        "production_claim_allowed": False,
        "non_claims": [
            "A remote preflight is not a GPU inference run.",
            "Cloud model filenames do not prove the weight SHA or loaded tensor identity.",
            "Shared seed/RandomNoise is not a global coordinate-indexed noise field.",
            "Per-tile SaveImage outputs are not an S6 core-only composed master.",
            "No S7 independent human acceptance is performed here.",
        ],
    }


def _validate_manifest(manifest: Mapping[str, Any]) -> dict[str, Any]:
    if manifest.get("schema") != "ige-comfy-cloud-run-manifest/0.1":
        raise ComfyWorkflowError("manifest schema must be ige-comfy-cloud-run-manifest/0.1")
    for key in ("workflow_path", "tile_inputs", "output_dir"):
        if key not in manifest:
            raise ComfyWorkflowError(f"manifest missing {key}")
    if not isinstance(manifest["tile_inputs"], list) or not manifest["tile_inputs"]:
        raise ComfyWorkflowError("tile_inputs must be a non-empty list")
    seen: set[str] = set()
    for item in manifest["tile_inputs"]:
        if not isinstance(item, Mapping):
            raise ComfyWorkflowError("each tile_inputs entry must be an object")
        node_id, path, expected = item.get("node_id"), item.get("path"), item.get("sha256")
        if not isinstance(node_id, str) or not node_id or node_id in seen:
            raise ComfyWorkflowError("tile input node_id must be unique non-empty string")
        if not isinstance(path, str) or not path:
            raise ComfyWorkflowError(f"tile input {node_id} needs path")
        if not isinstance(expected, str) or not re.fullmatch(r"[0-9a-fA-F]{64}", expected):
            raise ComfyWorkflowError(f"tile input {node_id} needs a SHA-256")
        seen.add(node_id)
    if not isinstance(manifest["workflow_path"], str) or not isinstance(manifest["output_dir"], str):
        raise ComfyWorkflowError("workflow_path/output_dir must be strings")
    return dict(manifest)


def _resolve_local(base_dir: Path, value: str) -> Path:
    path = Path(value).expanduser()
    return path.resolve() if path.is_absolute() else (base_dir / path).resolve()


def create_comfy_cloud_manifest(
    *,
    workflow_path: str | Path,
    tile_bindings: Sequence[tuple[str, str | Path]],
    manifest_path: str | Path,
    output_dir: str | Path,
    run_id: str | None = None,
) -> dict[str, Any]:
    """Create a manifest from local bytes so operators never hand-author input hashes."""
    workflow = Path(workflow_path).expanduser().resolve()
    if not workflow.is_file():
        raise ComfyWorkflowError(f"workflow file not found: {workflow}")
    api_workflow = load_api_workflow(workflow)
    if not tile_bindings:
        raise ComfyWorkflowError("at least one --tile NODE_ID=IMAGE_PATH is required")
    manifest_target = Path(manifest_path).expanduser().resolve()
    manifest_target.parent.mkdir(parents=True, exist_ok=True)
    base_dir = manifest_target.parent
    bindings = []
    seen: set[str] = set()
    for node_id, input_path in tile_bindings:
        if not isinstance(node_id, str) or not node_id or node_id in seen:
            raise ComfyWorkflowError(f"tile node id must be unique and non-empty: {node_id!r}")
        seen.add(node_id)
        node = _node(api_workflow, node_id)
        if node is None or node.get("class_type") != "LoadImage":
            raise ComfyWorkflowError(f"tile node {node_id!r} is not a LoadImage node in the API workflow")
        local_path = Path(input_path).expanduser().resolve()
        if not local_path.is_file():
            raise ComfyWorkflowError(f"tile image not found: {local_path}")
        bindings.append({
            "node_id": node_id,
            "path": os.path.relpath(local_path, base_dir),
            "sha256": sha256_file(local_path),
        })
    output_path = Path(output_dir).expanduser()
    if not output_path.is_absolute():
        output_path = (Path.cwd() / output_path).resolve()
    payload = {
        "schema": "ige-comfy-cloud-run-manifest/0.1",
        "run_id": run_id or f"comfy-cloud-{uuid.uuid4().hex[:12]}",
        "workflow_path": os.path.relpath(workflow, base_dir),
        "tile_inputs": bindings,
        "output_dir": os.path.relpath(output_path, base_dir),
        "diagnostic_only": True,
    }
    _validate_manifest(payload)
    manifest_target.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return {
        "manifest_path": str(manifest_target),
        "manifest_sha256": sha256_file(manifest_target),
        "manifest": payload,
        "execution_allowed": False,
        "diagnostic_only": True,
    }


def preflight_comfy_cloud(
    manifest_path: str | Path,
    *,
    client: ComfyCloudClient | None = None,
) -> dict[str, Any]:
    path = Path(manifest_path).resolve()
    manifest = _validate_manifest(json.loads(path.read_text(encoding="utf-8")))
    workflow_path = _resolve_local(path.parent, manifest["workflow_path"])
    workflow = load_api_workflow(workflow_path)
    workflow_sha = sha256_file(workflow_path)
    input_facts: list[dict[str, Any]] = []
    for item in manifest["tile_inputs"]:
        node_id = item["node_id"]
        node = _node(workflow, node_id)
        if node is None or node.get("class_type") != "LoadImage":
            raise ComfyWorkflowError(f"tile input node {node_id} must resolve to LoadImage")
        local_path = _resolve_local(path.parent, item["path"])
        if not local_path.is_file():
            raise ComfyWorkflowError(f"tile input file not found: {local_path}")
        digest = sha256_file(local_path)
        if digest.lower() != item["sha256"].lower():
            raise ComfyWorkflowError(f"tile input SHA mismatch at node {node_id}")
        input_facts.append({
            "node_id": node_id,
            "path": str(local_path),
            "sha256": digest,
            "size_bytes": local_path.stat().st_size,
        })
    client = client or ComfyCloudClient()
    live = client.health()
    models = client.model_inventory()
    audit = audit_api_workflow_live(
        workflow,
        object_info=live["object_info"],
        model_inventory=models,
    )
    return {
        "schema": "ige-comfy-cloud-preflight-report/0.1",
        "workflow_path": str(workflow_path),
        "workflow_sha256": workflow_sha,
        "input_facts": input_facts,
        "cloud": {
            "base_url": client.base_url,
            "status": live["status"],
            "live_node_count": live["node_count"],
            "features": live["features"],
            "model_folder_count": len(models.get("folders") or []),
            "model_name_count": len(_model_names(models)),
        },
        "runtime_audit": audit,
        "execution_allowed": False,
        "diagnostic_submit_requires_explicit_flag": True,
        "production_submit_allowed": False,
    }


def run_comfy_cloud_diagnostic(
    manifest_path: str | Path,
    *,
    diagnostic_submit: bool = False,
    client: ComfyCloudClient | None = None,
    timeout_seconds: float = 1800,
    poll_interval_seconds: float = 2,
) -> dict[str, Any]:
    """Execute a deliberately diagnostic-only cloud run.

    This route may run a workflow with known unresolved geometry/noise issues,
    but output is stamped diagnostic_only, never accepted, and never promotes
    Registry maturity. It requires an explicit diagnostic_submit=True.
    """
    if diagnostic_submit is not True:
        raise ComfyWorkflowError("submitting a diagnostic Cloud job requires --diagnostic-submit")
    path = Path(manifest_path).resolve()
    manifest = _validate_manifest(json.loads(path.read_text(encoding="utf-8")))
    if manifest.get("diagnostic_only") is not True:
        raise ComfyWorkflowError("manifest must explicitly contain diagnostic_only=true")
    workflow_path = _resolve_local(path.parent, manifest["workflow_path"])
    workflow = load_api_workflow(workflow_path)
    workflow_sha = sha256_file(workflow_path)
    client = client or ComfyCloudClient()

    # Re-run remote preflight immediately before upload/submit.
    live = client.health()
    model_inventory = client.model_inventory()
    audit = audit_api_workflow_live(workflow, object_info=live["object_info"], model_inventory=model_inventory)

    input_receipts: list[dict[str, Any]] = []
    prepared = copy.deepcopy(workflow)
    for item in manifest["tile_inputs"]:
        node_id = item["node_id"]
        node = _node(prepared, node_id)
        if node is None or node.get("class_type") != "LoadImage":
            raise ComfyWorkflowError(f"input binding node {node_id} must be LoadImage")
        local_path = _resolve_local(path.parent, item["path"])
        if not local_path.is_file():
            raise ComfyWorkflowError(f"tile input not found: {local_path}")
        source_sha = sha256_file(local_path)
        if source_sha.lower() != item["sha256"].lower():
            raise ComfyWorkflowError(f"tile input SHA mismatch at node {node_id}")
        uploaded = client.upload_image(local_path)
        node["inputs"]["image"] = uploaded["name"]
        input_receipts.append({
            "node_id": node_id,
            "source_path": str(local_path),
            "source_sha256": source_sha,
            "uploaded_name": uploaded["name"],
            "uploaded_subfolder": uploaded.get("subfolder", ""),
            "uploaded_type": uploaded.get("type", "input"),
        })

    prompt_id = client.submit_prompt(prepared)
    job = client.wait_for_job(
        prompt_id,
        timeout_seconds=timeout_seconds,
        poll_interval_seconds=poll_interval_seconds,
    )
    image_records = client.collect_images(job)
    if not image_records:
        raise ComfyWorkflowError(f"Cloud job {prompt_id} completed but returned no image records")
    output_dir = _resolve_local(path.parent, manifest["output_dir"])
    output_dir.mkdir(parents=True, exist_ok=True)
    tile_by_save_node: dict[str, dict[str, Any]] = {}
    for tile in audit.get("routed_tiles") or []:
        for save_node_id in tile.get("save_node_ids") or []:
            tile_by_save_node[str(save_node_id)] = {
                "tile_id": tile.get("tile_id"),
                "origin_xy": tile.get("origin_xy"),
                "sampler_id": tile.get("sampler_id"),
                "input_node_id": tile.get("input_node_id"),
                "save_node_id": str(save_node_id),
            }
    output_receipts: list[dict[str, Any]] = []
    for index, record in enumerate(image_records):
        source_name = record["filename"]
        safe_name = re.sub(r"[^A-Za-z0-9_.-]+", "_", Path(source_name).name)
        destination = output_dir / f"{prompt_id}_{index:02d}_{safe_name}"
        output_receipt = client.download_output(record, destination)
        output_node_id = record.get("node_id")
        tile_binding = tile_by_save_node.get(str(output_node_id)) if output_node_id is not None else None
        output_receipt.update({
            "output_node_id": output_node_id,
            "tile_binding": tile_binding,
            "tile_mapping_status": "BOUND" if tile_binding else "UNMAPPED_OUTPUT_NODE",
        })
        output_receipts.append(output_receipt)
    output_mapping_complete = bool(output_receipts) and all(
        x.get("tile_mapping_status") == "BOUND" for x in output_receipts
    )

    receipt = {
        "schema": RUN_RECEIPT_SCHEMA,
        "run_id": str(manifest.get("run_id") or prompt_id),
        "prompt_id": prompt_id,
        "cloud_base_url": client.base_url,
        "workflow_path": str(workflow_path),
        "workflow_sha256": workflow_sha,
        "job_status": job.get("status") or job.get("state"),
        "input_receipts": input_receipts,
        "output_receipts": output_receipts,
        "output_tile_mapping_complete": output_mapping_complete,
        "runtime_audit": audit,
        "execution_kind": "real_comfy_cloud_inference",
        "diagnostic_only": True,
        "candidate_accepted": False,
        "execution_allowed": False,
        "edit_permission": False,
        "maturity_remains": "workflow_candidate",
        "comfyui_claim": "REAL_DIAGNOSTIC_INFERENCE_ONLY_NOT_GEOMETRY_ACCEPTED",
        "non_claims": [
            "This is a real Comfy Cloud inference, but diagnostic only.",
            "The workflow still fails the global coordinate-indexed noise gate.",
            "The outputs are separate tile candidates, not a core-only composed master.",
            "Cloud filenames do not verify exact weight file SHA or loaded tensor identity.",
            "S6 and S7 are not performed by this command.",
        ],
    }
    receipt_path = output_dir / f"{prompt_id}.comfy_cloud_receipt.json"
    receipt_path.write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    receipt["receipt_path"] = str(receipt_path)
    receipt["receipt_sha256"] = sha256_file(receipt_path)
    return receipt
