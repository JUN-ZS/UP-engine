# Tile Core / Halo write-back ledger

## Purpose

Define the **S6 compositor ledger** that carries per-tile read bounds, disjoint
core bounds, optional halo bounds, **required** `output_sha256`, S2 canvas bind
(`canvas_sha256` + `coordinate_frame`), and **exact-once** core coverage.
Fail-closed. Offline / synthetic in this revision — no real pixel compositor
and no Comfy / GPU run.

**Ledger PASS ≠ actual Core/Halo pixel write-back PASS.** Declared
`output_sha256` values are digests on the evidence surface only; this branch
does not read back live compositor pixels.

This implements the tile ledger called out in
`docs/S0_S7_METHOD_REGISTRY_RUNTIME.md`: tile-specific counts
(`halo_write_pixels`, `core_overlap_pixels`, `coverage_gap_pixels`) remain
receipts; the ledger is the structured provenance those receipts bind to.

## Linked codes

| Code | Role |
|------|------|
| `E_PR11_TILE_PLAN_CORE_HALO` | Umbrella / Registry failure for `GEOMETRY_LOCKED_TILE_PLAN_RETURN` |
| `PR11_TILE_PLAN_CORE_HALO` | Matching test id |
| `E_TILE_LEDGER_SCHEMA` | Ledger JSON structure invalid |
| `E_TILE_LEDGER_REQUIRED` | Tile method reached S6 without a ledger |
| `E_TILE_S2_BIND` | `canvas_sha256` / `coordinate_frame` mismatch vs S2 geometry canvas |
| `E_TILE_OUTPUT_SHA` | Missing/invalid per-tile `output_sha256` |
| `E_TILE_CORE_NOT_SUBSET_READ` | `core_bounds` (or declared `halo_bounds`) not ⊆ `read_bounds` |
| `E_TILE_HALO_WRITE` | Any claim of halo writes (`wrote_halo` / `halo_write_pixels>0`) |
| `E_TILE_CORE_OVERLAP` | Pairwise core intersection non-empty |
| `E_TILE_COVERAGE_GAP` | Union of cores ≠ declared `coverage_target`, or multi-cover |

## Normative rules

1. Each tile has: `tile_id`, `read_bounds` (may include halo), `core_bounds`
   (disjoint write region), optional `halo_bounds`, **required** `output_sha256`,
   and `coordinate_frame` matching the S2 canvas frame when present on the tile.
2. Top-level **`canvas_sha256` + `coordinate_frame` are required** and must match
   `S2.geometry_contract` when audited through `evaluate_s0_s7`.
3. Bounds are half-open integer rectangles `[x0, y0, x1, y1)` with
   `x1 > x0` and `y1 > y0`.
4. Across the plan: cores are **pairwise disjoint**; union of cores equals the
   authorized / declared `coverage_target` (**exact-once**: no core overlap,
   no gaps, no extras outside target).
5. Halo is **read-only**: any receipt claiming halo writes → **FAIL**.
6. `core_bounds ⊆ read_bounds` (and declared `halo_bounds ⊆ read_bounds`).
7. Coverage uses a **scanline / interval-union region engine** (memory bounded
   by rectangle count, not canvas pixel count). Per-pixel Python set expansion
   is forbidden in the audit path.
8. Ledger alone does **not** grant edit permission and does **not** set
   `execution_allowed=true`. It does **not** promote
   `FLUX_HR_TILE_IMG2IMG` out of `workflow_candidate`.

## Schema / module

- Schema id: `ige-tile-core-halo-ledger/0.2`
- File: `schemas/tile_core_halo_ledger.schema.json`
- Module: `src/ige/comfy/tile_core_halo_ledger.py`
  - `load_ledger` / `validate_ledger_payload` / `audit_ledger` /
    `bind_ledger_to_s2` / `method_requires_tile_core_halo_ledger` /
    `missing_ledger_failure`
  - Region helpers: `union_area`, `exact_once_region_coverage`
  - Synthetic builders: valid two-tile PASS; overlap; gap; halo write;
    core not ⊆ read; missing output SHA; large (8K) grid

## CLI

```bash
ige audit-tile-ledger PATH [--out report.json]
```

Exit `0` only when `overall_status=PASS`. Exit `2` on FAIL. Even on PASS,
`execution_allowed` remains `false`. Standalone CLI audits schema/geometry;
pass S2 bind via `evaluate_s0_s7` for the full Tile-method gate.

## Mandatory S0–S7 wiring (Tile methods)

For Tile methods (`SIAX4X_TILE_CORE_SR`, `GEOMETRY_LOCKED_TILE_PLAN_RETURN`,
`FLUX_HR_TILE_IMG2IMG`, and any future method_id containing `TILE`):

- `S6.return_audit` **must** include either
  `tile_core_halo_ledger` (embedded) or `tile_core_halo_ledger_path`
- Missing ledger → S6 **FAIL** with `E_TILE_LEDGER_REQUIRED`
- Present ledger is audited fail-closed and **bound to S2**
  (`canvas_sha256` + `coordinate_frame`)
- Integer tile-count receipts (`halo_write_pixels` etc.) remain required
  alongside the ledger; they are no longer a substitute for it

Non-tile methods: ledger remains optional; if supplied, it is still audited
fail-closed with S2 bind.

`execution_allowed` stays `false`. Flux maturity stays `workflow_candidate`.

## Synthetic proof (required unit coverage)

1. **Positive:** overlapping reads, disjoint cores, full coverage, zero halo
   writes, S2 bind match, per-tile `output_sha256` → PASS.
2. **Counterexamples:** core overlap → FAIL; coverage gap → FAIL;
   `halo_write_pixels>0` → FAIL; core not ⊆ read → FAIL; missing ledger on
   Tile method → FAIL; S2 canvas/frame mismatch → FAIL; missing
   `output_sha256` → FAIL.
3. **8K sanity:** large-canvas grid (e.g. 8192² / 4×4 tiles) audits without
   per-pixel set expansion / OOM.
4. Comfy static fixture audit remains
   `execution_allowed=false` / `maturity_remains=workflow_candidate`.

## Non-claims

- Does not run a real tile compositor or rewrite pixels.
- Does not start ComfyUI or load Flux / Siax weights.
- Synthetic PASS ≠ live GPU core-only write-back proof.
- Declared `output_sha256` ≠ verified live tile buffer hash from a GPU run.
- Does not modify Method Registry maturity or `edit_permission`.
- Does not merge to `main`.

## See also

- `docs/S0_S7_METHOD_REGISTRY_RUNTIME.md` (S6 return_audit + mandatory ledger)
- `docs/COMFY_WORKFLOW_STATIC_AUDIT.md`
- `docs/GLOBAL_NOISE_FIELD_CONTRACT.md`
- Method `GEOMETRY_LOCKED_TILE_PLAN_RETURN` failure / test ids
