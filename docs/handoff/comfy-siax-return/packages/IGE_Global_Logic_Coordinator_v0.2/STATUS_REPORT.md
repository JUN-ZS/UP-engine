# IGE Global Logic Coordinator v0.2 — Status

## Objective

Keep the original SIAX full-frame upscale → TTP tile batch → shared sampler → TTP assembly architecture. Add one global rule contract so each tile is a child subset of the same scene and cannot independently redefine semantic permissions.

## Implemented

- Python global contract compiler and rule hierarchy.
- Action map: `PRESERVE`, `REFINE`, `GENERATE`, `REJECT`.
- Fail-closed authorization: `GENERATE` cannot be the global default or an unbounded global rule; it requires an explicit operator-confirmed polygon.
- Adapter for the actual TTP runtime metadata: `POSITIONS`, `ORIGINAL_SIZE`, `GRID_SIZE`; production does not infer positions from tile order.
- Global-to-tile projection with shared contract ID, rule digest, parent state, global coordinates and per-tile rule lineage.
- Per-tile latent noise masks sized from the actual VAE-encoded latent tensor; masks are applied before Candidate B sampler via stock `SetLatentNoiseMask`.
- Post-decode exact pixel restoration for `PRESERVE` / `REJECT`.
- Global overlap consensus; conflicting overlap pixels abstain to source instead of unconditional Feather/crossfade.
- Per-tile overlap diagnostics and failed subset attribution.
- Global acceptance audit and iteration-state lineage; no automatic policy mutation or geometry promotion.
- A/B ComfyUI workflow: original A path unchanged; B is a separate candidate path.
- Eight custom ComfyUI nodes.

## Validation performed

- Original graph: 29 nodes / 39 links.
- Patched graph: 45 nodes / 75 links.
- Unit tests: 21 passed, 0 failed.
- Python compileall: passed.
- Structural graph tests: links resolve, original A path retained, TTP runtime metadata drives projection, latent mask precedes B sampler.
- Metamorphic projection test: same global policy projects consistently across two tile grids. This proves coordinator mapping consistency only; it does not prove the diffusion model will produce the same pixels under changed tile boundaries.
- Offline replay of Job `c88c70e5`: 294,912 overlap pixels; 122,860 conflicts (41.66%); P95 spread 0.21046 versus 0.20; both participating tiles marked failed; conflicts reverted to source; outside-coverage changed pixels = 0.

## Current acceptance

`BLOCKED_PENDING_GEOMETRY_AND_CONSENSUS`.

The replay's two-tile positions are the prior ROI test fixture, not the original six-tile SIAX/TTP runtime metadata. No real ComfyUI UI execution, SIAX inference, Flux inference, GPU run or Cloud job was performed in this environment.

## Known limitations — do not overclaim

1. The supplied person geometry remains `assistant_provisional`; source-coordinate registration to the actual post-SIAX image and operator confirmation are pending.
2. The shipped policy currently defaults the full canvas to `REFINE`. With default weight 1.0, B's noise mask allows full-strength denoising across that default region. The person geometry attenuation remains inactive until both geometry and source alignment are operator-confirmed. This version does not yet hard-protect the person during sampling.
3. The noise mask is a soft denoising constraint, not a hard identity/pose/silhouette guarantee. Post-decode pixel gates restore `PRESERVE` / `REJECT` zones exactly, but current policy does not define a registered operator-confirmed person `PRESERVE` mask.
4. Candidate B uses one global CLIP conditioning object for the latent batch. Local subset prompts are compiled/grouped and incompatibility can block acceptance, but this graph does not yet route multiple incompatible prompt groups to separate sampler executions.
5. This version does not share a single global latent/noise field across independently executed tile jobs. It retains the original batched TTP sampler design and applies global semantic permissions/masks to the tile batch.
6. A/B currently compares original blank-prompt baseline A against candidate B with global prompt + mask/gates. It is not a factorial experiment isolating prompt-only versus mask-only effects.
7. RGB overlap agreement is a consistency signal, not identity recognition or semantic correctness.

## Recommended first live step

Install the custom-node folder, restart ComfyUI, open the v0.2 patched workflow and verify node import/graph availability first. Do not run the GPU workflow until the operator confirms the post-SIAX coordinate registration and decides how the central subject should be protected. Keep branch A as the control.
