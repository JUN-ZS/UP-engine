# Architecture decision records

## ADR-0001 — independent repository, no legacy mutation

**Decision:** Build a new project with a separate Git history. Treat `ai-image-gen-logic-review` as read-only source material.

**Reason:** The legacy repository is an archive plus an evolving set of rules, docs, and image artifacts. Bulk migration would carry forward unclear dependencies, mixed maturity, and large artifact weight.

**Consequence:** The new project begins with contracts, interfaces, tests, and provenance. Useful legacy skills are migrated one at a time.

## ADR-0002 — generation and reconstruction are separate stages

**Decision:** An image model returns a candidate; deterministic registration, masking, and compositing create the reconstructed output.

**Reason:** A generative model should not be trusted to preserve pixels or geometry outside its intended region.

## ADR-0003 — hard gates precede visual ranking

**Decision:** Identity, pose, topology, mask leakage, registration, preservation, and required resolution are pass/fail gates. Aesthetic metrics are considered only after these pass.

**Reason:** A weighted average can hide a catastrophic structural failure behind high sharpness or texture scores.
