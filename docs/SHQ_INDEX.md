# SHQ / Object Geometry Lock — docs index

`main` stays minimal. Object-geometry-locked upscaling work lives in docs + research on feature branches, and in sibling open PRs.

## This branch (v0.1 program guidance + latest Gemini pack)

| Doc | Purpose |
|-----|---------|
| [SHQ_OBJECT_GEOMETRY_LOCK_PROGRAM_GUIDANCE.md](./SHQ_OBJECT_GEOMETRY_LOCK_PROGRAM_GUIDANCE.md) | Actionable pipeline stages, gates, forbidden practices, module map |
| [SHQ_AI_USAGE_GUIDE.md](./SHQ_AI_USAGE_GUIDE.md) | **給 AI agent 嘅使用引導**：讀序、硬閘、S0–S7、Registry、回報格式 |
| [sources/gemini-share-nutrRjsw676R/](./sources/gemini-share-nutrRjsw676R/) | **最新** Gemini 源（19 turns；PR #12／宣稱再測 + 三技能／頻率層）；raw/payload 只留 SHA |
| [sources/gemini-share-hC9HlUpskKK9/](./sources/gemini-share-hC9HlUpskKK9/) | 上一包（17 turns；Method Registry + 真生成 8K）— 保留作 provenance |
| [sources/gemini-share-47yxULPlPy0W/](./sources/gemini-share-47yxULPlPy0W/) | 更早包（15 turns）— 保留作 provenance |
| [../research/shq_v9/README.md](../research/shq_v9/README.md) | Reference Python artifacts ×9（not production-wired） |

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
