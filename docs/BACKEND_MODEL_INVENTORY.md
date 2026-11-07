# Backend model inventory — declared record vs disk capture

## Purpose

Two evidence grades exist. They must not be conflated.

| Grade | Source | What it proves | What it does **not** prove |
|-------|--------|----------------|----------------------------|
| `declared_record` | Hand-authored / fixture JSON (`backend_model_inventory*.json`) | Schema fields, filename↔workflow alignment, Siax SHA **string** equals Registry pin | That this process (or CI) re-read operator PC weight files |
| `disk_capture` | Receipt from `ige capture-model-inventory` | A named host opened the files under `--models-root`, streamed size+SHA-256, and wrote a provenance receipt | Live ComfyUI load readiness, GPU inference, Flux maturity, `edit_permission` |

**CI never reads the operator's PC weights.** Unit tests use tiny temporary files only to exercise the capture tool.

This never runs GPU inference, never promotes `FLUX_HR_TILE_IMG2IMG` out of `workflow_candidate`, and never grants `edit_permission`.

## Schemas / fixtures

- Declared schema: `schemas/backend_model_inventory.schema.json` (`ige-backend-model-inventory/0.1`)
- Capture receipt schema: `schemas/model_inventory_capture_receipt.schema.json` (`ige-model-inventory-capture-receipt/0.1`)
- Example declared record (PC Dev FP8 host `DESKTOP-GNMQ0PF`):
  `fixtures/comfy/backend_model_inventory_pc_dev_fp8_v0.1.json`
  — marked `evidence_grade: declared_record`. Treat SHA strings as **operator-supplied declared values**, not as CI re-verification.

Operator: run capture on the PC to produce a real `disk_capture` receipt (see `tools/run_capture_on_host.md`).

## CLI

### Capture (disk evidence)

```bash
ige capture-model-inventory \
  --models-root "C:\Users\user\Documents\ComfyUI\models" \
  --out "%USERPROFILE%\Desktop\高清探\model_inventory_capture_receipt.json"
```

Optional:

- `--expect-relative REL` (repeatable) — capture a subset
- `--manifest PATH` — JSON with `assets[{asset_id,role,relative_path,expected_size_bytes?}]`
- `--chunk-size N` — stream chunk size (default 8 MiB; safe for ~24GB Flux)

Fail-closed: missing file or expected-size mismatch aborts; no receipt is written.

### Validate declared record

```bash
ige validate-model-inventory \
  --path fixtures/comfy/backend_model_inventory_pc_dev_fp8_v0.1.json
```

Prints `inventory_declared_ok` / `inventory_live_verified=false` for declared JSON.

### Static audit

```bash
# Declared only → evidence_grade=declared_record; inventory_live_verified=false
ige audit-comfy-workflow \
  --ui fixtures/comfy/workflow_ige_v03_dev_fp8.json \
  --api fixtures/comfy/workflow_cloud_api_prompt_v0.5.json \
  --model-inventory fixtures/comfy/backend_model_inventory_pc_dev_fp8_v0.1.json \
  --out /tmp/comfy_static_audit.json

# Capture receipt → evidence_grade=disk_capture when receipt validates
ige audit-comfy-workflow \
  --ui fixtures/comfy/workflow_ige_v03_dev_fp8.json \
  --api fixtures/comfy/workflow_cloud_api_prompt_v0.5.json \
  --capture-receipt /path/to/model_inventory_capture_receipt.json \
  --out /tmp/comfy_static_audit.json
```

Even when checks **PASS**, the report keeps:

- `execution_allowed: false`
- `maturity_remains: workflow_candidate`
- `overall_status: BLOCKED_WORKFLOW_CANDIDATE`

## Flags (precondition helper)

`backend_model_inventory_verified(...)` returns:

- `inventory_declared_ok` — declared JSON schema + role/filename (+ optional workflow) OK
- `inventory_capture_present` — a capture receipt was supplied
- `inventory_live_verified` — capture receipt provenance OK (+ workflow match when asked)
- `verified` — **alias of `inventory_live_verified` only** (declared fixture alone is `false`)
- `execution_allowed` — always `false`

## Siax registry pin

`SIAX4X` SHA-256 (declared string or capture digest) must equal pinned
`SIAX4X_TILE_CORE_SR.model_sha256` when both are present. Matching the pin is a
precondition check only — it does not authorize pixel edits.

## Recorded Dev FP8 assets (declared fixture v0.1)

| asset_id | role | filename | sha256 (declared) |
|----------|------|----------|-------------------|
| SIAX4X | upscale | `4x_NMKD-Siax_200k.pth` | `560424d9…127e` (matches Registry pin string) |
| FLUX_AE | vae | `ae.safetensors` | `afc8e282…9e38` (≠ claim of `ae.sft` equivalence) |
| CLIP_L | clip | `clip_l.safetensors` | `660c6f5b…6cdd` |
| T5XXL_FP16 | clip | `t5xxl_fp16.safetensors` | `6e480b09…7635` |
| FLUX1_DEV | unet | `flux1-dev.safetensors` | `4610115b…abd7` |

Load option (not a file SHA): `unet_weight_dtype=fp8_e4m3fn_fast`.

## Non-claims

- No ComfyUI / GPU inference.
- Declared PASS ≠ disk capture ≠ execution_allowed.
- Capture PASS ≠ Flux maturity promotion.
- Custom-node git SHAs (when present) are install fingerprints only; capture tool does not re-check git HEAD unless extended later.
- Global-noise contract and core/halo ledger are separate modules.
