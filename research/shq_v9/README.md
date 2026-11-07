# research/shq_v9 — Gemini-share reference code

**Status:** research / reference only. **Not** production-wired into `src/ige` (or any runtime package on `main`).

## Provenance

**Latest pack** (preferred):

- Short: https://share.gemini.google/hC9HlUpskKK9
- Share id: `49fb97a58dbe`
- Title: 物件導向幾何約束升頻架構
- Turns: **17** (+2 vs prior: **Method Registry**, **true generative 8K** mother plates)
- Transcript: `docs/sources/gemini-share-hC9HlUpskKK9/Gemini-完整對話.md`
- Extract notes: `docs/sources/gemini-share-hC9HlUpskKK9/EXTRACT.md`
- Media previews: `docs/sources/gemini-share-hC9HlUpskKK9/media/` (26 jpg)

**Prior pack** (kept under docs for provenance):

- Short: https://share.gemini.google/47yxULPlPy0W → share id `970343afbbef` (15 turns)

## Files (7)

| File | Role |
|------|------|
| `shq_v2_self_consistent_engine.py` | Orchestrator / boards / `run_v9_full_pipeline` entry |
| `shq_object_extractor.py` | Whole-part contracts, CLIPPING MASK REVERSE, pixel-inertia DNA, 3D/5D layer contracts |
| `shq_recursive_layer_return.py` | Guided whole-part return, hardpaste by 4-corners, L3→L2 reassembly |
| `shq_read_and_skill_router.py` | READ + state-dependent Skill Router (candidate marking, PATH1E / topology routes) |
| `shq_edit_hole_four_anti_debug.py` | Hole / remove / deduct / gen six-check audit (`strict` fail-closed) |
| `shq_5group_test_and_holdout_suite.py` | 5-group + holdout four-failure-mode separation tests |
| `shq_all24_true_generative_upscale_return.py` | True AI-gen 8K donors → geometry-locked return demo (S0–S7) |

## Important caveats (from the share critique)

- Early “generative upscale” paths in this lineage used **Lanczos + CLAHE + unsharp** disguised as generative detail — **forbidden** for UP-engine production.
- Treat these scripts as a **design fossil + experiment log**, not as the Siax / NCNN / ComfyUI inference contract.
- Production geometry lock must go through `docs/SHQ_OBJECT_GEOMETRY_LOCK_PROGRAM_GUIDANCE.md`, the AI usage guide `docs/SHQ_AI_USAGE_GUIDE.md`, and sibling feature PRs (#3 spatial geometry, #11 geometry-locked tiles, Siax runners, etc.).

## Intended next wiring (out of scope for this PR)

Map contracts → `src/ige` modules once bootstrap lands; keep research tree immutable for provenance.
