"""Global noise field contract for FLUX_HR_TILE candidate workflows.

Normative rule: a coordinate-consistent global noise field is indexed by global
canvas / latent coordinates (or an equivalent deterministic map from global XY
→ noise). Sharing one RNG seed across independent per-tile noise draws does
**not** satisfy this, even when every tile uses the same seed S.

Pass surfaces (must not be conflated):
  - noise_synthetic_ok / synthetic_pass — CI contract fixtures, static graph
    proofs, synthetic counterexamples. Offline only.
  - noise_live_verified / live_pass — ONLY when a live capture receipt of an
    actual noise tensor / generator proof is present. CI never sets this true;
    no GPU runners live here.

Three mechanism contracts (acceptance surfaces — not GPU implementations):
  1. global_latent_once_crop — generate one global latent, crop by coordinates
  2. coordinate_indexed_generator — (seed, global_x, global_y, channel) → sample
  3. global_then_local_refinement — architectural (not a seed tweak); note
     global-latent compute/memory cost

This module is offline / synthetic only. It NEVER injects Comfy noise, NEVER
runs GPU inference, NEVER sets execution_allowed=True, and NEVER promotes
Method Registry maturity.
"""

from __future__ import annotations

import hashlib
import json
import random
from typing import Any, Mapping, Sequence

FAILURE_NOISE = "E_NOISE_FIELD_NOT_GLOBAL"
TEST_ID_NOISE = "NOISE_FIELD_NOT_GLOBAL"
RECEIPT_SCHEMA = "ige-global-noise-field-receipt/0.2"
RECEIPT_SCHEMA_LEGACY = "ige-global-noise-field-receipt/0.1"

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

# Evidence grades — analogous to declared_record vs disk_capture for inventory.
EVIDENCE_GRADE_STATIC = "static_seed_only"
EVIDENCE_GRADE_SYNTHETIC = "synthetic_contract"
EVIDENCE_GRADE_LIVE = "live_capture"

EVIDENCE_GRADES = frozenset(
    {
        EVIDENCE_GRADE_STATIC,
        EVIDENCE_GRADE_SYNTHETIC,
        EVIDENCE_GRADE_LIVE,
    }
)

# Three mechanism contracts (enum).
MECHANISM_GLOBAL_LATENT_CROP = "global_latent_once_crop"
MECHANISM_COORDINATE_INDEXED_GENERATOR = "coordinate_indexed_generator"
MECHANISM_GLOBAL_THEN_LOCAL_REFINEMENT = "global_then_local_refinement"

MECHANISMS = frozenset(
    {
        MECHANISM_GLOBAL_LATENT_CROP,
        MECHANISM_COORDINATE_INDEXED_GENERATOR,
        MECHANISM_GLOBAL_THEN_LOCAL_REFINEMENT,
    }
)

# Status values returned by classify_noise_evidence / static audit wiring.
STATUS_PASS = "PASS"
STATUS_FAIL = "FAIL"
STATUS_UNKNOWN = "UNKNOWN"
STATUS_UNVERIFIED = "UNVERIFIED"

# Live receipt fields required before noise_live_verified may be true.
LIVE_PROOF_REQUIRED_FIELDS = (
    "host_id",
    "captured_at",
    "tensor_or_generator_proof",
    "overlap_probe",
)


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


def mechanism_contract_specs() -> dict[str, dict[str, Any]]:
    """Normative acceptance surfaces for the three noise mechanisms.

    These are contracts / docs for CI synthetic acceptance — not GPU code.
    """
    return {
        MECHANISM_GLOBAL_LATENT_CROP: {
            "mechanism": MECHANISM_GLOBAL_LATENT_CROP,
            "title": "Global latent noise once, then crop by coordinates",
            "summary": (
                "Allocate one global latent noise tensor for the full canvas, "
                "then crop each tile window by global coordinates. Overlap "
                "regions are views into the same underlying field."
            ),
            "architectural_vs_seed_tweak": False,
            "acceptance_criteria": [
                "global_latent_shape is declared and binds to the canvas/latent frame",
                "each tile crop uses global (x, y) origins — not local-only fills",
                "overlapping crops are value-identical on the shared cells",
                "shared RandomNoise seed alone is NOT accepted as this mechanism",
            ],
            "cost_notes": (
                "Memory scales with full-canvas latent (H×W×C). Large 8K canvases "
                "pay the full global allocation even when sampling one tile."
            ),
            "synthetic_probe": "synthetic_global_latent_crop_overlap_proof",
        },
        MECHANISM_COORDINATE_INDEXED_GENERATOR: {
            "mechanism": MECHANISM_COORDINATE_INDEXED_GENERATOR,
            "title": "Stateless coordinate-indexed generator",
            "summary": (
                "A pure function (seed, global_x, global_y, channel) → sample. "
                "No global tensor storage required. Same seed alone ≠ this "
                "mechanism — coordinates must enter the generator."
            ),
            "architectural_vs_seed_tweak": False,
            "acceptance_criteria": [
                "generator signature includes global_x and global_y (and channel)",
                "identical (seed, x, y, c) always yields the same sample",
                "overlapping tiles agree without storing a global buffer",
                "restarting an independent RNG at the same seed is a FAIL counterexample",
            ],
            "cost_notes": (
                "O(tile pixels) compute; no full-canvas latent memory. Suitable "
                "when global allocation is prohibitive."
            ),
            "synthetic_probe": "synthetic_coordinate_indexed_overlap_proof",
        },
        MECHANISM_GLOBAL_THEN_LOCAL_REFINEMENT: {
            "mechanism": MECHANISM_GLOBAL_THEN_LOCAL_REFINEMENT,
            "title": "Global generate then local tile detail refinement",
            "summary": (
                "Two-stage architecture: a global field is produced first, then "
                "each tile applies a local detail refinement stage. This is a "
                "different architecture — not a seed tweak of per-tile draws."
            ),
            "architectural_vs_seed_tweak": True,
            "acceptance_criteria": [
                "receipt declares distinct global_stage and local_refinement_stage",
                "local refinement is documented as architectural, not reseed-of-tile",
                "global-stage overlap consistency is proven before refinement",
                "compute/memory cost of the global latent stage is explicitly noted",
                "same seed alone does NOT satisfy this mechanism",
            ],
            "cost_notes": (
                "Pays global-latent compute + memory for stage 1, plus per-tile "
                "refinement compute for stage 2. Highest cost of the three; "
                "must not be confused with 'just change the seed'."
            ),
            "synthetic_probe": "synthetic_global_then_local_refinement_acceptance",
        },
    }


def coordinate_noise_at(seed: int, x: int, y: int, *, channel: int = 0) -> float:
    """Deterministic unit-interval sample indexed by global (x, y) + seed.

    Not a ComfyUI noise implementation — a synthetic stand-in for a
    coordinate-indexed field used in overlap equality proofs.
    """
    payload = f"{int(seed)}|{int(x)}|{int(y)}|{int(channel)}".encode("utf-8")
    digest = hashlib.sha256(payload).digest()
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


def build_synthetic_global_latent(
    *,
    seed: int,
    width: int,
    height: int,
    channels: int = 1,
) -> list[list[list[float]]]:
    """Allocate a synthetic global latent [H][W][C] via coordinate indexing.

    Stand-in for mechanism 1's global buffer — not a real GPU tensor.
    """
    field: list[list[list[float]]] = []
    for y in range(height):
        row: list[list[float]] = []
        for x in range(width):
            row.append(
                [coordinate_noise_at(seed, x, y, channel=c) for c in range(channels)]
            )
        field.append(row)
    return field


def crop_global_latent(
    field: Sequence[Sequence[Sequence[float]]],
    *,
    origin_xy: tuple[int, int],
    size_wh: tuple[int, int],
) -> dict[tuple[int, int], float]:
    """Crop a global latent by coordinates; returns channel-0 map keyed by global XY."""
    ox, oy = origin_xy
    w, h = size_wh
    out: dict[tuple[int, int], float] = {}
    for dy in range(h):
        for dx in range(w):
            gx, gy = ox + dx, oy + dy
            out[(gx, gy)] = float(field[gy][gx][0])
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
        "mechanism": MECHANISM_COORDINATE_INDEXED_GENERATOR,
        "field_kind": FIELD_KIND_COORDINATE_INDEXED,
        "evidence_grade": EVIDENCE_GRADE_SYNTHETIC,
        "seed": seed,
        "tile_origins": [list(a_origin), list(b_origin)],
        "tile_sizes": [list(a_size), list(b_size)],
        "overlap_probe": probe,
        "verified_synthetic": bool(probe.get("all_equal")),
        "noise_synthetic_ok": bool(probe.get("all_equal")),
        "noise_live_verified": False,
        "note": (
            "Synthetic coordinate-indexed proof only; not a live Comfy noise field. "
            "noise_live_verified remains false."
        ),
    }


def synthetic_global_latent_crop_overlap_proof(
    *,
    seed: int = 909424749197426,
    canvas_wh: tuple[int, int] = (8, 4),
    tile_a: tuple[tuple[int, int], tuple[int, int]] = ((0, 0), (4, 4)),
    tile_b: tuple[tuple[int, int], tuple[int, int]] = ((2, 0), (4, 4)),
) -> dict[str, Any]:
    """Mechanism 1 synthetic: one global latent, crop by coordinates, overlap agrees."""
    width, height = canvas_wh
    field = build_synthetic_global_latent(seed=seed, width=width, height=height)
    a_origin, a_size = tile_a
    b_origin, b_size = tile_b
    fa = crop_global_latent(field, origin_xy=a_origin, size_wh=a_size)
    fb = crop_global_latent(field, origin_xy=b_origin, size_wh=b_size)
    coords = overlap_region(a_origin, a_size, b_origin, b_size)
    probe = probe_overlap_equality(fa, fb, coords)
    return {
        "mechanism": MECHANISM_GLOBAL_LATENT_CROP,
        "field_kind": FIELD_KIND_COORDINATE_INDEXED,
        "evidence_grade": EVIDENCE_GRADE_SYNTHETIC,
        "seed": seed,
        "global_latent_shape": [height, width, 1],
        "tile_origins": [list(a_origin), list(b_origin)],
        "tile_sizes": [list(a_size), list(b_size)],
        "overlap_probe": probe,
        "verified_synthetic": bool(probe.get("all_equal")),
        "noise_synthetic_ok": bool(probe.get("all_equal")),
        "noise_live_verified": False,
        "cost_notes": mechanism_contract_specs()[MECHANISM_GLOBAL_LATENT_CROP]["cost_notes"],
        "note": (
            "Synthetic global-latent-crop proof only; no GPU tensor allocated. "
            "noise_live_verified remains false."
        ),
    }


def synthetic_global_then_local_refinement_acceptance(
    *,
    seed: int = 909424749197426,
    tile_a: tuple[tuple[int, int], tuple[int, int]] = ((0, 0), (4, 4)),
    tile_b: tuple[tuple[int, int], tuple[int, int]] = ((2, 0), (4, 4)),
) -> dict[str, Any]:
    """Mechanism 3 synthetic acceptance surface (architecture contract, not GPU).

    Stage 1: global coordinate-indexed base field (overlap must agree).
    Stage 2: local refinement = deterministic function of (base, global_xy) —
    still coordinate-indexed, proving refinement is architectural composition
    rather than an independent per-tile reseed.
    """
    a_origin, a_size = tile_a
    b_origin, b_size = tile_b
    # Stage 1 — global base
    base_a = fill_tile_coordinate_indexed(seed=seed, origin_xy=a_origin, size_wh=a_size)
    base_b = fill_tile_coordinate_indexed(seed=seed, origin_xy=b_origin, size_wh=b_size)
    coords = overlap_region(a_origin, a_size, b_origin, b_size)
    base_probe = probe_overlap_equality(base_a, base_b, coords)

    def _refine(base: Mapping[tuple[int, int], float]) -> dict[tuple[int, int], float]:
        out: dict[tuple[int, int], float] = {}
        for (x, y), v in base.items():
            # Architectural local detail: mixes base with a coord-indexed delta.
            # NOT an independent RNG restart at seed.
            delta = coordinate_noise_at(seed ^ 0xA5A5_A5A5, x, y, channel=1)
            out[(x, y)] = (float(v) + delta) % 1.0
        return out

    ref_a = _refine(base_a)
    ref_b = _refine(base_b)
    refined_probe = probe_overlap_equality(ref_a, ref_b, coords)

    # Counter: independent reseed refinement would break overlap — document contrast.
    ind_a = fill_tile_independent_rng(seed=seed, origin_xy=a_origin, size_wh=a_size)
    ind_b = fill_tile_independent_rng(seed=seed, origin_xy=b_origin, size_wh=b_size)
    reseed_probe = probe_overlap_equality(ind_a, ind_b, coords)

    ok = bool(base_probe.get("all_equal")) and bool(refined_probe.get("all_equal"))
    return {
        "mechanism": MECHANISM_GLOBAL_THEN_LOCAL_REFINEMENT,
        "field_kind": FIELD_KIND_COORDINATE_INDEXED,
        "evidence_grade": EVIDENCE_GRADE_SYNTHETIC,
        "architectural_vs_seed_tweak": True,
        "global_stage": {
            "name": "global_base_field",
            "overlap_probe": base_probe,
        },
        "local_refinement_stage": {
            "name": "coord_indexed_detail_delta",
            "overlap_probe": refined_probe,
            "note": "Refinement is f(base, global_xy) — not independent tile reseed",
        },
        "seed_tweak_counterexample": {
            "overlap_probe": reseed_probe,
            "demonstrates_not_architecture": bool(reseed_probe.get("mismatch_count", 0) > 0),
            "note": "Independent RNG restart at same seed ≠ global-then-local architecture",
        },
        "seed": seed,
        "tile_origins": [list(a_origin), list(b_origin)],
        "tile_sizes": [list(a_size), list(b_size)],
        "overlap_probe": refined_probe,
        "verified_synthetic": ok,
        "noise_synthetic_ok": ok,
        "noise_live_verified": False,
        "cost_notes": mechanism_contract_specs()[MECHANISM_GLOBAL_THEN_LOCAL_REFINEMENT][
            "cost_notes"
        ],
        "note": (
            "Synthetic architectural acceptance only. Does not run GPU refinement. "
            "noise_live_verified remains false."
        ),
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
        "evidence_grade": EVIDENCE_GRADE_STATIC,
        "seed": seed,
        "tile_origins": [list(a_origin), list(b_origin)],
        "tile_sizes": [list(a_size), list(b_size)],
        "overlap_probe": probe,
        "demonstrates_not_global": bool(probe.get("mismatch_count", 0) > 0),
        "noise_synthetic_ok": False,
        "noise_live_verified": False,
        "note": (
            "Independent RNG streams restarted at the same seed fill local tile "
            "order; overlapping global cells disagree — shared seed ≠ global field."
        ),
    }


def synthetic_identical_local_arrays_seam_counterexample(
    *,
    seed: int = 909424749197426,
    tile_a: tuple[tuple[int, int], tuple[int, int]] = ((0, 0), (4, 4)),
    tile_b: tuple[tuple[int, int], tuple[int, int]] = ((2, 0), (4, 4)),
) -> dict[str, Any]:
    """Seam counterexample: identical local-order arrays at different origins.

    Even when two tiles contain byte-identical local arrays (same seed stream
    length), placing them at different global origins makes overlap cells
    disagree in global space — seams without coordinate indexing.
    """
    a_origin, a_size = tile_a
    b_origin, b_size = tile_b
    # Build one local array, stamp onto both origins (identical local contents).
    local = fill_tile_independent_rng(seed=seed, origin_xy=(0, 0), size_wh=a_size)
    local_vals = [local[(x, y)] for y in range(a_size[1]) for x in range(a_size[0])]

    def _stamp(origin: tuple[int, int], size: tuple[int, int]) -> dict[tuple[int, int], float]:
        ox, oy = origin
        w, h = size
        out: dict[tuple[int, int], float] = {}
        i = 0
        for dy in range(h):
            for dx in range(w):
                out[(ox + dx, oy + dy)] = local_vals[i % len(local_vals)]
                i += 1
        return out

    fa = _stamp(a_origin, a_size)
    fb = _stamp(b_origin, b_size)
    coords = overlap_region(a_origin, a_size, b_origin, b_size)
    probe = probe_overlap_equality(fa, fb, coords)
    return {
        "field_kind": FIELD_KIND_SHARED_SEED_ONLY,
        "evidence_grade": EVIDENCE_GRADE_STATIC,
        "seed": seed,
        "tile_origins": [list(a_origin), list(b_origin)],
        "tile_sizes": [list(a_size), list(b_size)],
        "overlap_probe": probe,
        "identical_local_arrays": True,
        "demonstrates_seam_without_coord_indexing": bool(probe.get("mismatch_count", 0) > 0),
        "noise_synthetic_ok": False,
        "noise_live_verified": False,
        "note": (
            "Overlapping tiles with identical local arrays still seam-fail in "
            "global space without coordinate indexing."
        ),
    }


def evaluate_mechanism_synthetic_acceptance(
    mechanism: str,
) -> dict[str, Any]:
    """Run the synthetic acceptance probe for one mechanism contract.

    Always leaves noise_live_verified=false. No GPU.
    """
    specs = mechanism_contract_specs()
    if mechanism not in specs:
        return {
            "mechanism": mechanism,
            "synthetic_status": STATUS_FAIL,
            "noise_synthetic_ok": False,
            "noise_live_verified": False,
            "detail": f"unknown mechanism {mechanism!r}",
        }
    if mechanism == MECHANISM_GLOBAL_LATENT_CROP:
        proof = synthetic_global_latent_crop_overlap_proof()
    elif mechanism == MECHANISM_COORDINATE_INDEXED_GENERATOR:
        proof = synthetic_coordinate_indexed_overlap_proof()
    else:
        proof = synthetic_global_then_local_refinement_acceptance()
    ok = bool(proof.get("noise_synthetic_ok"))
    return {
        "mechanism": mechanism,
        "title": specs[mechanism]["title"],
        "architectural_vs_seed_tweak": specs[mechanism]["architectural_vs_seed_tweak"],
        "acceptance_criteria": list(specs[mechanism]["acceptance_criteria"]),
        "cost_notes": specs[mechanism]["cost_notes"],
        "synthetic_status": STATUS_PASS if ok else STATUS_FAIL,
        "live_status": STATUS_UNVERIFIED,
        "noise_synthetic_ok": ok,
        "noise_live_verified": False,
        "evidence_grade": EVIDENCE_GRADE_SYNTHETIC,
        "proof": proof,
        "detail": (
            f"mechanism {mechanism}: synthetic_status="
            f"{STATUS_PASS if ok else STATUS_FAIL}; live_status={STATUS_UNVERIFIED}"
        ),
    }


def evaluate_all_mechanism_synthetic_acceptances() -> dict[str, Any]:
    """CI catalog: all three mechanisms' synthetic surfaces (live stays unverified)."""
    results = {
        m: evaluate_mechanism_synthetic_acceptance(m) for m in sorted(MECHANISMS)
    }
    all_synth = all(r.get("noise_synthetic_ok") for r in results.values())
    return {
        "evidence_grade": EVIDENCE_GRADE_SYNTHETIC,
        "noise_synthetic_ok": all_synth,
        "noise_live_verified": False,
        "synthetic_status": STATUS_PASS if all_synth else STATUS_FAIL,
        "live_status": STATUS_UNVERIFIED,
        "mechanisms": results,
        "note": (
            "Mechanism synthetic_acceptance is CI contract coverage only. "
            "It does NOT prove the audited workflow has a live global noise field. "
            "noise_live_verified remains false without a live_capture receipt."
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


def _live_proof_complete(receipt: Mapping[str, Any]) -> bool:
    """True only when a live_capture receipt carries real proof fields.

    CI synthetic receipts must never satisfy this.
    """
    if receipt.get("evidence_grade") != EVIDENCE_GRADE_LIVE:
        return False
    if receipt.get("synthetic") is True:
        return False
    for key in LIVE_PROOF_REQUIRED_FIELDS:
        if key not in receipt:
            return False
    proof = receipt.get("tensor_or_generator_proof")
    if not isinstance(proof, Mapping) or not proof:
        return False
    # Require a digest or generator id — refuse empty placeholders.
    has_digest = isinstance(proof.get("sha256"), str) and len(proof["sha256"]) == 64
    has_gen = isinstance(proof.get("generator_id"), str) and bool(proof["generator_id"].strip())
    if not (has_digest or has_gen):
        return False
    probe = receipt.get("overlap_probe")
    if not isinstance(probe, Mapping):
        return False
    if not probe.get("all_equal") or int(probe.get("overlap_count") or 0) <= 0:
        return False
    if not bool(receipt.get("host_id")) or not bool(receipt.get("captured_at")):
        return False
    return True


def classify_noise_evidence(
    workflow_static_bits: Mapping[str, Any] | None = None,
    receipt: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Classify static / receipt evidence for the global noise field contract.

    Returns:
      - field_kind
      - evidence_grade
      - mechanism (optional)
      - noise_synthetic_ok / noise_live_verified  (surfaces; do not conflate)
      - synthetic_status / live_status
      - status — **live gate** for E_NOISE_FIELD_NOT_GLOBAL (PASS only if
        noise_live_verified). Synthetic-only never clears this gate.
      - detail, evidence, check

    Rules (fail-closed):
      - live_capture receipt with complete tensor/generator proof → live PASS
      - synthetic_contract receipt with overlap equality → synthetic PASS,
        live UNVERIFIED; E_NOISE status remains FAIL
      - RandomNoise / shared seed alone → shared_seed_only → both FAIL
      - independent_seed_per_tile → FAIL
      - otherwise → unknown → FAIL
    """
    bits = dict(workflow_static_bits or {})
    seeds = _collect_seeds_from_static_bits(bits)
    unique_seeds = (
        list({json.dumps(s, sort_keys=True): s for s in seeds}.values()) if seeds else []
    )

    def _pack(
        *,
        field_kind: str,
        evidence_grade: str,
        status: str,
        detail: str,
        noise_synthetic_ok: bool,
        noise_live_verified: bool,
        synthetic_status: str,
        live_status: str,
        mechanism: str | None = None,
        extra: Mapping[str, Any] | None = None,
        overlap_probe: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        evidence: dict[str, Any] = {
            "field_kind": field_kind,
            "evidence_grade": evidence_grade,
            "noise_synthetic_ok": noise_synthetic_ok,
            "noise_live_verified": noise_live_verified,
            "synthetic_status": synthetic_status,
            "live_status": live_status,
            "observed_seeds": seeds,
            "unique_seed_count": len(unique_seeds),
            "rule": "same RandomNoise seed ≠ coordinate-consistent global noise field",
            "rule_surfaces": (
                "synthetic_pass (noise_synthetic_ok) ≠ live_pass (noise_live_verified)"
            ),
            "test_id": TEST_ID_NOISE,
            "failure_code": FAILURE_NOISE,
        }
        if mechanism is not None:
            evidence["mechanism"] = mechanism
        if overlap_probe is not None:
            evidence["overlap_probe"] = dict(overlap_probe)
        if extra:
            evidence.update(dict(extra))
        check = _check(FAILURE_NOISE, status, detail, evidence=evidence)
        return {
            "field_kind": field_kind,
            "evidence_grade": evidence_grade,
            "mechanism": mechanism,
            "noise_synthetic_ok": noise_synthetic_ok,
            "noise_live_verified": noise_live_verified,
            "synthetic_status": synthetic_status,
            "live_status": live_status,
            "status": status,
            "detail": detail,
            "evidence": evidence,
            "check": check,
        }

    if receipt is not None:
        kind = receipt.get("field_kind")
        grade = receipt.get("evidence_grade")
        # Infer grade for legacy 0.1 receipts.
        if grade not in EVIDENCE_GRADES:
            if receipt.get("synthetic") is True:
                grade = EVIDENCE_GRADE_SYNTHETIC
            elif kind == FIELD_KIND_SHARED_SEED_ONLY:
                grade = EVIDENCE_GRADE_STATIC
            else:
                grade = EVIDENCE_GRADE_STATIC
        mechanism = receipt.get("mechanism")
        if mechanism is not None and mechanism not in MECHANISMS:
            mechanism = None
        probe = (
            receipt.get("overlap_probe")
            if isinstance(receipt.get("overlap_probe"), Mapping)
            else {}
        )
        synth_ok_flag = bool(receipt.get("noise_synthetic_ok"))
        # Legacy: verified+synthetic+coordinate_indexed+overlap → synthetic ok
        legacy_synth = (
            grade == EVIDENCE_GRADE_SYNTHETIC
            or receipt.get("synthetic") is True
        ) and (
            kind == FIELD_KIND_COORDINATE_INDEXED
            and bool(probe.get("all_equal"))
            and int(probe.get("overlap_count") or 0) > 0
        )
        noise_synthetic_ok = synth_ok_flag or legacy_synth or bool(
            receipt.get("verified") and receipt.get("synthetic") and legacy_synth
        )
        if legacy_synth:
            noise_synthetic_ok = True

        live_ok = _live_proof_complete(receipt) and bool(
            receipt.get("noise_live_verified", True)
        )
        # Hard rule: synthetic receipts can never flip live.
        if grade != EVIDENCE_GRADE_LIVE or receipt.get("synthetic") is True:
            live_ok = False
        # CI / callers must not set live without complete proof.
        if not _live_proof_complete(receipt):
            live_ok = False

        if live_ok:
            detail = (
                "live_capture coordinate-indexed global noise field verified "
                f"(overlap_count={probe.get('overlap_count')}); "
                "synthetic_pass also implied by live proof"
            )
            return _pack(
                field_kind=FIELD_KIND_COORDINATE_INDEXED,
                evidence_grade=EVIDENCE_GRADE_LIVE,
                status=STATUS_PASS,
                detail=detail,
                noise_synthetic_ok=True,
                noise_live_verified=True,
                synthetic_status=STATUS_PASS,
                live_status=STATUS_PASS,
                mechanism=mechanism,
                overlap_probe=probe,
                extra={
                    "receipt_schema": receipt.get("schema"),
                    "host_id": receipt.get("host_id"),
                },
            )

        if noise_synthetic_ok and kind == FIELD_KIND_COORDINATE_INDEXED:
            detail = (
                "synthetic_contract PASS (noise_synthetic_ok=true) but "
                "live_pass UNVERIFIED (noise_live_verified=false); "
                "E_NOISE live gate remains FAIL — synthetic ≠ live"
            )
            return _pack(
                field_kind=FIELD_KIND_COORDINATE_INDEXED,
                evidence_grade=EVIDENCE_GRADE_SYNTHETIC,
                status=STATUS_FAIL,
                detail=detail,
                noise_synthetic_ok=True,
                noise_live_verified=False,
                synthetic_status=STATUS_PASS,
                live_status=STATUS_UNVERIFIED,
                mechanism=mechanism,
                overlap_probe=probe,
                extra={"receipt_schema": receipt.get("schema")},
            )

        if kind == FIELD_KIND_SHARED_SEED_ONLY or (
            kind == FIELD_KIND_COORDINATE_INDEXED and not noise_synthetic_ok
        ):
            mapped_kind = (
                FIELD_KIND_SHARED_SEED_ONLY
                if kind == FIELD_KIND_SHARED_SEED_ONLY
                else FIELD_KIND_COORDINATE_INDEXED
            )
            detail = (
                "noise receipt present but not verified as synthetic or live "
                f"coordinate-indexed global field (field_kind={kind}, "
                f"evidence_grade={grade})"
            )
            return _pack(
                field_kind=mapped_kind,
                evidence_grade=grade if grade in EVIDENCE_GRADES else EVIDENCE_GRADE_STATIC,
                status=STATUS_FAIL,
                detail=detail,
                noise_synthetic_ok=False,
                noise_live_verified=False,
                synthetic_status=STATUS_FAIL,
                live_status=STATUS_UNVERIFIED,
                mechanism=mechanism,
                overlap_probe=probe,
                extra={"receipt_schema": receipt.get("schema")},
            )

        if kind == FIELD_KIND_INDEPENDENT_SEED_PER_TILE:
            detail = (
                "independent per-tile seeds cannot form a coordinate-consistent "
                "global noise field"
            )
            return _pack(
                field_kind=FIELD_KIND_INDEPENDENT_SEED_PER_TILE,
                evidence_grade=grade if grade in EVIDENCE_GRADES else EVIDENCE_GRADE_STATIC,
                status=STATUS_FAIL,
                detail=detail,
                noise_synthetic_ok=False,
                noise_live_verified=False,
                synthetic_status=STATUS_FAIL,
                live_status=STATUS_FAIL,
                mechanism=mechanism,
                extra={"receipt_schema": receipt.get("schema")},
            )

        detail = f"noise receipt field_kind={kind!r} insufficient for global field proof"
        return _pack(
            field_kind=kind if kind in FIELD_KINDS else FIELD_KIND_UNKNOWN,
            evidence_grade=grade if grade in EVIDENCE_GRADES else EVIDENCE_GRADE_STATIC,
            status=STATUS_FAIL,
            detail=detail,
            noise_synthetic_ok=False,
            noise_live_verified=False,
            synthetic_status=STATUS_FAIL,
            live_status=STATUS_UNVERIFIED,
            mechanism=mechanism,
            extra={"receipt_schema": receipt.get("schema")},
        )

    # Static workflow bits only (typical Comfy RandomNoise seed case).
    if not seeds:
        detail = "no RandomNoise seed found in supplied graphs"
        return _pack(
            field_kind=FIELD_KIND_UNKNOWN,
            evidence_grade=EVIDENCE_GRADE_STATIC,
            status=STATUS_FAIL,
            detail=detail,
            noise_synthetic_ok=False,
            noise_live_verified=False,
            synthetic_status=STATUS_FAIL,
            live_status=STATUS_UNVERIFIED,
        )

    declared = bits.get("field_kind")
    if declared == FIELD_KIND_INDEPENDENT_SEED_PER_TILE:
        detail = (
            "independent per-tile seeds cannot form a coordinate-consistent "
            "global noise field"
        )
        return _pack(
            field_kind=FIELD_KIND_INDEPENDENT_SEED_PER_TILE,
            evidence_grade=EVIDENCE_GRADE_STATIC,
            status=STATUS_FAIL,
            detail=detail,
            noise_synthetic_ok=False,
            noise_live_verified=False,
            synthetic_status=STATUS_FAIL,
            live_status=STATUS_FAIL,
        )

    detail = (
        "RandomNoise seed present but insufficient: same seed alone does not prove "
        "a coordinate-consistent global noise field "
        f"(noise_field_kind={FIELD_KIND_SHARED_SEED_ONLY}; "
        f"evidence_grade={EVIDENCE_GRADE_STATIC}; "
        "noise_synthetic_ok=false; noise_live_verified=false)"
    )
    return _pack(
        field_kind=FIELD_KIND_SHARED_SEED_ONLY,
        evidence_grade=EVIDENCE_GRADE_STATIC,
        status=STATUS_FAIL,
        detail=detail,
        noise_synthetic_ok=False,
        noise_live_verified=False,
        synthetic_status=STATUS_FAIL,
        live_status=STATUS_UNVERIFIED,
    )


def validate_receipt_payload(data: Mapping[str, Any]) -> list[str]:
    """Structural validation for global_noise_field_receipt (0.2; 0.1 legacy OK)."""
    errors: list[str] = []
    if not isinstance(data, Mapping):
        return ["receipt payload must be an object"]
    schema = data.get("schema")
    if schema not in {RECEIPT_SCHEMA, RECEIPT_SCHEMA_LEGACY}:
        errors.append(
            f"schema must be {RECEIPT_SCHEMA} (or legacy {RECEIPT_SCHEMA_LEGACY})"
        )
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
    if data.get("field_kind") not in FIELD_KINDS:
        errors.append(f"field_kind must be one of {sorted(FIELD_KINDS)}")
    if not isinstance(data.get("coordinate_frame"), str) or not str(
        data.get("coordinate_frame")
    ).strip():
        errors.append("coordinate_frame must be a non-empty string")
    if not isinstance(data.get("tile_origins"), list) or not data.get("tile_origins"):
        errors.append("tile_origins must be a non-empty array")
    if not isinstance(data.get("verified"), bool):
        errors.append("verified must be a boolean")

    grade = data.get("evidence_grade")
    if grade is not None and grade not in EVIDENCE_GRADES:
        errors.append(f"evidence_grade must be one of {sorted(EVIDENCE_GRADES)}")
    # 0.2 prefers explicit evidence_grade.
    if schema == RECEIPT_SCHEMA and grade not in EVIDENCE_GRADES:
        errors.append(f"schema {RECEIPT_SCHEMA} requires evidence_grade")

    mechanism = data.get("mechanism")
    if mechanism is not None and mechanism not in MECHANISMS:
        errors.append(f"mechanism must be one of {sorted(MECHANISMS)}")

    # Surface flags when present must be bool; live cannot be true on synthetic.
    for flag in ("noise_synthetic_ok", "noise_live_verified"):
        if flag in data and not isinstance(data.get(flag), bool):
            errors.append(f"{flag} must be a boolean when present")
    if data.get("noise_live_verified") is True:
        if data.get("synthetic") is True or grade == EVIDENCE_GRADE_SYNTHETIC:
            errors.append(
                "noise_live_verified=true is forbidden on synthetic_contract receipts"
            )
        if grade != EVIDENCE_GRADE_LIVE:
            errors.append(
                "noise_live_verified=true requires evidence_grade=live_capture"
            )
        if not _live_proof_complete(
            {**dict(data), "evidence_grade": EVIDENCE_GRADE_LIVE}
        ):
            errors.append(
                "noise_live_verified=true requires host_id, captured_at, "
                "tensor_or_generator_proof, and passing overlap_probe"
            )

    if data.get("verified") is True and data.get("field_kind") != FIELD_KIND_COORDINATE_INDEXED:
        errors.append("verified=true is only allowed when field_kind=coordinate_indexed")
    if data.get("verified") is True:
        probe = data.get("overlap_probe")
        if not isinstance(probe, Mapping) or not probe.get("all_equal"):
            errors.append("verified=true requires overlap_probe.all_equal=true")
        elif int(probe.get("overlap_count") or 0) <= 0:
            errors.append("verified=true requires overlap_probe.overlap_count > 0")
        # verified alone on synthetic must not imply live
        if grade == EVIDENCE_GRADE_SYNTHETIC or data.get("synthetic") is True:
            if data.get("noise_live_verified") is True:
                errors.append("synthetic verified receipt cannot set noise_live_verified")

    if not isinstance(data.get("non_claims"), list) or not data.get("non_claims"):
        errors.append("non_claims must be a non-empty array")
    canvas = data.get("canvas_sha256")
    if canvas is not None and not (
        isinstance(canvas, str)
        and len(canvas) == 64
        and all(c in "0123456789abcdefABCDEF" for c in canvas)
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
        "evidence_grade": EVIDENCE_GRADE_STATIC,
        "coordinate_frame": coordinate_frame,
        "seed": seed,
        "tile_origins": [list(t) for t in (tile_origins or [[0, 0]])],
        "overlap_probe": {
            "overlap_count": 0,
            "equal_count": 0,
            "mismatch_count": 0,
            "all_equal": False,
            "reason": "static RandomNoise seed only — no overlap probe performed",
        },
        "verified": False,
        "noise_synthetic_ok": False,
        "noise_live_verified": False,
        "non_claims": [
            "Shared RandomNoise seed is not a coordinate-consistent global noise field.",
            "This receipt does not claim live Comfy noise injection.",
            "noise_synthetic_ok and noise_live_verified both remain false.",
            "Does not promote FLUX_HR_TILE_IMG2IMG or grant edit_permission.",
        ],
    }
    if canvas_sha256 is not None:
        receipt["canvas_sha256"] = canvas_sha256
    return receipt


def build_synthetic_mechanism_receipt(
    *,
    mechanism: str,
    coordinate_frame: str = "global_canvas_xy",
    canvas_sha256: str | None = None,
) -> dict[str, Any]:
    """Build a synthetic_contract receipt from a mechanism acceptance probe.

    noise_live_verified is always false.
    """
    acceptance = evaluate_mechanism_synthetic_acceptance(mechanism)
    proof = acceptance.get("proof") or {}
    probe = proof.get("overlap_probe") or {
        "overlap_count": 0,
        "equal_count": 0,
        "mismatch_count": 0,
        "all_equal": False,
    }
    synth_ok = bool(acceptance.get("noise_synthetic_ok"))
    receipt: dict[str, Any] = {
        "schema": RECEIPT_SCHEMA,
        "field_kind": FIELD_KIND_COORDINATE_INDEXED if synth_ok else FIELD_KIND_UNKNOWN,
        "evidence_grade": EVIDENCE_GRADE_SYNTHETIC,
        "mechanism": mechanism,
        "coordinate_frame": coordinate_frame,
        "seed": proof.get("seed"),
        "tile_origins": proof.get("tile_origins") or [[0, 0]],
        "tile_sizes": proof.get("tile_sizes"),
        "overlap_probe": probe,
        "verified": synth_ok,  # verified here means synthetic overlap only
        "synthetic": True,
        "noise_synthetic_ok": synth_ok,
        "noise_live_verified": False,
        "acceptance_criteria": list(acceptance.get("acceptance_criteria") or []),
        "cost_notes": acceptance.get("cost_notes"),
        "architectural_vs_seed_tweak": bool(
            acceptance.get("architectural_vs_seed_tweak")
        ),
        "failure_code": FAILURE_NOISE,
        "test_id": TEST_ID_NOISE,
        "non_claims": [
            "Synthetic PASS ≠ Live PASS.",
            "noise_live_verified remains false; no GPU tensor / Comfy noise captured.",
            "Does not prove the audited workflow implements this mechanism.",
            "Does not promote FLUX_HR_TILE_IMG2IMG or grant edit_permission.",
        ],
    }
    if canvas_sha256 is not None:
        receipt["canvas_sha256"] = canvas_sha256
    if mechanism == MECHANISM_GLOBAL_LATENT_CROP and proof.get("global_latent_shape"):
        receipt["global_latent_shape"] = proof["global_latent_shape"]
    if mechanism == MECHANISM_GLOBAL_THEN_LOCAL_REFINEMENT:
        receipt["global_stage"] = proof.get("global_stage")
        receipt["local_refinement_stage"] = proof.get("local_refinement_stage")
    return receipt


def build_live_capture_receipt_template(
    *,
    mechanism: str,
    host_id: str,
    coordinate_frame: str = "global_canvas_xy",
) -> dict[str, Any]:
    """Template for a future host live_capture receipt.

    noise_live_verified stays false until tensor_or_generator_proof + overlap
    are filled by a real host capture (not implemented here; no GPU).
    """
    if mechanism not in MECHANISMS:
        raise ValueError(f"mechanism must be one of {sorted(MECHANISMS)}")
    return {
        "schema": RECEIPT_SCHEMA,
        "field_kind": FIELD_KIND_COORDINATE_INDEXED,
        "evidence_grade": EVIDENCE_GRADE_LIVE,
        "mechanism": mechanism,
        "coordinate_frame": coordinate_frame,
        "host_id": host_id,
        "captured_at": None,  # operator fills ISO-8601
        "tile_origins": [[0, 0], [0, 0]],
        "overlap_probe": {
            "overlap_count": 0,
            "equal_count": 0,
            "mismatch_count": 0,
            "all_equal": False,
            "reason": "template — no live overlap probe yet",
        },
        "tensor_or_generator_proof": {
            "sha256": None,
            "generator_id": None,
            "note": "Fill sha256 of captured noise tensor OR generator_id of live sampler",
        },
        "verified": False,
        "synthetic": False,
        "noise_synthetic_ok": False,
        "noise_live_verified": False,
        "non_claims": [
            "Template only — not a live PASS.",
            "CI must not set noise_live_verified=true.",
            "Requires real host capture of noise tensor / generator proof.",
            "Does not promote FLUX_HR_TILE_IMG2IMG or grant edit_permission.",
        ],
    }
