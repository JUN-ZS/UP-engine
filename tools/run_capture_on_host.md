# Run model-inventory capture on the operator PC

**Purpose:** produce a real `disk_capture` receipt by reading ComfyUI weight files
on the host. This is the only evidence grade that counts as disk capture.

**Does not:** run ComfyUI, load GPU weights for inference, unlock Flux, or merge PRs.

## Prerequisites

- UP-engine checkout on the `feat/comfy-workflow-static-audit-v0.1` branch (PR #18)
- Python 3.11+ with the package importable (`pip install -e .` from repo root)
- Models root present, e.g. `C:\Users\user\Documents\ComfyUI\models`

## Command (Windows / PowerShell)

```powershell
cd <UP-engine-checkout>
pip install -e .

ige capture-model-inventory `
  --models-root "C:\Users\user\Documents\ComfyUI\models" `
  --out "$env:USERPROFILE\Desktop\高清探\model_inventory_capture_receipt.json"
```

Or use the wrapper:

```powershell
.\tools\capture_model_inventory.ps1
```

Default asset set (Dev FP8 + Siax):

- `upscale_models/4x_NMKD-Siax_200k.pth`
- `vae/ae.safetensors`
- `clip/clip_l.safetensors`
- `clip/t5xxl_fp16.safetensors`
- `diffusion_models/flux1-dev.safetensors`

Flux ~24GB is hashed in 8 MiB chunks (streaming). Expect several minutes.

## Attach to static audit

```powershell
ige audit-comfy-workflow `
  --ui fixtures\comfy\workflow_ige_v03_dev_fp8.json `
  --api fixtures\comfy\workflow_cloud_api_prompt_v0.5.json `
  --capture-receipt "$env:USERPROFILE\Desktop\高清探\model_inventory_capture_receipt.json" `
  --out "$env:USERPROFILE\Desktop\高清探\comfy_static_audit_with_capture.json"
```

Confirm report fields:

- `backend_model_inventory.evidence_grade == disk_capture`
- `backend_model_inventory.inventory_live_verified == true` (receipt + filename/pin OK)
- `execution_allowed == false`
- `maturity_remains == workflow_candidate`

## Non-claims reminder

- CI unit tests never read this PC.
- Prior `backend_model_inventory_pc_dev_fp8_v0.1.json` is a **declared_record** only.
- `ae.safetensors` ≠ claim of `ae.sft` equivalence.
