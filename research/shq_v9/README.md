# research/shq_v9 — Gemini-share reference code

**Status:** research / reference only. **Not** production-wired into `src/ige` (or any runtime package on `main`).

## Provenance

**Latest pack** (preferred):

- Short: https://share.gemini.google/XMyk6HVn2J9S
- Share id: `381865631306`
- Title: 物件導向幾何約束升頻架構
- Turns: **20** (+1 vs nutr: **battlefield self-part traceability** / 生除扣洞反 + method→program→test→accept)
- Transcript: `docs/sources/gemini-share-XMyk6HVn2J9S/Gemini-完整對話.md`
- Extract notes: `docs/sources/gemini-share-XMyk6HVn2J9S/EXTRACT.md`
- Media previews: `docs/sources/gemini-share-XMyk6HVn2J9S/media/`

**Prior packs** (kept under docs for provenance):

- https://share.gemini.google/nutrRjsw676R → `f5fb21d16408` (19 turns；PR #12 宣稱 + 四技能／頻率層)
- https://share.gemini.google/hC9HlUpskKK9 → `49fb97a58dbe` (17 turns)
- https://share.gemini.google/47yxULPlPy0W → `970343afbbef` (15 turns)

## Files (10)

| File | Role |
|------|------|
| `shq_v2_self_consistent_engine.py` | Orchestrator / boards / `run_v9_full_pipeline` entry |
| `shq_object_extractor.py` | Whole-part contracts, CLIPPING MASK REVERSE, pixel-inertia DNA, 3D/5D layer contracts |
| `shq_recursive_layer_return.py` | Guided whole-part return, hardpaste by 4-corners, L3→L2 reassembly |
| `shq_read_and_skill_router.py` | READ + state-dependent Skill Router (candidate marking, PATH1E / topology routes) |
| `shq_edit_hole_four_anti_debug.py` | Hole / remove / deduct / gen six-check audit (`strict` fail-closed) |
| `shq_5group_test_and_holdout_suite.py` | 5-group + holdout four-failure-mode separation tests |
| `shq_all24_true_generative_upscale_return.py` | True AI-gen 8K donors → geometry-locked return demo (S0–S7) |
| `shq_4skill_frequency_layer_engine.py` | 三／四技能頻率層（超分／材質／微細節）+ Rule 01380 邊界保護 |
| `validate_registry.py` | Method Registry schema 驗收輔助 |
| `shq_battlefield_self_part_traceability_engine.py` | **New** — 戰場自身部件升級 + 生除扣洞反 + 一對一方法追溯 |

## Important caveats (from the share critique)

- Early “generative upscale” paths in this lineage used **Lanczos + CLAHE + unsharp** disguised as generative detail — **forbidden** for UP-engine production.
- Treat these scripts as a **design fossil + experiment log**, not as the Siax / NCNN / ComfyUI inference contract.
- Production geometry lock must go through `docs/SHQ_OBJECT_GEOMETRY_LOCK_PROGRAM_GUIDANCE.md`, the AI usage guide `docs/SHQ_AI_USAGE_GUIDE.md`, and sibling feature PRs (#3 spatial geometry, #11 geometry-locked tiles, Siax runners, etc.).

## Intended next wiring (out of scope for this PR)

Map contracts → `src/ige` modules once bootstrap lands; keep research tree immutable for provenance.
