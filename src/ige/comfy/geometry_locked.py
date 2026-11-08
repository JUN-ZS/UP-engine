"""Fail-closed SHQ geometry-bound, core-only image composition.

This module performs the local S6 pixel write-back after Comfy has produced
per-tile candidates. It never runs a model and never grants S3 permission.
"""
from __future__ import annotations

import hashlib
import re
from pathlib import Path
from typing import Any, Mapping, Sequence

import numpy as np
from PIL import Image, ImageDraw

from .tile_core_halo_ledger import LEDGER_SCHEMA, audit_ledger, ledger_passes


class GeometryLockedError(ValueError):
    """Raised when geometry, permission, tile output, or S6 evidence is invalid."""


def sha256_file(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _bounds(value: Any, label: str) -> tuple[int, int, int, int]:
    if not isinstance(value, (list, tuple)) or len(value) != 4:
        raise GeometryLockedError(f"{label} must be [x0,y0,x1,y1]")
    if any(type(v) is not int for v in value):
        raise GeometryLockedError(f"{label} coordinates must be integers")
    x0, y0, x1, y1 = value
    if x0 < 0 or y0 < 0 or x1 <= x0 or y1 <= y0:
        raise GeometryLockedError(f"{label} has invalid half-open bounds: {value}")
    return x0, y0, x1, y1


def _inside(bounds: tuple[int, int, int, int], width: int, height: int, label: str) -> None:
    x0, y0, x1, y1 = bounds
    if x1 > width or y1 > height:
        raise GeometryLockedError(f"{label} exceeds canvas {width}x{height}: {bounds}")


def _load_rgb_or_rgba(path: str | Path, label: str) -> Image.Image:
    try:
        with Image.open(path) as image:
            mode = "RGBA" if "A" in image.getbands() else "RGB"
            return image.convert(mode)
    except Exception as exc:
        raise GeometryLockedError(f"cannot decode {label} image {path}: {exc}") from exc


def _load_binary_mask(
    path: str | Path, size: tuple[int, int], label: str, *, require_nonempty: bool = True
) -> Image.Image:
    try:
        with Image.open(path) as image:
            mask = image.convert("L")
    except Exception as exc:
        raise GeometryLockedError(f"cannot decode {label} mask {path}: {exc}") from exc
    if mask.size != size:
        raise GeometryLockedError(f"{label} mask dimensions {mask.size} do not match canvas {size}")
    values = set(int(x) for x in np.unique(np.asarray(mask, dtype=np.uint8)))
    if not values.issubset({0, 255}):
        raise GeometryLockedError(f"{label} mask must be binary (0 or 255); got {sorted(values)[:8]}")
    if require_nonempty and 255 not in values:
        raise GeometryLockedError(f"{label} mask is empty")
    return mask


def _coverage_mask(size: tuple[int, int], rects: Sequence[Any]) -> Image.Image:
    width, height = size
    result = Image.new("L", size, 0)
    draw = ImageDraw.Draw(result)
    for index, raw in enumerate(rects):
        x0, y0, x1, y1 = _bounds(raw, f"coverage_target.rects[{index}]")
        _inside((x0, y0, x1, y1), width, height, f"coverage_target.rects[{index}]")
        # Rectangles describe the authorized S6 work envelope; no per-pixel
        # Python objects are created. Pillow's C implementation fills the area.
        draw.rectangle((x0, y0, x1 - 1, y1 - 1), fill=255)
    return result


def validate_geometry_tile_plan(
    plan: Mapping[str, Any],
    *,
    canvas_size: tuple[int, int],
    canvas_sha256: str,
) -> dict[str, Any]:
    if plan.get("schema") != "ige-comfy-tile-plan/0.1":
        raise GeometryLockedError("tile plan schema must be ige-comfy-tile-plan/0.1")
    coordinate_frame = plan.get("coordinate_frame")
    if not isinstance(coordinate_frame, str) or not coordinate_frame.strip():
        raise GeometryLockedError("tile plan coordinate_frame is required")
    coverage = plan.get("coverage_target")
    rects = coverage.get("rects") if isinstance(coverage, Mapping) else None
    if not isinstance(rects, list) or not rects:
        raise GeometryLockedError("tile plan coverage_target.rects must be non-empty")
    width, height = canvas_size
    checked_rects = []
    for index, raw in enumerate(rects):
        rect = _bounds(raw, f"coverage_target.rects[{index}]")
        _inside(rect, width, height, f"coverage_target.rects[{index}]")
        checked_rects.append(list(rect))
    raw_tiles = plan.get("tiles")
    if not isinstance(raw_tiles, list) or not raw_tiles:
        raise GeometryLockedError("tile plan must contain at least one tile")
    checked_tiles: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    seen_nodes: set[str] = set()
    for index, item in enumerate(raw_tiles):
        if not isinstance(item, Mapping):
            raise GeometryLockedError(f"tiles[{index}] must be an object")
        tile_id = item.get("tile_id")
        node_id = item.get("input_node_id")
        if (
            not isinstance(tile_id, str)
            or not re.fullmatch(r"[A-Za-z0-9_.-]{1,64}", tile_id)
            or tile_id in {".", ".."}
            or tile_id in seen_ids
        ):
            raise GeometryLockedError(
                f"tiles[{index}].tile_id must be unique, 1-64 safe filename characters"
            )
        if not isinstance(node_id, str) or not node_id.strip() or node_id in seen_nodes:
            raise GeometryLockedError(f"tiles[{index}].input_node_id must be unique and non-empty")
        seen_ids.add(tile_id)
        seen_nodes.add(node_id)
        read = _bounds(item.get("read_bounds"), f"tiles[{index}].read_bounds")
        core = _bounds(item.get("core_bounds"), f"tiles[{index}].core_bounds")
        _inside(read, width, height, f"tiles[{index}].read_bounds")
        _inside(core, width, height, f"tiles[{index}].core_bounds")
        if not (read[0] <= core[0] and read[1] <= core[1] and core[2] <= read[2] and core[3] <= read[3]):
            raise GeometryLockedError(f"tiles[{index}].core_bounds must be contained by read_bounds")
        tile = {
            "tile_id": tile_id,
            "input_node_id": node_id,
            "read_bounds": list(read),
            "core_bounds": list(core),
        }
        if item.get("halo_bounds") is not None:
            halo = _bounds(item.get("halo_bounds"), f"tiles[{index}].halo_bounds")
            _inside(halo, width, height, f"tiles[{index}].halo_bounds")
            if not (read[0] <= halo[0] and read[1] <= halo[1] and halo[2] <= read[2] and halo[3] <= read[3]):
                raise GeometryLockedError(f"tiles[{index}].halo_bounds must be contained by read_bounds")
            tile["halo_bounds"] = list(halo)
        input_record = item.get("input")
        if input_record is not None:
            if not isinstance(input_record, Mapping) or not isinstance(input_record.get("path"), str) or not isinstance(input_record.get("sha256"), str):
                raise GeometryLockedError(f"tiles[{index}].input must contain path and sha256")
            tile["input"] = {"path": input_record["path"], "sha256": input_record["sha256"]}
        checked_tiles.append(tile)

    ledger = {
        "schema": LEDGER_SCHEMA,
        "coordinate_frame": coordinate_frame,
        "canvas_sha256": canvas_sha256,
        "canvas_size_wh": [width, height],
        "coverage_target": {"kind": "rect_union", "rects": checked_rects},
        "tiles": [
            {
                **tile,
                "output_sha256": "0" * 64,
                "wrote_halo": False,
                "halo_write_pixels": 0,
            }
            for tile in checked_tiles
        ],
        "non_claims": ["Plan validation is geometry-only; no model has run and no pixels have been composed."],
    }
    audit = audit_ledger(
        ledger,
        s2_geometry={"coordinate_frame": coordinate_frame, "canvas_sha256": canvas_sha256},
        require_s2_bind=True,
    )
    if not ledger_passes(audit):
        raise GeometryLockedError(
            "tile plan fails exact-once Core/Halo geometry audit: " + ",".join(audit.get("blockers") or [])
        )
    return {
        "schema": plan["schema"],
        "coordinate_frame": coordinate_frame,
        "coverage_target": {"kind": "rect_union", "rects": checked_rects},
        "tiles": checked_tiles,
    }


def _assert_mask_inside_coverage(approved: Image.Image, coverage: Image.Image) -> None:
    approved_arr = np.asarray(approved, dtype=np.uint8) == 255
    covered_arr = np.asarray(coverage, dtype=np.uint8) == 255
    outside_count = int(np.count_nonzero(approved_arr & ~covered_arr))
    if outside_count:
        raise GeometryLockedError(
            f"approved edit mask has {outside_count} pixels outside the tile core coverage target"
        )


def compose_core_only_master(
    *,
    base_canvas_path: str | Path,
    approved_mask_path: str | Path,
    protected_mask_path: str | Path,
    tile_plan: Mapping[str, Any],
    tile_outputs: Sequence[Mapping[str, Any]],
    canvas_sha256: str,
    output_path: str | Path,
    overwrite: bool = False,
) -> dict[str, Any]:
    """Paste only each tile's disjoint core and only where S3 approved pixels exist."""
    base_path = Path(base_canvas_path)
    if sha256_file(base_path).lower() != canvas_sha256.lower():
        raise GeometryLockedError("base canvas SHA changed after S2 geometry was frozen")
    base = _load_rgb_or_rgba(base_path, "base canvas")
    size = base.size
    width, height = size
    validated_plan = validate_geometry_tile_plan(
        tile_plan, canvas_size=size, canvas_sha256=canvas_sha256
    )
    approved = _load_binary_mask(approved_mask_path, size, "approved edit")
    protected = _load_binary_mask(protected_mask_path, size, "protected", require_nonempty=False)
    approved_arr = np.asarray(approved, dtype=np.uint8) == 255
    protected_arr = np.asarray(protected, dtype=np.uint8) == 255
    overlap = int(np.count_nonzero(approved_arr & protected_arr))
    if overlap:
        raise GeometryLockedError(f"approved and protected masks overlap at {overlap} pixels")
    coverage = _coverage_mask(size, validated_plan["coverage_target"]["rects"])
    _assert_mask_inside_coverage(approved, coverage)

    expected = {tile["tile_id"]: tile for tile in validated_plan["tiles"]}
    supplied: dict[str, Mapping[str, Any]] = {}
    for record in tile_outputs:
        tile_id = record.get("tile_id")
        if not isinstance(tile_id, str) or tile_id not in expected:
            raise GeometryLockedError(f"unexpected tile output id: {tile_id!r}")
        if tile_id in supplied:
            raise GeometryLockedError(f"duplicate tile output for {tile_id}")
        supplied[tile_id] = record
    missing = sorted(set(expected) - set(supplied))
    if missing:
        raise GeometryLockedError(f"missing tile output(s): {missing}")

    ledger_tiles: list[dict[str, Any]] = []
    resolved_outputs: dict[str, tuple[Image.Image, Path, str]] = {}
    for tile_id, tile in expected.items():
        record = supplied[tile_id]
        output_path_value = record.get("path") or record.get("output_path")
        if not isinstance(output_path_value, (str, Path)):
            raise GeometryLockedError(f"tile {tile_id} output path is missing")
        output_file = Path(output_path_value)
        if not output_file.is_file():
            raise GeometryLockedError(f"tile {tile_id} output file does not exist: {output_file}")
        output_sha = sha256_file(output_file)
        declared_sha = record.get("sha256") or record.get("output_sha256")
        if not isinstance(declared_sha, str) or declared_sha.lower() != output_sha.lower():
            raise GeometryLockedError(f"tile {tile_id} output SHA mismatch")
        image = _load_rgb_or_rgba(output_file, f"tile {tile_id} output")
        rx0, ry0, rx1, ry1 = tile["read_bounds"]
        expected_size = (rx1 - rx0, ry1 - ry0)
        if image.size != expected_size:
            raise GeometryLockedError(
                f"tile {tile_id} output size {image.size} != read crop size {expected_size}; resizing is forbidden"
            )
        resolved_outputs[tile_id] = (image, output_file, output_sha)
        ledger_tiles.append({
            "tile_id": tile_id,
            "read_bounds": tile["read_bounds"],
            "core_bounds": tile["core_bounds"],
            **({"halo_bounds": tile["halo_bounds"]} if "halo_bounds" in tile else {}),
            "output_sha256": output_sha,
            "wrote_halo": False,
            "halo_write_pixels": 0,
            "write_receipt": {
                "wrote_core": True,
                "wrote_halo": False,
                "halo_write_pixels": 0,
                "write_kind": "local_pillow_core_crop_and_mask_paste",
            },
        })

    ledger = {
        "schema": LEDGER_SCHEMA,
        "coordinate_frame": validated_plan["coordinate_frame"],
        "canvas_sha256": canvas_sha256,
        "canvas_size_wh": [width, height],
        "coverage_target": validated_plan["coverage_target"],
        "tiles": ledger_tiles,
        "non_claims": [
            "Comfy emitted independent tile images; S6 composition ran locally after download.",
            "This local compositor does not prove coordinate-indexed global diffusion noise.",
            "This ledger does not verify Cloud model weight SHA or loaded tensor identity.",
            "S7 independent human acceptance is not performed by this compositor.",
        ],
    }
    ledger_audit = audit_ledger(
        ledger,
        s2_geometry={"coordinate_frame": validated_plan["coordinate_frame"], "canvas_sha256": canvas_sha256},
        require_s2_bind=True,
    )
    if not ledger_passes(ledger_audit):
        raise GeometryLockedError(
            "live tile output ledger failed: " + ",".join(ledger_audit.get("blockers") or [])
        )

    master = base.copy()
    for tile_id, tile in expected.items():
        image = resolved_outputs[tile_id][0]
        rx0, ry0, _, _ = tile["read_bounds"]
        cx0, cy0, cx1, cy1 = tile["core_bounds"]
        local = (cx0 - rx0, cy0 - ry0, cx1 - rx0, cy1 - ry0)
        core_image = image.crop(local).convert(master.mode)
        core_mask = approved.crop((cx0, cy0, cx1, cy1))
        master.paste(core_image, (cx0, cy0), core_mask)

    target = Path(output_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists() and not overwrite:
        raise GeometryLockedError(f"refusing to overwrite existing master: {target}")
    temporary = target.with_name(target.stem + ".tmp" + target.suffix)
    if temporary.exists():
        temporary.unlink()
    master.save(temporary, format="PNG")
    reloaded = _load_rgb_or_rgba(temporary, "reloaded candidate master")
    base_arr = np.asarray(base, dtype=np.uint8)
    output_arr = np.asarray(reloaded, dtype=np.uint8)
    diff = np.any(base_arr != output_arr, axis=2)
    outside_approved = int(np.count_nonzero(diff & ~approved_arr))
    protected_changed = int(np.count_nonzero(diff & protected_arr))
    changed_inside = int(np.count_nonzero(diff & approved_arr))
    if outside_approved or protected_changed:
        temporary.unlink(missing_ok=True)
        raise GeometryLockedError(
            f"pixel return audit failed: outside_approved={outside_approved}, protected_changed={protected_changed}"
        )
    temporary.replace(target)
    master_sha = sha256_file(target)
    return {
        "schema": "ige-comfy-shq-local-s6-composite-receipt/0.1",
        "status": "PASS_LOCAL_CORE_ONLY_COMPOSITOR",
        "master_path": str(target.resolve()),
        "master_sha256": master_sha,
        "width": width,
        "height": height,
        "tile_count": len(expected),
        "changed_pixels_inside_approved": changed_inside,
        "changed_pixels_outside_approved": outside_approved,
        "changed_pixels_in_protected": protected_changed,
        "outside_approved_pixel_return": "PASS",
        "protected_pixel_return": "PASS",
        "halo_write_pixels": 0,
        "halo_write_receipt": "LOCAL_CORE_ONLY_PASTE; HALO NOT WRITTEN",
        "ledger": ledger,
        "ledger_audit": ledger_audit,
        "evidence_grade": "runtime_instrumented_local_compositor",
        "execution_allowed": False,
        "edit_permission": False,
        "candidate_accepted": False,
        "s7_status": "NOT_PERFORMED",
        "non_claims": ledger["non_claims"],
    }
