# SHQ / Object Geometry Lock — docs index

`main` stays minimal. Object-geometry-locked upscaling work lives in docs + research on feature branches, and in sibling open PRs.

## This branch (v0.1 program guidance + latest Gemini pack)

| Doc | Purpose |
|-----|---------|
| [SHQ_OBJECT_GEOMETRY_LOCK_PROGRAM_GUIDANCE.md](./SHQ_OBJECT_GEOMETRY_LOCK_PROGRAM_GUIDANCE.md) | Actionable pipeline stages, gates, forbidden practices, module map |
| [SHQ_AI_USAGE_GUIDE.md](./SHQ_AI_USAGE_GUIDE.md) | **給 AI agent 嘅理解規約**：讀序、硬閘、S0–S7、Registry、宣稱邊界 |\n| [SHQ_OTHER_AI_STEP_BY_STEP_RUNBOOK.md](./SHQ_OTHER_AI_STEP_BY_STEP_RUNBOOK.md) | **其他 AI 直接照做嘅操作手冊**：Clone、依賴、Preflight、Registry、測試、L0→L4 Strict RUN、S7 與回報 JSON |
| [sources/gemini-share-XMyk6HVn2J9S/](./sources/gemini-share-XMyk6HVn2J9S/) | **最新** Gemini 源（20 turns；+1 vs nutr：戰場自身部件追溯／生除扣洞反）；raw/payload 只留 SHA |
| [sources/gemini-share-nutrRjsw676R/](./sources/gemini-share-nutrRjsw676R/) | 上一包（19 turns；PR #12／宣稱再測 + 三技能／頻率層）— 保留作 provenance |
| [sources/gemini-share-hC9HlUpskKK9/](./sources/gemini-share-hC9HlUpskKK9/) | 更早包（17 turns；Method Registry + 真生成 8K）— 保留作 provenance |
| [sources/gemini-share-47yxULPlPy0W/](./sources/gemini-share-47yxULPlPy0W/) | 更早包（15 turns）— 保留作 provenance |
| [../research/ige_shq_github_verifiable_package_v1.0/](../research/ige_shq_github_verifiable_package_v1.0/) | **Current verifiable reference package** — 5-layer L0→L4 + registry + tests + assets + `preflight_check.py` + pinned requirements（research-only） |
| [../research/shq_v9/README.md](../research/shq_v9/README.md) | Earlier single-script fossils ×10（not production-wired; superseded for end-to-end verify by package above） |

### External-AI execution rule

External agents must read the Runbook and run `preflight_check.py` before any long pipeline. A missing or mismatched asset is `BLOCK`, not a warning. The attached candidate ZIP audited on 2026-11-08 has SHA-256 `6f13bd5c45f99db1541f236991dbd9e07d7bb637f9d02138563f85ff7f63b2e8` and is missing `B0_GL` / `B2_GL`; it is not a replacement for the expanded Hub baseline. See Runbook §0.

## Sibling open PRs (do not treat as duplicates)

| PR | Theme |
|----|--------|
| [#3](https://github.com/JUN-ZS/UP-engine/pull/3) | READ v0.3 — spatial proposals, task geometry contracts, pixel-safe reconstruction |
| [#11](https://github.com/JUN-ZS/UP-engine/pull/11) | Geometry-locked two-tile generative experiment |
| [#10](https://github.com/JUN-ZS/UP-engine/pull/10) | SIAX DDXX multi-view geometry registration + ComfyUI |
| [#7](https://github.com/JUN-ZS/UP-engine/pull/7) / [#9](https://github.com/JUN-ZS/UP-engine/pull/9) | Distributed / heterogeneous Siax tile runners |
| [#6](https://github.com/JUN-ZS/UP-engine/pull/6) | Prevent blue injection on SIAX + DETAIL6 |
| [#2](https://github.com/JUN-ZS/UP-engine/pull/2) / [#4](https://github.com/JUN-ZS/UP-engine/pull/4) / [#5](https://github.com/JUN-ZS/UP-engine/pull/5) | READ / Grok adapters / REF router |
| [#1](https://github.com/JUN-ZS/UP-engine/pull/1) | Bootstrap scaffold |

This guidance PR **references** those tracks; it does not replace their runtime code.
