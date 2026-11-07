"""Core/Halo tile write-back ledger contract (offline / synthetic).

Normative rules:
- Each tile declares read_bounds (may include halo) and core_bounds (write region).
- Cores across the plan are pairwise disjoint.
- Union of cores equals the declared coverage_target (exact-once: no overlap, no gap).
- Halo is read-only: any receipt claiming halo writes → FAIL.
- core_bounds must be nested inside read_bounds (core ⊆ read).
- Ledger alone never grants edit_permission and never sets execution_allowed=true.

Aligned Registry / S6 codes:
- Umbrella: E_PR11_TILE_PLAN_CORE_HALO (GEOMETRY_LOCKED_TILE_PLAN_RETURN)
- Specific check codes: E_TILE_CORE_OVERLAP, E_TILE_COVERAGE_GAP,
  E_TILE_HALO_WRITE, E_TILE_CORE_NOT_SUBSET_READ, E_TILE_LEDGER_SCHEMA
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

LEDGER_SCHEMA = "ige-tile-core-halo-ledger/0.1"
UMBRELLA_FAILURE = "E_PR11_TILE_PLAN_CORE_HALO"
TEST_ID_UMBRELLA = "PR11_TILE_PLAN_CORE_HALO"

CODE_SCHEMA = "E_TILE_LEDGER_SCHEMA"
CODE_CORE_OVERLAP = "E_TILE_CORE_OVERLAP"
CODE_COVERAGE_GAP = "E_TILE_COVERAGE_GAP"
CODE_HALO_WRITE = "E_TILE_HALO_WRITE"
CODE_CORE_NOT_SUBSET = "E_TILE_CORE_NOT_SUBSET_READ"

STATUS_PASS = "PASS"
STATUS_FAIL = "FAIL"

Bounds = tuple[int, int, int, int]  # half-open [x0, y0, x1, y1)


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


def parse_bounds(value: Any, *, label: str) -> Bounds | str:
    """Parse half-open bounds; return Bounds or an error string."""
    if not isinstance(value, (list, tuple)) or len(value) != 4:
        return f"{label} must be [x0, y0, x1, y1]"
    try:
        x0, y0, x1, y1 = (int(v) for v in value)
    except (TypeError, ValueError):
        return f"{label} values must be integers"
    if x1 <= x0 or y1 <= y0:
        return f"{label} must satisfy x1>x0 and y1>y0 (got {[x0, y0, x1, y1]})"
    return (x0, y0, x1, y1)


def bounds_area(b: Bounds) -> int:
    x0, y0, x1, y1 = b
    return (x1 - x0) * (y1 - y0)


def bounds_contains(outer: Bounds, inner: Bounds) -> bool:
    ox0, oy0, ox1, oy1 = outer
    ix0, iy0, ix1, iy1 = inner
    return ox0 <= ix0 and oy0 <= iy0 and ix1 <= ox1 and iy1 <= oy1


def bounds_intersect(a: Bounds, b: Bounds) -> Bounds | None:
    ax0, ay0, ax1, ay1 = a
    bx0, by0, bx1, by1 = b
    x0, x1 = max(ax0, bx0), min(ax1, bx1)
    y0, y1 = max(ay0, by0), min(ay1, by1)
    if x0 >= x1 or y0 >= y1:
        return None
    return (x0, y0, x1, y1)


def bounds_pixels(b: Bounds) -> set[tuple[int, int]]:
    x0, y0, x1, y1 = b
    return {(x, y) for y in range(y0, y1) for x in range(x0, x1)}


def union_rects(rects: Sequence[Bounds]) -> set[tuple[int, int]]:
    out: set[tuple[int, int]] = set()
    for rect in rects:
        out |= bounds_pixels(rect)
    return out


def load_ledger(path: str | Path) -> dict[str, Any]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("tile ledger must be a JSON object")
    return payload


def validate_ledger_payload(data: Mapping[str, Any]) -> list[str]:
    """Lightweight structural validation (schema companion)."""
    errors: list[str] = []
    if not isinstance(data, Mapping):
        return ["ledger payload must be an object"]
    required = (
        "schema",
        "coordinate_frame",
        "coverage_target",
        "tiles",
        "non_claims",
    )
    missing = [k for k in required if k not in data]
    if missing:
        errors.append(f"missing top-level fields: {missing}")
    if data.get("schema") != LEDGER_SCHEMA:
        errors.append(f"schema must be {LEDGER_SCHEMA}")
    if not isinstance(data.get("coordinate_frame"), str) or not str(data.get("coordinate_frame")).strip():
        errors.append("coordinate_frame must be a non-empty string")
    canvas = data.get("canvas_sha256")
    if canvas is not None and not (
        isinstance(canvas, str)
        and len(canvas) == 64
        and all(c in "0123456789abcdefABCDEF" for c in canvas)
    ):
        errors.append("canvas_sha256 must be a 64-char hex digest when present")
    if not isinstance(data.get("non_claims"), list) or not data.get("non_claims"):
        errors.append("non_claims must be a non-empty array")
    elif any(not isinstance(x, str) or not x.strip() for x in data["non_claims"]):
        errors.append("non_claims entries must be non-empty strings")

    target = data.get("coverage_target")
    if not isinstance(target, Mapping):
        errors.append("coverage_target must be an object")
    else:
        if target.get("kind") != "rect_union":
            errors.append("coverage_target.kind must be 'rect_union'")
        rects = target.get("rects")
        if not isinstance(rects, list) or not rects:
            errors.append("coverage_target.rects must be a non-empty array")
        else:
            for i, rect in enumerate(rects):
                parsed = parse_bounds(rect, label=f"coverage_target.rects[{i}]")
                if isinstance(parsed, str):
                    errors.append(parsed)

    tiles = data.get("tiles")
    if not isinstance(tiles, list) or not tiles:
        errors.append("tiles must be a non-empty array")
        return errors

    seen_ids: set[str] = set()
    for i, tile in enumerate(tiles):
        p = f"tiles[{i}]"
        if not isinstance(tile, Mapping):
            errors.append(f"{p} must be an object")
            continue
        tid = tile.get("tile_id")
        if not isinstance(tid, str) or not tid.strip():
            errors.append(f"{p}.tile_id must be a non-empty string")
        elif tid in seen_ids:
            errors.append(f"duplicate tile_id: {tid}")
        else:
            seen_ids.add(tid)
        for key in ("read_bounds", "core_bounds"):
            parsed = parse_bounds(tile.get(key), label=f"{p}.{key}")
            if isinstance(parsed, str):
                errors.append(parsed)
        if "halo_bounds" in tile and tile.get("halo_bounds") is not None:
            parsed = parse_bounds(tile.get("halo_bounds"), label=f"{p}.halo_bounds")
            if isinstance(parsed, str):
                errors.append(parsed)
        out_sha = tile.get("output_sha256")
        if out_sha is not None and not (
            isinstance(out_sha, str)
            and len(out_sha) == 64
            and all(c in "0123456789abcdefABCDEF" for c in out_sha)
        ):
            errors.append(f"{p}.output_sha256 must be a 64-char hex digest when present")
        if "halo_write_pixels" in tile and type(tile.get("halo_write_pixels")) is not int:
            errors.append(f"{p}.halo_write_pixels must be an int when present")
        if "wrote_halo" in tile and not isinstance(tile.get("wrote_halo"), bool):
            errors.append(f"{p}.wrote_halo must be a boolean when present")
        frame = tile.get("coordinate_frame")
        if frame is not None and frame != data.get("coordinate_frame"):
            errors.append(
                f"{p}.coordinate_frame must match ledger coordinate_frame "
                f"({data.get('coordinate_frame')!r})"
            )
    return errors


def _tile_halo_write_claim(tile: Mapping[str, Any]) -> tuple[bool, str]:
    """Return (claimed_halo_write, reason)."""
    if tile.get("wrote_halo") is True:
        return True, "wrote_halo=true"
    hw = tile.get("halo_write_pixels")
    if type(hw) is int and hw > 0:
        return True, f"halo_write_pixels={hw}"
    receipt = tile.get("write_receipt")
    if isinstance(receipt, Mapping):
        if receipt.get("wrote_halo") is True:
            return True, "write_receipt.wrote_halo=true"
        rw = receipt.get("halo_write_pixels")
        if type(rw) is int and rw > 0:
            return True, f"write_receipt.halo_write_pixels={rw}"
    return False, ""


def audit_ledger(ledger: Mapping[str, Any]) -> dict[str, Any]:
    """Audit a tile core/halo ledger. Always execution_allowed=false."""
    checks: list[dict[str, Any]] = []
    blockers: list[str] = []

    schema_errors = validate_ledger_payload(ledger)
    if schema_errors:
        checks.append(
            _check(
                CODE_SCHEMA,
                STATUS_FAIL,
                "ledger schema/structure invalid",
                evidence={"errors": schema_errors},
            )
        )
        blockers.append(CODE_SCHEMA)
        return {
            "schema": LEDGER_SCHEMA,
            "overall_status": "FAIL",
            "umbrella_failure_code": UMBRELLA_FAILURE,
            "test_id": TEST_ID_UMBRELLA,
            "checks": checks,
            "blockers": blockers,
            "stats": {},
            "execution_allowed": False,
            "edit_permission": False,
            "non_claims": list(ledger.get("non_claims") or [])
            or ["Ledger audit does not grant execution or edit permission."],
        }

    checks.append(_check(CODE_SCHEMA, STATUS_PASS, "ledger schema/structure OK"))

    tiles = list(ledger["tiles"])
    target = ledger["coverage_target"]
    target_rects: list[Bounds] = []
    for rect in target["rects"]:
        parsed = parse_bounds(rect, label="coverage")
        assert not isinstance(parsed, str)
        target_rects.append(parsed)
    target_pixels = union_rects(target_rects)

    # Per-tile nesting + halo write claims.
    cores: list[tuple[str, Bounds]] = []
    halo_fail_tiles: list[dict[str, Any]] = []
    nest_fail_tiles: list[dict[str, Any]] = []

    for tile in tiles:
        tid = str(tile["tile_id"])
        read_b = parse_bounds(tile["read_bounds"], label="read")
        core_b = parse_bounds(tile["core_bounds"], label="core")
        assert not isinstance(read_b, str) and not isinstance(core_b, str)
        cores.append((tid, core_b))

        if not bounds_contains(read_b, core_b):
            nest_fail_tiles.append(
                {
                    "tile_id": tid,
                    "read_bounds": list(read_b),
                    "core_bounds": list(core_b),
                }
            )

        claimed, reason = _tile_halo_write_claim(tile)
        if claimed:
            halo_fail_tiles.append({"tile_id": tid, "reason": reason})

        # Optional halo_bounds must also sit inside read and not overlap core write semantics
        # (halo is context only). We only require halo_bounds ⊆ read when present.
        if tile.get("halo_bounds") is not None:
            halo_b = parse_bounds(tile["halo_bounds"], label="halo")
            if not isinstance(halo_b, str) and not bounds_contains(read_b, halo_b):
                nest_fail_tiles.append(
                    {
                        "tile_id": tid,
                        "issue": "halo_bounds not ⊆ read_bounds",
                        "read_bounds": list(read_b),
                        "halo_bounds": list(halo_b),
                    }
                )

    if nest_fail_tiles:
        checks.append(
            _check(
                CODE_CORE_NOT_SUBSET,
                STATUS_FAIL,
                "core (or declared halo) bounds not nested inside read_bounds",
                evidence={"tiles": nest_fail_tiles},
            )
        )
        blockers.append(CODE_CORE_NOT_SUBSET)
    else:
        checks.append(
            _check(
                CODE_CORE_NOT_SUBSET,
                STATUS_PASS,
                "every core_bounds ⊆ corresponding read_bounds",
            )
        )

    if halo_fail_tiles:
        checks.append(
            _check(
                CODE_HALO_WRITE,
                STATUS_FAIL,
                "halo is read-only; tile receipt claimed halo writes",
                evidence={"tiles": halo_fail_tiles},
            )
        )
        blockers.append(CODE_HALO_WRITE)
    else:
        checks.append(
            _check(
                CODE_HALO_WRITE,
                STATUS_PASS,
                "no tile claimed halo writes (halo_write_pixels=0 / wrote_halo=false)",
            )
        )

    # Pairwise disjoint cores.
    overlaps: list[dict[str, Any]] = []
    for i in range(len(cores)):
        for j in range(i + 1, len(cores)):
            tid_a, ba = cores[i]
            tid_b, bb = cores[j]
            inter = bounds_intersect(ba, bb)
            if inter is not None:
                overlaps.append(
                    {
                        "tile_a": tid_a,
                        "tile_b": tid_b,
                        "intersection": list(inter),
                        "intersection_pixels": bounds_area(inter),
                    }
                )
    if overlaps:
        checks.append(
            _check(
                CODE_CORE_OVERLAP,
                STATUS_FAIL,
                "tile cores are not pairwise disjoint",
                evidence={"overlaps": overlaps},
            )
        )
        blockers.append(CODE_CORE_OVERLAP)
    else:
        checks.append(
            _check(
                CODE_CORE_OVERLAP,
                STATUS_PASS,
                "tile cores are pairwise disjoint",
            )
        )

    # Exact-once coverage vs declared target.
    core_pixels: set[tuple[int, int]] = set()
    multi_covered = 0
    for _, core_b in cores:
        pix = bounds_pixels(core_b)
        multi_covered += len(core_pixels & pix)
        core_pixels |= pix
    gap = sorted(target_pixels - core_pixels)
    extra = sorted(core_pixels - target_pixels)
    # Overlap already counted via pairwise; multi_covered>0 also means not exact-once.
    coverage_ok = not gap and not extra and multi_covered == 0 and not overlaps
    if not coverage_ok:
        detail_parts = []
        if gap:
            detail_parts.append(f"gap_pixels={len(gap)}")
        if extra:
            detail_parts.append(f"extra_outside_target={len(extra)}")
        if multi_covered:
            detail_parts.append(f"multi_covered_pixels={multi_covered}")
        if overlaps:
            detail_parts.append("core_overlap_present")
        checks.append(
            _check(
                CODE_COVERAGE_GAP,
                STATUS_FAIL,
                "exact-once coverage vs coverage_target failed: " + ", ".join(detail_parts),
                evidence={
                    "gap_pixel_count": len(gap),
                    "extra_pixel_count": len(extra),
                    "multi_covered_pixels": multi_covered,
                    "gap_sample": gap[:16],
                    "extra_sample": extra[:16],
                    "target_pixel_count": len(target_pixels),
                    "core_union_pixel_count": len(core_pixels),
                },
            )
        )
        blockers.append(CODE_COVERAGE_GAP)
    else:
        checks.append(
            _check(
                CODE_COVERAGE_GAP,
                STATUS_PASS,
                "union of cores equals coverage_target with exact-once coverage",
                evidence={
                    "target_pixel_count": len(target_pixels),
                    "core_union_pixel_count": len(core_pixels),
                },
            )
        )

    overall = STATUS_PASS if not blockers else STATUS_FAIL
    return {
        "schema": LEDGER_SCHEMA,
        "overall_status": overall,
        "umbrella_failure_code": UMBRELLA_FAILURE,
        "test_id": TEST_ID_UMBRELLA,
        "coordinate_frame": ledger.get("coordinate_frame"),
        "checks": checks,
        "blockers": blockers,
        "stats": {
            "tile_count": len(tiles),
            "target_pixel_count": len(target_pixels),
            "core_union_pixel_count": len(core_pixels),
            "gap_pixel_count": len(gap),
            "extra_pixel_count": len(extra),
            "overlap_pair_count": len(overlaps),
        },
        "execution_allowed": False,
        "edit_permission": False,
        "maturity_unchanged": True,
        "non_claims": list(ledger.get("non_claims")),
    }


def ledger_passes(report: Mapping[str, Any]) -> bool:
    return report.get("overall_status") == STATUS_PASS and not report.get("blockers")


# --- Synthetic fixtures -------------------------------------------------


_NON_CLAIMS = [
    "Synthetic ledger only; no real compositor / GPU write-back.",
    "Does not grant edit_permission.",
    "Does not set execution_allowed=true.",
    "Does not promote FLUX_HR_TILE_IMG2IMG maturity.",
]


def _base_ledger(
    *,
    tiles: list[dict[str, Any]],
    coverage_rects: list[list[int]],
    coordinate_frame: str = "global_canvas_xy",
) -> dict[str, Any]:
    return {
        "schema": LEDGER_SCHEMA,
        "coordinate_frame": coordinate_frame,
        "coverage_target": {"kind": "rect_union", "rects": coverage_rects},
        "tiles": tiles,
        "non_claims": list(_NON_CLAIMS),
    }


def synthetic_valid_two_tile_ledger() -> dict[str, Any]:
    """Positive: two tiles with overlapping reads, disjoint cores, full coverage."""
    # Canvas coverage target 0..8 x 0..4
    # Tile A: read [-2,-1,6,5] conceptually clamped → use [0,0,6,4] read with core [0,0,4,4]
    # Tile B: read [2,0,8,4], core [4,0,8,4]
    tiles = [
        {
            "tile_id": "t0",
            "read_bounds": [0, 0, 6, 4],
            "core_bounds": [0, 0, 4, 4],
            "halo_bounds": [4, 0, 6, 4],
            "halo_write_pixels": 0,
            "wrote_halo": False,
            "write_receipt": {"wrote_core": True, "wrote_halo": False, "halo_write_pixels": 0},
            "coordinate_frame": "global_canvas_xy",
        },
        {
            "tile_id": "t1",
            "read_bounds": [2, 0, 8, 4],
            "core_bounds": [4, 0, 8, 4],
            "halo_bounds": [2, 0, 4, 4],
            "halo_write_pixels": 0,
            "wrote_halo": False,
            "write_receipt": {"wrote_core": True, "wrote_halo": False, "halo_write_pixels": 0},
            "coordinate_frame": "global_canvas_xy",
        },
    ]
    return _base_ledger(tiles=tiles, coverage_rects=[[0, 0, 8, 4]])


def synthetic_core_overlap_ledger() -> dict[str, Any]:
    """Counterexample: cores overlap on [3,0,5,4]."""
    tiles = [
        {
            "tile_id": "t0",
            "read_bounds": [0, 0, 6, 4],
            "core_bounds": [0, 0, 5, 4],
            "halo_write_pixels": 0,
            "wrote_halo": False,
        },
        {
            "tile_id": "t1",
            "read_bounds": [2, 0, 8, 4],
            "core_bounds": [3, 0, 8, 4],
            "halo_write_pixels": 0,
            "wrote_halo": False,
        },
    ]
    return _base_ledger(tiles=tiles, coverage_rects=[[0, 0, 8, 4]])


def synthetic_coverage_gap_ledger() -> dict[str, Any]:
    """Counterexample: cores leave a gap column at x=4..5."""
    tiles = [
        {
            "tile_id": "t0",
            "read_bounds": [0, 0, 5, 4],
            "core_bounds": [0, 0, 4, 4],
            "halo_write_pixels": 0,
            "wrote_halo": False,
        },
        {
            "tile_id": "t1",
            "read_bounds": [4, 0, 8, 4],
            "core_bounds": [5, 0, 8, 4],
            "halo_write_pixels": 0,
            "wrote_halo": False,
        },
    ]
    return _base_ledger(tiles=tiles, coverage_rects=[[0, 0, 8, 4]])


def synthetic_halo_write_ledger() -> dict[str, Any]:
    """Counterexample: otherwise valid geometry but halo_write_pixels>0."""
    ledger = synthetic_valid_two_tile_ledger()
    ledger["tiles"][0]["halo_write_pixels"] = 12
    ledger["tiles"][0]["wrote_halo"] = True
    ledger["tiles"][0]["write_receipt"] = {
        "wrote_core": True,
        "wrote_halo": True,
        "halo_write_pixels": 12,
    }
    return ledger


def synthetic_core_not_subset_read_ledger() -> dict[str, Any]:
    """Counterexample: core extends outside read_bounds."""
    tiles = [
        {
            "tile_id": "t0",
            "read_bounds": [0, 0, 4, 4],
            "core_bounds": [0, 0, 5, 4],  # x1=5 > read x1=4
            "halo_write_pixels": 0,
            "wrote_halo": False,
        },
        {
            "tile_id": "t1",
            "read_bounds": [4, 0, 8, 4],
            "core_bounds": [5, 0, 8, 4],
            "halo_write_pixels": 0,
            "wrote_halo": False,
        },
    ]
    return _base_ledger(tiles=tiles, coverage_rects=[[0, 0, 8, 4]])


def resolve_optional_ledger_from_s6(return_audit: Mapping[str, Any]) -> dict[str, Any] | None:
    """Extract optional embedded ledger or load from path on S6.return_audit.

    Returns None when no ledger was supplied (existing S6 path unchanged).
    Raises ValueError if a path is declared but unreadable / non-object.
    """
    if not isinstance(return_audit, Mapping):
        return None
    embedded = return_audit.get("tile_core_halo_ledger")
    if isinstance(embedded, Mapping):
        return dict(embedded)
    path = return_audit.get("tile_core_halo_ledger_path")
    if path is None or path == "":
        return None
    if not isinstance(path, str):
        raise ValueError("tile_core_halo_ledger_path must be a string")
    return load_ledger(path)
