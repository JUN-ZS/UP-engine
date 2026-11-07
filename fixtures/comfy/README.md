# ComfyUI workflow fixtures (static audit only)

Vendored copies used by `ige audit-comfy-workflow`. These files are inventory
inputs — they do **not** prove GPU inference, live conditioning routing, or a
coordinate-consistent global noise field.

| File | Role | Evidence grade |
|------|------|----------------|
| `workflow_ige_v03_dev_fp8.json` | PC Dev FP8 + IGE v0.3 UI graph | n/a (workflow) |
| `workflow_cloud_api_prompt_v0.5.json` | Geometry-locked two-tile cloud API prompt | n/a (workflow) |
| `inventory_ige_v03_cloud_v0.5.json` | Stripped class/model inventory + source hashes | n/a |
| `backend_model_inventory_pc_dev_fp8_v0.1.json` | **Declared record** of PC Dev FP8 weight SHA strings + custom-node notes | `declared_record` |
| `synthetic_*.json` | Tiny negative fixtures for unit tests | n/a |

**Declared ≠ captured.** The backend inventory fixture records SHA strings for
offline filename/pin checks. It is **not** a disk-capture receipt, and CI does
**not** re-read operator PC weight files. Produce live disk evidence with:

```bash
ige capture-model-inventory --models-root <ComfyUI/models> --out capture_receipt.json
```

See `docs/BACKEND_MODEL_INVENTORY.md` and `tools/run_capture_on_host.md`.

`FLUX_HR_TILE_IMG2IMG` remains `workflow_candidate`; static PASS never sets
`execution_allowed=true`.
