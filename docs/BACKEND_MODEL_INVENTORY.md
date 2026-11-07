# Offline backend model inventory

## Purpose

Record **host-measured** ComfyUI weight filenames + SHA-256 digests and custom
node pack fingerprints as a fail-closed precondition helper.

This does **not** run GPU inference, does **not** promote
`FLUX_HR_TILE_IMG2IMG` out of `workflow_candidate`, and does **not** grant
`edit_permission`.

## Schema / fixture

- Schema: `schemas/backend_model_inventory.schema.json`
  (`ige-backend-model-inventory/0.1`)
- Example (PC Dev FP8 host `DESKTOP-GNMQ0PF`):
  `fixtures/comfy/backend_model_inventory_pc_dev_fp8_v0.1.json`

Absolute Windows paths may appear as `host_metadata` (`absolute_path`,
`models_root`). CI validation uses `relative_path` + `filename` + `sha256` only.

## CLI

```bash
ige validate-model-inventory \
  --path fixtures/comfy/backend_model_inventory_pc_dev_fp8_v0.1.json

ige audit-comfy-workflow \
  --ui fixtures/comfy/workflow_ige_v03_dev_fp8.json \
  --api fixtures/comfy/workflow_cloud_api_prompt_v0.5.json \
  --model-inventory fixtures/comfy/backend_model_inventory_pc_dev_fp8_v0.1.json \
  --out /tmp/comfy_static_audit.json
```

Merged audits add check `E_BACKEND_MODEL_INVENTORY`. Even when that check
**PASS**es, the report keeps:

- `execution_allowed: false`
- `maturity_remains: workflow_candidate`
- `overall_status: BLOCKED_WORKFLOW_CANDIDATE`

## Siax registry pin

`SIAX4X` inventory SHA-256 must equal the pinned
`SIAX4X_TILE_CORE_SR.model_sha256` in `src/ige/data/method_registry.json`
when both are present. Matching the pin is a precondition check only — it does
not authorize pixel edits.

## Recorded Dev FP8 assets (v0.1 fixture)

| asset_id | role | filename | sha256 |
|----------|------|----------|--------|
| SIAX4X | upscale | `4x_NMKD-Siax_200k.pth` | `560424d9…127e` (matches Registry pin) |
| FLUX_AE | vae | `ae.safetensors` | `afc8e282…9e38` (≠ claim of `ae.sft` equivalence) |
| CLIP_L | clip | `clip_l.safetensors` | `660c6f5b…6cdd` |
| T5XXL_FP16 | clip | `t5xxl_fp16.safetensors` | `6e480b09…7635` |
| FLUX1_DEV | unet | `flux1-dev.safetensors` | `4610115b…abd7` |

Load option (not a file SHA): `unet_weight_dtype=fp8_e4m3fn_fast`.

Flux / AE / CLIP SHAs are recorded for **future** precondition use. Method
Registry maturity fields are **not** rewritten by this inventory.

## Non-claims

- No ComfyUI / GPU inference.
- Inventory PASS ≠ execution_allowed.
- Custom-node git SHAs are install fingerprints only.
- Does not start steps for global-noise contract or core/halo ledger.
