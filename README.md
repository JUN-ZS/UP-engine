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

Generate an unverified Grok Imagine candidate from the packet (persists image bytes + metadata; does not overwrite BASE):

    export XAI_API_KEY=...
    # optional: export XAI_IMAGINE_MODEL=grok-imagine-image-2.0
    ige generate-candidate runs/task-armor/generation_packet.json source.png --out runs/task-armor/candidate

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

## Source project

See docs/LEGACY_SOURCE_POLICY.md. The historical repository is not a dependency and will never be automatically pulled into this repository.
