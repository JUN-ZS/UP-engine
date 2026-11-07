"""Disk-capture receipts for ComfyUI weight inventories.

Produces provenance receipts by *reading files from disk* and streaming
SHA-256. Distinct from hand-authored declared inventory JSON.

Never runs ComfyUI / GPU inference, never sets execution_allowed=True, and
never promotes Method Registry maturity or edit_permission.
"""

from __future__ import annotations

import hashlib
import json
import platform
import socket
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any, Mapping, Sequence

from .model_inventory import (
    ModelInventoryError,
    assets_by_role,
    is_sha256,
    verify_against_workflow_audit,
    verify_siax_registry_pin,
)

CAPTURE_SCHEMA = "ige-model-inventory-capture-receipt/0.1"
RECEIPT_KIND = "model_inventory_capture"
EVIDENCE_GRADE_DISK = "disk_capture"
EVIDENCE_GRADE_DECLARED = "declared_record"
CAPTURE_TOOL = "ige.capture-model-inventory"
CAPTURE_TOOL_VERSION = "0.1.0"
ALGORITHM = "sha256"
DEFAULT_CHUNK_SIZE = 8 * 1024 * 1024  # 8 MiB — safe for ~24GB weights

# Default Dev FP8 + Siax set used by fixtures / PC ComfyUI layout.
DEFAULT_CAPTURE_ASSETS: tuple[dict[str, str], ...] = (
    {
        "asset_id": "SIAX4X",
        "role": "upscale",
        "relative_path": "upscale_models/4x_NMKD-Siax_200k.pth",
    },
    {
        "asset_id": "FLUX_AE",
        "role": "vae",
        "relative_path": "vae/ae.safetensors",
    },
    {
        "asset_id": "CLIP_L",
        "role": "clip",
        "relative_path": "clip/clip_l.safetensors",
    },
    {
        "asset_id": "T5XXL_FP16",
        "role": "clip",
        "relative_path": "clip/t5xxl_fp16.safetensors",
    },
    {
        "asset_id": "FLUX1_DEV",
        "role": "unet",
        "relative_path": "diffusion_models/flux1-dev.safetensors",
    },
)

_REQUIRED_TOP = (
    "schema",
    "receipt_kind",
    "evidence_grade",
    "capture_tool",
    "capture_tool_version",
    "package_version",
    "policy",
    "host",
    "models_root",
    "captured_at",
    "algorithm",
    "assets",
    "non_claims",
)
_REQUIRED_ASSET = (
    "asset_id",
    "role",
    "relative_path",
    "filename",
    "size_bytes",
    "sha256",
    "hashed_at",
)
_ALLOWED_ROLES = {"unet", "vae", "clip", "upscale", "other"}

DEFAULT_NON_CLAIMS: tuple[str, ...] = (
    "No ComfyUI / GPU inference was run during capture.",
    "Filenames and digests do not prove live ComfyUI load readiness.",
    "ae.safetensors SHA does not claim equivalence to ae.sft.",
    "Capture receipt never sets execution_allowed=true.",
    "Capture receipt does not promote FLUX_HR_TILE_IMG2IMG maturity.",
    "Registry edit_permission remains false.",
    "CI unit tests use tiny temporary files only; CI does not read operator PC weights.",
)


class CaptureInventoryError(ModelInventoryError):
    """Raised when disk capture or receipt validation fails (fail-closed)."""


def _hk_now_iso() -> str:
    """Asia/Hong_Kong (UTC+8) ISO-8601 timestamp."""
    tz = timezone(timedelta(hours=8), name="Asia/Hong_Kong")
    return datetime.now(tz).isoformat(timespec="seconds")


def _package_version() -> str:
    try:
        from ige import __version__

        return str(__version__)
    except Exception:  # pragma: no cover
        return "unknown"


def sha256_file_chunked(
    path: str | Path,
    *,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
) -> tuple[int, str]:
    """Stream SHA-256 of a file; returns (size_bytes, hex digest).

    Never loads the whole file into memory (supports ~24GB weights).
    """
    if chunk_size < 1:
        raise CaptureInventoryError("chunk_size must be >= 1")
    p = Path(path)
    if not p.is_file():
        raise CaptureInventoryError(f"not a file: {p}")
    digest = hashlib.sha256()
    size = 0
    with p.open("rb") as fh:
        while True:
            chunk = fh.read(chunk_size)
            if not chunk:
                break
            digest.update(chunk)
            size += len(chunk)
    st_size = p.stat().st_size
    if size != st_size:
        raise CaptureInventoryError(
            f"streamed size {size} != stat size {st_size} for {p}"
        )
    if size < 1:
        raise CaptureInventoryError(f"empty file forbidden: {p}")
    return size, digest.hexdigest()


def resolve_capture_specs(
    *,
    expect_relative: Sequence[str] | None = None,
    manifest: Mapping[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """Build the list of assets to capture.

    Priority: explicit manifest > --expect-relative paths matched against
    defaults (or synthesized) > full DEFAULT_CAPTURE_ASSETS.
    """
    if manifest is not None:
        assets = manifest.get("assets")
        if not isinstance(assets, list) or not assets:
            raise CaptureInventoryError("manifest.assets must be a non-empty array")
        out: list[dict[str, Any]] = []
        for i, raw in enumerate(assets):
            if not isinstance(raw, Mapping):
                raise CaptureInventoryError(f"manifest.assets[{i}] must be an object")
            rel = raw.get("relative_path")
            if not isinstance(rel, str) or not rel.strip():
                raise CaptureInventoryError(f"manifest.assets[{i}].relative_path required")
            role = raw.get("role") or "other"
            if role not in _ALLOWED_ROLES:
                raise CaptureInventoryError(f"manifest.assets[{i}].role invalid: {role}")
            asset_id = raw.get("asset_id") or Path(rel.replace("\\", "/")).stem.upper()
            item: dict[str, Any] = {
                "asset_id": str(asset_id),
                "role": str(role),
                "relative_path": rel.replace("\\", "/"),
            }
            if "expected_size_bytes" in raw:
                exp = raw["expected_size_bytes"]
                if not isinstance(exp, int) or isinstance(exp, bool) or exp < 1:
                    raise CaptureInventoryError(
                        f"manifest.assets[{i}].expected_size_bytes must be positive int"
                    )
                item["expected_size_bytes"] = exp
            out.append(item)
        return out

    if expect_relative:
        by_rel = {
            a["relative_path"].replace("\\", "/"): dict(a) for a in DEFAULT_CAPTURE_ASSETS
        }
        out = []
        for rel in expect_relative:
            norm = str(rel).replace("\\", "/")
            if norm in by_rel:
                out.append(dict(by_rel[norm]))
            else:
                name = Path(norm).name
                out.append(
                    {
                        "asset_id": Path(name).stem.upper().replace("-", "_"),
                        "role": "other",
                        "relative_path": norm,
                    }
                )
        return out

    return [dict(a) for a in DEFAULT_CAPTURE_ASSETS]


def capture_model_inventory(
    models_root: str | Path,
    *,
    expect_relative: Sequence[str] | None = None,
    manifest: Mapping[str, Any] | None = None,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    method_id_context: str | None = "FLUX_HR_TILE_IMG2IMG",
    load_options: Mapping[str, Any] | None = None,
    custom_nodes: Sequence[Mapping[str, Any]] | None = None,
    host_notes: str | None = None,
) -> dict[str, Any]:
    """Read each expected weight from disk, recompute size+SHA-256, build receipt.

    Fail-closed: any missing file / size mismatch aborts before writing a receipt.
    """
    root = Path(models_root).expanduser().resolve()
    if not root.is_dir():
        raise CaptureInventoryError(f"models_root is not a directory: {root}")

    specs = resolve_capture_specs(expect_relative=expect_relative, manifest=manifest)
    assets: list[dict[str, Any]] = []
    for spec in specs:
        rel = str(spec["relative_path"]).replace("\\", "/")
        # Prevent path escape outside models_root.
        target = (root / rel).resolve()
        try:
            target.relative_to(root)
        except ValueError as exc:
            raise CaptureInventoryError(f"relative_path escapes models_root: {rel}") from exc
        if not target.is_file():
            raise CaptureInventoryError(f"expected weight missing: {rel} (under {root})")

        expected_size = spec.get("expected_size_bytes")
        if expected_size is not None:
            st = target.stat().st_size
            if st != int(expected_size):
                raise CaptureInventoryError(
                    f"size mismatch for {rel}: stat={st} expected={expected_size}"
                )

        hashed_at = _hk_now_iso()
        size_bytes, digest = sha256_file_chunked(target, chunk_size=chunk_size)
        if expected_size is not None and size_bytes != int(expected_size):
            raise CaptureInventoryError(
                f"hashed size mismatch for {rel}: hashed={size_bytes} expected={expected_size}"
            )

        filename = Path(rel).name
        assets.append(
            {
                "asset_id": str(spec["asset_id"]),
                "role": str(spec["role"]),
                "relative_path": rel,
                "filename": filename,
                "size_bytes": size_bytes,
                "sha256": digest,
                "hashed_at": hashed_at,
                "absolute_path": str(target),
            }
        )

    receipt: dict[str, Any] = {
        "schema": CAPTURE_SCHEMA,
        "receipt_kind": RECEIPT_KIND,
        "evidence_grade": EVIDENCE_GRADE_DISK,
        "capture_tool": CAPTURE_TOOL,
        "capture_tool_version": CAPTURE_TOOL_VERSION,
        "package_version": _package_version(),
        "policy": "fail_closed",
        "host": {
            "hostname": socket.gethostname() or "unknown",
            "os": platform.system() or "unknown",
            "notes": host_notes
            or "Disk capture via ige capture-model-inventory; not a GPU run.",
        },
        "models_root": str(root),
        "captured_at": _hk_now_iso(),
        "algorithm": ALGORITHM,
        "chunk_size_bytes": chunk_size,
        "assets": assets,
        "custom_nodes": [dict(n) for n in (custom_nodes or [])],
        "load_options": dict(load_options or {"unet_weight_dtype": "fp8_e4m3fn_fast"}),
        "non_claims": list(DEFAULT_NON_CLAIMS),
    }
    if method_id_context:
        receipt["method_id_context"] = method_id_context

    errors = validate_capture_receipt(receipt)
    if errors:
        raise CaptureInventoryError("internal receipt invalid: " + "; ".join(errors))
    return receipt


def write_capture_receipt(receipt: Mapping[str, Any], out_path: str | Path) -> Path:
    errors = validate_capture_receipt(receipt)
    if errors:
        raise CaptureInventoryError("; ".join(errors))
    path = Path(out_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(dict(receipt), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


def validate_capture_receipt(data: Mapping[str, Any]) -> list[str]:
    """Schema + provenance validation for a disk-capture receipt."""
    errors: list[str] = []
    if not isinstance(data, Mapping):
        return ["capture receipt must be an object"]

    missing = [k for k in _REQUIRED_TOP if k not in data]
    if missing:
        errors.append(f"missing top-level fields: {missing}")

    if data.get("schema") != CAPTURE_SCHEMA:
        errors.append(f"schema must be {CAPTURE_SCHEMA}")
    if data.get("receipt_kind") != RECEIPT_KIND:
        errors.append(f"receipt_kind must be {RECEIPT_KIND}")
    if data.get("evidence_grade") != EVIDENCE_GRADE_DISK:
        errors.append(f"evidence_grade must be {EVIDENCE_GRADE_DISK}")
    if data.get("capture_tool") != CAPTURE_TOOL:
        errors.append(f"capture_tool must be {CAPTURE_TOOL}")
    if data.get("algorithm") != ALGORITHM:
        errors.append(f"algorithm must be {ALGORITHM}")
    if data.get("policy") != "fail_closed":
        errors.append("policy must be fail_closed")

    for key in ("capture_tool_version", "package_version", "models_root", "captured_at"):
        if key in data and (not isinstance(data.get(key), str) or not str(data.get(key)).strip()):
            errors.append(f"{key} must be a non-empty string")

    host = data.get("host")
    if host is not None:
        if not isinstance(host, Mapping):
            errors.append("host must be an object")
        elif not isinstance(host.get("hostname"), str) or not str(host.get("hostname")).strip():
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
        for key in ("filename", "relative_path", "hashed_at"):
            if key in asset and (not isinstance(asset.get(key), str) or not str(asset.get(key)).strip()):
                errors.append(f"{p}.{key} must be a non-empty string")
        size = asset.get("size_bytes")
        if "size_bytes" in asset and (not isinstance(size, int) or isinstance(size, bool) or size < 1):
            errors.append(f"{p}.size_bytes must be a positive integer")
        if "sha256" in asset and not is_sha256(asset.get("sha256")):
            errors.append(f"{p}.sha256 must be a 64-hex digest")
        rel = asset.get("relative_path")
        fn = asset.get("filename")
        if isinstance(rel, str) and isinstance(fn, str) and fn and not rel.replace("\\", "/").endswith(fn):
            errors.append(f"{p}.relative_path must end with filename {fn}")

    nodes = data.get("custom_nodes")
    if nodes is not None and not isinstance(nodes, list):
        errors.append("custom_nodes must be an array when present")

    non_claims = data.get("non_claims")
    if not isinstance(non_claims, list) or not non_claims:
        errors.append("non_claims must be a non-empty array of strings")
    elif any(not isinstance(x, str) or not x.strip() for x in non_claims):
        errors.append("non_claims entries must be non-empty strings")
    else:
        joined = " ".join(non_claims).lower()
        if "inference" not in joined:
            errors.append("non_claims must state that no inference was run")
        if "ae.sft" not in joined and "ae.safetensors" not in joined:
            errors.append("non_claims must address ae.safetensors ≠ ae.sft")

    return errors


def load_capture_receipt(path: str | Path) -> dict[str, Any]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    errors = validate_capture_receipt(payload)
    if errors:
        raise CaptureInventoryError("; ".join(errors))
    return dict(payload)


def receipt_as_inventory_view(receipt: Mapping[str, Any]) -> dict[str, Any]:
    """Project a capture receipt into the shape expected by filename/role helpers."""
    return {
        "schema": "ige-backend-model-inventory/0.1",
        "inventory_id": f"capture:{receipt.get('host', {}).get('hostname', 'unknown')}",
        "inventory_version": str(receipt.get("capture_tool_version") or "0"),
        "policy": "fail_closed",
        "host": dict(receipt.get("host") or {}),
        "models_root": receipt.get("models_root"),
        "hashed_at": receipt.get("captured_at"),
        "assets": [dict(a) for a in (receipt.get("assets") or [])],
        "custom_nodes": [dict(n) for n in (receipt.get("custom_nodes") or [])],
        "load_options": dict(receipt.get("load_options") or {}),
        "non_claims": list(receipt.get("non_claims") or []),
        "evidence_grade": EVIDENCE_GRADE_DISK,
        "receipt_kind": RECEIPT_KIND,
    }


def verify_capture_against_workflow(
    receipt: Mapping[str, Any],
    static_audit_report: Mapping[str, Any],
    *,
    registry: Any | None = None,
    required_roles: Sequence[str] | None = None,
) -> dict[str, Any]:
    """Filename/role match + Siax pin using a capture receipt."""
    view = receipt_as_inventory_view(receipt)
    return verify_against_workflow_audit(
        view,
        static_audit_report,
        registry=registry,
        required_roles=required_roles,
    )


def siax_matches_registry_pin(receipt_or_inventory: Mapping[str, Any], *, registry: Any | None = None) -> dict[str, Any]:
    """Compare SIAX4X SHA on a capture receipt or inventory view to Registry pin."""
    if receipt_or_inventory.get("receipt_kind") == RECEIPT_KIND:
        view = receipt_as_inventory_view(receipt_or_inventory)
    else:
        view = receipt_or_inventory
    return verify_siax_registry_pin(view, registry=registry)


def rehash_capture_receipt(
    receipt: Mapping[str, Any],
    *,
    models_root: str | Path | None = None,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
) -> dict[str, Any]:
    """Optional live re-hash against disk; fail-closed on any mismatch.

    Used by tests and future `--rehash` CLI. CI should only point this at
    tiny temporary files — never claim CI re-verified operator PC weights.
    """
    errors = validate_capture_receipt(receipt)
    if errors:
        raise CaptureInventoryError("; ".join(errors))
    root = Path(models_root or receipt["models_root"]).expanduser().resolve()
    mismatches: list[dict[str, Any]] = []
    for asset in receipt.get("assets") or []:
        rel = str(asset["relative_path"]).replace("\\", "/")
        target = (root / rel).resolve()
        try:
            target.relative_to(root)
        except ValueError:
            mismatches.append({"relative_path": rel, "error": "path_escape"})
            continue
        if not target.is_file():
            mismatches.append({"relative_path": rel, "error": "missing"})
            continue
        size, digest = sha256_file_chunked(target, chunk_size=chunk_size)
        if size != int(asset["size_bytes"]) or digest.lower() != str(asset["sha256"]).lower():
            mismatches.append(
                {
                    "relative_path": rel,
                    "error": "digest_or_size_mismatch",
                    "receipt_size": asset["size_bytes"],
                    "disk_size": size,
                    "receipt_sha256": asset["sha256"],
                    "disk_sha256": digest,
                }
            )
    return {
        "matched": not mismatches,
        "mismatches": mismatches,
        "models_root": str(root),
        "assets_checked": len(list(receipt.get("assets") or [])),
    }


def detect_inventory_kind(payload: Mapping[str, Any]) -> str:
    """Return 'capture_receipt' | 'declared_inventory' | 'unknown'."""
    if payload.get("receipt_kind") == RECEIPT_KIND or payload.get("evidence_grade") == EVIDENCE_GRADE_DISK:
        return "capture_receipt"
    if payload.get("schema") == "ige-backend-model-inventory/0.1":
        return "declared_inventory"
    return "unknown"
