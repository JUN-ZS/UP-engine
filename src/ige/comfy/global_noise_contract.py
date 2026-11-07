"""Global noise field contract for FLUX_HR_TILE candidate workflows.

Normative rule: a coordinate-consistent global noise field is indexed by global
canvas / latent coordinates (or an equivalent deterministic map from global XY
→ noise). Sharing one RNG seed across independent per-tile noise draws does
**not** satisfy this, even when every tile uses the same seed S.

This module is offline / synthetic only. It NEVER injects Comfy noise, NEVER
runs GPU inference, NEVER sets execution_allowed=True, and NEVER promotes
Method Registry maturity.
"""

from __future__ import annotations

import hashlib
import json
import random
from pathlib import Path
from typing import Any, Mapping, Sequence

FAILURE_NOISE = "E_NOISE_FIELD_NOT_GLOBAL"
TEST_ID_NOISE = "NOISE_FIELD_NOT_GLOBAL"
RECEIPT_SCHEMA = "ige-global-noise-field-receipt/0.1"

FIELD_KIND_COORDINATE_INDEXED = "coordinate_indexed"
FIELD_KIND_INDEPENDENT_SEED_PER_TILE = "independent_seed_per_tile"
FIELD_KIND_SHARED_SEED_ONLY = "shared_seed_only"
FIELD_KIND_UNKNOWN = "unknown"

FIELD_KINDS = frozenset(
    {
        FIELD_KIND_COORDINATE_INDEXED,
        FIELD_KIND_INDEPENDENT_SEED_PER_TILE,
        FIELD_KIND_SHARED_SEED_ONLY,
        FIELD_KIND_UNKNOWN,
    }
)

# Status values returned by classify_noise_evidence / static audit wiring.
STATUS_PASS = "PASS"  # only when a verified coordinate_indexed receipt is supplied
STATUS_FAIL = "FAIL"
STATUS_UNKNOWN = "UNKNOWN"


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


def coordinate_noise_at(seed: int, x: int, y: int, *, channel: int = 0) -> float:
    """Deterministic unit-interval sample indexed by global (x, y) + seed.

    Not a ComfyUI noise implementation — a synthetic stand-in for a
    coordinate-indexed field used in overlap equality proofs.
    """
    payload = f"{int(seed)}|{int(x)}|{int(y)}|{int(channel)}".encode("utf-8")
    digest = hashlib.sha256(payload).digest()
    # Map first 8 bytes to [0, 1).
    value = int.from_bytes(digest[:8], "big")
    return value / 2**64


def fill_tile_coordinate_indexed(
    *,
    seed: int,
    origin_xy: tuple[int, int],
    size_wh: tuple[int, int],
    channel: int = 0,
) -> dict[tuple[int, int], float]:
    """Fill a tile window by sampling a global coordinate-indexed field."""
    ox, oy = origin_xy
    w, h = size_wh
    out: dict[tuple[int, int], float] = {}
    for dy in range(h):
        for dx in range(w):
            gx, gy = ox + dx, oy + dy
            out[(gx, gy)] = coordinate_noise_at(seed, gx, gy, channel=channel)
    return out


def fill_tile_independent_rng(
    *,
    seed: int,
    origin_xy: tuple[int, int],
    size_wh: tuple[int, int],
) -> dict[tuple[int, int], float]:
    """Fill a tile by restarting an independent RNG at ``seed`` in local order.

    Overlapping tiles that share seed S but each restart their own stream will
    disagree on the overlap — demonstrating that shared seed ≠ global field.
    """
    ox, oy = origin_xy
    w, h = size_wh
    rng = random.Random(int(seed))
    out: dict[tuple[int, int], float] = {}
    for dy in range(h):
        for dx in range(w):
            out[(ox + dx, oy + dy)] = rng.random()
    return out


def overlap_region(
    a_origin: tuple[int, int],
    a_size: tuple[int, int],
    b_origin: tuple[int, int],
    b_size: tuple[int, int],
) -> list[tuple[int, int]]:
    ax0, ay0 = a_origin
    ax1, ay1 = ax0 + a_size[0], ay0 + a_size[1]
    bx0, by0 = b_origin
    bx1, by1 = bx0 + b_size[0], by0 + b_size[1]
    x0, x1 = max(ax0, bx0), min(ax1, bx1)
    y0, y1 = max(ay0, by0), min(ay1, by1)
    if x0 >= x1 or y0 >= y1:
        return []
    return [(x, y) for y in range(y0, y1) for x in range(x0, x1)]


def probe_overlap_equality(
    field_a: Mapping[tuple[int, int], float],
    field_b: Mapping[tuple[int, int], float],
    coords: Sequence[tuple[int, int]],
    *,
    atol: float = 0.0,
) -> dict[str, Any]:
    """Compare two tile fills on shared global coordinates."""
    if not coords:
        return {
            "overlap_count": 0,
            "equal_count": 0,
            "mismatch_count": 0,
            "all_equal": False,
            "reason": "empty overlap — cannot prove global consistency",
        }
    equal = 0
    mismatch = 0
    first_mismatch: dict[str, Any] | None = None
    for xy in coords:
        va = field_a.get(xy)
        vb = field_b.get(xy)
        if va is None or vb is None:
            mismatch += 1
            if first_mismatch is None:
                first_mismatch = {"xy": list(xy), "a": va, "b": vb, "kind": "missing"}
            continue
        if abs(float(va) - float(vb)) <= atol:
            equal += 1
        else:
            mismatch += 1
            if first_mismatch is None:
                first_mismatch = {
                    "xy": list(xy),
                    "a": float(va),
                    "b": float(vb),
                    "kind": "value",
                }
    return {
        "overlap_count": len(coords),
        "equal_count": equal,
        "mismatch_count": mismatch,
        "all_equal": mismatch == 0 and equal == len(coords),
        "first_mismatch": first_mismatch,
    }


def synthetic_coordinate_indexed_overlap_proof(
    *,
    seed: int = 909424749197426,
    tile_a: tuple[tuple[int, int], tuple[int, int]] = ((0, 0), (4, 4)),
    tile_b: tuple[tuple[int, int], tuple[int, int]] = ((2, 0), (4, 4)),
) -> dict[str, Any]:
    """Prove overlapping tiles agree when sampling a coordinate-indexed field."""
    a_origin, a_size = tile_a
    b_origin, b_size = tile_b
    fa = fill_tile_coordinate_indexed(seed=seed, origin_xy=a_origin, size_wh=a_size)
    fb = fill_tile_coordinate_indexed(seed=seed, origin_xy=b_origin, size_wh=b_size)
    coords = overlap_region(a_origin, a_size, b_origin, b_size)
    probe = probe_overlap_equality(fa, fb, coords)
    return {
        "field_kind": FIELD_KIND_COORDINATE_INDEXED,
        "seed": seed,
        "tile_origins": [list(a_origin), list(b_origin)],
        "tile_sizes": [list(a_size), list(b_size)],
        "overlap_probe": probe,
        "verified_synthetic": bool(probe.get("all_equal")),
        "note": "Synthetic coordinate-indexed proof only; not a live Comfy noise field.",
    }


def synthetic_shared_seed_independent_draws_counterexample(
    *,
    seed: int = 909424749197426,
    tile_a: tuple[tuple[int, int], tuple[int, int]] = ((0, 0), (4, 4)),
    tile_b: tuple[tuple[int, int], tuple[int, int]] = ((2, 0), (4, 4)),
) -> dict[str, Any]:
    """Counterexample: same seed + independent per-tile RNG → overlap mismatch."""
    a_origin, a_size = tile_a
    b_origin, b_size = tile_b
    fa = fill_tile_independent_rng(seed=seed, origin_xy=a_origin, size_wh=a_size)
    fb = fill_tile_independent_rng(seed=seed, origin_xy=b_origin, size_wh=b_size)
    coords = overlap_region(a_origin, a_size, b_origin, b_size)
    probe = probe_overlap_equality(fa, fb, coords)
    return {
        "field_kind": FIELD_KIND_SHARED_SEED_ONLY,
        "seed": seed,
        "tile_origins": [list(a_origin), list(b_origin)],
        "tile_sizes": [list(a_size), list(b_size)],
        "overlap_probe": probe,
        "demonstrates_not_global": bool(probe.get("mismatch_count", 0) > 0),
        "note": (
            "Independent RNG streams restarted at the same seed fill local tile "
            "order; overlapping global cells disagree — shared seed ≠ global field."
        ),
    }


def _collect_seeds_from_static_bits(static_bits: Mapping[str, Any]) -> list[Any]:
    seeds: list[Any] = []
    for noise in static_bits.get("noise_nodes") or []:
        if isinstance(noise, Mapping) and "noise_seed" in noise:
            seeds.append(noise.get("noise_seed"))
    models = static_bits.get("models") or {}
    if isinstance(models, Mapping) and models.get("noise_seed") is not None:
        seed = models.get("noise_seed")
        if seed not in seeds:
            seeds.append(seed)
    # inventories list form (from audit evaluate_checks)
    for inv in static_bits.get("inventories") or []:
        if not isinstance(inv, Mapping):
            continue
        for noise in inv.get("noise_nodes") or []:
            if isinstance(noise, Mapping) and "noise_seed" in noise:
                seeds.append(noise.get("noise_seed"))
        m = inv.get("models") or {}
        if isinstance(m, Mapping) and m.get("noise_seed") is not None:
            seed = m.get("noise_seed")
            if seed not in seeds:
                seeds.append(seed)
    observed = static_bits.get("observed_seeds")
    if isinstance(observed, list):
        for seed in observed:
            if seed not in seeds:
                seeds.append(seed)
    return seeds


def classify_noise_evidence(
    workflow_static_bits: Mapping[str, Any] | None = None,
    receipt: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Classify static / receipt evidence for the global noise field contract.

    Returns a dict with:
      - field_kind
      - status (PASS|FAIL|UNKNOWN) for E_NOISE_FIELD_NOT_GLOBAL
      - detail (human-readable)
      - evidence (structured)
      - check (audit check item)

    Rules (fail-closed):
      - verified coordinate_indexed receipt with overlapping equality → PASS
      - RandomNoise / shared seed alone → shared_seed_only → FAIL
      - independent_seed_per_tile → FAIL
      - otherwise → unknown → FAIL (insufficient evidence)
    """
    bits = dict(workflow_static_bits or {})
    seeds = _collect_seeds_from_static_bits(bits)
    unique_seeds = list({json.dumps(s, sort_keys=True): s for s in seeds}.values()) if seeds else []

    # Prefer an explicit receipt when provided.
    if receipt is not None:
        kind = receipt.get("field_kind")
        verified = bool(receipt.get("verified"))
        probe = receipt.get("overlap_probe") if isinstance(receipt.get("overlap_probe"), Mapping) else {}
        evidence = {
            "field_kind": kind,
            "receipt_schema": receipt.get("schema"),
            "verified": verified,
            "observed_seeds": seeds,
            "unique_seed_count": len(unique_seeds),
            "overlap_probe": dict(probe) if probe else None,
            "rule": "same RandomNoise seed ≠ coordinate-consistent global noise field",
            "test_id": TEST_ID_NOISE,
            "failure_code": FAILURE_NOISE,
        }
        if (
            kind == FIELD_KIND_COORDINATE_INDEXED
            and verified
            and bool(probe.get("all_equal"))
            and int(probe.get("overlap_count") or 0) > 0
        ):
            detail = (
                "coordinate-indexed global noise field verified via receipt "
                f"(overlap_count={probe.get('overlap_count')})"
            )
            check = _check(FAILURE_NOISE, STATUS_PASS, detail, evidence=evidence)
            return {
                "field_kind": FIELD_KIND_COORDINATE_INDEXED,
                "status": STATUS_PASS,
                "detail": detail,
                "evidence": evidence,
                "check": check,
            }

        if kind == FIELD_KIND_SHARED_SEED_ONLY or (
            kind == FIELD_KIND_COORDINATE_INDEXED and not verified
        ):
            mapped_kind = (
                FIELD_KIND_SHARED_SEED_ONLY
                if kind == FIELD_KIND_SHARED_SEED_ONLY
                else FIELD_KIND_COORDINATE_INDEXED
            )
            detail = (
                "noise receipt present but not verified as a live coordinate-indexed "
                f"global field (field_kind={kind}, verified={verified})"
            )
            evidence["field_kind"] = mapped_kind
            check = _check(FAILURE_NOISE, STATUS_FAIL, detail, evidence=evidence)
            return {
                "field_kind": mapped_kind,
                "status": STATUS_FAIL,
                "detail": detail,
                "evidence": evidence,
                "check": check,
            }

        if kind == FIELD_KIND_INDEPENDENT_SEED_PER_TILE:
            detail = (
                "independent per-tile seeds cannot form a coordinate-consistent "
                "global noise field"
            )
            check = _check(FAILURE_NOISE, STATUS_FAIL, detail, evidence=evidence)
            return {
                "field_kind": FIELD_KIND_INDEPENDENT_SEED_PER_TILE,
                "status": STATUS_FAIL,
                "detail": detail,
                "evidence": evidence,
                "check": check,
            }

        detail = f"noise receipt field_kind={kind!r} insufficient for global field proof"
        evidence["field_kind"] = kind if kind in FIELD_KINDS else FIELD_KIND_UNKNOWN
        check = _check(FAILURE_NOISE, STATUS_FAIL, detail, evidence=evidence)
        return {
            "field_kind": evidence["field_kind"],
            "status": STATUS_FAIL,
            "detail": detail,
            "evidence": evidence,
            "check": check,
        }

    # Static workflow bits only (typical Comfy RandomNoise seed case).
    evidence = {
        "field_kind": FIELD_KIND_UNKNOWN,
        "observed_seeds": seeds,
        "unique_seed_count": len(unique_seeds),
        "rule": "same RandomNoise seed ≠ coordinate-consistent global noise field",
        "test_id": TEST_ID_NOISE,
        "failure_code": FAILURE_NOISE,
    }

    if not seeds:
        detail = "no RandomNoise seed found in supplied graphs"
        evidence["field_kind"] = FIELD_KIND_UNKNOWN
        check = _check(FAILURE_NOISE, STATUS_FAIL, detail, evidence=evidence)
        return {
            "field_kind": FIELD_KIND_UNKNOWN,
            "status": STATUS_FAIL,
            "detail": detail,
            "evidence": evidence,
            "check": check,
        }

    # Declared kind from static bits (optional).
    declared = bits.get("field_kind")
    if declared == FIELD_KIND_INDEPENDENT_SEED_PER_TILE:
        evidence["field_kind"] = FIELD_KIND_INDEPENDENT_SEED_PER_TILE
        detail = (
            "independent per-tile seeds cannot form a coordinate-consistent "
            "global noise field"
        )
        check = _check(FAILURE_NOISE, STATUS_FAIL, detail, evidence=evidence)
        return {
            "field_kind": FIELD_KIND_INDEPENDENT_SEED_PER_TILE,
            "status": STATUS_FAIL,
            "detail": detail,
            "evidence": evidence,
            "check": check,
        }

    # Presence of RandomNoise seed(s) alone → shared_seed_only → FAIL.
    evidence["field_kind"] = FIELD_KIND_SHARED_SEED_ONLY
    detail = (
        "RandomNoise seed present but insufficient: same seed alone does not prove "
        "a coordinate-consistent global noise field "
        f"(noise_field_kind={FIELD_KIND_SHARED_SEED_ONLY})"
    )
    check = _check(FAILURE_NOISE, STATUS_FAIL, detail, evidence=evidence)
    return {
        "field_kind": FIELD_KIND_SHARED_SEED_ONLY,
        "status": STATUS_FAIL,
        "detail": detail,
        "evidence": evidence,
        "check": check,
    }


def validate_receipt_payload(data: Mapping[str, Any]) -> list[str]:
    """Lightweight structural validation for global_noise_field_receipt."""
    errors: list[str] = []
    if not isinstance(data, Mapping):
        return ["receipt payload must be an object"]
    required = (
        "schema",
        "field_kind",
        "coordinate_frame",
        "tile_origins",
        "verified",
        "non_claims",
    )
    missing = [k for k in required if k not in data]
    if missing:
        errors.append(f"missing top-level fields: {missing}")
    if data.get("schema") != RECEIPT_SCHEMA:
        errors.append(f"schema must be {RECEIPT_SCHEMA}")
    if data.get("field_kind") not in FIELD_KINDS:
        errors.append(f"field_kind must be one of {sorted(FIELD_KINDS)}")
    if not isinstance(data.get("coordinate_frame"), str) or not str(data.get("coordinate_frame")).strip():
        errors.append("coordinate_frame must be a non-empty string")
    if not isinstance(data.get("tile_origins"), list) or not data.get("tile_origins"):
        errors.append("tile_origins must be a non-empty array")
    if not isinstance(data.get("verified"), bool):
        errors.append("verified must be a boolean")
    if data.get("verified") is True and data.get("field_kind") != FIELD_KIND_COORDINATE_INDEXED:
        errors.append("verified=true is only allowed when field_kind=coordinate_indexed")
    if data.get("verified") is True:
        probe = data.get("overlap_probe")
        if not isinstance(probe, Mapping) or not probe.get("all_equal"):
            errors.append("verified=true requires overlap_probe.all_equal=true")
        elif int(probe.get("overlap_count") or 0) <= 0:
            errors.append("verified=true requires overlap_probe.overlap_count > 0")
    if not isinstance(data.get("non_claims"), list) or not data.get("non_claims"):
        errors.append("non_claims must be a non-empty array")
    canvas = data.get("canvas_sha256")
    if canvas is not None and not (
        isinstance(canvas, str) and len(canvas) == 64 and all(c in "0123456789abcdefABCDEF" for c in canvas)
    ):
        errors.append("canvas_sha256 must be a 64-char hex digest when present")
    return errors


def build_unverified_shared_seed_receipt(
    *,
    seed: Any,
    tile_origins: Sequence[Sequence[int]] | None = None,
    coordinate_frame: str = "global_canvas_xy",
    canvas_sha256: str | None = None,
) -> dict[str, Any]:
    """Build a fail-closed receipt documenting shared-seed-only static evidence."""
    receipt: dict[str, Any] = {
        "schema": RECEIPT_SCHEMA,
        "field_kind": FIELD_KIND_SHARED_SEED_ONLY,
        "coordinate_frame": coordinate_frame,
        "seed": seed,
        "tile_origins": [list(t) for t in (tile_origins or [])],
        "overlap_probe": {
            "overlap_count": 0,
            "equal_count": 0,
            "mismatch_count": 0,
            "all_equal": False,
            "reason": "static RandomNoise seed only — no overlap probe performed",
        },
        "verified": False,
        "non_claims": [
            "Shared RandomNoise seed is not a coordinate-consistent global noise field.",
            "This receipt does not claim live Comfy noise injection.",
            "verified remains false until a live/synthetic coordinate-indexed proof is attached.",
            "Does not promote FLUX_HR_TILE_IMG2IMG or grant edit_permission.",
        ],
    }
    if canvas_sha256 is not None:
        receipt["canvas_sha256"] = canvas_sha256
    return receipt


