# research/shq_v9 — Gemini-share reference code

**Status:** research / reference only. **Not** production-wired into `src/ige` (or any runtime package on `main`).

## Provenance

Copied from Gemini public share:

- Short: https://share.gemini.google/47yxULPlPy0W
- Share id: `970343afbbef`
- Title: 物件導向幾何約束升頻架構
- Transcript: `docs/sources/gemini-share-47yxULPlPy0W/Gemini-完整對話.md`
- Extract notes: `docs/sources/gemini-share-47yxULPlPy0W/EXTRACT.md`

## Files

| File | Role |
|------|------|
| `shq_v2_self_consistent_engine.py` | Orchestrator / boards / `run_v9_full_pipeline` entry |
| `shq_object_extractor.py` | Whole-part contracts, CLIPPING MASK REVERSE, pixel-inertia DNA, 3D/5D layer contracts |
| `shq_recursive_layer_return.py` | Guided whole-part return, hardpaste by 4-corners, L3→L2 reassembly |

## Important caveats (from the share critique)

- Early “generative upscale” paths in this lineage used **Lanczos + CLAHE + unsharp** disguised as generative detail — **forbidden** for UP-engine production.
- Treat these scripts as a **design fossil + experiment log**, not as the Siax / NCNN / ComfyUI inference contract.
- Production geometry lock must go through the program guidance gates in `docs/SHQ_OBJECT_GEOMETRY_LOCK_PROGRAM_GUIDANCE.md` and sibling feature PRs (#3 spatial geometry, #11 geometry-locked tiles, Siax runners, etc.).

## Intended next wiring (out of scope for this PR)

Map contracts → `src/ige` modules once bootstrap lands; keep research tree immutable for provenance.
