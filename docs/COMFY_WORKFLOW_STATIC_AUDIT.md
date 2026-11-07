# ComfyUI workflow static audit (FLUX_HR_TILE candidate)

## Purpose

Provide a **fail-closed, non-GPU** inventory audit of ComfyUI UI graphs and API
prompts that may later back `FLUX_HR_TILE_IMG2IMG`.

This sits on top of the S0–S7 Method Registry runtime (PR #17). It does **not**
promote method maturity and does **not** grant edit permission.

## CLI

```bash
ige audit-comfy-workflow \
  --ui fixtures/comfy/workflow_ige_v03_dev_fp8.json \
  --api fixtures/comfy/workflow_cloud_api_prompt_v0.5.json \
  --out /tmp/comfy_static_audit.json
```

Exit codes:

- `0` — structural candidate inventory OK (required nodes + Dev FP8 filenames)
- `2` — structural inventory blockers (`E_COMFY_NODE_MISSING`,
  `E_MODEL_INVENTORY_MISMATCH`, or UI/API value mismatch)
- Help / argparse errors follow argparse defaults

Even on exit `0`, the report always includes:

- `execution_allowed: false`
- `maturity_remains: workflow_candidate`
- `overall_status: BLOCKED_WORKFLOW_CANDIDATE`

## Checks (mapped to Registry failure codes where possible)

| Code | Meaning in this static audit |
|------|------------------------------|
| `E_COMFY_NODE_MISSING` | Required inventory classes absent from supplied graphs |
| `E_MODEL_INVENTORY_MISMATCH` | Declared UNET/VAE/CLIP/dtype filenames ≠ expected Dev FP8 set (**filenames only**) |
| `E_TILE_CONDITIONING_UNROUTED` | PASS only as *static* per-tile prompt evidence; never live routing proof |
| `E_NOISE_FIELD_NOT_GLOBAL` | Same `RandomNoise` seed alone → `noise_field_kind=shared_seed_only` → **FAIL**. Surfaces: `noise_synthetic_ok` ≠ `noise_live_verified` (see `docs/GLOBAL_NOISE_FIELD_CONTRACT.md`) |

Optional UI inventory (recorded, not execution proof): `IGE_TileNoiseMask`,
`SetLatentNoiseMask`, TTP tile nodes, `UpscaleModelLoader` (Siax filename).

## Non-claims

- No ComfyUI process started; no GPU inference.
- No Flux / Siax weight files loaded; no weight SHA verification.
- No S7 acceptance; no halo/core pixel proof on real outputs.
- Static per-tile `CLIPTextEncode` text ≠ live independent conditioning routes.
- Same seed ≠ global noise field (`shared_seed_only` ≠ `coordinate_indexed`).
- Synthetic PASS (`noise_synthetic_ok` / `synthetic_contract`) ≠ Live PASS (`noise_live_verified` / `live_capture`); CI never sets live true here.
- Does not modify `src/ige/data/method_registry.json`.
- Does not unblock `FLUX_HR_TILE_IMG2IMG`.

## Fixtures

See `fixtures/comfy/README.md`. Primary sources:

- UI: `workflow_ige_v03_dev_fp8.json` (PC Dev FP8 + IGE v0.3)
- API: `workflow_cloud_api_prompt_v0.5.json` (geometry-locked two-tile cloud)

## Remaining blockers before any live GPU step

1. Host has matching custom nodes + weight files; verify weight SHAs.
2. Prove each tile's conditioning is independently routed at runtime.
3. Prove coordinate-consistent global noise **live** (`noise_live_verified`; not seed equality alone; synthetic catalog ≠ live).
4. Prove core-only write / halo non-write / coverage on real outputs.
5. Independent S7 on real GPU outputs.
6. Explicit Method Registry maturity change (out of scope here).

## Offline backend model inventory

Optional `--model-inventory` attaches a host-recorded
`backend_model_inventory` JSON (filenames + SHA-256 + custom node packs).

```bash
ige audit-comfy-workflow \
  --ui fixtures/comfy/workflow_ige_v03_dev_fp8.json \
  --api fixtures/comfy/workflow_cloud_api_prompt_v0.5.json \
  --model-inventory fixtures/comfy/backend_model_inventory_pc_dev_fp8_v0.1.json
```

Adds check `E_BACKEND_MODEL_INVENTORY`. Standalone validator:

```bash
ige validate-model-inventory --path fixtures/comfy/backend_model_inventory_pc_dev_fp8_v0.1.json
```

See `docs/BACKEND_MODEL_INVENTORY.md`. Inventory PASS still leaves
`execution_allowed=false` and Flux as `workflow_candidate`. Siax SHA in the
v0.1 PC fixture exactly matches the Method Registry pin for
`SIAX4X_TILE_CORE_SR`.

## Related offline contracts (PR #18 steps 1–3)

- `docs/BACKEND_MODEL_INVENTORY.md` — offline weight SHA inventory
- `docs/GLOBAL_NOISE_FIELD_CONTRACT.md` — same seed ≠ global noise field; Synthetic≠Live; three mechanism contracts
- `docs/TILE_CORE_HALO_LEDGER.md` — Core/Halo exact-once write-back ledger (synthetic S6 gates)

```bash
ige audit-tile-ledger path/to/ledger.json --out /tmp/tile_ledger_audit.json
```

None of these promote `FLUX_HR_TILE_IMG2IMG` or set `execution_allowed=true`.



## Backend inventory evidence grades

- `--model-inventory` → `evidence_grade=declared_record` (fixture/hand-authored; not CI re-hash of PC files)
- `--capture-receipt` → `evidence_grade=disk_capture` (from `ige capture-model-inventory`)
- Either way: `execution_allowed=false`; Flux remains `workflow_candidate`
- Details: `docs/BACKEND_MODEL_INVENTORY.md`
