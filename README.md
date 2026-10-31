# UP-engine — Image Generation & Reconstruction Engine

A clean, independently versioned engine for **reading an image, planning a constrained edit, routing to a suitable generator, reconstructing the result, and validating what changed**.

> Status: READ v0.2 is executable for raster inspection, polygon masks, typed region semantics and human-authored relations. Production image generation and reconstruction adapters are not wired in yet.

## Non-negotiable design rules

1. **Read before generate.** Every edit starts with an explicit task contract and an analysis record.
2. **Generation is not reconstruction.** Model output is a candidate layer; registration, masking, compositing, and preservation are separate deterministic stages.
3. **Hard constraints cannot be traded for visual quality.** Identity, pose, topology, protected regions, and registration are pass/fail gates. Sharpness cannot compensate for a failed gate.
4. **Region identity and pixel permission are independent.** A garment can be editable; a hand or face can be protected; all may still be semantic objects.
5. **Every result is reproducible.** Inputs, model/version, prompt, seed, masks, transforms, parameters, parent assets, outputs, and validation results are recorded.
6. **Legacy sources are read-only.** The previous ai-image-gen-logic-review repository is a reference source only. This project does not modify or mirror its files.

## Pipeline

INTAKE → READ → CONTRACT/LOCK → ROUTE → GENERATE → REGISTER → RECONSTRUCT → DETAIL → VALIDATE → ACCEPT/REJECT

READ v0.2 exports source provenance, explicit region masks, a preview, model proposal masks and a typed human-authored relation graph. Segmentation proposals never become accepted edit masks automatically.

## Repository layout

    docs/                  architecture, workflow, skill mapping, migration policy, READ design
    schemas/               JSON Schemas for task contracts, PEEP manifests, READ regions and relations
    src/ige/               contracts, router, manifest validation, READ pipeline and providers
    configs/               example model registry and routing policy
    examples/              minimal manifests, region and relation annotations
    tests/                 deterministic unit tests
    .github/workflows/     CI

## Quick start

Requires Python 3.11+ for the core engine.

    python -m pip install -e .
    python -m unittest discover -s tests -v
    ige validate-manifest examples/peep_manifest.json
    ige read-image source.png --out runs/read-001 --regions examples/read_regions.example.json

For manually annotated contact geometry, supply a relation file as well:

    ige read-image source.png --out runs/hammer-read --regions examples/regions_hammer_contact.example.json --relations examples/relations_hammer_contact.example.json

Example polygons are placeholders and must be redrawn for the real source image. See docs/READ_ENGINE.md for mask policy, relation status, SAM 3.1 setup and limitations.

## READ Studio (local image annotation)

Open `tools/read-studio/index.html` directly in a modern browser, or serve the repository root locally:

    python -m http.server 8000

Then open `http://127.0.0.1:8000/tools/read-studio/`. Load the BASE image, click at least three points to draw each polygon, finish the region, and assign its semantic type, tags and separate pixel permission. Add relationships such as `contacts_at`, specifying both surfaces, then export `read_regions.json` and `read_relations.json`.

Run the engine with the exported files:

    ige read-image source.png --out runs/read-001 --regions read_regions.json --relations read_relations.json

READ Studio uses the image locally in the browser; it does not upload it or call a remote service. The original file is never changed. The tool exports annotations, not a claim that the image's physical geometry has been automatically understood.

## Current scope and explicit non-claims

- READ v0.2 computes raster statistics and exports human-authored semantic regions, editable/protected masks, relation assertions and previews.
- Optional SAM3 text segmentation returns unreviewed candidate masks; it does not grant edit permission.
- No production image-generation model is wired in.
- No automatic claim is made that physical geometry, object topology, identity or occlusion is understood; human relation assertions are explicit inputs.
- No image-quality or identity-preservation improvement is claimed until measured on a versioned test set.
- No model weights, private images, legacy artifact dumps or copied legacy scripts are included.

## Source project

See docs/LEGACY_SOURCE_POLICY.md. The historical repository is not a dependency and will never be automatically pulled into this repository.
