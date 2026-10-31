# Quality, gates and benchmark protocol

## Acceptance is lexicographic, not one weighted average

1. Required hard gates must all pass.
2. Only then compare soft quality metrics and operational cost.
3. If two candidates have similar quality, prefer the simpler and more reproducible pipeline.

## Minimum benchmark dimensions

- Identity: face/character similarity and human adjudication where required.
- Pose: landmark or silhouette deviation.
- Topology: part count, connectivity, occlusion ordering, silhouette.
- Protected pixels: change outside authorized mask, including boundary leakage.
- Registration: transform residual and landmark displacement.
- Material: texture/weave/frequency similarity without geometry change.
- Detail: local edge/detail quality at native and target display scale.
- Operations: wall time, peak VRAM/RAM, retries, failures, model/license/version.

## Dataset rules

Create a small, curated, versioned test set with at least: face/hair identity, garment silhouette, metallic material, hand/weapon occlusion, thin boundaries, background preservation, and multi-view/temporal continuity. Every sample needs a BASE, role-labelled references, allowed/protected masks, expected invariants, and human-reviewed ground truth notes.

Do not tune against the final holdout. Report per-case results and failure categories, not only averages. Record model version, runtime, quantization, hardware, prompt, seed, mask revision and transform. Model updates invalidate old benchmark claims until rerun.
