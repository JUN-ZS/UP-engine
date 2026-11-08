# ComfyUI Siax / IGE — Preflight + Resource Guard v0.1

Status: **IMPLEMENTED IN DRAFT / STATICALLY VERIFIED / NOT LIVE-COMFYUI OR GPU TESTED**

This change continues the existing Desktop 高清探 + SIAX + ComfyUI_IGE_GlobalLogicCoordinator workflow. It does not replace the original SIAX/TTP baseline and does not promote Flux from workflow_candidate.

## Why this change exists

The archived v03 graph had two independent routes after the full-frame ImageScaleToTotalPixels node 34:

- Geometry route: node 34 → IGE_GlobalLogicCompiler node 300.
- Baseline A route: node 34 → reroute 116 → TTP tile batch 36 → image-list/VAE encode → sampler 67.

Candidate B depended on node 300, but Baseline A did not. ComfyUI evaluates by dependency, not by visual left-to-right arrangement. Therefore a requested A output could reach its sampler without waiting for node 300 to finish.

The v0.1 patch changes the dependency graph rather than relying on node placement.

## New node 342 — IGE_GlobalPreflightGate

Inputs: full-frame image emitted by node 34; full compiler bundle emitted by node 300; execution_allowed, default false.

It verifies:
- Compiler source shape and actual image shape agree.
- Contract canvas width/height agree with the actual tensor.
- Image SHA-256 equals both compiler bundle hash and contract source hash.
- Geometry status is exactly operator_confirmed.
- Geometry provenance confirmation is exactly operator_confirmed.
- Source-coordinate registration is exactly operator_confirmed.
- Explicit execution toggle is true.

It returns the original image tensor unchanged. It does not resize, warp, relabel, or edit geometry.

Graph change: node 34 → node 300 remains intact; node 34 and node 300 both feed node 342; node 342 output replaces the direct node 34 → reroute 116 edge; TTP node 36 and both A/B sampler paths are downstream of this gate.

A compile mismatch now fails before TTP batch creation, VAE encode, or either Flux sampler branch. The earlier SIAX upscale and 16MP normalization nodes are upstream of this gate; this patch does not claim to preflight those operations before they execute.

## New node 343 — IGE_TileBatchBudgetGuard

Inserted between the actual TTP tile batch node 36 and all tile consumers: original A tile-list/VAE path, IGE subset projector, and original tiles input to the post-decode logic gate.

Default limits in the new workflow variants:
- max_tiles_per_batch = 1
- min_free_vram_mb = 2048
- min_free_ram_mb = 4096

It records actual CUDA free/total memory, available system RAM, tile batch count, tile dimensions and tensor bytes. It fails closed when CUDA telemetry is unavailable, memory reserves are not met, or incoming image batch exceeds the configured maximum. It does not alter pixels or silently downscale a tile.

### Important limitation: guard is not yet the sequential runner

The existing TTP node emits a batch of tiles. If that batch contains more than one tile, the default one-tile guard deliberately blocks it before VAE encode/sampling. This is intentional fail-closed behaviour, not a claim that the current batched workflow is now runnable.

The next runtime milestone is a sequential tile executor:
1. Preserve TTP's real POSITIONS, ORIGINAL_SIZE and GRID_SIZE.
2. Extract one tile at a time with its existing core/halo coordinates.
3. Queue one tile inference at a time through the local ComfyUI API or a validated in-process adapter.
4. Release model/latent working sets between tiles where supported.
5. Save per-tile outputs and execution receipts for resume.
6. Restore tiles using the original coordinate ledger; never change canvas geometry to accommodate memory.
7. Record measured peak VRAM/RAM for the exact model SHA, dtype, tile dimensions and ComfyUI version before marking a resource profile validated.

A single tile and a free-memory snapshot are not a mathematical guarantee against OOM. Actual peak activation memory is model/node/version dependent. The new node is an admission guard, not an OOM-proof certification.

## New workflow variants

- pc_高清探/workflow_ige_v03_dev_fp8_preflight.json
- pc_高清探/workflow_ige_v03_dev_fp8_local_preflight.json
- packages/IGE_Global_Logic_Coordinator_v0.2/source_reference/original_siax_with_ige_logic_coordinator_v0.2_preflight.json

The original source_reference/original_siax_workflow.json remains the 29-node unmodified baseline. Prior v03 and v0.2 integration JSON files are retained unchanged as comparison sources.

## Current live size blocker is not fixed by this guard

The existing report still identifies geometry reference 5376×3024 and image entering node 300 3862×2172.

The compiler remains strict. The new gate will not pass until the actual node 34 output and registered geometry are brought into one verified coordinate frame. No scale factor is guessed and no polygons/masks/landmarks are silently relabelled.

The archived v03 graph sets node 34 to Lanczos / 16MP. The next investigation must inspect the actual runtime tensor shape at node 34 and the exact executed workflow/API prompt; a workflow export alone does not prove what tensor was executed.

## Tests and evidence

Root CI test tests/test_comfy_siax_preflight_workflows.py verifies all three patched JSON graphs parse, all graph links resolve, both sampler nodes 67 and 310 have both gates in their upstream dependency closure, the original SIAX baseline remains untouched, and both archived custom-node snapshots parse and register the new classes.

The packaged Comfy node test file also includes runtime tests for exact image/hash/canvas checks, default execution BLOCK, and multi-tile batch BLOCK.

These are code/unit tests only. This Draft change has not run the local ComfyUI UI, Siax inference, Flux GPU inference, Cloud GPU, or human visual acceptance.

## Permission boundary

- Flux remains workflow_candidate.
- execution_allowed defaults false.
- Geometry remains provisional until the operator updates geometry/provenance and source-alignment records.
- No Cloud job or production run is authorized by this change.
- No change is made to compile_contract to bypass mismatched canvas dimensions.