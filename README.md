# UP-engine — Image Generation & Reconstruction Engine

A clean, independently versioned engine for **reading an image, planning a constrained edit, routing to a suitable generator, reconstructing the result, and validating what changed**.

> Status: READ v0.1 is executable. Production image generation and reconstruction adapters are not wired in yet.

## Non-negotiable design rules

1. **Read before generate.** Every edit starts with an explicit task contract and an analysis record.
2. **Generation is not reconstruction.** Model output is a candidate layer; registration, masking, compositing, and preservation are separate deterministic stages.
3. **Hard constraints cannot be traded for visual quality.** Identity, pose, topology, protected regions, and registration are pass/fail gates. Sharpness cannot compensate for a failed gate.
4. **Region-aware and state-aware.** Routing depends on task, region, geometry risk, current image state, available memory, model capabilities, and license—not a fixed model ranking.
5. **Every result is reproducible.** Inputs, model/version, prompt, seed, masks, transforms, parameters, parent assets, outputs, and validation results are recorded.
6. **Legacy sources are read-only.** The previous ai-image-gen-logic-review repository is a reference source only. This project does not modify or mirror its files.

## Pipeline

INTAKE → READ → CONTRACT/LOCK → ROUTE → GENERATE → REGISTER → RECONSTRUCT → DETAIL → VALIDATE → ACCEPT/REJECT

The READ stage is now executable for raster inspection, explicit region annotations, mask export, preview visualization, and optional semantic segmentation proposals. A segmentation proposal is not an accepted edit mask.

## Repository layout

    docs/                  architecture, workflow, skill mapping, migration policy, READ design
    schemas/               JSON Schemas for task contracts, PEEP manifests and READ regions
    src/ige/               contracts, router, manifest validator, READ pipeline and providers
    configs/               example model registry and routing policy
    examples/              minimal manifests and sample region annotations
    tests/                 deterministic unit tests
    .github/workflows/     CI

## Quick start

Requires Python 3.11+ for the core engine.

    python -m pip install -e .
    python -m unittest discover -s tests -v
    ige validate-manifest examples/peep_manifest.json
    ige read-image source.png --out runs/read-001 --regions examples/read_regions.example.json

Example region polygons are placeholders and must be redrawn for the real source image. See docs/READ_ENGINE.md for mask law, SAM 3.1 setup, output layout and limitations.

## Current scope and explicit non-claims

- READ v0.1 computes raster statistics and exports explicit region masks and previews.
- Optional SAM3 text segmentation returns unreviewed candidate masks; it does not grant edit permission.
- No production image-generation model is wired in.
- No automatic claim is made that physical geometry, object topology, identity or occlusion is understood.
- No image-quality or identity-preservation improvement is claimed until measured on a versioned test set.
- No model weights, private images, legacy artifact dumps or copied legacy scripts are included.

## Source project

See docs/LEGACY_SOURCE_POLICY.md. The historical repository is not a dependency and will never be automatically pulled into this repository.
