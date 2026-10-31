# UP-engine — Image Generation & Reconstruction Engine

A clean, independently versioned engine for **reading an image, planning a constrained edit, routing to a suitable generator, reconstructing the result, and validating what changed**.

> Status: READ v0.3 + Grok adapters. Grok Vision is the active READ reasoner path; Grok Imagine is the candidate generator adapter; registration is a separate gate. Qwen is deprecated and never used as fallback. Live xAI E2E remains NOT RUN without XAI_API_KEY and gold annotations.

## Non-negotiable design rules

1. **Read before generate.** Every edit starts with a typed source record and analysis.
2. **Generation is not reconstruction.** Model output is a candidate layer; registration, masking, compositing and preservation are separate deterministic stages.
3. **Hard constraints cannot be traded for visual quality.** Identity, pose, topology, protected regions and registration are pass/fail gates.
4. **Region identity and pixel permission are independent.** A garment can be editable; a hand or face can be protected; all may still be semantic objects.
5. **Model proposals are never permissions.** SAM masks and VLM relationships remain unreviewed until an explicit human action.
6. **Legacy sources are read-only.** The previous ai-image-gen-logic-review repository is a reference source only.

## Pipeline

INTAKE → READ → HUMAN REVIEW/LOCK → TASK-SCOPED MASK + GEOMETRY CONTRACT → MODEL ROUTE → GENERATE CANDIDATE → REGISTER → RECONSTRUCT → VALIDATE → ACCEPT/REJECT

READ v0.3 adds optional Grok Vision visual proposals (Qwen retained only as deprecated comparison) and task-specific generation packets. `ige generate-candidate` can call Grok Imagine; outputs remain unverified candidates.

## Quick start

Requires Python 3.11+ for the core engine.

    python -m pip install -e .
    python -m unittest discover -s tests -v
    ige validate-manifest examples/peep_manifest.json

Run READ Studio in a browser to annotate the actual BASE image and export region/relation JSON. Then:

    ige read-image source.png --out runs/read-001 --regions read_regions.json --relations read_relations.json

Optionally request Grok Vision object/part/relation proposals (requires XAI_API_KEY; no Transformers/Qwen import on this path):

    export XAI_API_KEY=...
    # optional: export XAI_VISION_MODEL=grok-4
    ige read-image source.png --out runs/read-002 --regions read_regions.json --relations read_relations.json --reasoner grok

These proposals are not accepted relations or edit masks. Inspect the output preview and analysis.json, then manually confirm or correct regions/relations in READ Studio. Geometry locks require human verification.

Deprecated comparison only (explicit, never fallback):

    python -m pip install -e ".[vlm]"
    ige read-image source.png --out runs/read-qwen --regions read_regions.json --relations read_relations.json --reasoner qwen

Compile a task-specific generation packet:

    ige compile-generation runs/read-002/analysis.json --base source.png --out runs/task-armor --objective "retexture the chest armor while preserving its silhouette" --target-region armor-chest

The task packet includes only the selected human-approved editable region mask; all other pixels are protected.

Primary candidate path is **HERE** (this Grok agent session + Grok Imagine tools), not the remote API:

    # 1) Prepare constrained prompt + job package (default --backend here)
    ige generate-candidate runs/task-armor/generation_packet.json source.png --out runs/task-armor/candidate

    # 2) In the Grok HERE session: edit BASE with Imagine using runs/task-armor/candidate/imagine_prompt.txt
    # 3) Ingest the produced candidate file
    ige accept-candidate runs/task-armor/generation_packet.json source.png /path/to/here-candidate.png --out runs/task-armor/candidate --overwrite

Secondary remote xAI Images API path (requires XAI_API_KEY):

    export XAI_API_KEY=...
    ige generate-candidate runs/task-armor/generation_packet.json source.png --out runs/task-armor/candidate-api --backend xai-api

Assess registration (dimension match only; no auto-resize/warp):

    ige assess-registration source.png runs/task-armor/candidate/candidate.png

If registration allows, composite and run the pixel-diff audit:

    ige composite-generation runs/task-armor/generation_packet.json source.png runs/task-armor/candidate/candidate.png --out runs/task-armor/composite.png --model-id xai.grok.imagine --require-registration-gate

The strict compositor accepts PNG output only, never resizes a candidate, re-checks BASE and mask hashes, verifies the encoded result has zero changes outside the task mask, and leaves identity/pose/topology/registration gates pending. See docs/GENERATION_HANDOFF.md.

## Model roles

- Grok Vision (xAI Responses API, default model env `XAI_VISION_MODEL` / `grok-4`): **active** READ object/part/relation proposer.
- Grok Imagine (`grok-imagine-image-2.0` via `XAI_IMAGINE_MODEL`): independent candidate image editor/generator.
- SAM 3.1: optional pixel segmentation proposal model.
- Qwen family: **deprecated** comparison-only local VLMs; not default; never silent fallback.
- HiSpatial-3B: optional RGB+XYZ spatial specialist; still disabled.

No model is enabled automatically. Hardware, license and project-specific quality must be checked before routing. Calling an API is not the same as passing pixel/geometry acceptance.

## Current scope and explicit non-claims

- READ v0.3 exports source provenance, region masks, segmentation/VLM proposals, human-authored relations and a task-scoped pixel whitelist.
- Grok Vision / Imagine adapters are wired; live API E2E is NOT RUN unless XAI_API_KEY is present and gold annotations exist.
- VLM outputs are strict, evidence-bearing proposals with uncalibrated confidence; they cannot self-verify relations or act as their own exam grader.
- Generation packets preserve only human-verified relations and check original image / mask SHA-256 hashes.
- Registration adapter reports dimension match only; size match ≠ geometric registration. Mismatch → BLOCKED, never silent resize.
- The deterministic compositor checks pixel preservation only; geometry, registration, identity, pose and topology remain separate gates.
- No image-quality, identity-preservation or spatial-reasoning improvement is claimed before evaluation on the project's real gold test corpus.
- No model weights, private images, API keys or legacy artifact dumps are included.



## Grok Vision skill diagnosis (candidate-only)

The skill router can now receive a first-pass image-defect diagnosis from the same xAI Grok Vision transport used by READ. It writes both a raw, provenance-bearing `diagnosis.json` and a `skill_plan.json`:

    export XAI_API_KEY=...
    ige diagnose-image BASE.png --out runs/diagnosis

When a canonical identity image is available, pass it explicitly as a second ordered image:

    ige diagnose-image BASE.png --out runs/diagnosis-a8b \\
      --identity-reference references/a8b.png \\
      --identity-reference-id a8b78fe5-2654-4f6f-84e3-c1dfbee61004

Without an identity reference, `identity_drift` is forcibly recorded as `unknown`; Grok is not allowed to infer identity mismatch from the BASE image alone. All Grok observations are tagged `source=grok_vision`, `verification=candidate`, and cannot authorize a skill or geometry lock. Human review is still required before promoting any observation to `human_verified`.

The diagnostic model request is wired and mock-tested; live xAI calls and project-image accuracy are **NOT RUN** until an operator supplies an API key and the project has a human-reviewed gold set.

## Automatic reference resolution and skill routing

UP-engine now ships an offline, provenance-pinned metadata snapshot of key a8b, skin, PATH1E and DETAIL6 references. It indexes asset IDs, roles, skills, source commit and source section. It does not pretend that a UUID means the underlying Imagine image bytes are locally available. The seed catalog is curated, not yet a complete crawl of every historical reference.

    ige ref-search --skill SKIN_MAT
    ige ref-search --query "a8b face identity"
    ige ref-search --query "metal detail" --asset-root ./reference-assets

For defect-aware routing, provide an evidence-bearing diagnosis. A Grok Vision proposal may inform the diagnosis, but it must remain a candidate until a human verifies it. Raster dimensions are measured automatically; face identity, topology, metal, skin and material defects are not guessed from generic pixel statistics.

    ige skill-plan source.png --diagnosis examples/skill_diagnosis.example.json --out runs/skill-plan.json

A topology error blocks downstream sharpening/upscale. PATH1E, TEX4, GRID_SIAX, PIXEL_CTRL and SKIN_MAT are still documented-only until their full execution paths are imported and benchmarked. The planner reports that limitation rather than pretending to execute them.

## Siax 4x + DETAIL6

The first DETAIL6 execution slice accepts a genuine 4x Siax master, applies region-limited residual detail with protected face/skin/eye-white masks, and exports JPEG 4:4:4. This is not yet the complete legacy DETAIL6 skill: GRID_CLEAN/BEAT donor selection and legacy clarity proof still need migration. It explicitly forbids inflating a small image to meet a megabyte target.

Install the optional local runtime:

    python -m pip install -e ".[upscale]"

The checkpoint is not committed. Download the pinned file from the reference listed in docs/DETAIL6_AND_REF_ROUTING.md, verify its SHA-256 and review its model terms first. The mirror repository labels itself MIT, but original model terms still require review. The command requires an explicit acknowledgement:

    ige upscale-siax source.png --checkpoint models/4x_NMKD-Siax_200k.pth --out runs/upscale/SIAX4X.png --confirm-model-license-review

The output includes a hash-bound .upscale.json sidecar. Prepare masks at BASE or 4x dimensions; the mask manifest must provide metal/stone/text/fire detail masks (at least one) and face/skin/eye_white protection masks:

    ige detail6 source.png --upscaled runs/upscale/SIAX4X.png --masks runs/masks.json --out runs/detail6 --minimum-bytes 30000000

The default byte threshold is 6,000,000, matching the legacy DETAIL6 floor. Set 30,000,000 only when that delivery target is specifically required. If the content does not naturally meet it, the size gate fails; no padding or fake enlargement is applied.

This partial DETAIL6 path emits a lossless working PNG, q98 and q100 JPEG 4:4:4 outputs, per-zone high-frequency diagnostics and a protected-pixel audit. HF energy is not an acceptance score; visual clarity review remains required. Exact pixel proof applies to the lossless PNG relative to the Siax master; JPEG is necessarily lossy. This stage does not certify identity, pose, topology, geometry or temporal continuity.

## Source project

See docs/LEGACY_SOURCE_POLICY.md. The historical repository is not a dependency and will never be automatically pulled into this repository.
