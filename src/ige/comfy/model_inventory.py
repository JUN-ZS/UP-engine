"""Offline backend model inventory (filenames + SHA-256 + custom node packs).

Fail-closed helper for future preconditions. NEVER runs ComfyUI, NEVER loads
GPU weights, NEVER sets execution_allowed=True, and NEVER promotes Method
Registry maturity or edit_permission.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Mapping, Sequence

INVENTORY_SCHEMA = "ige-backend-model-inventory/0.1"
FAILURE_BACKEND_INVENTORY = "E_BACKEND_MODEL_INVENTORY"

# Workflow model keys declared by static UI/API audit → inventory roles.
ROLE_WORKFLOW_KEYS: dict[str, tuple[str, ...]] = {
    "unet": ("unet_name",),
    "vae": ("vae_name",),
    "clip": ("clip_name1", "clip_name2"),
    "upscale": ("upscale_model",),
}

# Dev FP8 Flux HR tile candidate expects these roles present in inventory.
DEFAULT_REQUIRED_ROLES: tuple[str, ...] = ("unet", "vae", "clip", "upscale")

SIAX_METHOD_ID = "SIAX4X_TILE_CORE_SR"
SIAX_ASSET_ID = "SIAX4X"
SIAX_FILENAME = "4x_NMKD-Siax_200k.pth"

_SHA = re.compile(r"^[0-9a-fA-F]{64}$")
_REQUIRED_TOP = (
    "schema",
    "inventory_id",
    "inventory_version",
    "policy",
    "host",
    "models_root",
    "hashed_at",
    "assets",
    "custom_nodes",
    "load_options",
    "non_claims",
)
_REQUIRED_ASSET = ("asset_id", "role", "filename", "relative_path", "size_bytes", "sha256")
_ALLOWED_ROLES = {"unet", "vae", "clip", "upscale", "other"}


class ModelInventoryError(ValueError):
    pass


def is_sha256(value: Any) -> bool:
    return isinstance(value, str) and _SHA.fullmatch(value) is not None


def _check(
    code: str,
    status: str,
    detail: str,
    *,
    evidence: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    item: dict[str, Any] = {"code": code, "status": status, "detail": detail}
    if evidence is not None:
        item["evidence"] = dict(evidence)
    return item


def validate_inventory_payload(data: Mapping[str, Any]) -> list[str]:
    errors: list[str] = []
    if not isinstance(data, Mapping):
        return ["inventory payload must be an object"]

    missing = [k for k in _REQUIRED_TOP if k not in data]
    if missing:
        errors.append(f"missing top-level fields: {missing}")

    if data.get("schema") != INVENTORY_SCHEMA:
        errors.append(f"schema must be {INVENTORY_SCHEMA}")
    if data.get("policy") != "fail_closed":
        errors.append("policy must be fail_closed")

    for key in ("inventory_id", "inventory_version", "models_root", "hashed_at"):
        if key in data and (not isinstance(data.get(key), str) or not str(data.get(key)).strip()):
            errors.append(f"{key} must be a non-empty string")

    host = data.get("host")
    if host is not None:
        if not isinstance(host, Mapping):
            errors.append("host must be an object")
        elif not isinstance(host.get("hostname"), str) or not host.get("hostname", "").strip():
            errors.append("host.hostname must be a non-empty string")

    assets = data.get("assets")
    if not isinstance(assets, list) or not assets:
        errors.append("assets must be a non-empty array")
        assets = []

    asset_ids: set[str] = set()
    for i, asset in enumerate(assets):
        p = f"assets[{i}]"
        if not isinstance(asset, Mapping):
            errors.append(f"{p} must be an object")
            continue
        for key in _REQUIRED_ASSET:
            if key not in asset:
                errors.append(f"{p} missing {key}")
        aid = asset.get("asset_id")
        if not isinstance(aid, str) or not aid.strip():
            errors.append(f"{p}.asset_id must be a non-empty string")
        elif aid in asset_ids:
            errors.append(f"duplicate asset_id: {aid}")
        else:
            asset_ids.add(aid)
        if asset.get("role") not in _ALLOWED_ROLES:
            errors.append(f"{p}.role must be one of {sorted(_ALLOWED_ROLES)}")
        for key in ("filename", "relative_path"):
            if key in asset and (not isinstance(asset.get(key), str) or not str(asset.get(key)).strip()):
                errors.append(f"{p}.{key} must be a non-empty string")
        size = asset.get("size_bytes")
        if "size_bytes" in asset and (not isinstance(size, int) or isinstance(size, bool) or size < 1):
            errors.append(f"{p}.size_bytes must be a positive integer")
        if "sha256" in asset and not is_sha256(asset.get("sha256")):
            errors.append(f"{p}.sha256 must be a 64-hex digest")
        # relative_path must end with filename when both present
        rel = asset.get("relative_path")
        fn = asset.get("filename")
        if isinstance(rel, str) and isinstance(fn, str) and fn and not rel.replace("\\", "/").endswith(fn):
            errors.append(f"{p}.relative_path must end with filename {fn}")

    nodes = data.get("custom_nodes")
    if nodes is None:
        errors.append("custom_nodes must be an array")
    elif not isinstance(nodes, list):
        errors.append("custom_nodes must be an array")
    else:
        for i, node in enumerate(nodes):
            p = f"custom_nodes[{i}]"
            if not isinstance(node, Mapping):
                errors.append(f"{p} must be an object")
                continue
            if not isinstance(node.get("pack_id"), str) or not node.get("pack_id", "").strip():
                errors.append(f"{p}.pack_id must be a non-empty string")
            if not isinstance(node.get("present"), bool):
                errors.append(f"{p}.present must be boolean")
            git_sha = node.get("git_sha", None)
            if git_sha is not None and not (isinstance(git_sha, str) and len(git_sha) >= 7):
                errors.append(f"{p}.git_sha must be null or a git SHA string")

    load_options = data.get("load_options")
    if load_options is not None and not isinstance(load_options, Mapping):
        errors.append("load_options must be an object")

    non_claims = data.get("non_claims")
    if not isinstance(non_claims, list) or not non_claims:
        errors.append("non_claims must be a non-empty array of strings")
    elif any(not isinstance(x, str) or not x.strip() for x in non_claims):
        errors.append("non_claims entries must be non-empty strings")

    return errors


def load_model_inventory(path: str | Path) -> dict[str, Any]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    errors = validate_inventory_payload(payload)
    if errors:
        raise ModelInventoryError("; ".join(errors))
    return dict(payload)


def assets_by_id(inventory: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for asset in inventory.get("assets") or []:
        if isinstance(asset, Mapping) and isinstance(asset.get("asset_id"), str):
            out[asset["asset_id"]] = dict(asset)
    return out


def assets_by_filename(inventory: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for asset in inventory.get("assets") or []:
        if isinstance(asset, Mapping) and isinstance(asset.get("filename"), str):
            out[asset["filename"]] = dict(asset)
    return out


def assets_by_role(inventory: Mapping[str, Any]) -> dict[str, list[dict[str, Any]]]:
    out: dict[str, list[dict[str, Any]]] = {}
    for asset in inventory.get("assets") or []:
        if not isinstance(asset, Mapping):
            continue
        role = asset.get("role")
        if not isinstance(role, str):
            continue
        out.setdefault(role, []).append(dict(asset))
    return out


def _workflow_models_from_audit(report: Mapping[str, Any]) -> dict[str, Any]:
    models: dict[str, Any] = {}
    inventories = report.get("inventories") or {}
    if isinstance(inventories, Mapping):
        for inv in inventories.values():
            if not isinstance(inv, Mapping):
                continue
            for key, value in (inv.get("models") or {}).items():
                if value is not None and key not in models:
                    models[key] = value
    return models


def verify_siax_registry_pin(
    inventory: Mapping[str, Any],
    *,
    registry: Any | None = None,
) -> dict[str, Any]:
    """Compare SIAX4X inventory SHA to Method Registry pin when both exist."""
    from ige.method_registry import MethodRegistry

    reg = registry if registry is not None else MethodRegistry.load()
    method = reg.resolve(SIAX_METHOD_ID)
    pinned = method.get("model_sha256")
    by_id = assets_by_id(inventory)
    by_name = assets_by_filename(inventory)
    asset = by_id.get(SIAX_ASSET_ID) or by_name.get(SIAX_FILENAME)
    evidence = {
        "method_id": SIAX_METHOD_ID,
        "registry_model_sha256": pinned,
        "inventory_asset_id": (asset or {}).get("asset_id"),
        "inventory_filename": (asset or {}).get("filename"),
        "inventory_sha256": (asset or {}).get("sha256"),
    }
    if not is_sha256(pinned):
        return {
            "status": "FAIL",
            "matched": False,
            "detail": f"registry pin for {SIAX_METHOD_ID} missing or invalid",
            "evidence": evidence,
        }
    if asset is None:
        return {
            "status": "FAIL",
            "matched": False,
            "detail": f"inventory missing Siax asset ({SIAX_ASSET_ID} / {SIAX_FILENAME})",
            "evidence": evidence,
        }
    actual = asset.get("sha256")
    if not is_sha256(actual):
        return {
            "status": "FAIL",
            "matched": False,
            "detail": "inventory Siax sha256 missing or invalid",
            "evidence": evidence,
        }
    if str(actual).lower() != str(pinned).lower():
        return {
            "status": "FAIL",
            "matched": False,
            "detail": "inventory Siax SHA-256 does not match Method Registry pin",
            "evidence": evidence,
        }
    return {
        "status": "PASS",
        "matched": True,
        "detail": "SIAX4X inventory SHA-256 exactly matches Method Registry pin",
        "evidence": evidence,
    }


def verify_against_workflow_audit(
    inventory: Mapping[str, Any],
    static_audit_report: Mapping[str, Any],
    *,
    registry: Any | None = None,
    required_roles: Sequence[str] | None = None,
) -> dict[str, Any]:
    """Match workflow filenames to inventory assets by role; pin-check Siax.

    Returns a check payload. Does NOT mutate maturity / execution_allowed.
    """
    roles = tuple(required_roles) if required_roles is not None else DEFAULT_REQUIRED_ROLES
    workflow_models = _workflow_models_from_audit(static_audit_report)
    by_role = assets_by_role(inventory)
    by_name = assets_by_filename(inventory)

    blockers: list[str] = []
    mismatches: list[dict[str, Any]] = []
    matched: list[dict[str, Any]] = []

    for role in roles:
        assets = by_role.get(role) or []
        if not assets:
            blockers.append(f"missing_required_role:{role}")
            continue
        keys = ROLE_WORKFLOW_KEYS.get(role, ())
        for key in keys:
            declared = workflow_models.get(key)
            if declared is None:
                # Upscale may be UI-only; if workflow omits it, still require inventory asset.
                if role == "upscale":
                    continue
                blockers.append(f"workflow_missing_model_key:{key}")
                continue
            asset = by_name.get(str(declared))
            if asset is None:
                blockers.append(f"inventory_missing_filename:{declared}")
                mismatches.append({"workflow_key": key, "declared": declared, "role": role})
                continue
            if asset.get("role") != role and role != "other":
                blockers.append(f"role_mismatch:{declared}:expected_{role}:got_{asset.get('role')}")
                mismatches.append(
                    {
                        "workflow_key": key,
                        "declared": declared,
                        "expected_role": role,
                        "inventory_role": asset.get("role"),
                    }
                )
                continue
            matched.append(
                {
                    "workflow_key": key,
                    "filename": declared,
                    "asset_id": asset.get("asset_id"),
                    "role": role,
                    "sha256": asset.get("sha256"),
                }
            )

    # weight_dtype load option vs workflow
    load_options = inventory.get("load_options") or {}
    dtype_inv = load_options.get("unet_weight_dtype") if isinstance(load_options, Mapping) else None
    dtype_wf = workflow_models.get("weight_dtype")
    dtype_ok = True
    if dtype_inv is not None and dtype_wf is not None and dtype_inv != dtype_wf:
        dtype_ok = False
        blockers.append(f"weight_dtype_mismatch:inventory={dtype_inv}:workflow={dtype_wf}")

    siax = verify_siax_registry_pin(inventory, registry=registry)
    if not siax["matched"]:
        blockers.append("siax_registry_pin_mismatch")

    status = "PASS" if not blockers else "FAIL"
    detail = (
        "offline inventory filenames/SHAs align with workflow model declarations and Siax registry pin"
        if status == "PASS"
        else f"backend model inventory blockers: {blockers}"
    )
    return _check(
        FAILURE_BACKEND_INVENTORY,
        status,
        detail,
        evidence={
            "blockers": blockers,
            "matched_assets": matched,
            "mismatches": mismatches,
            "workflow_models": workflow_models,
            "load_option_unet_weight_dtype": dtype_inv,
            "workflow_weight_dtype": dtype_wf,
            "weight_dtype_ok": dtype_ok,
            "siax_registry_pin": siax,
            "non_claims_echo": list(inventory.get("non_claims") or [])[:3],
        },
    )


def backend_model_inventory_verified(
    inventory: Mapping[str, Any],
    *,
    static_audit_report: Mapping[str, Any] | None = None,
    registry: Any | None = None,
    required_roles: Sequence[str] | None = None,
) -> dict[str, Any]:
    """Precondition helper: returns verified flag + blockers; never unlocks execution."""
    schema_errors = validate_inventory_payload(inventory)
    blockers: list[str] = [f"schema:{e}" for e in schema_errors]

    check: dict[str, Any] | None = None
    if static_audit_report is not None and not schema_errors:
        check = verify_against_workflow_audit(
            inventory,
            static_audit_report,
            registry=registry,
            required_roles=required_roles,
        )
        blockers.extend(list((check.get("evidence") or {}).get("blockers") or []))
    elif static_audit_report is None and not schema_errors:
        # Schema-only path still pin-checks Siax when registry available.
        siax = verify_siax_registry_pin(inventory, registry=registry)
        if not siax["matched"]:
            blockers.append("siax_registry_pin_mismatch")
        roles = tuple(required_roles) if required_roles is not None else DEFAULT_REQUIRED_ROLES
        by_role = assets_by_role(inventory)
        for role in roles:
            if not by_role.get(role):
                blockers.append(f"missing_required_role:{role}")

    verified = len(blockers) == 0
    return {
        "verified": verified,
        "blockers": blockers,
        "execution_allowed": False,
        "maturity_unchanged": True,
        "check": check,
        "non_claims": [
            "backend_model_inventory_verified never sets execution_allowed=true",
            "Inventory SHA recording does not promote FLUX_HR_TILE_IMG2IMG maturity",
            "Registry edit_permission remains false",
        ],
    }


def summarize_inventory(inventory: Mapping[str, Any]) -> dict[str, Any]:
    assets = []
    for asset in inventory.get("assets") or []:
        if not isinstance(asset, Mapping):
            continue
        assets.append(
            {
                "asset_id": asset.get("asset_id"),
                "role": asset.get("role"),
                "filename": asset.get("filename"),
                "relative_path": asset.get("relative_path"),
                "size_bytes": asset.get("size_bytes"),
                "sha256": asset.get("sha256"),
            }
        )
    nodes = []
    for node in inventory.get("custom_nodes") or []:
        if not isinstance(node, Mapping):
            continue
        nodes.append(
            {
                "pack_id": node.get("pack_id"),
                "present": node.get("present"),
                "git_sha": node.get("git_sha"),
            }
        )
    return {
        "inventory_id": inventory.get("inventory_id"),
        "inventory_version": inventory.get("inventory_version"),
        "host": (inventory.get("host") or {}).get("hostname")
        if isinstance(inventory.get("host"), Mapping)
        else None,
        "hashed_at": inventory.get("hashed_at"),
        "asset_count": len(assets),
        "assets": assets,
        "custom_node_count": len(nodes),
        "custom_nodes": nodes,
        "load_options": dict(inventory.get("load_options") or {}),
    }
