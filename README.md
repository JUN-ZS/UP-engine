# UP-engine — Image Generation & Reconstruction Engine

A clean, independently versioned engine for **reading an image, planning a constrained edit, routing to a suitable generator, reconstructing the result, and validating what changed**.

> Status: architecture scaffold / no production image model is wired in yet.

## Non-negotiable design rules

1. **Read before generate.** Every edit starts with an explicit task contract and an analysis record.
2. **Generation is not reconstruction.** Model output is a candidate layer; registration, masking, compositing, and preservation are separate deterministic stages.
3. **Hard constraints cannot be traded for visual quality.** Identity, pose, topology, protected regions, and registration are pass/fail gates. Sharpness cannot compensate for a failed gate.
4. **Region-aware and state-aware.** Routing depends on task, region, geometry risk, current image state, available memory, model capabilities, and license—not a fixed model ranking.
5. **Every result is reproducible.** Inputs, model/version, prompt, seed, masks, transforms, parameters, parent assets, outputs, and validation results are recorded.
6. **Legacy sources are read-only.** The previous `ai-image-gen-logic-review` repository is a reference source only. This project does not modify or mirror its files.

## Pipeline

`INTAKE → READ → CONTRACT/LOCK → ROUTE → GENERATE → REGISTER → RECONSTRUCT → DETAIL → VALIDATE → ACCEPT/REJECT`

The first implementation focuses on the contracts and evidence trail. A model adapter is not considered usable until it passes the same benchmark suite as every other adapter.

## Repository layout

```text
constitution/          (to be added as stable, versioned rules mature)
docs/                  architecture, workflow, skill mapping, migration policy
schemas/               JSON Schemas for task contracts and PEEP manifests
src/ige/               typed contracts, router, manifest validation, gates
src/ige/adapters/      model adapter interface; providers remain opt-in
configs/               model registry and routing policy
examples/              minimal valid manifests and task contracts
tests/                 deterministic unit tests
.github/workflows/     CI
```

## Quick start

Requires Python 3.11+.

```bash
python -m pip install -e .
python -m unittest discover -s tests -v
ige validate-manifest examples/peep_manifest.json
```

## Current scope and explicit non-claims

- This scaffold validates contracts and manifests; it does **not** generate or edit images yet.
- It contains no model weights, private images, legacy artifact dumps, or copied legacy scripts.
- A model name in research notes is a candidate, not proof of operational integration or quality.
- No claim of identity preservation, geometric correctness, or image-quality improvement is made until measured on a versioned test set.

## Source project

See [`docs/LEGACY_SOURCE_POLICY.md`](docs/LEGACY_SOURCE_POLICY.md). The historical repository is not a dependency and will never be automatically pulled into this repository.
