# Visual reasoning and generation handoff — READ v0.3

## Why use separate perception models

The image reconstruction problem contains two different prediction tasks:

1. **Where are the pixels?** A segmentation model should propose pixel masks.
2. **What does the scene mean?** A vision-language model should propose object/part identities and relations such as part_of, occludes, contacts_at, opposes and aligned_with.

UP-engine does not ask one model to do both jobs. SAM 3.1 is the optional pixel segmentation provider. Qwen3.8-27B is the primary open-weight RGB visual reasoner candidate. Their outputs are evidence proposals and remain separate.

## Model research and routing decision

### Qwen3.8-27B — primary RGB visual reasoner candidate

The official Qwen3.8 project describes a native vision-language model for image and video understanding, with improved multimodal reasoning and agent execution. The Qwen3.8-27B Hugging Face model card lists Apache-2.0 and a BF16 checkpoint size of approximately 55.6GB. Its public benchmark table includes spatial / embodied tasks such as ERQA; the reported ERQA score is higher than the Qwen3.6-27B result in the same table. These are upstream benchmarks, not a prediction of accuracy on the project's exact hammer-contact or garment-boundary examples.

Sources:
- https://github.com/QwenLM/Qwen3.8
- https://huggingface.co/Qwen/Qwen3.8-27B
- https://huggingface.co/Qwen/Qwen3.8-35B-A3B

UP-engine includes an optional local adapter for Qwen3.8-27B. It is not enabled by the model router because it has not yet been benchmarked on the project's own images. The adapter uses Transformers AutoModelForImageTextToText, requires Transformers >=5.8.1 and an independently compatible PyTorch build. The structured READ adapter disables chain-of-thought output so the result can be parsed as one strict JSON object. A separate benchmark should compare direct-output mode with thinking mode; neither is assumed superior for relation precision without measurement.

The Qwen3.8-27B BF16 checkpoint is about 55.6GB on the model repository. An NVIDIA NIM NVFP4 package is listed at about 20.44GB, but that is a specific quantized distribution, not a universal peak-VRAM figure. Actual peak memory depends on runtime, image resolution, context, attention/KV cache, batch size and quantization. The user's GPU is not yet recorded, so no local execution claim is made.

Install the VLM extra and a compatible PyTorch build:

    python -m pip install -e ".[vlm]"

Then run:

    ige read-image source.png --out runs/read-001 --regions read_regions.json --relations read_relations.json --reasoner qwen

Override the checkpoint when comparing models:

    ige read-image source.png --out runs/read-qwen36 --regions read_regions.json --relations read_relations.json --reasoner qwen --reasoning-model Qwen/Qwen3.6-27B
    ige read-image source.png --out runs/read-qwenvl --regions read_regions.json --relations read_relations.json --reasoner qwen --reasoning-model Qwen/Qwen3-VL-8B-Instruct

The default installation does not import Transformers, download the model, or initialize GPU memory. No model is enabled automatically. A failed load, unsupported hardware or missing weights does not silently switch to a different model.

### Qwen3.6-27B and Qwen3-VL-8B — historical baselines

Qwen3.6-27B is retained to compare the newer generation against the preceding dense model. Qwen3-VL-8B is retained as a lower-parameter baseline for hardware and latency comparisons. Public model-card capability claims are not project-specific validation. Compare the same fixed image set, prompts, decoder settings, output parser, and human-scored contact/occlusion labels.

### Qwen3.8-35B-A3B — sparse MoE comparison

This model has 35B total parameters and about 3B active parameters. The Hugging Face repository is approximately 71.9GB in the listing used for this registry. The active-parameter count affects compute per token; it does not mean that only 3B parameters' weights must be stored. Keep it disabled until actual runtime profiling shows a benefit over the dense Qwen3.8-27B path.

### HiSpatial-3B — second-stage RGB+XYZ comparison

Microsoft Research's HiSpatial-3B is a specialist candidate for hierarchical spatial reasoning. Its documented inference takes an RGB image plus a metric XYZ point map estimated with MoGe. Its model card lists an approximately 14GB checkpoint and Gemma Terms of Use.

Sources:
- https://github.com/microsoft/HiSpatial
- https://microsoft.github.io/HiSpatial/
- https://huggingface.co/lhzzzzzy/HiSpatial-3B

This is not the default path. It adds a depth-estimation dependency and an estimated 3D input which can be wrong on stylized/generated imagery. Metric-looking coordinates are not ground truth. We keep HiSpatial disabled until a controlled comparison demonstrates that the depth input improves hammer-contact, hand/weapon, garment and occlusion cases rather than adding false geometric certainty.

### Model roles

| Model | UP-engine role | Output | Acceptance state |
|---|---|---|---|
| SAM 3.1 | semantic segmentation candidate | pixel masks and object boxes | optional, unreviewed |
| Qwen3.8-27B | primary open-weight RGB reasoner candidate | object boxes, relation candidates, evidence boxes | optional, unreviewed |
| Qwen3.6-27B | previous-generation comparison | same proposal contract | disabled |
| Qwen3-VL-8B | lower-parameter historical baseline | same proposal contract | disabled |
| Qwen3.8-35B-A3B | sparse-MoE comparison | same proposal contract | disabled |
| HiSpatial-3B | RGB+XYZ spatial specialist comparison | spatial question answers | disabled; MoGe required |

Published benchmark scores are useful for choosing candidates, not evidence that a model will preserve the exact surface geometry of two T-hammers or identify a thin garment/hand boundary in this dataset. The only acceptance evidence that matters for enabling a model is a versioned replay on the project's own gold set.

## Reasoning proposal contract

A VLM response must be strict JSON with:

- nodes: visible objects/parts, each with a normalized bounding box, semantic type, direct visual evidence and uncertainty;
- relations: subject, predicate, object, normalized evidence box, visual evidence, uncertainty, optional confidence and surface details;
- uncertainties: unresolved questions.

The parser rejects invalid JSON, invalid coordinates, unknown relation endpoints, unsupported predicates, empty evidence, missing contact-surface labels and non-positive boxes. It does not try to repair malformed JSON or guess missing values.

All parsed VLM data is forcibly serialized as candidate, source=model, edit_permission=false and geometry_lock=false. Self-reported confidence is uncalibrated; it is not interpreted as a statistical probability. The preview draws VLM object boxes and relation-evidence boxes separately from SAM proposals and human-approved polygons.

## Geometry contract and human confirmation

The VLM proposal does not enter the human-authored scene graph. To create a lock, the operator must:

1. inspect the original image and the candidate evidence boxes;
2. use READ Studio to draw/correct actual region polygons and semantic types;
3. mark their independent pixel permission;
4. add the relation in READ Studio;
5. set relation status to human_verified with human source and specific visual evidence.

For contacts_at, both surfaces must be explicit, e.g. cylindrical_end_face against cylindrical_end_face. A generic box overlap is not contact proof. For a T-shaped hammer, the head, cylindrical end face and shaft side are different surfaces. The annotation must identify the actual surface that meets the other hammer.

compile-generation includes only these human_verified relations. Candidate model relations are written to candidate_relations_excluded and cannot become geometry locks. The resulting contract is explicitly image-plane 2D; it does not assert metric 3D coordinates, hidden surfaces, physical forces or camera calibration.

## Task-specific pixel authorization

A full-image READ can have several separate editable regions (for example armor and cloak). A particular generation task must not inherit permission to edit every editable region just because one of them was selected.

Compile a task packet from the READ analysis:

    ige compile-generation runs/read-001/analysis.json --out runs/task-armor --objective "retexture the chest armor while preserving its silhouette" --target-region armor-chest

To verify a moved or separately stored BASE, pass the exact original file:

    ige compile-generation runs/read-001/analysis.json --base source.png --out runs/task-armor --objective "retexture the chest armor" --target-region armor-chest

Before writing the packet, UP-engine verifies the BASE SHA-256, human-approved target permission, region mask dimensions and SHA-256, and evidence for human-verified relations. Candidate model relations are explicitly excluded. The task generation mask is the union of only selected region masks; its protected mask is the exact full-frame complement.

## Pixel-preserving reconstruction compositor

The project includes a deterministic compositor for already-registered candidate images:

    ige composite-generation runs/task-armor/generation_packet.json source.png registered-candidate.png --out runs/task-armor/composite.png --model-id your-generator-id

The candidate must have the same EXIF-corrected display dimensions as BASE. The compositor does not resize, warp or guess alignment. It checks BASE SHA-256, task-mask SHA-256 values, binary masks, exact protected-mask complement and authorized pixel count. It copies candidate pixels only where generation_mask is set; all other pixels are copied from immutable BASE.

The output must be PNG. JPEG is rejected because lossy re-encoding can change pixels outside the authorized mask. The saved PNG is read back and checked again; any outside-mask pixel change causes the output file to be deleted and the operation to fail. A sidecar .audit.json records the pixel diff and model ID.

The compositor deliberately reports only parent source identity, mask integrity, protected-region pixel preservation, mask leakage and native resolution as pass. Registration quality, identity, pose, topology and geometry-lock preservation remain pending. Matching dimensions alone do not prove correct alignment. The sidecar final_acceptance is always false in this stage.

## Required project benchmark

The first curated set should cover:
- T-hammer end-face to end-face contact, and false contact through shaft sides;
- hammer head / shaft topology under different views;
- hand gripping a weapon, with fingers overlapping the shaft;
- hair strands crossing face/garment boundaries;
- armor and cloth texture changes without silhouette drift;
- front/behind ambiguity at thin overlap edges;
- identity, pose and background protection.

Report per-sample region IoU / boundary F-score, relation precision/recall by predicate, false-positive contact rate, evidence-box overlap, hard-gate failure counts, model latency and peak memory. Do not collapse contact correctness and mask quality into one average score.
