# Cloud Asset Mapping — v0.5

## Core correction
The original UI graph contains **model loader references**, not the model weight files themselves. The 24 MB/23.5 MB ZIP only needs to contain the workflow, runner, source/tile images, geometry plan and tests. It is correct that it contains no `.safetensors` or `.sft` weights.

Comfy Cloud preinstalls common model assets. A workflow loader must select an asset name actually exposed by the Cloud model category; writing a filename into a node does not trigger an automatic internet download.

## Exact original graph inventory
- `UNETLoader`: `CC_V1.safetensors` — absent from the supplied Cloud account preflight.
- `VAELoader`: `ae.sft` — old/local label; map to the Cloud standard Ae VAE `ae.safetensors`. Do not report this as a missing VAE.
- `DualCLIPLoader`: `t5xxl_fp16.safetensors` and `clip_l.safetensors` — standard Cloud Flux encoders.
- Three **active** custom LoRAs: Kodak Motion Picture Film style v1 (0.85), 女生精致臉模_01_F.1 (0.87), wow_details (0.93). They were absent from the supplied Cloud account preflight.
- `Flux Dev 4-step LoRA` node was bypassed. The separate two-LoRA ice/hologram style stack was also bypassed. They are not active dependencies of the original graph.

## v0.5 zero-import Cloud profile
| Component | Selected Cloud asset | Status |
|---|---|---|
| Diffusion UNet | `flux1-dev.safetensors` | Preinstalled stock Flux1 Dev; deliberate substitute for CC_V1, not equivalent weights |
| VAE | `ae.safetensors` | Standard preinstalled Ae VAE; corrects the old `ae.sft` filename mismatch |
| T5 | `t5xxl_fp16.safetensors` | Preinstalled standard Flux encoder |
| CLIP-L | `clip_l.safetensors` | Preinstalled standard Flux encoder |
| Custom LoRA | none | No user model import; intentionally omits the three active custom LoRAs |

This profile is a **Cloud smoke/geometry baseline**, not a reproduction of the local CC_V1 + three active LoRA appearance. The base-model substitution can change image style, identity cues, detail distribution and geometry stability. Results must be labelled as Flux1 Dev baseline and not compared as if they came from CC_V1.

## Why the package does not upload model weights
Only `tile_left.png` and `tile_right.png` are uploaded as image inputs when the workflow runs. Standard model weights are already resident in Comfy Cloud. No model weights are bundled, no local `models` directory is needed, and no checkpoint/VAE/encoder/LoRA upload is attempted.

## If exact original model parity is later required
A public/preinstalled Flux1 Dev baseline cannot replace `CC_V1` with weight equivalence. The three custom LoRAs also have to be available in the Cloud account's supported model library or imported through a supported remote source on an eligible plan. This is a different profile and should be tested as a separate branch. v0.5 never silently imports them or substitutes similar-looking LoRAs.

## Official references
- Comfy Cloud preinstalled model overview: https://comfy.org/cloud
- Supported model catalogue: https://comfy.org/hub/models/local/
- Official Flux.1 tutorial and asset names: https://docs.comfy.org/tutorials/flux/flux-1-text-to-image
- Cloud workflow API quickstart: https://docs.comfy.org/development/api-development/quickstart
