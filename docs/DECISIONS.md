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

## 2026-11-01 — Grok Vision + Imagine replace active Qwen path

Decision:
- Active READ visual reasoner: xAI Grok Vision (`src/ige/read/providers/xai_grok.py`).
- Active candidate generator: xAI Grok Imagine (`src/ige/adapters/xai_imagine.py`).
- Qwen local adapters remain in-tree only as deprecated comparison paths.
- No silent fallback from Grok failure to Qwen.
- Registration is a separate gate (`src/ige/adapters/registration.py`). Dimension mismatch is BLOCKED; no auto-resize into compositor.
- Grok Vision must not grade its own geometry as human truth. Gold annotations + UP-engine pixel/geometry gates remain independent evidence.

Non-claims:
- Adapter presence ≠ gold-set PASS.
- API call success ≠ final_acceptance.
- Imagine prompt text is not a permission system.
