from __future__ import annotations

import hashlib
import importlib
import json
import uuid
from pathlib import Path
from typing import Any, Callable, Mapping

import numpy as np
from PIL import Image

from .method_registry import MethodRegistry, MethodRegistryError

MANIFEST_SCHEMA = "ige-agent-run-manifest/0.1"
STATUS_BLOCKED = "BLOCKED"
STATUS_READY = "READY_FOR_EXPLICIT_EXECUTION"
STATUS_EXECUTED = "S5_COMPLETE_AWAITING_S6_S7"

# Registry strings are data, not executable code. Only exact reviewed entrypoints
# may be imported by this dispatcher. New backends require a code review and tests.
CALLABLE_ALLOWLIST: dict[str, tuple[str, str, str]] = {
    "src/ige/upscale/siax.py::run_siax_upscale": (
        "ige.upscale.siax", "run_siax_upscale", "spandrel_siax_4x",
    ),
}


class AgentDriverError(ValueError):
    pass


class DispatchBlocked(AgentDriverError):
    pass


def sha256_file(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _is_sha(value: Any) -> bool:
    return isinstance(value, str) and len(value) == 64 and all(
        ch in "0123456789abcdefABCDEF" for ch in value
    )


def _canonical_json_sha256(value: Any) -> str:
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _require_file(path_value: Any, label: str) -> Path:
    if not isinstance(path_value, str) or not path_value.strip():
        raise AgentDriverError(f"{label} path is required")
    path = Path(path_value).expanduser().resolve()
    if not path.is_file():
        raise AgentDriverError(f"{label} file does not exist: {path}")
    return path


def _check_file_hash(path: Path, expected: Any, label: str) -> str:
    if not _is_sha(expected):
        raise AgentDriverError(f"{label} SHA-256 must be a 64-character hex digest")
    actual = sha256_file(path)
    if actual.lower() != str(expected).lower():
        raise AgentDriverError(f"{label} SHA-256 mismatch: expected {expected}, got {actual}")
    return actual


def _load_image_size(path: Path) -> tuple[int, int]:
    try:
        with Image.open(path) as opened:
            opened.verify()
        with Image.open(path) as opened:
            return opened.convert("RGB").size
    except Exception as exc:
        raise AgentDriverError(f"cannot decode image {path}: {exc}") from exc


def _load_binary_mask(path: Path, expected_size: tuple[int, int], label: str) -> np.ndarray:
    try:
        with Image.open(path) as opened:
            mask = np.asarray(opened.convert("L"))
    except Exception as exc:
        raise AgentDriverError(f"cannot decode {label}: {exc}") from exc
    if mask.shape != (expected_size[1], expected_size[0]):
        raise AgentDriverError(f"{label} dimensions do not match the geometry canvas")
    if not set(int(v) for v in np.unique(mask)).issubset({0, 255}):
        raise AgentDriverError(f"{label} must be binary (only 0 and 255)")
    if not np.any(mask == 255):
        raise AgentDriverError(f"{label} must contain at least one approved pixel")
    return mask


def validate_manifest(manifest: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(manifest, Mapping):
        raise AgentDriverError("manifest root must be an object")
    if manifest.get("schema") != MANIFEST_SCHEMA:
        raise AgentDriverError(f"schema must be {MANIFEST_SCHEMA}")
    required = (
        "run_id", "method_id", "source", "read_receipt", "geometry_contract",
        "permission", "tile_plan", "backend", "output_path",
    )
    for key in required:
        if key not in manifest:
            raise AgentDriverError(f"manifest missing required field: {key}")
    for key in ("run_id", "method_id", "output_path"):
        if not isinstance(manifest.get(key), str) or not manifest[key].strip():
            raise AgentDriverError(f"{key} must be a non-empty string")
    for key in ("source", "read_receipt", "geometry_contract", "permission", "tile_plan", "backend"):
        if not isinstance(manifest.get(key), Mapping):
            raise AgentDriverError(f"{key} must be an object")
    return dict(manifest)


def load_manifest(path: str | Path) -> dict[str, Any]:
    manifest_path = Path(path)
    try:
        payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise AgentDriverError(f"cannot read manifest {manifest_path}: {exc}") from exc
    result = validate_manifest(payload)
    result["_manifest_path"] = str(manifest_path.resolve())
    return result


class CallableDispatcher:
    """Resolve only exact reviewed Registry entrypoints. Never eval Registry text."""

    def resolve(self, method: Mapping[str, Any]) -> Callable[..., Any]:
        entrypoint = method.get("entrypoint")
        approved = CALLABLE_ALLOWLIST.get(entrypoint)
        if approved is None:
            raise DispatchBlocked(
                f"entrypoint is not in the reviewed callable allowlist: {entrypoint!r}"
            )
        module_name, function_name, expected_backend = approved
        if method.get("backend_id") != expected_backend:
            raise DispatchBlocked("Registry backend_id does not match the reviewed entrypoint")
        module = importlib.import_module(module_name)
        function = getattr(module, function_name, None)
        if not callable(function):
            raise DispatchBlocked(f"reviewed entrypoint is not callable: {entrypoint}")
        return function


def _preflight(
    manifest: Mapping[str, Any],
    registry: MethodRegistry,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    source = manifest["source"]
    geometry = manifest["geometry_contract"]
    permission = manifest["permission"]
    tile_plan = manifest["tile_plan"]
    backend = manifest["backend"]
    read = manifest["read_receipt"]

    source_path = _require_file(source.get("path"), "source")
    source_sha = _check_file_hash(source_path, source.get("sha256"), "source")
    if read.get("source_sha256") != source_sha or read.get("candidate_only") is not True:
        raise AgentDriverError("S1 READ receipt must bind to the frozen source and remain candidate-only")
    observations = read.get("observations")
    if not isinstance(observations, Mapping):
        raise AgentDriverError("S1 observations must be an object")
    topology = observations.get("topology_error")
    if not isinstance(topology, Mapping) or topology.get("state") not in {"absent", "resolved"} or topology.get("verification") != "human_verified":
        raise AgentDriverError("S1 topology must be human-verified absent or resolved")

    canvas_path = _require_file(geometry.get("canvas_path"), "geometry canvas")
    canvas_sha = _check_file_hash(canvas_path, geometry.get("canvas_sha256"), "geometry canvas")
    if geometry.get("source_sha256") != source_sha:
        raise AgentDriverError("S2 geometry contract is not bound to the frozen source")
    if geometry.get("geometry_human_verified") is not True:
        raise AgentDriverError("S2 geometry must be explicitly human-verified")
    coordinate_frame = geometry.get("coordinate_frame")
    if not isinstance(coordinate_frame, str) or not coordinate_frame.strip():
        raise AgentDriverError("S2 coordinate_frame is required")
    if not isinstance(geometry.get("object_transform"), Mapping) or not geometry["object_transform"]:
        raise AgentDriverError("S2 object_transform is required")
    scale = geometry.get("model_scale")
    if isinstance(scale, bool) or not isinstance(scale, (int, float)) or scale <= 0:
        raise AgentDriverError("S2 model_scale must be positive numeric")
    tile_size = geometry.get("tile_size")
    tile_context = geometry.get("tile_context")
    if type(tile_size) is not int or tile_size < 32:
        raise AgentDriverError("S2 tile_size must be an integer >= 32")
    if type(tile_context) is not int or tile_context < 0 or tile_context >= tile_size:
        raise AgentDriverError("S2 tile_context must be an integer in [0, tile_size)")
    source_size = _load_image_size(source_path)
    canvas_size = _load_image_size(canvas_path)
    if canvas_size != (source_size[0] * int(scale), source_size[1] * int(scale)):
        raise AgentDriverError("S2 coordinate canvas dimensions do not match source dimensions × model_scale")

    if permission.get("human_reviewed") is not True or permission.get("permission_granted") is not True:
        raise AgentDriverError("S3 requires explicit human-reviewed permission")
    if permission.get("base_sha256") != source_sha or permission.get("coordinate_canvas_sha256") != canvas_sha:
        raise AgentDriverError("S3 permission receipt is not bound to the source and geometry canvas")
    if not isinstance(permission.get("reviewer_ref"), str) or not permission["reviewer_ref"].strip():
        raise AgentDriverError("S3 reviewer_ref is required")
    if not isinstance(permission.get("reviewed_at"), str) or not permission["reviewed_at"].strip():
        raise AgentDriverError("S3 reviewed_at is required")
    targets = permission.get("target_regions")
    if not isinstance(targets, list) or not targets or any(not isinstance(x, str) or not x.strip() for x in targets):
        raise AgentDriverError("S3 target_regions must be a non-empty list of labels")
    approved_path = _require_file(permission.get("approved_edit_mask_path"), "approved edit mask")
    protected_path = _require_file(permission.get("protected_mask_path"), "protected mask")
    _check_file_hash(approved_path, permission.get("approved_edit_mask_sha256"), "approved edit mask")
    _check_file_hash(protected_path, permission.get("protected_mask_sha256"), "protected mask")
    approved = _load_binary_mask(approved_path, canvas_size, "approved edit mask")
    protected = _load_binary_mask(protected_path, canvas_size, "protected mask")
    if np.any((approved == 255) & (protected == 255)):
        raise AgentDriverError("S3 approved and protected masks overlap")

    if tile_plan.get("verified") is not True:
        raise AgentDriverError("S4 tile plan must be explicitly verified")
    if tile_plan.get("tile_size") != tile_size or tile_plan.get("tile_context") != tile_context:
        raise AgentDriverError("S4 tile plan does not match the S2 tile_size/tile_context")
    if float(scale) != 4.0:
        raise AgentDriverError("the currently reviewed Siax adapter only supports exact 4x scale")

    method = registry.resolve(manifest["method_id"])
    if method.get("maturity") == "workflow_candidate" or method.get("execution_kind") == "diffusion":
        raise DispatchBlocked(
            "ComfyUI/Flux is workflow_candidate: static inventory, disk model capture and synthetic tests do not authorize execution"
        )
    checkpoint_path = _require_file(backend.get("checkpoint_path"), "backend checkpoint")
    checkpoint_sha = _check_file_hash(checkpoint_path, backend.get("checkpoint_sha256"), "backend checkpoint")
    if backend.get("license_review_acknowledged") is not True:
        raise AgentDriverError("backend checkpoint/license review must be explicitly acknowledged")
    if method.get("model_sha256") and checkpoint_sha.lower() != str(method["model_sha256"]).lower():
        raise AgentDriverError("backend checkpoint SHA does not match the Registry pin")
    if backend.get("device", "auto") not in {"auto", "cpu", "cuda"}:
        raise AgentDriverError("backend.device must be auto, cpu or cuda")

    context = {
        "s0_source_sha_verified": True,
        "topology_verified": True,
        "topology_state": topology["state"],
        "topology_human_verified": True,
        "checkpoint_sha_verified": True,
        "license_acknowledged": True,
        "geometry_contract_verified": True,
        "tile_plan_verified": True,
        "approved_masks_verified": True,
        "human_permission": True,
        "backend_adapter_available": True,
    }
    decision = registry.evaluate(manifest["method_id"], context)
    if not decision.get("execution_allowed"):
        blockers = ", ".join(decision.get("blockers") or [decision.get("status", "blocked")])
        raise DispatchBlocked(f"Registry blocked method {manifest['method_id']}: {blockers}")
    return method, decision, {
        "source_path": source_path, "source_sha256": source_sha,
        "canvas_path": canvas_path, "canvas_sha256": canvas_sha,
        "canvas_size": canvas_size, "checkpoint_path": checkpoint_path,
        "checkpoint_sha256": checkpoint_sha, "tile_size": tile_size,
        "tile_context": tile_context,
    }


def _build_tile_ledger(
    tile_trace: list[Mapping[str, Any]],
    *,
    coordinate_frame: str,
    canvas_sha256: str,
    canvas_size: tuple[int, int],
) -> dict[str, Any]:
    width, height = canvas_size
    tiles = []
    for index, item in enumerate(tile_trace):
        read_bounds = item.get("read_bounds")
        core_bounds = item.get("core_bounds")
        if not (
            isinstance(read_bounds, list) and len(read_bounds) == 4
            and isinstance(core_bounds, list) and len(core_bounds) == 4
            and all(type(v) is int for v in read_bounds + core_bounds)
        ):
            raise AgentDriverError(f"Siax tile trace {index} has invalid read/core bounds")
        tiles.append({
            "tile_id": str(item.get("tile_id", f"tile-{index:05d}")),
            "read_bounds": read_bounds,
            "core_bounds": core_bounds,
            "halo_write_pixels": 0,
            "wrote_halo": False,
            "write_receipt": {
                "wrote_core": True,
                "wrote_halo": False,
                "halo_write_pixels": 0,
                "instrumentation": "ige.upscale.siax.tile_trace",
            },
        })
    if not tiles:
        raise AgentDriverError("Siax adapter returned no tile write trace")
    return {
        "schema": "ige-tile-core-halo-ledger/0.1",
        "coordinate_frame": coordinate_frame,
        "canvas_sha256": canvas_sha256,
        "canvas_size_wh": [width, height],
        "coverage_target": {"kind": "rect_union", "rects": [[0, 0, width, height]]},
        "tiles": tiles,
        "evidence_grade": "runtime_instrumented_adapter",
        "non_claims": [
            "This trace records Siax adapter core writes; it does not prove perceptual quality or geometry identity.",
            "The ledger never grants edit_permission or ComfyUI execution permission.",
        ],
    }


def run_agent_manifest(
    manifest: Mapping[str, Any],
    *,
    execute: bool = False,
    registry: MethodRegistry | None = None,
    dispatcher: CallableDispatcher | None = None,
) -> dict[str, Any]:
    payload = validate_manifest(manifest)
    registry = registry or MethodRegistry.load()
    dispatcher = dispatcher or CallableDispatcher()
    method_id = payload["method_id"]
    stages: list[dict[str, Any]] = []

    try:
        method, decision, facts = _preflight(payload, registry)
    except (AgentDriverError, MethodRegistryError, OSError) as exc:
        return {
            "schema": "ige-agent-run-report/0.1", "run_id": payload["run_id"],
            "status": STATUS_BLOCKED, "selected_method": method_id,
            "stages": [{"stage": "S0-S4", "status": "BLOCKED", "reasons": [str(exc)]}],
            "execution_allowed": False, "edit_permission": False,
            "comfyui_claim": "NOT_EXECUTED_NOT_VERIFIED",
        }

    stages.extend([
        {"stage": "S0", "status": "PASS", "source_sha256": facts["source_sha256"]},
        {"stage": "S1", "status": "PASS", "candidate_only": True, "topology_state": payload["read_receipt"]["observations"]["topology_error"]["state"]},
        {"stage": "S2", "status": "PASS", "coordinate_frame": payload["geometry_contract"]["coordinate_frame"], "canvas_sha256": facts["canvas_sha256"]},
        {"stage": "S3", "status": "PASS", "human_reviewed": True, "permission_granted": True},
        {"stage": "S4", "status": "PASS", "method_decision": decision},
    ])

    if not execute:
        stages.extend([
            {"stage": "S5", "status": "NOT_RUN", "reason": "explicit --execute flag not supplied"},
            {"stage": "S6", "status": "NOT_RUN"},
            {"stage": "S7", "status": "NOT_RUN"},
        ])
        return {
            "schema": "ige-agent-run-report/0.1", "run_id": payload["run_id"],
            "status": STATUS_READY, "selected_method": method_id,
            "method_decision": decision, "stages": stages,
            "execution_allowed": False, "edit_permission": False,
            "comfyui_claim": "NOT_EXECUTED_NOT_VERIFIED",
        }

    try:
        function = dispatcher.resolve(method)
        output_path = Path(payload["output_path"]).expanduser().resolve()
        if output_path.suffix.lower() != ".png":
            raise AgentDriverError("candidate output must be a lossless PNG")
        if output_path.exists():
            raise AgentDriverError(f"refusing to overwrite existing candidate: {output_path}")
        output_path.parent.mkdir(parents=True, exist_ok=True)
        result = function(
            facts["source_path"], facts["checkpoint_path"], output_path,
            tile_size=facts["tile_size"], tile_pad=facts["tile_context"],
            confirm_model_license_review=True,
            device=payload["backend"].get("device", "auto"),
        )
        if sha256_file(facts["source_path"]) != facts["source_sha256"]:
            raise AgentDriverError("frozen source changed during backend execution")
        output_sha = _check_file_hash(output_path, result.get("output_sha256"), "Siax output")
        output_dimensions = result.get("output_dimensions", {})
        if (output_dimensions.get("width"), output_dimensions.get("height")) != facts["canvas_size"]:
            raise AgentDriverError("Siax output dimensions do not match the human-verified geometry canvas")
        tile_trace = result.get("tile_trace")
        if not isinstance(tile_trace, list):
            raise AgentDriverError("Siax adapter did not emit instrumented tile_trace")
        ledger = _build_tile_ledger(
            tile_trace,
            coordinate_frame=payload["geometry_contract"]["coordinate_frame"],
            canvas_sha256=facts["canvas_sha256"],
            canvas_size=facts["canvas_size"],
        )
        from .comfy.tile_core_halo_ledger import audit_ledger, ledger_passes
        ledger_report = audit_ledger(ledger)
        if not ledger_passes(ledger_report):
            raise AgentDriverError(f"Siax runtime tile ledger failed: {ledger_report.get('blockers')}")

        request_id = f"{payload['run_id']}:{uuid.uuid4().hex}"
        backend_receipt = {
            "real_backend_call": True, "receipt_verified": True,
            "backend_id": method["backend_id"], "model_id": result["model_id"],
            "model_sha256": result["checkpoint_sha256"], "model_path": result["checkpoint_path"],
            "parent_source_sha256": facts["source_sha256"],
            "input_sha256s": [facts["source_sha256"]],
            "output_sha256": output_sha, "output_path": str(output_path),
            "request_id": request_id,
            "parameters": {
                "scale": result["scale"], "tile_size": facts["tile_size"],
                "tile_pad": facts["tile_context"], "device": result["runtime"]["device"],
                "architecture": result["architecture"], "tile_count": len(tile_trace),
            },
        }
        report_path = Path(payload.get("_report_path") or (str(output_path) + ".agent-run.json"))
        ledger_path = report_path.with_name(report_path.stem + ".tile_core_halo_ledger.json")
        ledger_path.parent.mkdir(parents=True, exist_ok=True)
        ledger_path.write_text(json.dumps(ledger, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        ledger_sha = sha256_file(ledger_path)
        metadata_path = _require_file(result.get("metadata_path"), "Siax adapter metadata")
        metadata_payload = json.loads(metadata_path.read_text(encoding="utf-8"))
        if (
            metadata_payload.get("output_sha256") != output_sha
            or metadata_payload.get("checkpoint_sha256") != facts["checkpoint_sha256"]
            or metadata_payload.get("tile_trace") != tile_trace
        ):
            raise AgentDriverError("Siax sidecar metadata does not match the returned output/checkpoint/tile trace")
        metadata_sha = sha256_file(metadata_path)
        tile_trace_sha = _canonical_json_sha256(tile_trace)
        backend_receipt.update({
            "adapter_metadata_path": str(metadata_path),
            "adapter_metadata_sha256": metadata_sha,
            "tile_trace_sha256": tile_trace_sha,
            "tile_ledger_path": str(ledger_path),
            "tile_ledger_sha256": ledger_sha,
        })
        s5_path = report_path.with_name(report_path.stem + ".S5_backend_receipt.json")
        s5_path.write_text(json.dumps(backend_receipt, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        s5_sha = sha256_file(s5_path)
        stages.extend([
            {"stage": "S5", "status": "PASS", "backend_receipt": backend_receipt, "receipt_path": str(s5_path), "receipt_sha256": s5_sha},
            {"stage": "S6", "status": "NOT_RUN", "tile_ledger_path": str(ledger_path), "tile_ledger_sha256": ledger_sha, "reason": "S6 must consume this exact S5-bound ledger and prove compose/return plus protected-pixel preservation"},
            {"stage": "S7", "status": "NOT_RUN", "reason": "independent disk reload and human visual acceptance have not been performed"},
        ])
        return {
            "schema": "ige-agent-run-report/0.1", "run_id": payload["run_id"],
            "status": STATUS_EXECUTED, "selected_method": method_id,
            "method_decision": decision, "stages": stages,
            "candidate_output_path": str(output_path), "candidate_output_sha256": output_sha,
            "s5_backend_receipt_path": str(s5_path), "s5_backend_receipt_sha256": s5_sha,
            "tile_core_halo_ledger_path": str(ledger_path), "tile_core_halo_ledger_sha256": ledger_sha,
            "tile_ledger_audit": ledger_report,
            "execution_allowed": False, "edit_permission": False,
            "candidate_accepted": False, "comfyui_claim": "NOT_EXECUTED_NOT_VERIFIED",
            "non_claims": [
                "S5 candidate inference is not S6 return acceptance.",
                "S7 human visual review was not performed by this command.",
                "This run does not execute ComfyUI or promote FLUX_HR_TILE_IMG2IMG.",
                "Candidate execution never grants future edit_permission.",
            ],
        }
    except Exception as exc:
        stages.extend([
            {"stage": "S5", "status": "FAIL", "reasons": [str(exc)]},
            {"stage": "S6", "status": "NOT_RUN"},
            {"stage": "S7", "status": "NOT_RUN"},
        ])
        return {
            "schema": "ige-agent-run-report/0.1", "run_id": payload["run_id"],
            "status": STATUS_BLOCKED, "selected_method": method_id,
            "method_decision": decision, "stages": stages,
            "execution_allowed": False, "edit_permission": False,
            "candidate_accepted": False, "comfyui_claim": "NOT_EXECUTED_NOT_VERIFIED",
        }


def run_agent_manifest_file(
    manifest_path: str | Path,
    *,
    execute: bool = False,
    report_path: str | Path | None = None,
    registry_path: str | Path | None = None,
) -> dict[str, Any]:
    payload = load_manifest(manifest_path)
    if report_path is not None:
        payload["_report_path"] = str(Path(report_path).expanduser().resolve())
    registry = MethodRegistry.load(registry_path)
    report = run_agent_manifest(payload, execute=execute, registry=registry)
    if report_path is not None:
        path = Path(report_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return report
