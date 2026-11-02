# Upscale strategy portfolio

## Why strategy families are separate from legacy skills

A legacy skill (for example PATH1E, GRID_SIAX or DETAIL6) is a project-specific procedure. A super-resolution method family is a mechanism for recovering or synthesizing image detail. A checkpoint is one implementation of one family.

The previous router largely selected from the migrated legacy skills, which meant its apparent method search space was too narrow. This portfolio is now an independent layer returned as `skill_plan.json -> strategy_portfolio`. It does not add another CLI command and does not claim that every listed runtime is installed.

## Method families

| Strategy ID | Mechanism | Best suited to | Main failure mode | Current UP-engine status |
|---|---|---|---|---|
| `RESAMPLE_CONTROL` | Lanczos/bicubic interpolation | Dimension-only control and delivery sizing | Enlarges pixels without recovering detail | Pillow available; control only |
| `CLASSICAL_RESTORATION` | Deconvolution, deblur, denoise, deblock, deringing | Blur/noise/codec damage where signal remains | Amplifies noise or cannot recover destroyed signal | Not imported |
| `MULTISCALE_FREQUENCY_ENHANCEMENT` | Wavelet/Laplacian bands and local edge-aware contrast | Microcontrast loss when source signal exists | Halos, ringing and noise amplification | Not imported |
| `CNN_GAN_SR` | Learned feed-forward SR (ESRGAN family) | Single-image 2x/4x texture reconstruction | Plausible but invented microtexture | Siax adapter available conditionally; other checkpoints not imported |
| `TRANSFORMER_SR` | Window/global attention restoration and SR | Long repeated structures and broader contextual consistency | Training-domain mismatch and texture smoothing | Not imported |
| `DIFFUSION_SR` | Conditional diffusion restoration/SR | Severe degradation or AIGC detail completion | Identity, text, topology and geometry hallucination | Not imported |
| `IDENTITY_GUIDED_FACE_RESTORATION` | Canonical face reference + aligned plate/ROI + protected compositing | Face detail repair where identity must remain tied to a8b | Face seams, landmark drift and overfitting to a reference | PATH1E documented-only |
| `REFERENCE_GUIDED_SR` | Retrieve, register and transfer matching high-resolution donor patches | Gold mesh, cloth weave, hair, armour or scene texture with a true donor | Wrong donor/material/pose leaks texture into the target | Not imported; needs actual local donor bytes |
| `NATIVE_GENERATIVE_REDETAIL` | Image-to-image regeneration / native image edit | Reconstructing coherent detail when the source lacks enough information | Changes pose, parts, silhouette, texture boundaries or identity | External HERE candidate workflow; not pixel-faithful SR |
| `ROI_HYBRID` | Different specialist methods per semantic region, then protected composition | Face, skin, metal, cloth, text and environment need different treatment | Mask errors and compositing seams | Partial foundation; full GRID×SIAX not imported |
| `TEMPORAL_MULTI_FRAME_SR` | Align and fuse sub-pixel evidence across multiple frames | Same-state burst/video frames | Ghosting from motion, occlusion, lighting or pose changes | Not imported |
| `GEOMETRY_GUIDED_SR` | Depth/normal/mesh-conditioned restoration | Surface detail needing edge flow and 3D part constraints | Incorrect estimated geometry propagates into detail | Not imported |

These are different mechanisms, not twelve promised working buttons. `strategy_portfolio` records eligibility, prerequisites, risks, candidate models and non-claims for every family.

## State-dependent selection

The planner reads the diagnosis and optional human-supplied `strategy_context`:

- Topology or garment connectivity defect: all downstream detail methods are blocked or held for structural review. Sharpening is not a topology repair.
- Motion/defocus blur, noise, JPEG blocks, compression or ringing: classical restoration is proposed before aggressive detail synthesis.
- Material or face detail deficit: CNN/GAN, Transformer, Diffusion, native re-detail and ROI hybrid appear as competing families; the planner does not rank them without same-BASE replay.
- Local microcontrast deficit with noise controlled: multi-scale frequency enhancement becomes eligible.
- Canonical a8b image: can select identity-guided face restoration only when the actual reference bytes are supplied; it is not treated as a generic metal/cloth donor.
- Material donor: reference-guided SR is eligible only when donor role and local bytes/hash are available. An asset UUID alone is insufficient.
- Two or more frames: temporal SR remains blocked until same-state registration is verified.
- Depth/normal/mesh: geometry-guided SR is conditional on verified map/mesh inputs.

Model-reported defects remain candidate evidence. Portfolio inclusion is not authorization to run irreversible generation or to accept an output.

## The three HERE results are not three independent SR families

The supplied result descriptions identify two outputs as same-structure native detail-lock generations and a third as a hybrid native generation with a8b face locking. They are useful A/B/C variants inside generative re-detail / ROI-hybrid workflows. They are not independent pixel-restoration/SR families, and the stated 1792×1008 dimensions do not establish any spatial super-resolution.

The genuine Siax checkpoint is a separate CNN/GAN SR branch. The user-provided memory-efficient execution form is integrated into the adapter: it writes tiles into a final RGB uint8 canvas instead of allocating a full 4x float32 tensor. For a 1792×1008 BASE, a 4x RGB float32 canvas is about 347 MB decimal, while the uint8 canvas is about 86.7 MB decimal, excluding model/input/tile memory. Default tile settings are 128/8 and remain configurable. This is a memory optimization, not a quality improvement claim.

## Fair comparison protocol

For every comparison:

1. Freeze the same BASE SHA-256 and source crop.
2. Keep target dimensions, colour management and evaluation crops consistent.
3. Run at least a no-detail resampling control plus distinct eligible method families.
4. Record model/checkpoint revision, weights SHA-256, parameters, seed, device, tile settings, runtime, output SHA-256 and dimensions.
5. Score identity, topology, pose, material microtexture, edge/halo artifacts, text legibility, protected-region pixel changes and perceptual quality separately.
6. Use a human-reviewed project gold set; a model must not be the sole judge of its own output.
7. Do not produce one global winner when face, mesh, garment and environment regions prefer different branches.

The router currently proposes alternatives only. Only Siax inference has an optional local adapter in this branch; all other families remain non-executable until their adapters, license/hardware checks and project-image tests are added.

## Research references

- iRAG (ICCV 2025): retrieval-augmented reference-based diffusion SR with reference patch retrieval and hallucination filtering: https://openaccess.thecvf.com/content/ICCV2025/html/Lee_Reference-based_Super-Resolution_via_Image-based_Retrieval-Augmented_Generation_Diffusion.html
- GuideSR (ICCV 2025 Workshops): dual-branch guidance combining full-resolution structure with diffusion-based perceptual enhancement: https://openaccess.thecvf.com/content/ICCV2025W/MIPI/html/Arora_GuideSR_Rethinking_Guidance_for_One-Step_High-Fidelity_Diffusion-Based_Super-Resolution_ICCVW_2025_paper.html
- RefGC-SR2: reference-guided SR/refinement for AI-generated content using original high-resolution references: https://cmlab-korea.github.io/RefGC-SR2/
