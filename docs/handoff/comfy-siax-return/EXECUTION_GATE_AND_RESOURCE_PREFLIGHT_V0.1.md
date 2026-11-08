# ComfyUI Siax-return: execution gate and resource preflight v0.2

This is a repair layer on the archived Siax + IGE workflow, not a replacement workflow.

## What changed

- Added IGE_ExecutionAuthorizationGate to both archived copies of ComfyUI_IGE_GlobalLogicCoordinator.
- Added a workflow patcher that inserts this gate in front of every SamplerCustomAdvanced.latent_image input. Baseline A and Candidate B are both gated.
- Added a read-only resource preflight helper for graph inspection and current free VRAM/RAM probes.
- The preflight distinguishes a real unsplit multi-image path from the archived v03 path that splits the TTP batch to a list before VAEEncode.
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

## Batch/list semantics in the archived v03 graph

The archived v03 workflow contains:

TTP_Image_Tile_Batch (Node 36) → easy imageBatchToImageList (Node 163) → VAEEncode (Node 129) → SamplerCustomAdvanced (Node 67 / Node 310)

The upstream Easy-Use implementation declares OUTPUT_IS_LIST = (True,) and returns one image slice per list item:
https://github.com/yolain/ComfyUI-Easy-Use/blob/main/py/nodes/image.py

ComfyUI's list scheduler maps downstream node calls across list items in a loop:
https://github.com/Comfy-Org/ComfyUI/blob/master/execution.py

Therefore, the existence of a configured 2×3 TTP grid does not by itself prove that six tiles occupy the sampler simultaneously. The v0.2 preflight now recognizes the list-split-before-VAE path as a static sequential-map candidate. It only blocks a multi-tile path when no recognized splitter is upstream of the VAEEncode input.

This remains a static inference until the installed Easy-Use version and runtime latent batch shape are captured on the operator PC. It is not a live proof that exactly one tile is resident at every stage, nor does it account for ComfyUI's intermediate-output cache.

## Stage 2 model-release barriers

The original v03 graph contains LayerUtility PurgeVRAM Node 262 as a terminal output connected to the Baseline A sampler branch. It is not a dataflow dependency between both samplers and their VAE decoders, and the archived node inventory does not identify the installed LayerStyle package version.

The new Stage 2 candidate removes Node 262 and inserts explicit IGE_LatentMemoryBarrier nodes:
- Node 344: Baseline A sampler 67 → barrier 344 → VAEDecodeTiled 96.
- Node 345: Candidate B sampler 310 → barrier 345 → VAEDecodeTiled 311.

Each barrier synchronizes CUDA, calls Comfy model unload/soft cache release, performs CUDA cache cleanup, records free/allocated/reserved VRAM before/after, and passes the latent through unchanged. The resource and geometry preflights verify these graph connections and that release flags remain enabled.

This reduces model-weight overlap between Flux sampling and VAE decoding, but it is not a complete OOM guarantee: the latent remains live, ComfyUI may retain cached outputs, the VAE may reload for decode, and an OOM can still occur inside the preceding sampler. Actual 8GB runtime peaks must be measured locally.

## Remaining OOM work

The archived list path is a better starting point than a simultaneous six-tile latent batch, but OOM protection is not yet complete:

- No runtime peak VRAM/RAM telemetry is attached to each tile.
- No verified model unload/retention policy is applied between tile items.
- No durable per-tile output ledger or resume after a mid-list failure is implemented.
- No OOM retry that recomputes the full TTP plan and core/halo bounds is implemented.
- The VAE decode nodes are tiled, but the installed runtime parameters and actual peak memory still require capture.

Do not silently reduce tile size, crop or output resolution after an OOM. Any retry must regenerate the tile plan, revalidate geometry/coverage/core/halo, preserve the original source and completed outputs, and produce a new plan hash. A separate per-tile Comfy API orchestrator remains a possible architecture if the existing list scheduler cannot provide reliable output checkpoints.

## Evidence boundary

Static graph tests and CPU-only unit tests are not live ComfyUI tests. This patch does not establish a correct coordinate transform between 5376×3024 and 3862×2172. It does not relax compile_contract, promote provisional geometry, enable Flux, set execution_allowed=true, or prove cross-tile semantic continuity.
