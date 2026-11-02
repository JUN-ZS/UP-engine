# Architecture: separate the cognitive and pixel pipelines

## Two independent workflows

### A. New image / new IP

Brief → concept/world read → character & object design → identity/geometry lock → master frame → variants

The master frame is the source of truth. PRE/POST or multi-view derivatives are generated only from an accepted master and must preserve the declared identity, camera, and object topology.

### B. Existing image reconstruction

IMAGE INTAKE → READ → HUMAN REVIEW / LOCK → TASK-SCOPED MASK + GEOMETRY CONTRACT → MODEL ROUTE → GENERATE CANDIDATE → REGISTER → RECONSTRUCT → DETAIL → VALIDATE

A model-generated candidate is never automatically treated as the final image.

## Separate the perception jobs

- **Segmentation provider:** proposes pixel masks and object boxes. It does not decide if those pixels can be edited.
- **Visual reasoner:** proposes semantic object/part nodes and typed relations with evidence boxes. It does not create masks, certify contact or promote its own assertions.
- **Human annotation / relation review:** turns a selected proposal into an explicit region permission or human_verified relation.
- **Geometry contract compiler:** consumes the original READ report; includes only human-verified relations and creates a per-task generation whitelist plus its exact protected complement.

SAM 3.1 and Qwen3-VL therefore perform complementary jobs. They are never collapsed into one "understand image" switch.

## Core services

- **Perception / READ:** source hash, scene/region graph, object-part candidates, material regions, masks, boundaries, confidence and uncertainty.
- **Task planner:** turns the requested outcome into a typed task plus explicit locks/unlocks.
- **Reference manager:** gives every image a role (BASE, identity, pose, geometry, donor, swatch, context, candidate). Never pass an ambiguous pile of references.
- **Model router:** filters by capabilities, license, validation state, local/remote constraints, resolution and resource budget; then ranks eligible choices using state and risk.
- **PEEP orchestrator:** records parent image, task-specific generation/protected masks, context ring, coordinate transform, adapter, seed and output.
- **Registration:** aligns candidate output to the parent coordinate system; records transform and residual.
- **Compositor:** applies only approved pixels / frequency bands. BASE remains immutable; output is a new artifact.
- **Validator:** runs non-negotiable gates before aesthetic scoring.

## State-dependent routing

Routing is not task → favorite model. It is:

route = f(task, region, geometry_risk, mask_complexity, drift_history, source_resolution, VRAM, RAM, latency_budget, offline_policy, license, benchmark_state)

A model can be eligible for a simple texture fill but ineligible for identity-critical face work. A history of geometry drift should increase the priority of deterministic reconstruction or an independently validated geometry-capable path.

## No single score for acceptance

Hard gates: identity, pose, topology, mask leakage, registration, protected-region preservation, native-resolution requirements.

Soft metrics: texture similarity, edge quality, fine detail, seam quality, perceptual quality, runtime and memory. Soft scores rank candidates only after all required hard gates pass.

## Immutable parent and task-scoped write area

The generation mask for one task is not the global set of every region ever marked editable. It is the union of only the selected target-region masks. Its protected mask is the exact complement across the BASE dimensions. Other editable regions therefore remain protected for this particular task.

The task packet binds:
- original BASE SHA-256 and display dimensions;
- selected human-approved region IDs and mask hashes;
- task generation mask and exact protected mask hashes;
- human-verified image-plane relation locks;
- excluded candidate relation IDs;
- downstream pixel-diff, topology, registration and preservation requirements.

This is the bridge from "READ says these regions exist" to "this specific generation request may touch only these pixels".
