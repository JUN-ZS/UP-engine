# READ Engine v0.1 — perception before generation

## Purpose

READ is the first stage of UP-engine. Its job is not to make the picture prettier. Its job is to create a traceable description of the source image, propose object regions, and define exactly which pixels are permitted to change.

The engine keeps three kinds of evidence separate:

1. **Raster facts** — source hash, display-oriented dimensions, color/luminance statistics and a deliberately simple edge-density statistic.
2. **Model proposals** — candidate object masks returned by a segmentation provider. These are unreviewed evidence, not truth.
3. **Human-approved regions** — polygon annotations explicitly assigned one role: editable, protected, context, or object.

Only the third category can authorize editing.

## v0.1 workflow

IMAGE → EXIF NORMALIZATION → RASTER READ → OPTIONAL CONCEPT SEGMENTATION → HUMAN REGION ANNOTATION → MASKS + PREVIEW + JSON REPORT

The source image is never overwritten. Outputs are written to a separate run directory.

### Mask law

Let E be the union of pixels in regions explicitly annotated with role editable.

- editable.png = E
- protected_effective.png = complement(E)
- explicit_protected.png records only regions explicitly marked protected.
- context.png records regions marked context.
- unlabelled.png records pixels not covered by any human annotation.
- object annotations are structural references, not edit permission.

A pixel may not be both editable and explicitly protected. This is a hard error, not a warning. An empty editable mask is valid and means no pixel is currently authorized for modification.

**Critical distinction:** the effective protected mask is the complement of the editable mask, not merely the regions the operator remembered to mark as protected. Unknown areas are therefore protected by default.

### Model proposal law

A provider returns one or more masks, prompt text and a score. Each proposal is stored under proposals/ with status unreviewed_proposal and edit_permission=false.

A high score does not turn a proposal into an approved region. The operator must inspect the preview, correct the polygon/region annotation, and explicitly set the approved role. A model's mask may cut through a hand, weapon, hair strand, cloth fold, specular highlight or contact boundary; the mask is not a topology certificate.

## Run without a segmentation model

Install UP-engine:

    python -m pip install -e .

Run raster READ and export masks from human annotations:

    ige read-image source.png --out runs/read-001 --regions examples/read_regions.example.json

The example polygons are placeholders, not a mask fitted to your actual image. Replace them with polygons traced in the source image's display orientation.

Without a provider, READ still exports source provenance, raster metrics, human masks, an overlay preview, and an uncertainty-aware report. It does not invent semantic object labels.

## SAM 3.1 provider candidate

Meta's official SAM 3 repository documents text and visual prompts for image/video object segmentation. SAM 3 introduces open-vocabulary concept prompts; SAM 3.1 Object Multiplex was announced on 2026-03-27. Official image inference uses build_sam3_image_model, Sam3Processor, set_image, then set_text_prompt, which is the interface wrapped by the optional adapter.

Official sources:
- https://github.com/facebookresearch/sam3
- https://ai.meta.com/research/sam3
- https://github.com/facebookresearch/sam3/blob/main/LICENSE

The official repository currently specifies Python 3.12+, PyTorch 2.7+, and CUDA 12.6+ for its documented setup. The checkpoint requires a separate Hugging Face access request and authentication. SAM 3 is distributed under Meta's SAM License, not a blanket assumption of Apache/MIT licensing. Check the current license and business/use restrictions before enabling it in any deployment.

Install SAM3 separately in a compatible environment, request and authenticate checkpoint access, then run:

    ige read-image source.png --out runs/sam3-read-001 --provider sam3 --prompt "silver armor"
    ige read-image source.png --out runs/sam3-read-002 --provider sam3 --prompt "hammer head" --prompt "hand gripping the handle"

No model weights are included in UP-engine. CI does not download or exercise SAM3. A successful import is not a model-quality acceptance.

## What SAM3 can and cannot establish

SAM3 can propose masks for concepts described by short text phrases, and can work with visual prompts in its own API. This makes it a good first segmentation candidate for requests such as garment, hand, hammer head, hair or metallic armor.

Segmentation is not the same as understanding the physical scene. A mask alone does not establish:

- which cylindrical end-face contacts another surface;
- whether two T-shaped hammer faces are actually opposing each other;
- which part is in front or behind at a contact boundary;
- whether a limb or prop is connected to the expected joint;
- whether a camera change has altered the apparent geometry;
- whether a generated frame preserves the same topology as its parent.

Those require a separate relation/geometry read, evidence, and explicit acceptance. v0.1 intentionally reports these dimensions as not_claimed; it does not fill them with invented relationships.

## Output contract

A successful run creates:

- analysis.json — source SHA-256, dimensions, raster metrics, region inventory, proposal inventory, policy and limitations.
- READ_REPORT.md — concise human-readable interpretation.
- preview.png — visual overlay: editable, explicitly protected, context and proposal bounding boxes.
- masks/editable.png — the only mask that can authorize pixel writes.
- masks/protected_effective.png — complement of editable; default preservation mask.
- masks/explicit_protected.png — explicitly annotated protection.
- masks/context.png and masks/unlabelled.png.
- masks/regions/*.png — per-annotation masks.
- proposals/*.png — unreviewed model candidates.

The source SHA-256 and coordinate dimensions are recorded so downstream generation and compositing can verify they are operating on the same parent and pixel coordinate system.

## Failure conditions

READ must stop rather than silently degrade when:

- the source image is missing or invalid;
- normalized coordinates are invalid or region IDs collide;
- editable and protected annotations overlap;
- a provider returns masks with dimensions different from the EXIF-normalized source;
- a non-empty output directory would be overwritten without explicit permission.

There is no implicit resize of model masks. A geometric mask must not be stretched to fit because that conceals a coordinate-space error.

## Known v0.1 limits

- Polygon annotations are supplied as JSON; an interactive annotation UI is not included yet.
- Raster metrics are descriptive and are not semantic understanding or image-quality scores.
- SAM3 is an optional provider adapter and has not been benchmarked on the project's actual image set in CI.
- Automatic object-part graphs, occlusion/contact relations, identity anchors, and temporal continuity are not yet inferred.
- The generated preview is for inspection; human approval remains a separate action.

The next READ increment should add a visual annotation/review surface and a typed object/relation graph, then benchmark SAM3 masks against human-corrected masks on the project's real garment, face/hair, hand/weapon, thin-boundary and hammer-contact samples.
