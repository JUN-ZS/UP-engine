# IGE Global Logic Coordinator v0.2

**Purpose:** add a global rule/geometry coordination layer around the user's existing SIAX full-frame upscale → TTP tile batch → shared sampler → TTP assembly workflow. This package does not replace the Siax upscaler or TTP tiler.

## The architectural correction

The target is **not** to eliminate tiling. The target is to prevent each tile from making independent semantic decisions.

The original workflow supplied in `source_reference/original_siax_workflow.json` already:

1. applies `4x_NMKD-Siax_200k.pth` to the full input;
2. normalizes the result to 16 MP with Lanczos;
3. creates a TTP tile batch and carries `POSITIONS`, `ORIGINAL_SIZE`, `GRID_SIZE`;
4. converts the tile batch to an image list, VAE-encodes it, processes it through one `SamplerCustomAdvanced` node, and decodes it;
5. reassembles tiles through `TTP_Image_Assy`.

The v0.2 layer adds a shared global contract, projects that contract into each tile's spatial subset, attaches a per-tile latent noise mask before the candidate-B sampler, applies exact pixel write gates after decode, reconciles overlap by candidate agreement rather than unconditional blending, audits the full canvas, and records feedback for the next iteration. The original SIAX workflow is preserved as baseline A; candidate B duplicates the sampler/decode path.

## Package structure

- `ige_logic/core.py`: versioned contract, rule hierarchy, pixel action map, TTP coordinate adapter, global-to-tile projection.
- `ige_logic/prompting.py`: one global conditioning prompt and local subset prompt profiles.
- `ige_logic/masks.py`: maps parent action/geometry rules into conservative per-tile latent denoise masks.
- `ige_logic/reconcile.py`: PRESERVE/REJECT pixel gate and overlap consensus with source fallback on conflict.
- `ige_logic/audit.py`: full-frame invariant checks and acceptance blocking.
- `ige_logic/coordinator.py`: compatible subset grouping and iteration feedback.
- `ige_logic/ttp.py`: offline reference implementation of TTP's published `TTP_Image_Tile_Batch` position algorithm; production node consumes the actual TTP metadata outputs.
- `custom_nodes/ComfyUI_IGE_GlobalLogicCoordinator/`: eight ComfyUI nodes.
- `source_reference/`: the original UI workflow and geometry handoff files supplied in this conversation, plus a node/edge map.

## Eight custom nodes

1. `IGE · Global Logic Compiler`
   - Inputs: full-frame image, geometry JSON file, policy JSON file.
   - Outputs: global contract, action map, geometry-guard map, contract report, global conditioning prompt.
2. `IGE · TTP Global-to-Subset Projector`
   - Inputs: contract + the actual `TTP_Image_Tile_Batch` IMAGE/POSITIONS/ORIGINAL_SIZE/GRID_SIZE outputs.
   - Outputs: one inherited subset per tile, task JSON, execution-group JSON.
3. `IGE · Tile Latent Noise Mask`
   - Converts each tile action map into a conservative MASK at latent resolution. PRESERVE/REJECT become zero-noise cells; REFINE/GENERATE use configured weights; geometry attenuation stays inactive until operator-confirmed coordinate registration.
   - This mask connects to stock `SetLatentNoiseMask` before Candidate B `SamplerCustomAdvanced`.
4. `IGE · Logic Map Preview`
   - Visual diagnostic only; action-map numeric data remains separate.
5. `IGE · Tile Logic Gate`
   - Restores exact source pixels in PRESERVE/REJECT zones. REFINE/GENERATE candidate pixels are passed through for later reconciliation.
6. `IGE · Global Consensus Reconciler`
   - Reassembles in full-frame coordinates. Non-overlap uses the one available tile. Overlap is written only when the tile candidates agree; conflict reverts to source pixels. Pixels outside the TTP coverage remain unchanged.
7. `IGE · Global Acceptance Audit`
   - Checks outside-coverage identity, protected pixels, overlap conflict, geometry observations, source-coordinate registration and conditioning-group compatibility.
8. `IGE · Iteration Feedback Compiler`
   - Records failed subsets and operator feedback into a next-iteration state proposal. It does not silently alter policy or promote geometry.

## Rule model

Action codes:

- `PRESERVE`: exact source pixels only.
- `REFINE`: local appearance/detail may change, inherited geometry/semantic rules remain.
- `GENERATE`: new content is permitted only inside an explicit operator-confirmed region.
- `REJECT`: candidate content is vetoed; source pixels are restored.

Spatial operator rules can explicitly override the global default. Where spatial rules overlap, the most restrictive action wins. A child subset may tighten but cannot weaken a parent rule. `REJECT` is absolute.

The shipped policy defaults to `REFINE`, with new semantics disabled. The central subject rule is `REFINE` with silhouette/landmark/pose constraints. The supplied subject geometry remains `assistant_provisional`.

## Critical execution limitation

The stock `SamplerCustomAdvanced` has one shared conditioning input for its latent batch. Candidate B uses one **global shared prompt**; local subset instructions are compiled into execution groups. If those groups differ, the audit blocks acceptance until the groups are separately executed or a per-sample conditioning adapter has been independently validated.

Candidate B now also receives a per-tile latent noise mask through stock `SetLatentNoiseMask` before its duplicated sampler. `SamplerCustomAdvanced` consumes the optional `noise_mask` field in its latent input. Fractional weights are intended as soft denoising attenuation, not a hard geometry lock. Exact PRESERVE/REJECT pixel regions are restored after decode. The original A branch remains unchanged, including its original blank prompt and TTP assembly. Geometry still requires independent observations and operator acceptance.

## Source-coordinate warning for this supplied geometry

The supplied `object_geometry.provisional.json` was annotated on a 5376×3024 Lanczos-derived reference. The original SIAX workflow's 16MP canvas may have the same dimensions, but the post-SIAX pixel content is not byte-identical to that Lanczos reference. Therefore the default policy marks `source_alignment_status` as `pending_operator_registration_to_siax_output`. The matching dimensions are not proof that polygon/landmark coordinates have been registered to the actual SIAX output. Acceptance remains blocked until registration is confirmed.

## Installation

1. Copy `custom_nodes/ComfyUI_IGE_GlobalLogicCoordinator/` into `ComfyUI/custom_nodes/`.
2. Copy `config/object_geometry.provisional.json` and `config/global_logic_policy.json` into `ComfyUI/custom_nodes/ComfyUI_IGE_GlobalLogicCoordinator/config/` (already included in this folder).
3. Restart ComfyUI.
4. The patched JSON contains two paths: baseline A unchanged and candidate B with global conditioning/noise-mask coordination.
5. Open `source_reference/original_siax_with_ige_logic_coordinator_v0.2.json`, then follow `docs/WORKFLOW_INTEGRATION.md` and `source_reference/workflow_integration_spec.json`.

## CLI

Python 3.10+; dependencies: numpy, Pillow. ComfyUI supplies Torch. `IGE_IterationFeedback` produces a state JSON that can be supplied to the compiler on the next cycle; it carries lineage/warnings but never auto-applies policy changes. Example:

```bash
python -m ige_logic emit-ttp-metadata --width 5376 --height 3024 --tile-width 2048 --tile-height 1024 --out /tmp/ttp_positions.json
python -m ige_logic compile --source /path/to/siax_16mp.png --geometry config/object_geometry.provisional.json --policy config/global_logic_policy.json --positions /tmp/ttp_positions.json --out-dir /tmp/ige_compile
# Optional: pass the prior iteration state to preserve lineage
python -m ige_logic compile --source /path/to/siax_16mp.png --geometry config/object_geometry.provisional.json --policy config/global_logic_policy.json --positions /tmp/ttp_positions.json --state /path/to/iteration_state.json --out-dir /tmp/ige_compile_next
```

For live TTP runs, do not use guessed tile dimensions: connect the actual `POSITIONS`, `ORIGINAL_SIZE`, and `GRID_SIZE` outputs to the projector node.

## Tests

```bash
python -m unittest discover -s tests -v
python -m compileall -q ige_logic custom_nodes tests
```

Tests use synthetic images and actual source-schema examples. They validate rule inheritance, coordinate mapping, overlap consensus, fallback, preservation and audit blocking. They do not execute Siax, Flux or a GPU sampler.

## Status

`PROTOTYPE / LOCAL TESTED / NOT GPU EXECUTED / NOT LIVE-CLOUD VALIDATED`.

## v0.2 validation snapshot

- Static workflow graph: **45 nodes / 75 links**. The original 29-node workflow remains the baseline path; 16 nodes were added for the B branch and coordinator.
- Local test suite: **21 tests passed** (`python -m unittest discover -s tests -v`).
- Metamorphic check: the same global policy/action map projects consistently into different tile grids. This proves coordinate projection invariance at the coordinator layer; it does **not** prove diffusion output invariance when tile boundaries move.
- Offline replay of Cloud Job `c88c70e5`: two prior ROI tile outputs were reconciled against their supplied two-tile position fixture. The replay is **not** a replay of the original six-tile SIAX/TTP full-frame runtime batch.
- Replay result: 294,912 overlap pixels; 122,860 conflicts (41.66%); overlap P95 spread 0.21046 against 0.20; both participating tiles are identified as failed subsets; all conflicts abstain to source pixels; outside tile coverage changed pixels = 0; audit remains `BLOCKED_PENDING_GEOMETRY_AND_CONSENSUS`.

## Important limits of the current candidate-B path

1. The shipped policy defaults the whole canvas to `REFINE`. With the current default `refine_noise_weight=1.0`, this produces a full-strength latent noise mask except where explicit `PRESERVE` / `REJECT` rules exist. The provisional person rule marks a geometry guard, but the guard's denoise attenuation is intentionally **inactive** until both object geometry and coordinate registration are operator-confirmed. The shipped config therefore does not yet hard-protect the person during sampling.
2. The post-decode pixel gate can exactly restore `PRESERVE` / `REJECT` pixels. That is a write gate, not a guarantee that diffusion did not alter them internally before restoration.
3. Candidate B has one global CLIP conditioning shared by its latent batch. Local subset prompts are compiled and grouped for compatibility reporting; this graph does not yet execute different local prompt groups separately. Acceptance blocks when a single shared sampler would be incompatible.
4. `SetLatentNoiseMask` is a soft denoising mask. Fractional values attenuate denoising; they do not guarantee exact geometry, identity, pose or semantic preservation.
5. The v0.2 graph and nodes have passed local Python/mock tests only. They have not been loaded in a live ComfyUI UI, nor run on the actual SIAX/Flux GPU path.

Treat B as an experimental control branch, not a production-approved workflow. Keep A as the original baseline until live node compatibility and the required geometric/semantic observations are verified.
