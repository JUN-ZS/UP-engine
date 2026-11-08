# SHQ ↔ ComfyUI Geometry-Locked Runtime v0.1 (Draft)

## Purpose

Connect the existing S2/S3/S4/S6 SHQ contracts to the live Comfy Cloud diagnostic adapter without granting Flux production maturity. Comfy generates one image per tile; UP-engine then performs a **real local S6 core-only compositor** using the frozen global canvas, approved mask and disjoint core plan.

This is intentionally separate from `ige agent-run` and the production callable dispatcher. It does not modify Registry maturity or route Comfy/Flux around its existing `workflow_candidate` block.

## Current integration boundary

- Reuses PR #21 `ComfyCloudClient` for Cloud health, model inventory, uploads, prompt submission, job polling and signed output downloads.
- Reuses `audit_api_workflow_live` for graph and tile-route validation. Workflow prompt text must declare `TILE: <tile_id>` and `GLOBAL TILE ORIGIN: [x0, y0]`.
- Binds every input `LoadImage` node to one frozen S4 tile, and every output `SaveImage` node back to exactly one tile.
- Generates tile read crops from the frozen baseline canvas; no caller-supplied crop can silently drift from the declared global bounds.
- After Cloud outputs are downloaded, writes only each disjoint `core_bounds`, further clipped by the S3 approved mask. Halo pixels are read context only and never written.
- Reloads the PNG master and measures changed pixels outside the approved mask and inside the protected mask. Both counts must be zero.

## Prepare a run

Inputs must be local files:

1. `source.png`: original/source identity anchor (S0 hash).
2. `canvas_4x.png`: frozen full-resolution baseline/output canvas; its pixel dimensions define the S2 coordinate canvas.
3. `s2_geometry_contract.json`: the existing SHQ Agent Driver `geometry_contract` fields (`source_sha256`, `canvas_path`, `canvas_sha256`, `geometry_human_verified`, `coordinate_frame`, `object_transform`, `model_scale`, `tile_size`, `tile_context`). See `examples/comfy_s2_geometry_contract.example.json` for shape only; replace both zero hashes and the illustrative transform with actual S2 evidence. The bridge verifies source/canvas hashes and `canvas dimensions = source dimensions × model_scale`.
4. `approved_edit_mask.png` and `protected_mask.png`: binary 0/255 masks at exactly the canvas dimensions. They must not overlap.
5. `workflow_cloud_api_prompt_v0.5.json`: the reviewed Comfy API graph.
6. A tile plan in the global pixel coordinate frame.

Example using the two-tile bridge workflow already present in this branch:

```powershell
ige-comfy-shq prepare `
  --workflow fixtures/comfy/workflow_cloud_api_prompt_v0.5.json `
  --source C:\\project\\source.png `
  --canvas C:\\project\\baseline_4x.png `
  --geometry-contract C:\\project\\s2_geometry_contract.json `
  --approved-mask C:\\project\\approved_edit_mask.png `
  --protected-mask C:\\project\\protected_mask.png `
  --tile-plan examples/comfy_geometry_tile_plan_citybridge.example.json `
  --output-dir runs/citybridge_geometry_locked `
  --out runs/citybridge_geometry_locked/run.json
```

`prepare` freezes hashes and creates each tile crop under `output-dir/inputs/`. It also creates `run.permission-review.json` with decision `PENDING_REVIEW`. It does not submit Cloud work.

The example tile plan matches the existing workflow's declared tile prompts: left tile origin `[1656,960]`, right tile origin `[2536,960]`, 1168×1024 read crops, and a 2048×1024 ROI. The core boundary is at global x=2680: each tile owns one 1024-pixel-wide core; the 288-pixel read overlap is split into read-only halo bands. Confirm those coordinates against the actual current canvas before using the example.

## S3 human review gate

Open the generated permission review JSON and inspect all seven artifacts: source, full canvas, S2 geometry contract, approved mask, protected mask, tile plan and workflow. Only after review, fill:

- `decision`: `APPROVED`
- `reviewer_ref`: an operator/reviewer reference
- `reviewed_at`: ISO-8601 timestamp with an explicit timezone
- `reviewed_artifacts`: all seven artifact identifiers

The runner checks every SHA/frame/path binding against the frozen manifest. The S2 contract must be exported from the reviewed geometry step; this bridge does not invent object transforms. This is a **human attestation**, not a cryptographic identity signature; that limitation is written into every receipt. The review scope can only be `diagnostic_candidate_only`.

## Live Cloud preflight (no submit)

```powershell
$env:COMFY_CLOUD_API_KEY = "YOUR_KEY"
ige-comfy-shq preflight runs/citybridge_geometry_locked/run.json --out runs/citybridge_geometry_locked/preflight.json
```

Preflight calls the live Cloud control plane and checks model filenames, graph edges, tile IDs, global origins, input node IDs and SaveImage mapping. It does not spend job credits.

## Explicit diagnostic submit + local S6

```powershell
ige-comfy-shq run runs/citybridge_geometry_locked/run.json `
  --permission runs/citybridge_geometry_locked/run.permission-review.json `
  --diagnostic-submit --timeout 1800
```

The `--diagnostic-submit` flag is mandatory because this submits a real Cloud job and may consume credits. For each output:

- SaveImage node identity must map to exactly one planned tile.
- Exactly one output must exist for every tile; unknown, duplicate or missing outputs fail closed.
- Downloaded image dimensions must equal the declared read crop dimensions. No implicit resize is allowed.
- Actual output bytes are hashed and inserted into the S6 tile ledger.
- The local compositor extracts only `core_bounds` from each tile and pastes only where the approved mask is white.
- The persisted master is reloaded and pixel-compared to the frozen canvas.

The result is `<prompt_id>_geometry_locked_master.png` plus a JSON receipt and the original Cloud tile outputs.

## Evidence and blockers

A successful run can report:

- **Observed:** Cloud job ID/status, SaveImage output mapping, downloaded tile bytes and SHA-256.
- **Derived:** exact tile geometry, core coverage, image dimensions, local write-back pixel counts and master SHA.
- **S6:** `PASS_LOCAL_CORE_ONLY_COMPOSITOR` only when the live downloaded outputs pass the actual local write-back and protected-pixel audit.

It always retains these production blockers in v0.1:

1. `E_NOISE_FIELD_NOT_GLOBAL`: current workflow does not prove a coordinate-indexed global noise tensor or overlap equality.
2. `E_CLOUD_MODEL_SHA_UNVERIFIED`: Cloud catalogue filenames do not prove exact weights SHA or loaded tensor identity.
3. `E_S7_HUMAN_REVIEW_REQUIRED`: independent reload/visual acceptance has not yet been performed.

Every receipt remains `candidate_accepted=false`, `execution_allowed=false`, `edit_permission=false`, and `maturity_remains=workflow_candidate`. The local S6 compositor does not rewrite Comfy workflow maturity and does not change the existing Agent Driver allowlist.

## Tests

`tests/test_geometry_locked_comfy.py` covers S2 source/canvas/scale binding, manifest and crop generation, S3 binding, fail-closed diagnostics, exact-once core composition, approved/protected mask preservation, unsafe tile IDs, wrong-size output rejection, and a mocked Cloud-to-S6 run. `tests/test_geometry_cli.py` checks command parsing. Mocked Cloud tests are not GPU inference; the existing PR #21 workflow tests remain separate.

## Non-goals in this PR

- No shared-latent backend or coordinate-indexed global noise implementation.
- No Cloud model loaded-tensor attestation.
- No internal Comfy custom-node compositor; S6 is an explicit local post-process over downloaded tile outputs.
- No automatic S7 approval, no Registry promotion, no `main` merge.
- No bundling of source image assets, user API keys, or the research-only 22-method toolkit into the production runtime.
