# Global noise field contract

## Purpose

Define what counts as a **coordinate-consistent global noise field** for
`FLUX_HR_TILE_IMG2IMG` tile workflows, how static / synthetic / live evidence is
classified, and the **three mechanism contracts**. Fail-closed. Offline /
synthetic CI in this revision — **no GPU**.

Linked Registry codes:

- Failure code: `E_NOISE_FIELD_NOT_GLOBAL`
- Test id: `NOISE_FIELD_NOT_GLOBAL`

## Pass surfaces (do not conflate)

| Surface | Flag | `evidence_grade` | Meaning |
|---------|------|------------------|---------|
| **Synthetic PASS** | `noise_synthetic_ok` | `synthetic_contract` | CI contract fixtures, static graph proofs, synthetic overlap / seam counterexamples |
| **Live PASS** | `noise_live_verified` | `live_capture` | Host capture of an actual noise tensor / generator proof with overlap equality |

Rules:

- Synthetic PASS **≠** Live PASS.
- CI **must not** set `noise_live_verified=true` in this revision (no GPU / no
  live tensor capture tool run here).
- `E_NOISE_FIELD_NOT_GLOBAL` **live gate** PASSes only when
  `noise_live_verified=true`. A synthetic-only receipt leaves the check
  **FAIL** with `synthetic_status=PASS`, `live_status=UNVERIFIED`.
- Current Dev FP8 / cloud fixtures remain `shared_seed_only` → both surfaces
  false → check **FAIL** (correct: no coordinate-indexed proof on the graph).

Analogous to inventory: `declared_record` ≠ `disk_capture`.

## Normative definition

A coordinate-consistent global noise field is a noise sample indexed by
**global canvas / latent coordinates** (or an equivalent deterministic mapping
from global XY → noise) such that two overlapping tiles read **identical noise
values in the overlapping region** when sampled from the same field.

**Non-definition:** Sharing one RNG seed across independent per-tile noise
draws does **not** satisfy this contract, even when every tile uses the same
seed `S`. Same seed ≠ same global field.

## Field kinds

| `field_kind` | Meaning | Global check |
|--------------|---------|--------------|
| `coordinate_indexed` | Noise at cell (x,y) is a function of global coordinates (+ optional seed) | Synthetic OK with overlap equality; Live PASS only with `live_capture` |
| `shared_seed_only` | `RandomNoise` (or equivalent) seed observed; no coordinate indexing proof | **FAIL** both surfaces |
| `independent_seed_per_tile` | Each tile has its own seed / stream | **FAIL** |
| `unknown` | No usable evidence | **FAIL** |

## Three mechanism contracts

Acceptance surfaces only — **not** GPU implementations.

| `mechanism` | Idea | Notes |
|-------------|------|-------|
| `global_latent_once_crop` | Generate **one** global latent noise tensor, then **crop** each tile by global coordinates | Memory scales with full-canvas latent |
| `coordinate_indexed_generator` | Stateless `(seed, global_x, global_y, channel) → sample` | Same seed alone ≠ this; no global buffer required |
| `global_then_local_refinement` | Global generate, then **local tile detail refinement** | **Architectural** (not a seed tweak). Must document global-latent compute/memory cost |

Each mechanism has explicit `acceptance_criteria` and `cost_notes` in
`mechanism_contract_specs()` (`src/ige/comfy/global_noise_contract.py`).

### Synthetic probes (CI)

1. **Positive (mech 1):** `synthetic_global_latent_crop_overlap_proof` — global
   buffer cropped by coords → overlap equal.
2. **Positive (mech 2):** `synthetic_coordinate_indexed_overlap_proof` — coord
   generator → overlap equal.
3. **Positive (mech 3):** `synthetic_global_then_local_refinement_acceptance` —
   global base + coord-indexed refinement agree; independent-reseed contrast
   fails.
4. **Counterexample:** `synthetic_shared_seed_independent_draws_counterexample`
   — same seed + independent RNG → overlap **mismatch**.
5. **Seam counterexample:** `synthetic_identical_local_arrays_seam_counterexample`
   — identical local arrays at different origins still seam-fail without
   coordinate indexing.

Catalog helper: `evaluate_all_mechanism_synthetic_acceptances()` → all three
`synthetic_status=PASS`, `noise_live_verified=false`.

## Receipt schema

- Schema id: `ige-global-noise-field-receipt/0.2` (legacy `0.1` still parseable)
- File: `schemas/global_noise_field_receipt.schema.json`
- Required surfaces: `noise_synthetic_ok`, `noise_live_verified`, `evidence_grade`
- `noise_live_verified=true` requires `evidence_grade=live_capture` plus
  `host_id`, `captured_at`, `tensor_or_generator_proof`, and passing
  `overlap_probe`. Synthetic receipts **cannot** set live true.
- Template for future host capture: `build_live_capture_receipt_template`
  (not filled / not verified in this revision).

## Static audit wiring

`ige audit-comfy-workflow` classifies observed `RandomNoise` seeds via
`classify_noise_evidence` and always emits:

- `noise_field_kind`, `noise_field_reason`
- `noise_evidence_grade`
- `noise_synthetic_ok` / `noise_live_verified`
- `noise_synthetic_status` / `noise_live_status`
- `noise_mechanism_contracts` — CI synthetic acceptance catalog (informational;
  **not** a claim that the workflow implements a mechanism)

Fixture pair today:

- `noise_field_kind: shared_seed_only`
- `noise_synthetic_ok: false`, `noise_live_verified: false`
- check `E_NOISE_FIELD_NOT_GLOBAL` → **FAIL**
- report stays `execution_allowed=false`,
  `maturity_remains=workflow_candidate`,
  `overall_status=BLOCKED_WORKFLOW_CANDIDATE`

## Non-claims

- Does not inject or rewrite ComfyUI noise nodes / workflow JSON.
- Does not run GPU inference or load Flux weights.
- Synthetic coordinate-indexed / mechanism proof ≠ live Comfy global noise.
- Mechanism catalog Synthetic PASS ≠ workflow Live PASS.
- Does not promote `FLUX_HR_TILE_IMG2IMG` out of `workflow_candidate`.
- Does not grant `edit_permission`.
- Live receipt tool is **defined but not run** on operator PC in this step.

## See also

- `docs/COMFY_WORKFLOW_STATIC_AUDIT.md`
- Method Registry failure / test ids for `FLUX_HR_TILE_IMG2IMG`
