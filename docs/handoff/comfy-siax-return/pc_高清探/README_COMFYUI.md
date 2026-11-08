# Geometry-Locked Two-Tile — Comfy Cloud v0.5

**Profile:** Cloud-preinstalled Flux1 Dev baseline; zero model-weight uploads and zero custom-LoRA imports.

## What is in the ZIP?
The ZIP contains the workflow graph, PC runner, input images, provisional geometry contract, planner/audit/stitch utilities and evidence tests. It does **not** need to contain model weights: Comfy Cloud already preinstalls standard models.

See `CLOUD_ASSET_MAPPING_V0.5.md` for the source-graph audit and exact distinction between preinstalled assets and active custom LoRAs.

## Cloud assets used
| Workflow component | Cloud asset |
|---|---|
| Diffusion UNet | `flux1-dev.safetensors` |
| VAE | `ae.safetensors` (standard Ae) |
| Text encoder 1 | `t5xxl_fp16.safetensors` |
| Text encoder 2 | `clip_l.safetensors` |
| Custom LoRA | none in the zero-import baseline |

The original local graph displayed `ae.sft`. v0.5 maps to Cloud's standard Ae VAE filename `ae.safetensors`; the old suffix mismatch must not be reported as a missing model. This selects the standard Ae VAE asset; no binary-hash equivalence is claimed from the filename alone.

## Important change versus your original workflow
Original local model stack:
- `CC_V1.safetensors`
- three active custom LoRAs: Kodak 0.85, 女生精致脸模 0.87, wow_details 0.93

Cloud baseline:
- preinstalled `flux1-dev.safetensors`
- no custom LoRA

This is an explicit model/profile change because CC_V1 and the custom LoRA trio were not in the provided Cloud inventory. It is **not** a claim of weight equivalence or identical style. The 4-step LoRA and the other style stack from the original ComfyUI UI were in bypass mode and were not part of the active original chain.

## What gets uploaded?
Only `tile_left.png` and `tile_right.png` as image inputs for the workflow run. No `.safetensors` or `.sft` model weights are uploaded by this package.

## Workflow graph
- Shared preinstalled Flux1 Dev UNet and standard Ae VAE / text encoders.
- Two independent image branches: VAE Encode → Sampler → VAE Decode → SaveImage.
- Independent left/right geometry-aware text conditioning.
- Shared fixed noise seed and same sampler/scheduler/step/denoise/guidance parameters.
- Core ComfyUI nodes only; no rgthree custom nodes.

## Run
Read `PC_BOT_TASK.txt`, then:

```powershell
powershell -ExecutionPolicy Bypass -File .\RUN_COMFY_CLOUD.ps1 -PreflightOnly
```

Only after live Cloud model and node preflight passes:

```powershell
powershell -ExecutionPolicy Bypass -File .\RUN_COMFY_CLOUD.ps1
```

The API key must be supplied through the secure PowerShell prompt / environment only. Never paste it into chat or place it in JSON.

## Evidence boundary
- Static / mock tests do not prove actual Cloud model inference.
- Live Cloud preflight does not prove credits or that GPU inference finished.
- Actual Cloud output does not prove geometry correctness.
- Geometry metrics do not promote the source annotation from `assistant_provisional` to `human_verified`.


## v0.5 preflight correction

The two `LoadImage.image` values are runtime-bound. Read-only preflight verifies local PNG SHA/dimensions and the live Cloud schema field, but does not require local filenames to appear in Cloud image dropdowns before upload. Only after preflight passes does Execute upload the two PNGs to `/api/upload/image`, bind the returned Cloud filenames, and submit `/api/prompt`. No other dropdown validation is relaxed.
