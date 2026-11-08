# ComfyUI Siax-return: execution gate and resource preflight v0.1

This is a repair layer on the archived Siax + IGE workflow, not a replacement workflow.

## What changed

- Added IGE_ExecutionAuthorizationGate to both archived copies of ComfyUI_IGE_GlobalLogicCoordinator.
- Added a workflow patcher that inserts this gate in front of every SamplerCustomAdvanced.latent_image input. Baseline A and Candidate B are both gated.
- Added a read-only resource preflight helper for graph inspection and current free VRAM/RAM probes.
- Added CPU-only tests. No ComfyUI UI, Siax model, Flux sampler, GPU inference or Cloud job was run.

## Execution authorization

The gate is intentionally fail-closed. Its authorization widget defaults to an empty JSON object. It rejects execution unless all of these conditions hold:

1. The compiler bundle has a valid IGE contract and consistent source shape/canvas.
2. The source SHA256 in the bundle equals the SHA256 in the contract.
3. geometry_status and source_alignment_status are both operator_confirmed.
4. A JSON approval record is bound to the exact contract_id, source SHA, policy ID/revision and branch ID.
5. The approval sets execution_allowed=true, operator_authorized=true, workflow_status=ACCEPTED, and geometry_acceptance_status=ACCEPTED.

The approval record is an operator-consent artifact, not a cryptographic signature. Do not treat it as a security boundary against a person who can edit the workflow and node source. The current provisional geometry and pending source registration cannot pass this gate.

## Patch the original workflow without overwriting it

From the repository root:

~~~powershell
python tools/patch_comfy_siax_execution_gates.py --input "docs/handoff/comfy-siax-return/pc_高清探/workflow_ige_v03_dev_fp8.json" --output "docs/handoff/comfy-siax-return/pc_高清探/workflow_ige_v03_dev_fp8_gated_candidate.json"
~~~

For the local variant, use the _local.json input and a matching _local_gated_candidate.json output. The script is idempotent and never overwrites the input unless the operator explicitly chooses the same output path.

Install the updated custom node package into the live ComfyUI custom_nodes directory, restart ComfyUI, and inspect node import status before opening the generated workflow. This PR only changes the HUB snapshot; it does not copy files onto the operator PC.

## Resource preflight

~~~powershell
python tools/comfy_resource_preflight.py --workflow "docs/handoff/comfy-siax-return/pc_高清探/workflow_ige_v03_dev_fp8_gated_candidate.json" --min-free-vram-mb 2048 --min-free-ram-mb 8192 --max-sampler-batch 1 --output "runs/comfy_resource_preflight.json"
~~~

The tool does not queue a prompt. It checks that every sampler's latent input is directly gated, measures currently free CUDA VRAM when PyTorch/CUDA is available, and probes available system RAM. The 2048 MB VRAM and 8192 MB RAM values are configurable admission reserves, not measured peak-memory predictions or a guarantee against OOM.

## Known unresolved OOM architecture

The archived v03 graph routes the TTP 2×3 tile batch through batch-to-list conversion and then a VAE encode whose latent batch is passed to the sampler. The graph therefore does not prove one-tile-at-a-time sampler execution. The preflight infers six tiles from the TTP_Tile_image_size node configuration and blocks this multi-tile sampler batch under the default max batch of one.

Sequential per-tile inference, output ledger/resume, and safe OOM retry are not implemented by this patch. They require a separate orchestrator that consumes the actual runtime TTP POSITIONS, ORIGINAL_SIZE, and GRID_SIZE, submits one tile at a time, verifies each output SHA/dimensions, and only then reassembles using the existing geometry/core/halo contract. Automatically reducing tile dimensions without rebuilding the plan is forbidden.

## Evidence boundary

Static graph tests and CPU-only unit tests are not live ComfyUI tests. This patch does not establish a correct coordinate transform between 5376×3024 and 3862×2172. It does not relax compile_contract, promote provisional geometry, enable Flux, set execution_allowed=true, or prove cross-tile semantic continuity.
