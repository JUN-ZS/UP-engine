# Architecture: separate the cognitive and pixel pipelines

## Two independent workflows

### A. New image / new IP

`Brief → concept/world read → character & object design → identity/geometry lock → master frame → variants`

The master frame is the source of truth. PRE/POST or multi-view derivatives are generated only from an accepted master and must preserve the declared identity, camera, and object topology.

### B. Existing image reconstruction

`Image intake → READ → region/scene graph → task contract → model route → masked candidate generation → registration → compositor → detail pass → validation`

A model-generated candidate is never automatically treated as the final image.

## Core services

- **Perception / READ:** scene graph, object parts, material regions, masks, boundaries, confidence, uncertainty.
- **Task planner:** turns the requested outcome into a typed task plus explicit locks/unlocks.
- **Reference manager:** gives every image a role (BASE, identity, pose, geometry, donor, swatch, context, candidate). Never pass an ambiguous pile of references.
- **Model router:** filters by capabilities, license, validation state, local/remote constraints, resolution and resource budget; then ranks eligible choices using state and risk.
- **PEEP orchestrator:** records parent image, generation/protected masks, context ring, coordinate transform, adapter, seed and output.
- **Registration:** aligns candidate output to the parent coordinate system; records transform and residual.
- **Compositor:** applies only approved pixels / frequency bands. BASE remains immutable; output is a new artifact.
- **Validator:** runs non-negotiable gates before aesthetic scoring.

## State-dependent routing

Routing is not `task → favorite model`. It is:

`route = f(task, region, geometry_risk, mask_complexity, drift_history, source_resolution, VRAM, RAM, latency_budget, offline_policy, license, benchmark_state)`

A model can be eligible for a simple texture fill but ineligible for identity-critical face work. A history of geometry drift should increase the priority of deterministic reconstruction or an independently validated geometry-capable path.

## No single score for acceptance

Hard gates: identity, pose, topology, mask leakage, registration, protected-region preservation, native-resolution requirements.

Soft metrics: texture similarity, edge quality, fine detail, seam quality, perceptual quality, runtime and memory. Soft scores rank candidates only after all required hard gates pass.
