# SHQ Object Geometry Lock — Program Guidance

**Status:** normative implementation contract; not proof that any backend is live.  
**Related AI instructions:** [SHQ_AI_USAGE_GUIDE.md](./SHQ_AI_USAGE_GUIDE.md)  
**Python enforcement:** [SHQ_AGENT_DRIVER.md](./SHQ_AGENT_DRIVER.md)  
**Research provenance:** [PR #12 19-turn pack](https://github.com/JUN-ZS/UP-engine/tree/feat/shq-geometry-lock-program-guidance-v0.1/docs/sources/gemini-share-nutrRjsw676R/)

## Intent

Perform object-aware reconstruction with geometry locked before generation. Do not misrepresent interpolation, sharpening, donor transfer or synthetic texture as neural/diffusion generation.

## Independent parameters

model_scale, object_transform, tile_size, tile_context, and delivery_transform have separate meanings and receipts. Increasing tile size is a memory/context decision, not an object transform.

## S0–S7 contract

| Stage | Name | Fail-closed requirement |
|---|---|---|
| S0 | BASE freeze | SHA-256 and dimensions re-read; hash drift blocks |
| S1 | OBJECT READ | observations are candidate-only; unknown remains unknown |
| S2 | GEOMETRY LOCK | human-verified coordinate canvas, frame and object transform |
| S3 | PERMISSION | human-reviewed approved/protected binary masks bound to S0/S2 |
| S4 | METHOD ROUTER | Registry maturity, preconditions and callable backend verified |
| S5 | INFERENCE | real adapter invocation and matching model/input/output receipts |
| S6 | COMPOSE / RETURN | disjoint core writes, halo read-only, exact coverage, protected pixels preserved |
| S7 | INDEPENDENT ACCEPT | output reloaded from disk, SHA checked, human review and all gates PASS |

A failure stops all later stages. S7 accepts a candidate only; it never grants permission for future edits.

## EDGE → WHOLE → LOCATE → RETURN

1. EDGE: binary, closed object silhouette; preserve a distinct protected region.
2. WHOLE: operate only in approved subject pixels.
3. LOCATE: use a verified coordinate frame and object transform; no inferred mirror.
4. RETURN: write disjoint tile cores only, preserve protected pixels exactly, and audit the saved master.

## Prohibited claims and shortcuts

- Lanczos / CLAHE / unsharp / Gaussian residual are not generative upscale.
- A saved prompt or workflow graph is not a backend run.
- Same random seed does not prove a coordinate-indexed global noise field.
- A donor tile is not equivalent to destination-tile diffusion.
- Synthetic PASS does not promote method maturity.
- A report's self-declared metric is not independent acceptance.

## Root-change invalidation

Any change to BASE, empty-BG, geometry canvas, approved/protected masks, model weights, workflow, or tile plan invalidates downstream receipts. Re-run from the earliest stage whose inputs changed.

## S7

S7 must reload the exact saved output from disk, verify SHA and dimensions, recompute geometry/protected-region checks independently, and include a human visual review record. No S7 result can be inferred from S5 or from a static audit.
