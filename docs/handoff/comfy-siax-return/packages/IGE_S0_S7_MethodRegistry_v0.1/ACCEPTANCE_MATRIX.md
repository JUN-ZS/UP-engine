# Acceptance Matrix — no score averaging across hard gates

## Required groups

| Group | Tests | Hard failure examples | Evidence |
|---|---|---|---|
| S0 provenance | file SHA, decoded pixel SHA, EXIF, colour profile, source immutability | source hash drift, missing paired-source transform | source manifest + re-read hash |
| S1 READ | candidate-only semantics, evidence boxes, relation anti-overreach, `unknown` for unobservable | unsupported contact/3D claim, no evidence box | READ JSON + evidence overlay + human GT where available |
| S2 geometry | global frame, silhouette, landmarks, hierarchy, transform separation | unbound coordinate frame, mask/landmark source mismatch, mirror transform | geometry contract + transform ledger |
| S3 permission | approved/protected masks disjoint, human verification and provenance | AI candidate grants permission, missing protection mask, mask overlap | permission compiler JSON + binary masks + review record |
| S4 router/tile | method preconditions, core/halo coverage, router counterfactuals | missing method implementation, topology error sent to detail route, duplicate core writers | Registry resolution log + tile plan + coverage bitmap |
| S5 inference | real adapter, model/checkpoint SHA, per-tile params/seed/input/output hashes | no backend call, missing receipt, synthetic stand-in labelled generative | backend receipt + raw tile outputs |
| S6 return | core-only writes, no silent resize/warp/flip, hierarchy order, exact protected pixels | halo pasted twice, wrong transform, soft blend conceals drift | return manifest + per-core write map + saved-image re-read |
| S7 independent accept | geometry, ghosting, flip, coverage, outside pixel identity, visual quality review | missing observation, unreviewed provisional geometry, any hard-gate fail | `*_S7_AUDIT_REPORT.json` + full-resolution boards + output SHA |

## Important anti-tautology rules

- A mask compared against itself is a pipeline self-consistency check, not ground-truth segmentation accuracy.
- Copying the source alpha into the output alpha proves the compositor copied a mask; it does not prove the candidate geometry stayed correct.
- Writing only inside a mask makes outside-mask equality likely by construction; S7 must re-read the saved output and compare it independently to the frozen source.
- Sobel energy, Laplacian energy, HF RMS or detail-gain ratios are diagnostic signals. They cannot alone prove authentic detail, semantic correctness or perceptual quality.
- A successful synthetic test is a unit test, not a real-image holdout.
- Holdout cases must be new, fixed inputs and actual executions with backend receipts; hard-coded case summaries do not count as holdout inference.
- A prompt, seed, batch sampler or identical Noise node is not proof of shared global latent/noise.

## Proposed first holdout protocol

Use one human-reviewed source and two independently reviewed objects (one thin/occluded boundary, one material-rich object). Freeze source and references before any tuning.

1. Run route A: verified Siax 4x SR.
2. Run route B: Flux HR tile image-to-image with same global contract, per-tile receipts and core/halo ledger.
3. Run route C: external donor transfer only if original donor bytes and generation receipt are available.
4. For route B, compare at least two tile-grid offsets while keeping global mask, source and method fixed.
5. Evaluate the same held-out observations against the same S7 gates. Do not change tolerances after seeing results.
6. Report hard gates first. Only candidates passing all hard gates may be ranked on detail/texture/runtime.

No single composite score may allow sharpness to offset identity, topology, geometry or protected-pixel failure.
