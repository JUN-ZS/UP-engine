# SHQ AI 使用引導（給另一個 AI Agent）

**Audience:** 任何要跟進／實作／驗收「物件導向幾何約束升頻」的 AI Agent  
**Normative contract:** [SHQ_OBJECT_GEOMETRY_LOCK_PROGRAM_GUIDANCE.md](./SHQ_OBJECT_GEOMETRY_LOCK_PROGRAM_GUIDANCE.md)  
**Executable control plane:** [SHQ_AGENT_DRIVER.md](./SHQ_AGENT_DRIVER.md)  
**Latest research source:** [Gemini 19-turn pack on PR #12](https://github.com/JUN-ZS/UP-engine/tree/feat/shq-geometry-lock-program-guidance-v0.1/docs/sources/gemini-share-nutrRjsw676R/)  
**Research fossils:** [research/shq_v9](../research/shq_v9/) — not production runtime

---

## 1. Read order

1. [SHQ_INDEX.md](./SHQ_INDEX.md) — repository map and branch relationships.
2. [SHQ_OBJECT_GEOMETRY_LOCK_PROGRAM_GUIDANCE.md](./SHQ_OBJECT_GEOMETRY_LOCK_PROGRAM_GUIDANCE.md) — normative geometry, stage and return contract.
3. This guide — operating checklist and evidence semantics.
4. [SHQ_AGENT_DRIVER.md](./SHQ_AGENT_DRIVER.md) — actual Python control plane and manifest.
5. [PR #12 latest Gemini source pack](https://github.com/JUN-ZS/UP-engine/tree/feat/shq-geometry-lock-program-guidance-v0.1/docs/sources/gemini-share-nutrRjsw676R/) — 19 turns; provenance and research, not runtime.
6. research/shq_v9/ — design fossils / experiments only. Never import these files as production methods without a reviewed adapter and tests.

## 2. Core intent

> Lock each object's geometry first; then plan tiles and run a real inference backend inside that contract. Do not substitute larger tiles, Lanczos sharpening, soft alpha, fake inpaint, or synthetic texture for generation.

Keep these independent: model_scale ≠ object_transform ≠ tile_size ≠ tile_context ≠ delivery_transform.

## 3. Hard gates

Any of the following in a production path is BLOCK:
- Lanczos / CLAHE / unsharp / Gaussian residual described as generative upscale.
- A claimed generative result without a real backend call and matching input/model/output receipts.
- Soft-alpha or feathering used to hide geometry drift or ghosting.
- Horizontal flip / mirror in RETURN.
- Halo/context written into the master; only tile core may be written.
- Downsampled previews used as proof of bit-exact source pixels.
- Reusing downstream masks/donors/tiles after their empty-BG or geometry root changes.
- AI-generated candidate observations being treated as permission.

## 4. Canonical stages

| Stage | Responsibility | Required evidence |
|---|---|---|
| S0 | BASE freeze | File path, dimensions, SHA-256; verify hash again before/after execution |
| S1 | OBJECT READ | Source-bound candidate observations; topology/identity states explicitly unknown until verified |
| S2 | GEOMETRY LOCK | Human-verified coordinate canvas + SHA; separate object transform, model scale, tile size/context and delivery transform |
| S3 | PERMISSION | Human-reviewed approved/protected masks; hashes, dimensions, binary values, non-overlap, reviewer/time |
| S4 | ROUTER | Registry method ID, maturity, preconditions and backend capability |
| S5 | EXECUTE | Real backend receipt, checkpoint/model SHA, input/output SHA, parameters, request ID |
| S6 | COMPOSE / RETURN | Core-only ledger, exact-once coverage, output SHA, protected-pixel audit, no implicit resize/flip |
| S7 | INDEPENDENT ACCEPT | Disk reload, independent metrics, human visual review, explicit gate results |

A stage failure stops downstream stages. No AI may overwrite a failed stage status with PASS.

## 5. Driver is the execution authority

Use ige agent-run manifest.json to preflight. The default mode is plan-only and runs no backend. Add --execute only when S0–S4 evidence, model SHA, license review and method preconditions pass.

The Dispatcher only invokes exact, reviewed callable entrypoints from its code allowlist. Registry strings are never evaluated as Python. Unknown or non-runnable methods fail closed.

The current allowlist contains the existing pinned Siax 4x adapter only. Flux/Comfy is intentionally not callable. audit-comfy-workflow and capture-model-inventory are static/offline tools, not execution authority.

## 6. Backend truth labels

- Siax: existing local adapter can run when all manifest and Registry checks pass; its result is still a candidate.
- Flux / Comfy: workflow_candidate; static node/model inventory does not prove execution, conditioning, global noise or tile writes.
- External donor: separate research/transfer path; never relabel as destination-tile diffusion.
- DETAIL6: partial deterministic residual path; not a generative backend.
- research/shq_v9: research-only unless a separately reviewed production adapter imports a specific capability.

## 7. Evidence invalidation

If any parent SHA changes (BASE, empty-BG, coordinate canvas, masks, checkpoint, workflow, tile plan), invalidate all dependent receipts and recompute from the earliest affected stage. Never reuse an S5, S6 or S7 receipt against a different parent hash.

## 8. Required report

Report exact branch/commit, method ID, stages S0–S7, source/model/output SHA, adapter receipt, tile ledger, CI evidence, and non-claims. Distinguish Observed, Derived, Estimated and Hypothetical evidence. Never call unit tests, synthetic ledgers, static Comfy audits or declared model inventories a live GPU generation run.
