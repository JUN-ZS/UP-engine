# UP-engine — Image Generation & Reconstruction Engine

A clean, independently versioned engine for **reading an image, planning a constrained edit, routing to a suitable generator, reconstructing the result, and validating what changed**.

> Status: READ v0.3 prepares visual-reasoning proposals and task-specific generation packets. A deterministic pixel-preserving compositor is executable; production image generation and automatic registration are not wired in yet.

## Non-negotiable design rules

1. **Read before generate.** Every edit starts with a typed source record and analysis.
2. **Generation is not reconstruction.** Model output is a candidate layer; registration, masking, compositing and preservation are separate deterministic stages.
3. **Hard constraints cannot be traded for visual quality.** Identity, pose, topology, protected regions and registration are pass/fail gates.
4. **Region identity and pixel permission are independent.** A garment can be editable; a hand or face can be protected; all may still be semantic objects.
5. **Model proposals are never permissions.** SAM masks and VLM relationships remain unreviewed until an explicit human action.
6. **Legacy sources are read-only.** The previous ai-image-gen-logic-review repository is a reference source only.

## Pipeline

INTAKE → READ → HUMAN REVIEW/LOCK → TASK-SCOPED MASK + GEOMETRY CONTRACT → MODEL ROUTE → GENERATE CANDIDATE → REGISTER → RECONSTRUCT → VALIDATE → ACCEPT/REJECT

READ v0.3 adds optional Qwen3.8 visual proposals and task-specific generation packets. It does not invoke an image generator automatically.

## Quick start

Requires Python 3.11+ for the core engine.

    python -m pip install -e .
    python -m unittest discover -s tests -v
    ige validate-manifest examples/peep_manifest.json

Run READ Studio in a browser to annotate the actual BASE image and export region/relation JSON. Then:

    ige read-image source.png --out runs/read-001 --regions read_regions.json --relations read_relations.json

Optionally request Qwen visual object/part/relation proposals (install a compatible PyTorch build and UP-engine's VLM extra first):

    python -m pip install -e ".[vlm]"
    ige read-image source.png --out runs/read-002 --regions read_regions.json --relations read_relations.json --reasoner qwen

The default reasoner checkpoint is Qwen/Qwen3.8-27B. Override with --reasoning-model to compare another Qwen model. The default output mode disables thinking to preserve strict JSON; thinking-mode comparisons require their own measured test.

These proposals are not accepted relations or edit masks. Inspect the output preview and analysis.json, then manually confirm or correct regions/relations in READ Studio.

Compile a task-specific generation packet:

    ige compile-generation runs/read-002/analysis.json --base source.png --out runs/task-armor --objective "retexture the chest armor while preserving its silhouette" --target-region armor-chest

The task packet includes only the selected human-approved editable region mask; all other pixels are protected.

Once an external generator has produced a candidate already registered to the BASE dimensions, composite it and run the pixel-diff audit:

    ige composite-generation runs/task-armor/generation_packet.json source.png registered-candidate.png --out runs/task-armor/composite.png --model-id your-generator-id

The strict compositor accepts PNG output only, never resizes a candidate, re-checks BASE and mask hashes, verifies the encoded result has zero changes outside the task mask, and leaves identity/pose/topology/registration gates pending. See docs/GENERATION_HANDOFF.md.

## Model roles

- SAM 3.1: optional pixel segmentation proposal model.
- Qwen3.8-27B: primary open-weight RGB object/part/relation candidate; BF16 weights are about 55.6GB.
- Qwen3.6-27B and Qwen3-VL-8B: previous-generation comparison baselines.
- Qwen3.8-35B-A3B: sparse-MoE comparison; 3B active parameters do not mean 3B weight storage.
- HiSpatial-3B: optional RGB+XYZ spatial specialist; requires MoGe point-map estimation.

No model is enabled automatically. Hardware, license and project-specific quality must be checked before routing. Model candidates are not validated merely because their weights load.

## Current scope and explicit non-claims

- READ v0.3 exports source provenance, region masks, segmentation/VLM proposals, human-authored relations and a task-scoped pixel whitelist.
- VLM outputs are strict, evidence-bearing proposals with uncalibrated confidence; they cannot self-verify relations.
- Generation packets preserve only human-verified relations and check original image / mask SHA-256 hashes.
- The deterministic compositor checks pixel preservation only; geometry, registration, identity, pose and topology remain separate gates.
- No production image-generation adapter or automatic registration model is wired in yet.
- No image-quality, identity-preservation or spatial-reasoning improvement is claimed before evaluation on the project's real test corpus.
- No model weights, private images or legacy artifact dumps are included.

## Source project

See docs/LEGACY_SOURCE_POLICY.md. The historical repository is not a dependency and will never be automatically pulled into this repository.
