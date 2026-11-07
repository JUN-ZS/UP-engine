# Tile Core / Halo write-back ledger

## Purpose

Define the **S6 compositor ledger** that carries per-tile read bounds, disjoint
core bounds, optional halo bounds, optional output hashes, and **exact-once**
core coverage. Fail-closed. Offline / synthetic in this revision — no real
pixel compositor and no Comfy / GPU run.

This implements the “future tile ledger” called out in
`docs/S0_S7_METHOD_REGISTRY_RUNTIME.md`: tile-specific counts
(`halo_write_pixels`, `core_overlap_pixels`, `coverage_gap_pixels`) remain
receipts; the ledger is the structured provenance those receipts should bind to.

## Linked codes

| Code | Role |
|------|------|
| `E_PR11_TILE_PLAN_CORE_HALO` | Umbrella / Registry failure for `GEOMETRY_LOCKED_TILE_PLAN_RETURN` |
| `PR11_TILE_PLAN_CORE_HALO` | Matching test id |
| `E_TILE_LEDGER_SCHEMA` | Ledger JSON structure invalid |
| `E_TILE_CORE_NOT_SUBSET_READ` | `core_bounds` (or declared `halo_bounds`) not ⊆ `read_bounds` |
| `E_TILE_HALO_WRITE` | Any claim of halo writes (`wrote_halo` / `halo_write_pixels>0`) |
| `E_TILE_CORE_OVERLAP` | Pairwise core intersection non-empty |
| `E_TILE_COVERAGE_GAP` | Union of cores ≠ declared `coverage_target`, or multi-cover |

## Normative rules

1. Each tile has: `tile_id`, `read_bounds` (may include halo), `core_bounds`
   (disjoint write region), optional `halo_bounds`, optional `output_sha256`,
   and `coordinate_frame` matching the S2 canvas frame when present.
2. Bounds are half-open integer rectangles `[x0, y0, x1, y1)` with
   `x1 > x0` and `y1 > y0`.
3. Across the plan: cores are **pairwise disjoint**; union of cores equals the
   authorized / declared `coverage_target` (**exact-once**: no core overlap,
   no gaps, no extras outside target).
4. Halo is **read-only**: any receipt claiming halo writes → **FAIL**.
5. `core_bounds ⊆ read_bounds` (and declared `halo_bounds ⊆ read_bounds`).
6. Ledger alone does **not** grant edit permission and does **not** set
   `execution_allowed=true`. It does **not** promote
   `FLUX_HR_TILE_IMG2IMG` out of `workflow_candidate`.

## Schema / module

- Schema id: `ige-tile-core-halo-ledger/0.1`
- File: `schemas/tile_core_halo_ledger.schema.json`
- Module: `src/ige/comfy/tile_core_halo_ledger.py`
  - `load_ledger` / `validate_ledger_payload` / `audit_ledger`
  - Synthetic builders: valid two-tile PASS; overlap; gap; halo write;
    core not ⊆ read

## CLI

```bash
ige audit-tile-ledger PATH [--out report.json]
```

Exit `0` only when `overall_status=PASS`. Exit `2` on FAIL. Even on PASS,
`execution_allowed` remains `false`.

## Optional S0–S7 wiring

When `S6.return_audit` includes either:

- `tile_core_halo_ledger` — embedded ledger object, or
- `tile_core_halo_ledger_path` — filesystem path to ledger JSON

`evaluate_s0_s7` runs `audit_ledger` fail-closed and blocks S6 if the ledger
fails. When neither field is present, behaviour is unchanged (existing
integer tile-count receipts still apply). Live S6 should attach a ledger
later; this revision does not require every evidence bundle to carry one.

## Synthetic proof (required unit coverage)

1. **Positive:** overlapping reads, disjoint cores, full coverage, zero halo
   writes → PASS.
2. **Counterexamples:** core overlap → FAIL; coverage gap → FAIL;
   `halo_write_pixels>0` → FAIL; core not ⊆ read → FAIL.
3. Comfy static fixture audit remains
   `execution_allowed=false` / `maturity_remains=workflow_candidate`.

## Non-claims

- Does not run a real tile compositor or rewrite pixels.
- Does not start ComfyUI or load Flux / Siax weights.
- Synthetic PASS ≠ live GPU core-only write-back proof.
- Does not modify Method Registry maturity or `edit_permission`.
- Does not merge to `main`.

## See also

- `docs/S0_S7_METHOD_REGISTRY_RUNTIME.md` (S6 return_audit + future ledger note)
- `docs/COMFY_WORKFLOW_STATIC_AUDIT.md`
- `docs/GLOBAL_NOISE_FIELD_CONTRACT.md`
- Method `GEOMETRY_LOCKED_TILE_PLAN_RETURN` failure / test ids
