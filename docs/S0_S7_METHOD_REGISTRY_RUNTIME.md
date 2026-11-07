# IGE S0-S7 Method Registry Runtime v0.2

## Authority and scope

This runtime slice implements the operating contract established by PR #12:
- \`docs/SHQ_AI_USAGE_GUIDE.md\` is the operator/AI usage contract.
- \`docs/SHQ_OBJECT_GEOMETRY_LOCK_PROGRAM_GUIDANCE.md\` is the normative geometry and return guidance.
- PR #15 remains technique lineage and failure memory.
- PR #5 supplies the current READ, candidate diagnosis, Skill Router and optional Siax runtime.
- PR #11 supplies experimental geometry-locked tile planning concepts.

This is a feature branch stacked on PR #5. It is not a replacement for the PR #12 documents, and it does not claim that research fossils are production implementations.

## Commands

Validate the packaged registry:

\`\`\`bash
ige validate-method-registry
\`\`\`

Validate a custom registry:

\`\`\`bash
ige validate-method-registry --path path/to/method_registry.json
\`\`\`

Create an evidence-aware plan:

\`\`\`bash
ige skill-plan input.png --diagnosis diagnosis.json --out run/skill_plan.json
\`\`\`

An optional \`--license-review-acknowledged\` records the operator's checkpoint/license review in the plan. It does not grant pixel permission and does not replace the Siax runtime's own \`--confirm-model-license-review\` control.

Audit a complete evidence bundle:

\`\`\`bash
ige audit-s0-s7 run/s0_s7_evidence.json --out run/s0_s7_audit.json
\`\`\`

Exit code is zero only when the candidate reaches \`ACCEPTED_CANDIDATE\`; incomplete or failed evidence exits non-zero.

## The eight stages

| Stage | Responsibility | Minimum evidence |
|---|---|---|
| S0 | Freeze BASE | Existing source file, matching SHA-256, explicit frozen and immutable flags |
| S1 | READ | Source-bound READ receipt; all model/segmentation findings remain candidate observations |
| S2 | Geometry Lock | Human-verified coordinate canvas and SHA, coordinate frame, independent model scale/object transform/tile size/tile context, explicit delivery transform if resampled |
| S3 | Permission | Human review record; BASE-bound approved and protected binary masks; both masks hash-checked, same canvas dimensions and non-overlapping |
| S4 | Method Router | Registry Method ID, maturity and preconditions; topology must be human-verified absent or resolved |
| S5 | Execute | Real backend/model receipt or deterministic operation receipt, source/input/model/output hashes and parameters |
| S6 | Compose / Return | Actual output file hash; core-only and coverage receipts; independently recomputed RGB pixel changes outside the approved mask; no implicit resize or flip |
| S7 | Independent Acceptance | Saved output reloaded and hash-checked; human visual review; identity, pose, topology, geometry, coverage, permission, protected-region, provenance and visual-quality gates |

The audit stops at the first failed stage and marks later stages \`NOT_RUN\`.

## Evidence bundle contract

The accepted top-level shape is a JSON object with \`S0\` through \`S7\`:

- \`S0.source_path\`, \`source_sha256\`, \`source_frozen=true\`, \`immutable=true\`
- \`S1.read_receipt.source_sha256\`, \`candidate_only=true\`, and an \`observations\` object
- \`S2.geometry_contract.source_sha256\`, \`canvas_path\`, \`canvas_sha256\`, \`coordinate_frame\`, \`geometry_human_verified=true\`, \`object_transform\`, \`model_scale\`, \`tile_size\`, \`tile_context\`; if \`delivery_resampled=true\`, a non-empty \`delivery_transform\` is mandatory
- \`S3.permission\`: \`human_reviewed\`, \`permission_granted\`, \`reviewer_ref\`, \`reviewed_at\`, \`base_sha256\`, \`coordinate_canvas_sha256\`, approved/protected mask paths and hashes, and non-empty \`target_regions\`
- \`S4.method_id\` and optional \`method_context\`
- \`S5.backend_receipt\` for \`neural_sr\`, \`diffusion\`, or \`external_backend\`; otherwise \`S5.operation_receipt\`
- \`S6.return_audit\` with \`output_path\`, \`output_sha256\`, \`core_only_writes\`, zero halo writes/core overlap/coverage gaps/outside-authorized changes, and explicit false resize/flip flags
- \`S7.acceptance\` with independent reload, exact saved-output path/hash, human reviewer/time and all nine hard-gate results set to \`PASS\`

S2's \`canvas_path\` defines the exact raster on which S3 masks are drawn. For a native 4x delivery, the coordinate canvas must itself be that native 4x raster or an explicitly declared transform must map it into that raster. Do not mix raw-source coordinates, native model-output coordinates and delivery coordinates.

The S6 pixel audit decodes the coordinate canvas, final output and approved binary mask. It rejects dimension mismatch, soft/feathered mask values and any changed pixel outside the approved mask. The protected mask must also be binary, non-empty, same-sized and disjoint from the approved mask.

Tile-specific counts (halo writes, core overlap and coverage gaps) are still receipts supplied by the tile compositor; this module does not reconstruct tile provenance from the final raster alone. The optional Core/Halo ledger (`ige-tile-core-halo-ledger/0.1`, see `docs/TILE_CORE_HALO_LEDGER.md`) carries per-tile read bounds, disjoint core bounds, optional output hashes and exact-once core coverage. When `S6.return_audit.tile_core_halo_ledger` or `tile_core_halo_ledger_path` is supplied, `evaluate_s0_s7` audits it fail-closed; absent ledger leaves the legacy integer receipts path unchanged. Synthetic ledger PASS ≠ live GPU compositor proof.

## Registry is the single routing authority

The JSON Registry is the single source for skill aliases, route-stage labels, source-document references, method maturity, preconditions and acceptance descriptions. The legacy hard-coded `SKILL_REGISTRY` table has been removed from `skill_router.py`; an unmapped alias now fails closed instead of falling back to a hidden default.

## Method maturity is not a single boolean

The Registry records distinct maturity classes:
- \`optional_runtime\`: real local adapter exists but dependencies, checkpoint, license, geometry and permission preconditions still gate use (currently pinned Siax 4x).
- \`partial\`: a limited non-generative operation exists (currently DETAIL6 residual/delivery); it is not generative inference.
- \`workflow_candidate\`: a workflow graph is known but backend/node/model receipts are not yet verified (currently Flux HR tile img2img).
- \`documented_only\`, \`research_only\`, \`external_donor_research\`, \`proxy_only\`, and \`contract_only\`: explicitly blocked from runtime execution.
- \`experimental\`: review/holdout required; not promoted by a passing synthetic test.

The four geometry/runtime variables \`model_scale\`, \`object_transform\`, \`tile_size\`, and \`tile_context\` are separate fields. Tile changes must not rewrite the global object transform.

The paired HOLE/REMOVE/DIFF/ANTI path is a conditional evidence method selected by S4, not a mandatory pre-processing chain. A trusted human-verified mask can bypass paired editing. A changed or invalid empty-background root invalidates downstream masks, donors and tiles.

## Registry safety rules

- Method IDs and aliases are unique and every method declares test IDs and acceptance conditions.
- A registry entry with \`edit_permission=true\` is invalid.
- Unknown methods fail closed.
- The registry cannot grant S3 permission.
- A model-generated observation or mask proposal is not human permission.
- File existence alone is not proof of checkpoint, model output, masks or reference materialization.
- S7 accepts an audited candidate only; it does not grant authorization for later edits.

## Current verified boundary

The Siax entry is pinned to the SHA-256 recorded in the existing \`src/ige/upscale/siax.py\` implementation. The CI tests verify the registry resolver, fail-closed preconditions, hash and receipt schema, mask constraints, and actual pixel-level outside-mask counterexamples with synthetic fixtures. The unit tests mock the pinned Siax model file hash; this is not live neural inference.

The Flux HR-tile entry remains \`workflow_candidate\`. No live ComfyUI node inventory, model inventory, per-tile conditioning routing, coordinate-consistent global noise field, GPU inference or real tile receipt has been validated in this branch. A workflow JSON or a synthetically passing test must not be represented as a real generative upscale run.

## Next integration boundary

Before enabling the Flux method:
1. Import the actual ComfyUI workflow and compare serialized API prompt values with the visible widget values (including UNET/VAE filenames).
2. Verify required custom nodes and model file SHA-256 inventory on the actual runner.
3. Prove conditioning and geometry contracts are routed per tile/subset, and prove whether the noise field is globally coordinate-consistent.
4. Prove disjoint core-only writes and exact-once coverage on **real** outputs (offline ledger contract exists; live compositor receipts still required); halo is read-only.
5. Execute at least one real holdout through S0-S7 and retain model, node, prompt, seed, inputs, tile, output and acceptance receipts.

Until then, the user does not need to run a ComfyUI test merely to validate the Registry/Router work. ComfyUI becomes necessary for the next live-inference proof.
