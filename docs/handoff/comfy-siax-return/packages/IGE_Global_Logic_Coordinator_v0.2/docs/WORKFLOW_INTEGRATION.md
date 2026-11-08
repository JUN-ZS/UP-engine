# Original SIAX workflow integration v0.2

## Preserve the original A path

The candidate workflow keeps the supplied baseline A path intact:

`node 42 blank CLIPTextEncode → 73 FluxGuidance → 72 BasicGuider → 67 SamplerCustomAdvanced → 96 VAEDecodeTiled → 237 ImageListToImageBatch → 127 TTP_Image_Assy → 128 SaveImage`.

Do not remove or change the original Siax/TTP nodes or settings:

- `ImageUpscaleWithModel` node 134;
- `ImageScaleToTotalPixels` node 34;
- `TTP_Tile_image_size` node 111;
- `TTP_Image_Tile_Batch` node 36;
- original VAE encode and sampler path nodes 129 / 67;
- original TTP assembly node 127.

## Candidate B data path

The v0.2 patched graph duplicates the conditioning, sampler, decode and batch-conversion path so candidate B does not alter baseline A.

1. `IGE_GlobalLogicCompiler` node 300 receives full-frame node 34, the geometry/policy JSON files, and optional prior `NEXT_ITERATION_STATE_JSON` pasted into `iteration_state_json` (default `{}`).
2. `IGE_TTPSubsetProjector` node 301 receives the compiled parent contract and the actual four outputs from TTP node 36: `IMAGES`, `POSITIONS`, `ORIGINAL_SIZE`, `GRID_SIZE`.
3. `IGE_TileNoiseMask` node 308 receives the actual VAEEncode LATENT from node 129, reads its exact B,C,H,W shape, and converts each projected subset's action/guard maps into a per-tile latent-resolution MASK batch. It does not assume a fixed VAE scale.
4. Stock `SetLatentNoiseMask` node 309 attaches that MASK to the encoded tile LATENT from node 129.
5. The B path uses duplicated `SamplerCustomAdvanced` node 310, `VAEDecodeTiled` node 311 and `ImageListToImageBatch` node 312. It shares the same noise source, sampler, sigma schedule, model/LoRA stack and VAE as A.
6. B's duplicate CLIPTextEncode / FluxGuidance / BasicGuider nodes 313–315 receive the global logic prompt. A retains its original blank prompt, unchanged.
7. `IGE_ApplyLogicGate` node 302 restores exact input pixels in explicit PRESERVE/REJECT zones after decode.
8. `IGE_GlobalReconciler` node 303 uses the true TTP positions in global coordinates. A pixel in overlap is written only when the candidates agree; otherwise that pixel reverts to the full-frame source.
9. `IGE_GlobalAcceptanceAudit` node 304 receives the full-frame candidate and updated subset metadata. Its observations input starts as `{}` and should block acceptance.
10. `IGE_IterationFeedback` node 305 records a next-iteration proposal; it never silently edits the policy or promotes geometry. Paste that JSON into node 300 on the next run to carry parent-state lineage and warnings forward. This records history only; the active geometry/policy files remain authoritative and are never auto-mutated.

## Noise-mask semantics and limits

- `PRESERVE` / `REJECT` → noise mask weight 0.0. Post-decode pixel gate also restores those exact source pixels.
- `REFINE` → configured `refine_noise_weight` (default 1.0).
- `GENERATE` → configured `generate_noise_weight` (default 1.0); the policy compiler still requires an operator-confirmed region.
- Pixels inside the silhouette/landmark geometry guard receive `guarded_refine_noise_weight` (default 0.25) only if both geometry status and source coordinate registration are `operator_confirmed`.
- Otherwise geometry-specific attenuation is disabled. This prevents an unregistered provisional polygon from masking the wrong place.
- The image-space mask is reduced to the actual latent resolution using conservative min pooling. Any protected pixel makes its containing latent cell no more permissive than the protected pixel. This can widen a boundary by at most `latent_downscale - 1` source pixels.
- The noise mask is a soft denoising constraint, not a hard geometric proof. Fractional values can reduce denoising influence but cannot certify identity, silhouette or landmarks.

`SamplerCustomAdvanced` supports an optional `noise_mask` in the latent input, and stock `SetLatentNoiseMask` stores the mask on that latent. See the ComfyUI core implementation and node documentation: [SetLatentNoiseMask / ComfyUI nodes.py](https://github.com/Comfy-Org/ComfyUI/blob/master/nodes.py) and [SamplerCustomAdvanced documentation](https://github.com/Comfy-Org/docs/blob/main/built-in-nodes/SamplerCustomAdvanced.mdx).

## Shared context vs per-tile prompts

Candidate B has one global shared Conditioning input for the batch. The projector compiles local subset instructions and groups compatible subsets. If there is more than one incompatible local conditioning profile, one stock shared sampler cannot apply every local prompt independently. The audit must block acceptance until those groups run separately or a per-sample conditioning adapter is built and verified.

## Source alignment is a hard prerequisite

The supplied object geometry was annotated on a 5376×3024 Lanczos-derived reference. Matching dimensions do not prove correspondence with the full-frame image immediately after SIAX. Until the source pixels/coordinates are registered and operator-confirmed, geometry-specific noise attenuation remains disabled and formal acceptance remains blocked.

## Execution status

The v0.2 graph JSON, Python logic and node plumbing are locally tested. The graph has not been opened/executed inside ComfyUI in this environment. No SIAX model, Flux sampler, GPU, Cloud job or credit-consuming run was performed.

## Per-tile feedback

The reconciler emits `subset_overlap_diagnostics` and `failed_subsets`. Each failed record identifies the TTP tile ID/index and overlap conflict fraction. `IGE_GlobalAcceptanceAudit` propagates these IDs to `failed_subsets`; `IGE_IterationFeedback` carries them into the next iteration state. This is review/targeting metadata only: it does not automatically change masks, prompts, policy or geometry.
