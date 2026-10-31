# READ Engine v0.3 — perception before generation

## Purpose

READ is the first stage of UP-engine. Its job is not to make the picture prettier. Its job is to create a traceable description of the source image, propose object regions and relationships, and define exactly which pixels are permitted to change.

The engine keeps four kinds of evidence separate:

1. **Raster facts** — source hash, display-oriented dimensions, color/luminance statistics and a deliberately simple edge-density statistic.
2. **Model proposals** — candidate object masks returned by a segmentation provider. These are unreviewed evidence, not truth.
3. **Human region annotations** — region polygons with semantic identity, tags and a separate pixel permission.
4. **Relation assertions** — typed links between annotated regions, explicitly marked candidate, human_verified or rejected.

## Region identity is not pixel permission

A region has independent fields:

- semantic_type says what the region represents, e.g. garment, face, hand, hammer_head, cylindrical_end_face, hair or background.
- permission says whether its pixels may be changed: editable or protected.
- tags describe cross-cutting functions such as object, context, identity_anchor, contact_surface or occlusion_boundary.

This distinction matters: armor can be an object and be editable; a hand can be an object and remain protected; a face can be an identity anchor and remain protected. These facts must not be collapsed into one mutually exclusive role.

## v0.3 workflow

IMAGE → EXIF NORMALIZATION → RASTER READ → OPTIONAL CONCEPT SEGMENTATION → HUMAN REGION ANNOTATION → RELATION GRAPH → MASKS + PREVIEW + JSON REPORT

The source image is never overwritten. Outputs are written to a separate run directory. All annotation polygons use normalized 0..1 coordinates in the EXIF-corrected display orientation.

### Mask law

Let E be the union of pixels in regions explicitly annotated with permission editable.

- editable.png = E
- protected_effective.png = complement(E)
- explicit_protected.png records regions explicitly marked protected.
- context.png records any regions tagged context.
- objects_reference.png records any regions tagged object.
- unlabelled.png records pixels not covered by any human region annotation.

A pixel may not be both editable and explicitly protected. This is a hard error, not a warning. An empty editable mask is valid and means no pixel is currently authorized for modification.

**Critical distinction:** the effective protected mask is the complement of the editable mask, not merely the regions the operator remembered to mark as protected. Unknown areas are therefore protected by default.

### Model proposal law

A segmentation provider returns masks, prompt text and an optional score. Each proposal is stored under proposals/ with status unreviewed_proposal and edit_permission=false.

A high score does not turn a proposal into an approved region. The operator must inspect the preview, correct the polygon/region annotation, and explicitly assign permission. A model's mask may cut through a hand, weapon, hair strand, cloth fold, specular highlight or contact boundary; the mask is not a topology certificate. Missing model scores remain null; UP-engine does not invent confidence.

## Typed relation graph

Relations refer to region IDs and have a predicate, status, source, confidence, evidence, and optional evidence region.

Supported predicates include:

- part_of — a directed structural hierarchy; cycles are rejected.
- occludes / in_front_of / behind — image-space overlap ordering.
- touches / contacts_at — contact assertions; contacts_at requires explicit subject_surface and object_surface.
- attached_to, aligned_with, opposes, parallel_to, perpendicular_to, same_object_as.

A human_verified relation must have source human and non-empty evidence. A model cannot declare its own relation human-verified. A contacts_at relation must identify both surfaces, for example cylindrical_end_face against cylindrical_end_face; this allows the exact contact geometry to be stated instead of the vague assertion that two objects touch.

Model-produced relation assertions are proposals and are not inferred facts. They are stored separately from human-authored relations. The file format is ready for human-confirmed geometry now and model-generated candidates later. A text/vision model may propose a relationship, but it must remain candidate until reviewed. The region graph does not replace a true 3D reconstruction or establish hidden surfaces from a single 2D image.

## Run without a segmentation model

Install UP-engine:

    python -m pip install -e .

Run raster READ and export masks from human annotations:

    ige read-image source.png --out runs/read-001 --regions examples/read_regions.example.json

The example polygons are placeholders, not masks fitted to your actual image. Replace them with polygons traced in the source image's display orientation.

To include explicit relation assertions, supply both region and relation files:

    ige read-image source.png --out runs/hammer-read --regions examples/regions_hammer_contact.example.json --relations examples/relations_hammer_contact.example.json

The hammer example is a schema template only. The polygons and relation evidence must be replaced or visually verified against the actual image before any relation is marked human_verified.

Without a provider, READ exports source provenance, raster metrics, human masks, relation graph, preview and an uncertainty-aware report. It does not invent semantic object labels or physical relations.



## READ Studio — local polygon and relation annotation

Open tools/read-studio/index.html in a modern browser, or serve the repo root:

    python -m http.server 8000

Open http://127.0.0.1:8000/tools/read-studio/. The page loads an image through a local browser object URL and performs no network requests or uploads. Click at least three polygon points, finish the region, then enter:

- region ID and label;
- semantic_type (what the region is);
- permission (whether its pixels may be changed);
- tags such as object, context, identity_anchor, contact_surface or occlusion_boundary.

The UI defaults every new region to protected. It exports read_regions.json and read_relations.json. Relations can be marked candidate, human_verified or rejected; human_verified requires human source plus evidence, and contacts_at requires both surface names.

Use the exports with:

    ige read-image source.png --out runs/read-001 --regions read_regions.json --relations read_relations.json

The example polygons in the repo are templates. Always trace the actual source image. The tool does not alter the original image and does not infer occlusion/contact automatically.

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

Those require explicit relation assertions, evidence and review. v0.3 supports optional VLM candidate proposals but does not auto-verify relations.

## Output contract

A successful run creates:

- analysis.json — source SHA-256, dimensions, raster metrics, region inventory, relation graph, proposal inventory, policy and limitations.
- READ_REPORT.md — concise human-readable interpretation.
- preview.png — visual overlay: editable, explicitly protected, context and proposal bounding boxes.
- masks/editable.png — the only mask that can authorize pixel writes.
- masks/protected_effective.png — complement of editable; default preservation mask.
- masks/explicit_protected.png — explicitly annotated protection.
- masks/context.png and masks/objects_reference.png.
- masks/unlabelled.png and masks/regions/*.png.
- proposals/*.png — unreviewed model candidates.

The source SHA-256 and coordinate dimensions are recorded so downstream generation and compositing can verify they are operating on the same parent and pixel coordinate system.

## Failure conditions

READ must stop rather than silently degrade when:

- the source image is missing or invalid;
- normalized coordinates are invalid or region IDs collide;
- editable and protected annotations overlap;
- relation endpoints do not exist;
- human_verified relations are not human-sourced or lack evidence;
- a part_of relation graph contains a cycle;
- a contacts_at relation omits the specific subject/object surfaces;
- a provider returns masks with dimensions different from the EXIF-normalized source;
- a non-empty output directory would be overwritten without explicit permission.

There is no implicit resize of model masks. A geometric mask must not be stretched to fit because that conceals a coordinate-space error.

## Known v0.3 limits

- Region polygons and relations can be created in the local-only READ Studio under tools/read-studio/; the visual reviewer is intentionally manual and does not infer hidden geometry.
- Raster metrics are descriptive and are not semantic understanding or image-quality scores.
- VLM outputs are unreviewed candidate nodes/relations with uncalibrated self-assessment confidence.
- Task-specific generation packets and an external-candidate pixel-preserving compositor are available; no production image generator or automatic registration model is active yet.
- SAM3 is an optional provider adapter and has not been benchmarked on the project's actual image set in CI.
- Automatic relation/occlusion/contact inference, identity embedding, camera geometry and temporal continuity are not yet implemented.
- The generated preview is for inspection; human approval remains a separate action.

See docs/GENERATION_HANDOFF.md for the Qwen3.8-27B reasoner, earlier Qwen baselines, optional HiSpatial comparison, strict candidate contract, task-scoped mask generation, geometry-lock handoff and pixel-preserving compositor. The next increment is a visual candidate-review surface and benchmark replay on the project's actual garment, face/hair, hand/weapon, thin-boundary and hammer-contact samples.
