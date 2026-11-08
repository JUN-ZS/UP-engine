# IGE / SIAX — PR #12 Contract Integration

**Design package:** `IGE_S0_S7_METHOD_REGISTRY_V0.1`  
**Status:** architecture + registry seed; not production-wired, not a ComfyUI workflow export, not GPU-validated.  
**Source contract:** `UP-engine` PR #12 head `4bc4bd472f1cc4188c4b1feaf94ab8f0d140ad15`.

## 1. Decision

PR #12 is the normative operating contract. PR #15 is technique lineage and failure memory. PR #5 contributes the executable READ/diagnosis and state-dependent router. PR #11 contributes the geometry-locked tile plan, core/halo separation, exact return and geometry audit. Siax runners and ComfyUI adapters remain separate inference backends.

Do not merge the branches merely because their concepts fit. First connect each `method_id` to a callable implementation, tests, evidence, and an independent acceptance gate.

## 2. Correct outer pipeline: S0–S7

| Stage | Contract | Required artifact / gate |
|---|---|---|
| S0 BASE | Freeze immutable source and every paired reference | File SHA-256, decoded-pixel SHA-256, EXIF/orientation, dimensions, colour mode/profile, bit depth; no mid-run drift |
| S1 READ | Layered 2D observations and scene graph | Candidate object/part labels, evidence boxes, closed-mask proposals, `part_of` / `occludes` / `contacts_at` evidence; unobservable facts stay `unknown` |
| S2 GEOMETRY LOCK | Create authoritative global coordinates and object contracts | BBox, silhouette, landmarks, hierarchy, transform matrix, mask and source binding; AI proposals cannot self-promote |
| S3 PERMISSION | Compile human-reviewed edit permissions | `approved_edit_mask`, `protected_preserve_mask`, disjointness proof; candidate observations grant no write permission |
| S4 ROUTER + TILE PLAN | Select method by state and assets, then plan core/halo tiles | Method ID/version, precondition report, global tile coordinates, core coverage, halo/context, per-tile task receipts |
| S5 INFERENCE | Call the named real backend | Backend/model/weight SHA, prompt/conditioning, seed, sampler, steps, denoise, guidance, runtime, input/output SHA per tile |
| S6 RETURN | EDGE → WHOLE → LOCATE → RETURN; hierarchical bottom-up | Core-only writes, halo excluded, no implicit resize/warp/flip, hardpaste or explicitly approved deterministic return |
| S7 ACCEPT | Independent audit against frozen S0 and approved S2/S3 contract | Fail-closed JSON + full-resolution boards; geometry, coverage, ghosting, flip, permission, pixel identity, provenance |

The Guide and Program Guidance use slightly different stage numbering around TILE PLANNER / permission / router. The implementation must cover all named responsibilities, not copy one numbering scheme while omitting a gate.

## 3. Four independent scale / geometry / tiling variables

Never collapse these into one size knob:

- `model_scale`: model's native output factor. Siax checkpoint is fixed 4x.
- `object_transform`: global object pose/size/silhouette transform on the target canvas.
- `tile_size`: inference window / compute budget.
- `tile_context`: halo/prepadding needed by a backend.

Also record an explicit `delivery_transform` when a model-native output is resampled to a different delivery canvas. It must not overwrite `model_scale` or silently mutate the geometry contract.

### Important issue in the pasted ComfyUI workflow

The graph runs `ImageUpscaleWithModel` with `4x_NMKD-Siax_200k.pth`, then `ImageScaleToTotalPixels` targeting 16 MP. For a 1792×1008 source, a native 4x result would be 7168×4032 (~28.90 MP); a 16 MP delivery target is approximately 3x linear scale, not a native 4x master. Keep the 4x native master or explicitly record and validate the subsequent delivery transform and update all masks/landmarks through that transform. Never label the resampled 16 MP result as an unchanged native 4x master.

## 4. Four-state HOLE / REMOVE / DIFF / GENERATE / ANTI is conditional

It is a method family selected by S4, not a mandatory stage for every image.

Use it when the defect requires a part-removal counterfactual, a missing-part hole, or a verified in-hole generation route. If a human-verified closed mask already exists and its provenance is sound, the router may skip REMOVE/DIFF. For ordinary material refinement, use an appropriate non-hole method.

Canonical paired-evidence route:

1. `L0`: source with target part.
2. `L1`: native-edit empty/removed-part counterpart, same coordinate frame and registered to L0.
3. `DIFF`: produce a *candidate* difference support, never an automatic permission mask.
4. `HOLE`: reconcile candidate support with READ, geometry and human review to create `M_hole`.
5. `ANTI`: `M_anti = complement(M_hole)` in the same global frame.
6. `GENERATE`: only an authorized backend may write inside `M_hole`.
7. Return and independently re-read the saved output for S7.

If the empty-background root is wrong, rebuild the mask and invalidate all downstream masks, donors, tile packets and composites derived from it. Do not patch a wrong root with feathering or ad-hoc inpainting.

## 5. Three different detail-generation families

Never report them under one `generative_upscale` label:

### A. Neural super-resolution

`BASE → Siax/NCNN 4x → core/halo → return → S7`.

This is a real neural SR backend. It reconstructs detail from learned image priors; it is not evidence that missing geometry or identity has been recovered.

### B. High-resolution tile diffusion (the intended Comfy Flux route)

`BASE → geometry/permission contract → high-resolution read tiles → Flux image-to-image inference → decoded tile outputs → core-only return → S7`.

This is the route that actually runs diffusion on the high-resolution tile. Each tile needs an explicit global coordinate, core, halo, contract ID, conditioning/permission digest, model/adapter receipt and output hash. Same seed does not establish a shared latent/noise field. The current pasted graph has one global Conditioning path for the whole batch; it does not yet implement true per-subset Conditioning routing or shared global latent/noise.

### C. AI-donor-guided multiband transfer

`external AI-generated donor → registration/part correspondence → band transfer → mask return → S7`.

This is a useful auxiliary method, but it is not a diffusion inference call on the destination high-resolution tile. The PR #12 `ALL24` fossil loads external donor images and transfers Laplacian/high-frequency bands. The script itself does not call Flux/Comfy/Imagine. Its donor assets are described as 8K in names/comments, but the script records donor dimensions such as 896×1200 and 1376×768; therefore those bytes are not native 8K images. The output master is 5504×3072. Treat donor-generation provenance as external/unverified unless the original backend job, prompt, seed and original image bytes are supplied.

## 6. Tile contract

- Plan all tiles in one global high-resolution coordinate frame.
- Distinguish `read_window = core + halo` from `write_core`.
- Only disjoint write cores are pasted into the master. Halo pixels are context only and must never be written twice.
- Coverage must prove that every authorized target pixel is either covered by exactly one write core or explicitly omitted with a reason.
- Keep geometry/mask/landmark projection derived from the global contract; do not independently infer or rescale geometry per tile.
- Do not assume `TTP_Image_Assy` obeys core-only write semantics. Inspect its implementation or prove it with adversarial tests before using it as a production return node. Its `padding=125` is not itself proof of core exclusion.

## 7. Current graph-specific blockers (from the supplied workflow JSON)

1. **Model field mismatch:** UNETLoader `widgets_values` says `flux1-dev.safetensors`, while `widgets_values_named` says `CC_V1.safetensors`; VAELoader similarly says `ae.safetensors` vs `ae.sft`. Synchronize both representations and validate the API prompt payload, not just the UI JSON.
2. **Global compiler outputs:** `GLOBAL_ACTION_MAP` and `GEOMETRY_GUARD` are not visibly connected. Either include them in the `GLOBAL_CONTRACT` consumed by Projector and prove that in code/tests, or wire them as typed Projector inputs. Do not assume they are active.
3. **Permission authority:** S3 must create a human-reviewed `approved_edit_mask` and protected mask. Noise mask is not permission and is not a hard geometry constraint.
4. **Noise mask semantics:** `SetLatentNoiseMask` modulates latent noise; it does not guarantee that decoded pixels outside a protected region remain unchanged. Keep an output-side hard gate and independent pixel audit.
5. **Conditioning:** Node 313 creates one Conditioning from one global prompt and supplies it to the B batch. No actual per-subset/per-tile Conditioning Router is shown.
6. **Shared noise:** reusing one RandomNoise node/seed across a batch is not proof of a globally coordinate-consistent noise field.
7. **Assembly:** A uses TTP assembly; B goes through Global Reconciler. Before comparing these paths, audit whether both write the same disjoint cores and use identical coordinate semantics.
8. **Iteration state:** Node 300 currently receives literal `{}`; Node 305's next-state output is not persisted/reloaded. Cross-run memory is therefore not established.
9. **S7 inputs:** the default observations JSON `{}` is not sufficient for acceptance. Missing required observations must be BLOCK, not a permissive empty report.
10. **Geometry source binding:** the object contract must identify which raster (raw BASE, native Siax 4x master, or delivery-resampled master) its coordinates refer to. Convert once with a recorded transform; never infer from dimensions alone.

## 8. Correct implementation order

1. Freeze this contract and add a real, versioned Method Registry file + schema + validator.
2. Connect PR #5 READ outputs as candidate observations; no direct permission grant.
3. Add S2/S3 global geometry and human permission compiler; bind every mask to source SHA and coordinate frame.
4. Add S4 router that resolves `method_id` from the Registry and checks preconditions/assets/status.
5. Adapt Siax, Flux tile diffusion, and donor transfer as different S5 adapters with different evidence receipts.
6. Change/validate S6 return to disjoint core-only write; do not hide drift with blending.
7. Build S7 independent audit over saved output bytes and source hashes.
8. Only then add a true per-subset Conditioning Router and later a coordinate-indexed global noise field.

## 9. Non-claims

- PR #12 is an open draft, docs/research-only guidance PR; it does not wire its seven fossils into `src/ige`.
- `SHQ_METHOD_REGISTRY_V1.json` is described by the guide/transcript but is not among PR #12's changed files. The Router fossil has a `registry_path` parameter, but the path is not read; method IDs are selected by hard-coded state branches.
- The latest four-state research Python is improved, but its `execute_hole_scalelock_hf_pipeline()` creates a Gaussian high-frequency residual candidate, not diffusion. It must be classified as non-generative diagnostic/detail processing.
- The latest script's `__main__` resizes the empty-BG input before calling `anti_diff`, which means its command-line path does not test the strict size-mismatch rejection on that input. The 5-group suite separately tests a mismatched-size pair.
- The four “holdout” cases in the 5-group suite are declared records in the script, not four independent live backend inference holdouts.
- Several checks in the research suite use the same mask as both prediction and reference, making those particular mask comparisons self-consistency checks, not ground-truth accuracy measurements.
- Sobel/detail-gain increases, alpha copied from the same source mask, or zero outside-mask writes do not prove perceptual detail truth, semantic correctness or geometry quality.
- The 5D UV/depth fields are proxy representations derived from 2D masks/appearance; they are not calibrated physical 3D reconstruction or camera-space measurements.
- No PR is merged, no main branch is changed, and no real Comfy Cloud inference is claimed by this design package.
