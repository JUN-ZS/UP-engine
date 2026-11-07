# ComfyUI workflow fixtures (static audit only)

Vendored copies used by `ige audit-comfy-workflow`. These files are inventory
inputs — they do **not** prove GPU inference, weight SHA, live conditioning
routing, or a coordinate-consistent global noise field.

| File | Role |
|------|------|
| `workflow_ige_v03_dev_fp8.json` | PC Dev FP8 + IGE v0.3 UI graph |
| `workflow_cloud_api_prompt_v0.5.json` | Geometry-locked two-tile cloud API prompt |
| `inventory_ige_v03_cloud_v0.5.json` | Stripped class/model inventory + source hashes |
| `synthetic_*.json` | Tiny negative fixtures for unit tests |

`FLUX_HR_TILE_IMG2IMG` remains `workflow_candidate`; static PASS never sets
`execution_allowed=true`.
