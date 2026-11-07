"""Core/Halo tile write-back ledger contract (offline / synthetic).

Normative rules (ige-tile-core-halo-ledger/0.2):
- Each tile declares read_bounds (may include halo) and core_bounds (write region).
- Each tile MUST carry output_sha256 (synthetic hash OK; NOT live pixel proof).
- Ledger MUST bind to S2 Geometry Canvas via canvas_sha256 + coordinate_frame.
- Cores across the plan are pairwise disjoint.
- Union of cores equals the declared coverage_target (exact-once: no overlap, no gap).
- Halo is read-only: any receipt claiming halo writes → FAIL.
- core_bounds must be nested inside read_bounds (core ⊆ read).
- Coverage audit uses scanline / interval-union region math (8K-safe); never expands
  rectangles into per-pixel Python sets.
- For Tile methods, S6 requires this ledger (fail-closed if absent).
- Ledger alone never grants edit_permission and never sets execution_allowed=true.
- Ledger PASS ≠ actual pixel write-back PASS.

Aligned Registry / S6 codes:
- Umbrella: E_PR11_TILE_PLAN_CORE_HALO (GEOMETRY_LOCKED_TILE_PLAN_RETURN)
- Specific: E_TILE_CORE_OVERLAP, E_TILE_COVERAGE_GAP, E_TILE_HALO_WRITE,
  E_TILE_CORE_NOT_SUBSET_READ, E_TILE_LEDGER_SCHEMA, E_TILE_LEDGER_REQUIRED,
  E_TILE_S2_BIND, E_TILE_OUTPUT_SHA
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping, Sequence

LEDGER_SCHEMA = "ige-tile-core-halo-ledger/0.2"
UMBRELLA_FAILURE = "E_PR11_TILE_PLAN_CORE_HALO"
TEST_ID_UMBRELLA = "PR11_TILE_PLAN_CORE_HALO"

CODE_SCHEMA = "E_TILE_LEDGER_SCHEMA"
CODE_CORE_OVERLAP = "E_TILE_CORE_OVERLAP"
CODE_COVERAGE_GAP = "E_TILE_COVERAGE_GAP"
CODE_HALO_WRITE = "E_TILE_HALO_WRITE"
CODE_CORE_NOT_SUBSET = "E_TILE_CORE_NOT_SUBSET_READ"
CODE_LEDGER_REQUIRED = "E_TILE_LEDGER_REQUIRED"
CODE_S2_BIND = "E_TILE_S2_BIND"
CODE_OUTPUT_SHA = "E_TILE_OUTPUT_SHA"

STATUS_PASS = "PASS"
STATUS_FAIL = "FAIL"

# Methods whose S6 path must carry a Core/Halo ledger (fail-closed if missing).
# Maturity / execution_allowed are unchanged by this requirement alone.
TILE_LEDGER_REQUIRED_METHOD_IDS = frozenset(
    {
        "SIAX4X_TILE_CORE_SR",
        "GEOMETRY_LOCKED_TILE_PLAN_RETURN",
        "FLUX_HR_TILE_IMG2IMG",
    }
)

Bounds = tuple[int, int, int, int]  # half-open [x0, y0, x1, y1)


def method_requires_tile_core_halo_ledger(method_id: str | None) -> bool:
    """True when S6 must supply and pass a Core/Halo ledger for this method."""
    if not isinstance(method_id, str) or not method_id:
        return False
    if method_id in TILE_LEDGER_REQUIRED_METHOD_IDS:
        return True
    # Defensive: any future *TILE* method id inherits the mandatory ledger gate.
    return "TILE" in method_id.upper()


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


def _is_sha256(value: Any) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 64
        and all(c in "0123456789abcdefABCDEF" for c in value)
    )


# --- Region coverage (scanline / interval-union; 8K-safe) -----------------


def merge_x_intervals(intervals: Sequence[tuple[int, int]]) -> list[tuple[int, int]]:
    """Merge half-open [x0, x1) intervals; touching intervals coalesce."""
    if not intervals:
        return []
    ordered = sorted((int(a), int(b)) for a, b in intervals if b > a)
    if not ordered:
        return []
    merged: list[tuple[int, int]] = [ordered[0]]
    for a, b in ordered[1:]:
        la, lb = merged[-1]
        if a <= lb:
            merged[-1] = (la, max(lb, b))
        else:
            merged.append((a, b))
    return merged


def intervals_length(intervals: Sequence[tuple[int, int]]) -> int:
    return sum(b - a for a, b in intervals)


def union_area(rects: Sequence[Bounds]) -> int:
    """Axis-aligned rectangle union area via horizontal sweep + x-interval merge.

    Memory/time are O(n^2) in rectangle count for the naive active list, NOT O(pixels).
    Safe for ~8K canvases described by a modest number of tile rects.
    """
    if not rects:
        return 0
    # Events: (y, typ, x0, x1). typ 0 = enter, 1 = leave. Process enters before leaves at same y.
    events: list[tuple[int, int, int, int]] = []
    for x0, y0, x1, y1 in rects:
        events.append((y0, 0, x0, x1))
        events.append((y1, 1, x0, x1))
    events.sort(key=lambda e: (e[0], e[1]))

    active: list[tuple[int, int]] = []
    area = 0
    prev_y = events[0][0]
    i = 0
    n = len(events)
    while i < n:
        y = events[i][0]
        if y > prev_y and active:
            area += intervals_length(merge_x_intervals(active)) * (y - prev_y)
        while i < n and events[i][0] == y:
            _, typ, x0, x1 = events[i]
            if typ == 0:
                active.append((x0, x1))
            else:
                # Remove one matching interval (multiset semantics for identical spans).
                try:
                    active.remove((x0, x1))
                except ValueError:
                    pass
            i += 1
        prev_y = y
    return area


def rect_covered_by_union(inner: Bounds, cover: Sequence[Bounds]) -> bool:
    """True iff every pixel of inner lies in the union of cover (region math)."""
    clips: list[Bounds] = []
    for c in cover:
        inter = bounds_intersect(inner, c)
        if inter is not None:
            clips.append(inter)
    return union_area(clips) == bounds_area(inner)


def exact_once_region_coverage(
    cores: Sequence[Bounds],
    target_rects: Sequence[Bounds],
) -> dict[str, Any]:
    """Exact-once coverage without per-pixel sets.

    Requires pairwise-disjoint cores (caller reports overlap separately), each core
    ⊆ target union, and sum(core areas) == union_area(target).
    """
    target_area = union_area(target_rects)
    core_areas = [bounds_area(c) for c in cores]
    core_area_sum = sum(core_areas)
    not_subset: list[int] = []
    for i, core in enumerate(cores):
        if not rect_covered_by_union(core, target_rects):
            not_subset.append(i)
    # Pairwise multi-cover detection is the overlap check; here we only need area+subset.
    ok = not not_subset and core_area_sum == target_area
    return {
        "ok": ok,
        "target_area": target_area,
        "core_area_sum": core_area_sum,
        "cores_outside_target_indices": not_subset,
        "gap_or_extra": core_area_sum != target_area or bool(not_subset),
        "engine": "scanline_interval_union",
    }


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
        "canvas_sha256",
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
    if not _is_sha256(data.get("canvas_sha256")):
        errors.append("canvas_sha256 must be a 64-char hex digest (S2 geometry canvas bind)")
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
        if not _is_sha256(out_sha):
            errors.append(
                f"{p}.output_sha256 is required (64-char hex); "
                "synthetic digests allowed — not live pixel write-back proof"
            )
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


def bind_ledger_to_s2(
    ledger: Mapping[str, Any],
    s2_geometry: Mapping[str, Any] | None,
) -> dict[str, Any]:
    """Verify ledger.canvas_sha256 + coordinate_frame against S2 geometry canvas evidence.

    Returns a check dict (PASS/FAIL). When s2_geometry is None, FAIL — Tile S6 bind
    requires an S2 evidence object (standalone CLI may pass an explicit bind object).
    """
    ledger_frame = ledger.get("coordinate_frame")
    ledger_canvas = ledger.get("canvas_sha256")
    if not isinstance(s2_geometry, Mapping):
        return _check(
            CODE_S2_BIND,
            STATUS_FAIL,
            "S2 geometry bind required but no S2 geometry evidence was supplied",
            evidence={"ledger_coordinate_frame": ledger_frame, "ledger_canvas_sha256": ledger_canvas},
        )
    s2_frame = s2_geometry.get("coordinate_frame")
    s2_canvas = s2_geometry.get("canvas_sha256")
    mismatches: list[str] = []
    if not isinstance(s2_frame, str) or not s2_frame.strip():
        mismatches.append("S2.coordinate_frame missing/empty")
    elif s2_frame != ledger_frame:
        mismatches.append(
            f"coordinate_frame mismatch ledger={ledger_frame!r} s2={s2_frame!r}"
        )
    if not _is_sha256(s2_canvas):
        mismatches.append("S2.canvas_sha256 missing/invalid")
    elif s2_canvas != ledger_canvas:
        mismatches.append("canvas_sha256 mismatch vs S2 geometry canvas")
    if mismatches:
        return _check(
            CODE_S2_BIND,
            STATUS_FAIL,
            "ledger not bound to S2 Geometry Canvas",
            evidence={
                "mismatches": mismatches,
                "ledger_coordinate_frame": ledger_frame,
                "ledger_canvas_sha256": ledger_canvas,
                "s2_coordinate_frame": s2_frame,
                "s2_canvas_sha256": s2_canvas,
            },
        )
    return _check(
        CODE_S2_BIND,
        STATUS_PASS,
        "ledger.coordinate_frame and canvas_sha256 match S2 geometry canvas",
        evidence={
            "coordinate_frame": ledger_frame,
            "canvas_sha256": ledger_canvas,
        },
    )


def audit_ledger(
    ledger: Mapping[str, Any],
    *,
    s2_geometry: Mapping[str, Any] | None = None,
    require_s2_bind: bool = False,
) -> dict[str, Any]:
    """Audit a tile core/halo ledger. Always execution_allowed=false.

    When require_s2_bind is True (S6 tile-method path), ledger must match the
    provided S2 geometry canvas SHA + coordinate_frame.
    Standalone audits without S2 evidence skip the bind check unless require_s2_bind.
    """
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
        # Still surface missing output SHA distinctly when that is the only theme.
        if any("output_sha256" in e for e in schema_errors):
            checks.append(
                _check(
                    CODE_OUTPUT_SHA,
                    STATUS_FAIL,
                    "one or more tiles missing/invalid output_sha256",
                    evidence={"errors": [e for e in schema_errors if "output_sha256" in e]},
                )
            )
            blockers.append(CODE_OUTPUT_SHA)
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
            "coverage_engine": "scanline_interval_union",
            "non_claims": list(ledger.get("non_claims") or [])
            or ["Ledger audit does not grant execution or edit permission."],
            "note": (
                "Ledger PASS would still not prove live pixel write-back; "
                "this revision is contract + synthetic CI only."
            ),
        }

    checks.append(_check(CODE_SCHEMA, STATUS_PASS, "ledger schema/structure OK"))
    checks.append(
        _check(
            CODE_OUTPUT_SHA,
            STATUS_PASS,
            "every tile declares output_sha256 (synthetic allowed; not live pixel proof)",
        )
    )

    if require_s2_bind or s2_geometry is not None:
        bind_check = bind_ledger_to_s2(ledger, s2_geometry)
        checks.append(bind_check)
        if bind_check["status"] != STATUS_PASS:
            blockers.append(CODE_S2_BIND)

    tiles = list(ledger["tiles"])
    target = ledger["coverage_target"]
    target_rects: list[Bounds] = []
    for rect in target["rects"]:
        parsed = parse_bounds(rect, label="coverage")
        assert not isinstance(parsed, str)
        target_rects.append(parsed)

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

    # Pairwise disjoint cores (rectangle intersection; not per-pixel).
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
                        "intersection_area": bounds_area(inter),
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

    # Exact-once coverage via region engine (no per-pixel sets).
    core_bounds_only = [b for _, b in cores]
    coverage = exact_once_region_coverage(core_bounds_only, target_rects)
    coverage_ok = coverage["ok"] and not overlaps
    if not coverage_ok:
        detail_parts = []
        if coverage["cores_outside_target_indices"]:
            detail_parts.append(
                f"cores_outside_target={coverage['cores_outside_target_indices']}"
            )
        if coverage["core_area_sum"] < coverage["target_area"]:
            detail_parts.append(
                f"gap_area={coverage['target_area'] - coverage['core_area_sum']}"
            )
        if coverage["core_area_sum"] > coverage["target_area"]:
            detail_parts.append(
                f"extra_area={coverage['core_area_sum'] - coverage['target_area']}"
            )
        if overlaps:
            detail_parts.append("core_overlap_present")
        checks.append(
            _check(
                CODE_COVERAGE_GAP,
                STATUS_FAIL,
                "exact-once coverage vs coverage_target failed: " + ", ".join(detail_parts),
                evidence={
                    "target_area": coverage["target_area"],
                    "core_area_sum": coverage["core_area_sum"],
                    "cores_outside_target_indices": coverage["cores_outside_target_indices"],
                    "engine": coverage["engine"],
                },
            )
        )
        blockers.append(CODE_COVERAGE_GAP)
    else:
        checks.append(
            _check(
                CODE_COVERAGE_GAP,
                STATUS_PASS,
                "union of cores equals coverage_target with exact-once coverage (region engine)",
                evidence={
                    "target_area": coverage["target_area"],
                    "core_area_sum": coverage["core_area_sum"],
                    "engine": coverage["engine"],
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
        "canvas_sha256": ledger.get("canvas_sha256"),
        "checks": checks,
        "blockers": blockers,
        "stats": {
            "tile_count": len(tiles),
            "target_area": coverage["target_area"],
            "core_area_sum": coverage["core_area_sum"],
            "overlap_pair_count": len(overlaps),
            "coverage_engine": "scanline_interval_union",
        },
        "execution_allowed": False,
        "edit_permission": False,
        "maturity_unchanged": True,
        "coverage_engine": "scanline_interval_union",
        "non_claims": list(ledger.get("non_claims")),
        "note": (
            "Ledger contract PASS is not live Core/Halo pixel write-back proof; "
            "output_sha256 fields are declared digests only in this revision."
        ),
    }


def ledger_passes(report: Mapping[str, Any]) -> bool:
    return report.get("overall_status") == STATUS_PASS and not report.get("blockers")


def missing_ledger_failure(*, method_id: str) -> dict[str, Any]:
    """S6 fail-closed report when a Tile method omits the Core/Halo ledger."""
    return {
        "schema": LEDGER_SCHEMA,
        "overall_status": STATUS_FAIL,
        "umbrella_failure_code": UMBRELLA_FAILURE,
        "test_id": TEST_ID_UMBRELLA,
        "checks": [
            _check(
                CODE_LEDGER_REQUIRED,
                STATUS_FAIL,
                f"Tile method {method_id} requires tile_core_halo_ledger "
                "(or tile_core_halo_ledger_path); legacy counter-only path is closed",
                evidence={"method_id": method_id},
            )
        ],
        "blockers": [CODE_LEDGER_REQUIRED],
        "stats": {},
        "execution_allowed": False,
        "edit_permission": False,
        "maturity_unchanged": True,
        "non_claims": [
            "Missing ledger blocks S6 for Tile methods; does not unlock Flux.",
            "Does not set execution_allowed=true.",
        ],
    }


# --- Synthetic fixtures -------------------------------------------------


_NON_CLAIMS = [
    "Synthetic ledger only; no real compositor / GPU write-back.",
    "output_sha256 values are declared synthetic digests, not live pixel proofs.",
    "Does not grant edit_permission.",
    "Does not set execution_allowed=true.",
    "Does not promote FLUX_HR_TILE_IMG2IMG maturity.",
    "Ledger PASS ≠ actual Core/Halo pixel write-back PASS.",
]

# Stable synthetic digests for fixtures (not real file hashes).
_SYN_CANVAS = "a" * 64
_SYN_OUT_T0 = "b" * 64
_SYN_OUT_T1 = "c" * 64
_SYN_OUT_T2 = "d" * 64


def _base_ledger(
    *,
    tiles: list[dict[str, Any]],
    coverage_rects: list[list[int]],
    coordinate_frame: str = "global_canvas_xy",
    canvas_sha256: str = _SYN_CANVAS,
) -> dict[str, Any]:
    return {
        "schema": LEDGER_SCHEMA,
        "coordinate_frame": coordinate_frame,
        "canvas_sha256": canvas_sha256,
        "coverage_target": {"kind": "rect_union", "rects": coverage_rects},
        "tiles": tiles,
        "non_claims": list(_NON_CLAIMS),
    }


def _tile(
    tile_id: str,
    read_bounds: list[int],
    core_bounds: list[int],
    *,
    output_sha256: str,
    halo_bounds: list[int] | None = None,
    halo_write_pixels: int = 0,
    wrote_halo: bool = False,
    coordinate_frame: str = "global_canvas_xy",
    write_receipt: dict[str, Any] | None = None,
) -> dict[str, Any]:
    item: dict[str, Any] = {
        "tile_id": tile_id,
        "read_bounds": read_bounds,
        "core_bounds": core_bounds,
        "output_sha256": output_sha256,
        "halo_write_pixels": halo_write_pixels,
        "wrote_halo": wrote_halo,
        "coordinate_frame": coordinate_frame,
    }
    if halo_bounds is not None:
        item["halo_bounds"] = halo_bounds
    if write_receipt is not None:
        item["write_receipt"] = write_receipt
    else:
        item["write_receipt"] = {
            "wrote_core": True,
            "wrote_halo": wrote_halo,
            "halo_write_pixels": halo_write_pixels,
        }
    return item


def synthetic_valid_two_tile_ledger(
    *,
    coordinate_frame: str = "global_canvas_xy",
    canvas_sha256: str = _SYN_CANVAS,
) -> dict[str, Any]:
    """Positive: two tiles with overlapping reads, disjoint cores, full coverage."""
    tiles = [
        _tile(
            "t0",
            [0, 0, 6, 4],
            [0, 0, 4, 4],
            output_sha256=_SYN_OUT_T0,
            halo_bounds=[4, 0, 6, 4],
            coordinate_frame=coordinate_frame,
        ),
        _tile(
            "t1",
            [2, 0, 8, 4],
            [4, 0, 8, 4],
            output_sha256=_SYN_OUT_T1,
            halo_bounds=[2, 0, 4, 4],
            coordinate_frame=coordinate_frame,
        ),
    ]
    return _base_ledger(
        tiles=tiles,
        coverage_rects=[[0, 0, 8, 4]],
        coordinate_frame=coordinate_frame,
        canvas_sha256=canvas_sha256,
    )


def synthetic_core_overlap_ledger() -> dict[str, Any]:
    """Counterexample: cores overlap on [3,0,5,4]."""
    tiles = [
        _tile("t0", [0, 0, 6, 4], [0, 0, 5, 4], output_sha256=_SYN_OUT_T0),
        _tile("t1", [2, 0, 8, 4], [3, 0, 8, 4], output_sha256=_SYN_OUT_T1),
    ]
    return _base_ledger(tiles=tiles, coverage_rects=[[0, 0, 8, 4]])


def synthetic_coverage_gap_ledger() -> dict[str, Any]:
    """Counterexample: cores leave a gap column at x=4..5."""
    tiles = [
        _tile("t0", [0, 0, 5, 4], [0, 0, 4, 4], output_sha256=_SYN_OUT_T0),
        _tile("t1", [4, 0, 8, 4], [5, 0, 8, 4], output_sha256=_SYN_OUT_T1),
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
        _tile("t0", [0, 0, 4, 4], [0, 0, 5, 4], output_sha256=_SYN_OUT_T0),
        _tile("t1", [4, 0, 8, 4], [5, 0, 8, 4], output_sha256=_SYN_OUT_T1),
    ]
    return _base_ledger(tiles=tiles, coverage_rects=[[0, 0, 8, 4]])


def synthetic_missing_output_sha_ledger() -> dict[str, Any]:
    """Counterexample: valid geometry but output_sha256 omitted."""
    ledger = synthetic_valid_two_tile_ledger()
    del ledger["tiles"][0]["output_sha256"]
    return ledger


def synthetic_large_canvas_grid_ledger(
    *,
    canvas_w: int = 8192,
    canvas_h: int = 8192,
    tiles_x: int = 4,
    tiles_y: int = 4,
    halo: int = 64,
    coordinate_frame: str = "global_canvas_xy",
    canvas_sha256: str = _SYN_CANVAS,
) -> dict[str, Any]:
    """8K-friendly grid: many large cores without expanding to pixel sets."""
    if canvas_w % tiles_x or canvas_h % tiles_y:
        raise ValueError("canvas dims must divide evenly by tile grid")
    tw, th = canvas_w // tiles_x, canvas_h // tiles_y
    tiles: list[dict[str, Any]] = []
    for ty in range(tiles_y):
        for tx in range(tiles_x):
            x0, y0 = tx * tw, ty * th
            x1, y1 = x0 + tw, y0 + th
            rx0, ry0 = max(0, x0 - halo), max(0, y0 - halo)
            rx1, ry1 = min(canvas_w, x1 + halo), min(canvas_h, y1 + halo)
            digest = f"{(ty * tiles_x + tx):064x}"
            tiles.append(
                _tile(
                    f"t{ty}_{tx}",
                    [rx0, ry0, rx1, ry1],
                    [x0, y0, x1, y1],
                    output_sha256=digest,
                    coordinate_frame=coordinate_frame,
                )
            )
    return _base_ledger(
        tiles=tiles,
        coverage_rects=[[0, 0, canvas_w, canvas_h]],
        coordinate_frame=coordinate_frame,
        canvas_sha256=canvas_sha256,
    )


def resolve_optional_ledger_from_s6(return_audit: Mapping[str, Any]) -> dict[str, Any] | None:
    """Extract embedded ledger or load from path on S6.return_audit.

    Returns None when no ledger was supplied.
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


# Back-compat alias name used by older tests / call sites.
resolve_ledger_from_s6 = resolve_optional_ledger_from_s6
