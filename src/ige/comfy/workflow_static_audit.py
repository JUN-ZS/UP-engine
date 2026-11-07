"""Static audit of ComfyUI UI graphs and API prompts for FLUX_HR_TILE_IMG2IMG.

This module NEVER runs ComfyUI, NEVER loads GPU weights for inference, and
NEVER sets execution_allowed=True. Optional offline backend_model_inventory
may record weight SHAs for precondition checks only. Maturity remains
workflow_candidate regardless of inventory PASS.
"""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any, Mapping

METHOD_ID = "FLUX_HR_TILE_IMG2IMG"
MATURITY = "workflow_candidate"
AUDIT_SCHEMA = "ige-comfy-workflow-static-audit/0.1"

# Filename inventory only — not weight-file SHA verification.
EXPECTED_DEV_FP8_MODELS: dict[str, Any] = {
    "unet_name": "flux1-dev.safetensors",
    "weight_dtype": "fp8_e4m3fn_fast",
    "vae_name": "ae.safetensors",
    "clip_name1": "t5xxl_fp16.safetensors",
    "clip_name2": "clip_l.safetensors",
    "clip_type": "flux",
}

# Structural classes that must appear for a Flux HR tile *candidate inventory*.
# Custom IGE/TTP nodes are optional inventory (UI has them; API v0.5 does not).
REQUIRED_FLUX_HR_TILE_CLASSES: tuple[str, ...] = (
    "UNETLoader",
    "VAELoader",
    "DualCLIPLoader",
    "RandomNoise",
    "SamplerCustomAdvanced",
    "CLIPTextEncode",
)

OPTIONAL_INVENTORY_CLASSES: tuple[str, ...] = (
    "UpscaleModelLoader",
    "IGE_TileNoiseMask",
    "SetLatentNoiseMask",
    "TTP_Image_Tile_Batch",
    "TTP_Tile_image_size",
    "TTP_Image_Assy",
    "VAEEncode",
    "VAEDecodeTiled",
    "BasicGuider",
    "FluxGuidance",
    "KSamplerSelect",
    "BasicScheduler",
)

FAILURE_COMFY_NODE_MISSING = "E_COMFY_NODE_MISSING"
FAILURE_MODEL_MISMATCH = "E_MODEL_INVENTORY_MISMATCH"
FAILURE_TILE_COND = "E_TILE_CONDITIONING_UNROUTED"
FAILURE_NOISE = "E_NOISE_FIELD_NOT_GLOBAL"


def file_sha256(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_workflow_json(path: str | Path) -> Any:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def detect_format(payload: Any) -> str:
    if isinstance(payload, dict) and isinstance(payload.get("nodes"), list):
        return "ui_graph"
    if isinstance(payload, dict) and payload and all(
        isinstance(v, dict) and "class_type" in v for v in payload.values()
    ):
        return "api_prompt"
    raise ValueError("unrecognized ComfyUI workflow JSON (expected UI graph or API prompt)")


def _check(
    code: str,
    status: str,
    detail: str,
    *,
    evidence: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    item: dict[str, Any] = {
        "code": code,
        "status": status,
        "detail": detail,
    }
    if evidence is not None:
        item["evidence"] = dict(evidence)
    return item


def extract_ui_inventory(graph: Mapping[str, Any]) -> dict[str, Any]:
    classes: Counter[str] = Counter()
    models: dict[str, Any] = {}
    clip_texts: list[dict[str, Any]] = []
    noise_nodes: list[dict[str, Any]] = []
    interesting: list[dict[str, Any]] = []

    for node in graph.get("nodes", []):
        cls = node.get("type")
        if not isinstance(cls, str):
            continue
        classes[cls] += 1
        widgets = node.get("widgets_values")
        entry = {
            "id": node.get("id"),
            "class_type": cls,
            "title": node.get("title"),
            "widgets_values": widgets,
        }
        if cls in REQUIRED_FLUX_HR_TILE_CLASSES or cls in OPTIONAL_INVENTORY_CLASSES or cls.startswith("IGE_"):
            interesting.append(entry)

        if cls == "UNETLoader" and isinstance(widgets, list) and len(widgets) >= 2:
            models["unet_name"] = widgets[0]
            models["weight_dtype"] = widgets[1]
        elif cls == "VAELoader" and isinstance(widgets, list) and widgets:
            models["vae_name"] = widgets[0]
        elif cls == "DualCLIPLoader" and isinstance(widgets, list) and len(widgets) >= 3:
            models["clip_name1"] = widgets[0]
            models["clip_name2"] = widgets[1]
            models["clip_type"] = widgets[2]
        elif cls == "UpscaleModelLoader" and isinstance(widgets, list) and widgets:
            models["upscale_model"] = widgets[0]
        elif cls == "RandomNoise" and isinstance(widgets, list) and widgets:
            seed = widgets[0]
            mode = widgets[1] if len(widgets) > 1 else None
            models["noise_seed"] = seed
            models["noise_mode"] = mode
            noise_nodes.append({"id": node.get("id"), "noise_seed": seed, "noise_mode": mode})
        elif cls == "CLIPTextEncode":
            text = widgets[0] if isinstance(widgets, list) and widgets else ""
            clip_texts.append(
                {
                    "id": node.get("id"),
                    "title": node.get("title"),
                    "text_preview": (text[:160] + "...") if isinstance(text, str) and len(text) > 160 else text,
                    "text_len": len(text) if isinstance(text, str) else 0,
                    "nonempty": bool(isinstance(text, str) and text.strip()),
                }
            )

    return {
        "format": "ui_graph",
        "node_count": len(graph.get("nodes", [])),
        "class_counts": dict(sorted(classes.items())),
        "models": models,
        "clip_text_encodes": clip_texts,
        "noise_nodes": noise_nodes,
        "interesting_nodes": interesting,
        "has_ige_tile_noise_mask": classes.get("IGE_TileNoiseMask", 0) > 0,
        "has_set_latent_noise_mask": classes.get("SetLatentNoiseMask", 0) > 0,
        "has_ttp_tile_batch": classes.get("TTP_Image_Tile_Batch", 0) > 0,
    }


def extract_api_inventory(prompt: Mapping[str, Any]) -> dict[str, Any]:
    classes: Counter[str] = Counter()
    models: dict[str, Any] = {}
    clip_texts: list[dict[str, Any]] = []
    noise_nodes: list[dict[str, Any]] = []
    nodes: list[dict[str, Any]] = []
    guider_conditionings: list[dict[str, Any]] = []

    for nid, node in prompt.items():
        if not isinstance(node, dict):
            continue
        cls = node.get("class_type")
        if not isinstance(cls, str):
            continue
        inputs = node.get("inputs", {})
        if not isinstance(inputs, dict):
            inputs = {}
        classes[cls] += 1
        nodes.append({"id": str(nid), "class_type": cls, "inputs": inputs})

        if cls == "UNETLoader":
            models["unet_name"] = inputs.get("unet_name")
            models["weight_dtype"] = inputs.get("weight_dtype")
        elif cls == "VAELoader":
            models["vae_name"] = inputs.get("vae_name")
        elif cls == "DualCLIPLoader":
            models["clip_name1"] = inputs.get("clip_name1")
            models["clip_name2"] = inputs.get("clip_name2")
            models["clip_type"] = inputs.get("type")
        elif cls == "UpscaleModelLoader":
            models["upscale_model"] = inputs.get("model_name") or inputs.get("upscale_model")
        elif cls == "RandomNoise":
            seed = inputs.get("noise_seed")
            models["noise_seed"] = seed
            noise_nodes.append({"id": str(nid), "noise_seed": seed})
        elif cls == "CLIPTextEncode":
            text = inputs.get("text", "")
            preview = text
            if isinstance(text, str) and len(text) > 160:
                preview = text[:160] + "..."
            clip_texts.append(
                {
                    "id": str(nid),
                    "text_preview": preview,
                    "text_len": len(text) if isinstance(text, str) else 0,
                    "nonempty": bool(isinstance(text, str) and text.strip()),
                    "mentions_tile_origin": isinstance(text, str)
                    and ("TILE ORIGIN" in text.upper() or "tile-local" in text.lower() or "GLOBAL TILE" in text.upper()),
                }
            )
        elif cls == "BasicGuider":
            guider_conditionings.append(
                {
                    "id": str(nid),
                    "conditioning": inputs.get("conditioning"),
                    "model": inputs.get("model"),
                }
            )

    distinct_cond_refs = {
        json.dumps(item.get("conditioning"), sort_keys=True)
        for item in guider_conditionings
        if item.get("conditioning") is not None
    }

    return {
        "format": "api_prompt",
        "node_count": len(prompt),
        "class_counts": dict(sorted(classes.items())),
        "models": models,
        "clip_text_encodes": clip_texts,
        "noise_nodes": noise_nodes,
        "nodes": nodes,
        "guider_conditionings": guider_conditionings,
        "distinct_guider_conditioning_refs": len(distinct_cond_refs),
        "has_ige_tile_noise_mask": classes.get("IGE_TileNoiseMask", 0) > 0,
        "has_set_latent_noise_mask": classes.get("SetLatentNoiseMask", 0) > 0,
        "has_ttp_tile_batch": classes.get("TTP_Image_Tile_Batch", 0) > 0,
    }


def _merge_models(*inventories: Mapping[str, Any]) -> dict[str, Any]:
    merged: dict[str, Any] = {}
    for inv in inventories:
        for key, value in (inv.get("models") or {}).items():
            if value is not None and key not in merged:
                merged[key] = value
    return merged


def _class_present(inventories: list[Mapping[str, Any]], class_name: str) -> bool:
    for inv in inventories:
        if (inv.get("class_counts") or {}).get(class_name, 0) > 0:
            return True
    return False


def _compare_ui_api_models(
    ui_models: Mapping[str, Any],
    api_models: Mapping[str, Any],
) -> list[dict[str, Any]]:
    mismatches: list[dict[str, Any]] = []
    keys = sorted(set(ui_models) | set(api_models))
    for key in keys:
        # Upscale model is expected on UI Dev FP8 graph but absent from geometry-locked API v0.5.
        if key == "upscale_model":
            continue
        if key == "noise_mode":
            continue
        left = ui_models.get(key)
        right = api_models.get(key)
        if left is None or right is None:
            continue
        if left != right:
            mismatches.append({"key": key, "ui": left, "api": right})
    return mismatches


def evaluate_checks(
    inventories: list[Mapping[str, Any]],
    *,
    ui_models: Mapping[str, Any] | None = None,
    api_models: Mapping[str, Any] | None = None,
) -> list[dict[str, Any]]:
    checks: list[dict[str, Any]] = []
    class_union: Counter[str] = Counter()
    for inv in inventories:
        class_union.update(inv.get("class_counts") or {})

    missing = [cls for cls in REQUIRED_FLUX_HR_TILE_CLASSES if class_union.get(cls, 0) <= 0]
    if missing:
        checks.append(
            _check(
                FAILURE_COMFY_NODE_MISSING,
                "FAIL",
                f"required Flux HR tile inventory classes missing: {missing}",
                evidence={"missing": missing, "present_counts": dict(class_union)},
            )
        )
    else:
        checks.append(
            _check(
                FAILURE_COMFY_NODE_MISSING,
                "PASS",
                "required Flux HR tile inventory classes are present in at least one supplied graph",
                evidence={"required": list(REQUIRED_FLUX_HR_TILE_CLASSES)},
            )
        )

    optional_present = {
        cls: class_union.get(cls, 0) for cls in OPTIONAL_INVENTORY_CLASSES if class_union.get(cls, 0) > 0
    }
    checks.append(
        _check(
            "INVENTORY_OPTIONAL_NODES",
            "PASS" if optional_present else "UNKNOWN",
            "optional core/halo / tile / mask nodes recorded as inventory only (not live proof)",
            evidence={
                "optional_present": optional_present,
                "ige_tile_noise_mask": any(inv.get("has_ige_tile_noise_mask") for inv in inventories),
                "set_latent_noise_mask": any(inv.get("has_set_latent_noise_mask") for inv in inventories),
                "ttp_tile_batch": any(inv.get("has_ttp_tile_batch") for inv in inventories),
            },
        )
    )

    merged_models = _merge_models(*inventories)
    model_mismatches: list[dict[str, Any]] = []
    for key, expected in EXPECTED_DEV_FP8_MODELS.items():
        actual = merged_models.get(key)
        if actual != expected:
            model_mismatches.append({"key": key, "expected": expected, "actual": actual})

    if model_mismatches:
        checks.append(
            _check(
                FAILURE_MODEL_MISMATCH,
                "FAIL",
                "declared model filenames/dtype do not match expected Dev FP8 inventory (filenames only; weight SHA not verified)",
                evidence={"mismatches": model_mismatches, "observed": merged_models},
            )
        )
    else:
        checks.append(
            _check(
                FAILURE_MODEL_MISMATCH,
                "PASS",
                "declared Dev FP8 model filenames/dtype match expected inventory (filenames only; weight SHA NOT verified)",
                evidence={"observed": {k: merged_models.get(k) for k in EXPECTED_DEV_FP8_MODELS}},
            )
        )

    if ui_models is not None and api_models is not None:
        cross = _compare_ui_api_models(ui_models, api_models)
        if cross:
            checks.append(
                _check(
                    "E_UI_API_VALUE_MISMATCH",
                    "FAIL",
                    "UI widget values disagree with API prompt inputs for shared model/noise keys",
                    evidence={"mismatches": cross},
                )
            )
        else:
            checks.append(
                _check(
                    "E_UI_API_VALUE_MISMATCH",
                    "PASS",
                    "UI and API agree on shared Dev FP8 model/noise inventory keys (upscale_model excluded)",
                    evidence={
                        "ui": {k: ui_models.get(k) for k in EXPECTED_DEV_FP8_MODELS},
                        "api": {k: api_models.get(k) for k in EXPECTED_DEV_FP8_MODELS},
                        "noise_seed_ui": ui_models.get("noise_seed"),
                        "noise_seed_api": api_models.get("noise_seed"),
                    },
                )
            )

    # Conditioning: static per-tile prompt evidence only.
    api_invs = [inv for inv in inventories if inv.get("format") == "api_prompt"]
    ui_invs = [inv for inv in inventories if inv.get("format") == "ui_graph"]
    per_tile_static = False
    cond_evidence: dict[str, Any] = {}

    if api_invs:
        api = api_invs[0]
        encodes = api.get("clip_text_encodes") or []
        nonempty = [e for e in encodes if e.get("nonempty")]
        distinct_guiders = api.get("distinct_guider_conditioning_refs") or 0
        tile_hints = [e for e in encodes if e.get("mentions_tile_origin")]
        cond_evidence = {
            "clip_text_encode_count": len(encodes),
            "nonempty_prompt_count": len(nonempty),
            "tile_origin_hint_count": len(tile_hints),
            "distinct_guider_conditioning_refs": distinct_guiders,
            "claim": "static_per_tile_prompt_evidence_only",
        }
        if len(nonempty) >= 2 and distinct_guiders >= 2:
            per_tile_static = True
        elif len(nonempty) >= 2:
            # Two prompts exist but guider wiring unclear.
            per_tile_static = True
            cond_evidence["note"] = "multiple nonempty CLIPTextEncode nodes; treat as static evidence only"

    if not per_tile_static and ui_invs:
        ui = ui_invs[0]
        encodes = ui.get("clip_text_encodes") or []
        nonempty = [e for e in encodes if e.get("nonempty")]
        cond_evidence.setdefault("ui_clip_text_encode_count", len(encodes))
        cond_evidence.setdefault("ui_nonempty_prompt_count", len(nonempty))
        # Empty UI prompts alone are not per-tile routing evidence.
        if len(nonempty) >= 2:
            per_tile_static = True
            cond_evidence["claim"] = "static_per_tile_prompt_evidence_only"

    if per_tile_static:
        checks.append(
            _check(
                FAILURE_TILE_COND,
                "PASS",
                "static evidence of per-tile prompts present; NOT live routing proof",
                evidence=cond_evidence,
            )
        )
    else:
        shared_only = False
        total_encodes = 0
        for inv in inventories:
            total_encodes += len(inv.get("clip_text_encodes") or [])
        if total_encodes <= 1:
            shared_only = True
        checks.append(
            _check(
                FAILURE_TILE_COND,
                "FAIL" if shared_only or total_encodes == 0 else "UNKNOWN",
                "no static per-tile conditioning evidence (single/shared or empty prompts); live routing unverified",
                evidence=cond_evidence or {"clip_text_encode_total": total_encodes},
            )
        )

    # Noise: same seed alone is insufficient / FAIL for global field proof.
    # Delegates classification to the global noise field contract module.
    # Synthetic PASS ≠ Live PASS — see noise_* surfaces on the audit report.
    from .global_noise_contract import classify_noise_evidence

    noise_classification = classify_noise_evidence(
        workflow_static_bits={"inventories": list(inventories)},
    )
    checks.append(noise_classification["check"])
    return checks


def audit_comfy_workflows(
    *,
    ui_path: str | Path | None = None,
    api_path: str | Path | None = None,
    model_inventory_path: str | Path | None = None,
    capture_receipt_path: str | Path | None = None,
) -> dict[str, Any]:
    if ui_path is None and api_path is None:
        raise ValueError("at least one of ui_path or api_path is required")

    sources: dict[str, Any] = {}
    inventories: list[dict[str, Any]] = []
    ui_models: dict[str, Any] | None = None
    api_models: dict[str, Any] | None = None

    if ui_path is not None:
        path = Path(ui_path)
        payload = load_workflow_json(path)
        fmt = detect_format(payload)
        if fmt != "ui_graph":
            raise ValueError(f"--ui path is not a ComfyUI UI graph: {path}")
        inv = extract_ui_inventory(payload)
        inventories.append(inv)
        ui_models = dict(inv.get("models") or {})
        sources["ui"] = {
            "path": str(path),
            "filename": path.name,
            "sha256": file_sha256(path),
            "bytes": path.stat().st_size,
            "format": fmt,
            "node_count": inv["node_count"],
        }

    if api_path is not None:
        path = Path(api_path)
        payload = load_workflow_json(path)
        fmt = detect_format(payload)
        if fmt != "api_prompt":
            raise ValueError(f"--api path is not a ComfyUI API prompt: {path}")
        inv = extract_api_inventory(payload)
        inventories.append(inv)
        api_models = dict(inv.get("models") or {})
        sources["api"] = {
            "path": str(path),
            "filename": path.name,
            "sha256": file_sha256(path),
            "bytes": path.stat().st_size,
            "format": fmt,
            "node_count": inv["node_count"],
        }

    checks = evaluate_checks(
        inventories,
        ui_models=ui_models,
        api_models=api_models,
    )

    backend_inventory_summary: dict[str, Any] | None = None
    provisional = {
        "inventories": {
            ("ui" if inv["format"] == "ui_graph" else "api"): {
                "models": inv.get("models"),
            }
            for inv in inventories
        }
    }

    if model_inventory_path is not None:
        from .model_inventory import (
            EVIDENCE_GRADE_DECLARED,
            load_model_inventory,
            summarize_inventory,
            validate_declared_inventory,
            verify_against_workflow_audit,
        )

        inv_payload = load_model_inventory(model_inventory_path)
        declared = validate_declared_inventory(inv_payload)
        backend_check = verify_against_workflow_audit(inv_payload, provisional)
        # Filename/role alignment still contributes to structural inventory status,
        # but evidence_grade remains declared_record (not live disk proof).
        checks.append(backend_check)
        backend_inventory_summary = {
            "path": str(Path(model_inventory_path)),
            "filename": Path(model_inventory_path).name,
            "sha256": file_sha256(model_inventory_path),
            "status": backend_check["status"],
            "evidence_grade": EVIDENCE_GRADE_DECLARED,
            "inventory_declared_ok": declared["inventory_declared_ok"]
            and backend_check["status"] == "PASS",
            "inventory_capture_present": False,
            "inventory_live_verified": False,
            "summary": summarize_inventory(inv_payload),
            "siax_registry_pin": (backend_check.get("evidence") or {}).get("siax_registry_pin"),
            "note": (
                "Declared inventory record only — SHA strings were not re-hashed from "
                "operator PC disk by this audit. Use --capture-receipt for disk_capture."
            ),
        }
        sources["backend_model_inventory"] = {
            "path": str(Path(model_inventory_path)),
            "filename": Path(model_inventory_path).name,
            "sha256": file_sha256(model_inventory_path),
            "bytes": Path(model_inventory_path).stat().st_size,
            "inventory_id": inv_payload.get("inventory_id"),
            "inventory_version": inv_payload.get("inventory_version"),
            "evidence_grade": EVIDENCE_GRADE_DECLARED,
        }

    if capture_receipt_path is not None:
        from .model_inventory import EVIDENCE_GRADE_DISK
        from .model_inventory_capture import (
            load_capture_receipt,
            siax_matches_registry_pin,
            verify_capture_against_workflow,
        )

        receipt = load_capture_receipt(capture_receipt_path)
        capture_check = verify_capture_against_workflow(receipt, provisional)
        checks.append(
            {
                **capture_check,
                "code": "E_BACKEND_MODEL_CAPTURE",
                "detail": (
                    capture_check.get("detail")
                    or "disk-capture receipt workflow alignment"
                ),
            }
        )
        siax = siax_matches_registry_pin(receipt)
        capture_summary = {
            "path": str(Path(capture_receipt_path)),
            "filename": Path(capture_receipt_path).name,
            "sha256": file_sha256(capture_receipt_path),
            "status": capture_check["status"],
            "evidence_grade": EVIDENCE_GRADE_DISK,
            "inventory_declared_ok": backend_inventory_summary.get("inventory_declared_ok")
            if backend_inventory_summary
            else None,
            "inventory_capture_present": True,
            "inventory_live_verified": capture_check["status"] == "PASS",
            "receipt_kind": receipt.get("receipt_kind"),
            "capture_tool": receipt.get("capture_tool"),
            "host": (receipt.get("host") or {}).get("hostname"),
            "models_root": receipt.get("models_root"),
            "captured_at": receipt.get("captured_at"),
            "asset_count": len(receipt.get("assets") or []),
            "siax_registry_pin": siax,
            "note": (
                "Disk-capture receipt present. Provenance validated; optional --rehash "
                "against the same host is separate. CI never reads operator PC weights."
            ),
        }
        if backend_inventory_summary is None:
            backend_inventory_summary = capture_summary
        else:
            backend_inventory_summary["capture"] = capture_summary
            backend_inventory_summary["inventory_capture_present"] = True
            backend_inventory_summary["inventory_live_verified"] = capture_summary[
                "inventory_live_verified"
            ]
            # Prefer disk_capture grade when receipt supplied
            backend_inventory_summary["evidence_grade"] = EVIDENCE_GRADE_DISK
        sources["model_inventory_capture_receipt"] = {
            "path": str(Path(capture_receipt_path)),
            "filename": Path(capture_receipt_path).name,
            "sha256": file_sha256(capture_receipt_path),
            "bytes": Path(capture_receipt_path).stat().st_size,
            "evidence_grade": EVIDENCE_GRADE_DISK,
            "receipt_kind": receipt.get("receipt_kind"),
        }

    from .global_noise_contract import (
        classify_noise_evidence as _classify_noise_evidence,
        evaluate_all_mechanism_synthetic_acceptances,
    )

    # Re-classify from inventories so report surfaces match the E_NOISE check.
    noise_classification = _classify_noise_evidence(
        workflow_static_bits={"inventories": list(inventories)},
    )
    noise_field_kind = noise_classification.get("field_kind") or "unknown"
    noise_field_detail = noise_classification.get("detail")
    noise_evidence_grade = (
        noise_classification.get("evidence_grade") or "static_seed_only"
    )
    noise_synthetic_ok = bool(noise_classification.get("noise_synthetic_ok"))
    noise_live_verified = bool(noise_classification.get("noise_live_verified"))
    noise_synthetic_status = noise_classification.get("synthetic_status") or "FAIL"
    noise_live_status = noise_classification.get("live_status") or "UNVERIFIED"
    noise_mechanism = noise_classification.get("mechanism")

    # CI mechanism catalog: Synthetic can PASS while Live stays unverified.
    # Informational only — does NOT claim the workflow implements a mechanism.
    noise_mechanism_contracts = evaluate_all_mechanism_synthetic_acceptances()

    structural_codes = {
        FAILURE_COMFY_NODE_MISSING,
        FAILURE_MODEL_MISMATCH,
        "E_UI_API_VALUE_MISMATCH",
        "E_BACKEND_MODEL_INVENTORY",
        "E_BACKEND_MODEL_CAPTURE",
    }
    structural_fail = [
        c for c in checks if c["code"] in structural_codes and c["status"] == "FAIL"
    ]
    inventory_status = "FAIL_STATIC_INVENTORY" if structural_fail else "PASS_STATIC_INVENTORY"

    # Hard rule: never unlock execution / maturity from static audit alone.
    report: dict[str, Any] = {
        "schema": AUDIT_SCHEMA,
        "method_id": METHOD_ID,
        "maturity_remains": MATURITY,
        "execution_allowed": False,
        "inventory_status": inventory_status,
        "overall_status": "BLOCKED_WORKFLOW_CANDIDATE",
        "sources": sources,
        "inventories": {
            ("ui" if inv["format"] == "ui_graph" else "api"): {
                "format": inv["format"],
                "node_count": inv["node_count"],
                "class_counts": inv["class_counts"],
                "models": inv["models"],
                "clip_text_encodes": inv.get("clip_text_encodes"),
                "noise_nodes": inv.get("noise_nodes"),
                "has_ige_tile_noise_mask": inv.get("has_ige_tile_noise_mask"),
                "has_set_latent_noise_mask": inv.get("has_set_latent_noise_mask"),
                "has_ttp_tile_batch": inv.get("has_ttp_tile_batch"),
                **(
                    {
                        "distinct_guider_conditioning_refs": inv.get("distinct_guider_conditioning_refs"),
                        "guider_conditionings": inv.get("guider_conditionings"),
                    }
                    if inv["format"] == "api_prompt"
                    else {}
                ),
            }
            for inv in inventories
        },
        "checks": checks,
        "noise_field_kind": noise_field_kind,
        "noise_field_reason": noise_field_detail,
        "noise_evidence_grade": noise_evidence_grade,
        "noise_synthetic_ok": noise_synthetic_ok,
        "noise_live_verified": noise_live_verified,
        "noise_synthetic_status": noise_synthetic_status,
        "noise_live_status": noise_live_status,
        "noise_mechanism": noise_mechanism,
        "noise_mechanism_contracts": {
            "noise_synthetic_ok": noise_mechanism_contracts.get("noise_synthetic_ok"),
            "noise_live_verified": False,
            "synthetic_status": noise_mechanism_contracts.get("synthetic_status"),
            "live_status": "UNVERIFIED",
            "note": noise_mechanism_contracts.get("note"),
            "mechanisms": {
                mid: {
                    "synthetic_status": m.get("synthetic_status"),
                    "live_status": "UNVERIFIED",
                    "noise_synthetic_ok": m.get("noise_synthetic_ok"),
                    "noise_live_verified": False,
                    "architectural_vs_seed_tweak": m.get("architectural_vs_seed_tweak"),
                    "title": m.get("title"),
                    "cost_notes": m.get("cost_notes"),
                }
                for mid, m in (noise_mechanism_contracts.get("mechanisms") or {}).items()
            },
        },
        "structural_blockers": [c["code"] for c in structural_fail],
        "remaining_live_blockers": [
            "Declared inventory ≠ disk capture; even a capture receipt still requires live ComfyUI load + runtime node proof.",
            "Live proof that each tile's conditioning is independently routed (not only static prompts).",
            "Coordinate-consistent global noise field live proof (noise_live_verified; shared_seed_only ≠ coordinate_indexed; synthetic_pass ≠ live_pass; see docs/GLOBAL_NOISE_FIELD_CONTRACT.md).",
            "Core-only write / halo non-write / full coverage on real GPU outputs.",
            "Independent S7 acceptance on real GPU outputs.",
            "Method Registry maturity promotion is out of scope for this static audit.",
        ],
        "non_claims": [
            "No GPU inference was run.",
            "No Siax / Flux weights were loaded into a runtime for inference.",
            "Optional --model-inventory is evidence_grade=declared_record only; it does not prove CI re-hashed operator PC weights.",
            "Optional --capture-receipt is evidence_grade=disk_capture; still never sets execution_allowed=true.",
            "Per-tile CLIPTextEncode text is static evidence only.",
            "Same RandomNoise seed is classified as noise_field_kind=shared_seed_only and is not a global noise-field proof.",
            "noise_synthetic_ok (synthetic_contract / CI) ≠ noise_live_verified (live_capture); CI never sets live true here.",
            "noise_mechanism_contracts Synthetic PASS is CI catalog coverage only — not workflow live noise proof.",
            "FLUX_HR_TILE_IMG2IMG remains workflow_candidate; execution_allowed=false.",
            "This audit does not modify Method Registry edit_permission.",
            "ae.safetensors SHA (when inventoried) does not claim equivalence to ae.sft.",
        ],
    }
    if backend_inventory_summary is not None:
        report["backend_model_inventory"] = backend_inventory_summary
    return report


def structural_inventory_ok(report: Mapping[str, Any]) -> bool:
    return report.get("inventory_status") == "PASS_STATIC_INVENTORY"
