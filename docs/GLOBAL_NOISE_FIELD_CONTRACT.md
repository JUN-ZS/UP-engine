# Global noise field contract

## Purpose

Define what counts as a **coordinate-consistent global noise field** for
`FLUX_HR_TILE_IMG2IMG` tile workflows, and how static / synthetic evidence is
classified. Fail-closed. Offline only in this revision.

Linked Registry codes:

- Failure code: `E_NOISE_FIELD_NOT_GLOBAL`
- Test id: `NOISE_FIELD_NOT_GLOBAL`

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
| `coordinate_indexed` | Noise at cell (x,y) is a function of global coordinates (+ optional seed) | PASS only with `verified=true` and non-empty overlap equality |
| `shared_seed_only` | `RandomNoise` (or equivalent) seed observed; no coordinate indexing proof | **FAIL** |
| `independent_seed_per_tile` | Each tile has its own seed / stream | **FAIL** |
| `unknown` | No usable evidence | **FAIL** |

## Synthetic proof (required unit coverage)

1. **Positive:** Two overlapping tile windows sample a deterministic
   coordinate-indexed function → overlap cells equal.
2. **Counterexample:** Two overlapping tiles restart an independent RNG at the
   **same** seed and fill in local order → overlap cells **disagree** → must
   classify as **not** global (`shared_seed_only` / FAIL).

Implementation: `src/ige/comfy/global_noise_contract.py`.

## Receipt schema

Future / optional evidence object:

- Schema id: `ige-global-noise-field-receipt/0.1`
- File: `schemas/global_noise_field_receipt.schema.json`
- `verified` remains `false` until a live or accepted synthetic
  coordinate-indexed overlap proof is attached.
- `verified=true` is only valid with `field_kind=coordinate_indexed`.

## Static audit wiring

`ige audit-comfy-workflow` classifies observed `RandomNoise` seeds via
`classify_noise_evidence`. Presence of a shared seed alone yields:

- `noise_field_kind: shared_seed_only`
- check `E_NOISE_FIELD_NOT_GLOBAL` → **FAIL**
- report stays `execution_allowed=false`,
  `maturity_remains=workflow_candidate`,
  `overall_status=BLOCKED_WORKFLOW_CANDIDATE`

## Non-claims

- Does not inject or rewrite ComfyUI noise nodes / workflow JSON.
- Does not run GPU inference or load Flux weights.
- Synthetic coordinate-indexed proof ≠ live Comfy global noise implementation.
- Does not promote `FLUX_HR_TILE_IMG2IMG` out of `workflow_candidate`.
- Does not grant `edit_permission`.

## See also

- `docs/COMFY_WORKFLOW_STATIC_AUDIT.md`
- Method Registry failure / test ids for `FLUX_HR_TILE_IMG2IMG`
