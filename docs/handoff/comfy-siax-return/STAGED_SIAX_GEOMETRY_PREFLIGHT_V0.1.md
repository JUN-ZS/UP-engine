# SIAX → IGE staged workflow and CPU geometry preflight v0.1

This is a staged execution plan for the existing ComfyUI SIAX + IGE workflow. It splits the archived v03 graph at the existing ImageScaleToTotalPixels node; it does not replace SIAX, TTP or IGE.

## Generated workflow candidates

Dev FP8:
- workflow_ige_v03_dev_fp8_siax_stage1_export.json
- workflow_ige_v03_dev_fp8_ige_stage2_gated_candidate.json
- workflow_ige_v03_dev_fp8_staging_build_report.json

Local:
- workflow_ige_v03_dev_fp8_local_siax_stage1_export.json
- workflow_ige_v03_dev_fp8_local_ige_stage2_gated_candidate.json
- workflow_ige_v03_dev_fp8_local_staging_build_report.json

Original v03 and v03 gated candidate files remain unchanged.

## Stage 1 — SIAX canvas export only

Stage 1 retains the original nodes needed for:

LoadImage → ImageResizeKJ → ImageUpscaleWithModel (SIAX) → ImageScaleToTotalPixels (Lanczos 16MP) → SaveImage

It contains no UNETLoader, no DualCLIPLoader and no SamplerCustomAdvanced. Its SaveImage prefix is IGE/SIAX_STAGE1_CANVAS.

1. Open the Stage 1 workflow in the existing ComfyUI.
2. Confirm the input image and SIAX model selection are the intended ones.
3. Run Stage 1 only.
4. Find the saved PNG in the ComfyUI output directory.
5. Record its actual width, height and SHA256. Do not infer its dimensions from the 16MP widget or filename.
6. Copy that exact PNG into the ComfyUI input directory so Stage 2 can load it.

This is the only stage intended to run before geometry review. It uses the existing SIAX model; it does not load Flux/T5 samplers.

## Stage 2 — IGE / TTP / Flux candidate

Stage 2 removes the original pre-SIAX nodes 233, 244, 133 and 134, removes the unsequenced terminal LayerUtility PurgeVRAM Node 262, and reuses Node 34 as a LoadImage. All downstream links from Node 34 are preserved, including the compiler source and the TTP source path. Both sampler latent inputs remain behind their fail-closed authorization gates. It inserts IGE_LatentMemoryBarrier Node 344 between Baseline A sampler 67 and VAE Decode 96, and Node 345 between Candidate B sampler 310 and VAE Decode 311. Each barrier requests Comfy model unload, CUDA cache release and synchronization, while passing the latent unchanged.

1. Open the Stage 2 workflow.
2. In Node 34, select the exact Stage 1 PNG copied into ComfyUI/input.
3. Save/export the resulting UI workflow JSON. Do not queue it yet.
4. Run the CPU-only preflight below against that exact exported workflow and that exact PNG.

## CPU geometry preflight

From the UP-engine repository root:

~~~powershell
python tools/comfy_siax_geometry_preflight.py --workflow "path\to\stage2_selected_and_saved.json" --source-image "C:\Users\user\Documents\ComfyUI\input\SIAX_STAGE1_CANVAS.png" --geometry "C:\Users\user\Documents\ComfyUI\custom_nodes\ComfyUI_IGE_GlobalLogicCoordinator\config\object_geometry.provisional.json" --policy "C:\Users\user\Documents\ComfyUI\custom_nodes\ComfyUI_IGE_GlobalLogicCoordinator\config\global_logic_policy.json" --output "runs\stage2_geometry_preflight.json"
~~~

The preflight:

- verifies Node 34 selects the exact file passed on the command line;
- verifies Node 300 compiler and Node 36 TTP use the same Node 34 canvas;
- verifies every SamplerCustomAdvanced latent input is directly behind an IGE execution gate bound to Node 300;
- reads the saved PNG dimensions and computes the quantized pixel digest convention used by the IGE compiler;
- compares actual width/height with the geometry canvas;
- calls the existing compile_contract only after dimension equality;
- reports geometry human-confirmation, source-registration and reference-file-SHA status separately;
- never submits a prompt, queues a job or sets execution_allowed=true.

## Expected result with the currently archived geometry/policy

The archived geometry is assistant_provisional; its provenance operator confirmation is pending. The policy source_alignment_status is pending_operator_registration_to_siax_output.

Therefore, even when the Stage 1 canvas is 5376×3024 and the compiler contract can be built, the expected result remains:

BLOCKED_PENDING_HUMAN_GEOMETRY_AND_SOURCE_REGISTRATION

This is intentional. Matching dimensions do not prove that the provisional person silhouette, landmarks and polygon are registered to the actual SIAX-upscaled pixels. The geometry reference SHA identifies the Lanczos-derived reference image, not automatically the output of the neural SIAX node.

If the Stage 1 output remains 3862×2172, preflight returns BLOCKED_CANVAS_DIMENSION_MISMATCH and reports scale ratios for diagnosis. It does not generate a transform or rewrite geometry.

## Hard limits

- No automatic stretch, crop, pad, coordinate relabel or affine-transform guess.
- No Stage 2 Flux execution while geometry remains provisional or source registration is pending.
- No weakening of compile_contract.
- No automatic setting of execution_allowed=true.
- A passing dimension check is not geometry acceptance.
- The memory-release barrier retains the latent and cannot free ComfyUI cached outputs; it does not prevent OOM inside the preceding sampler and may cause VAE weights to reload for decode.
- A static JSON check is not a live ComfyUI node-import or GPU run.
- The current stage split does not prove cross-tile semantic continuity.
- Stage 1 SIAX execution and Stage 2 Flux execution are separate user-controlled ComfyUI runs; no GPU job was run while preparing this PR.
