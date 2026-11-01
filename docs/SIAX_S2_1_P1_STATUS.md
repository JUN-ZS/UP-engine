# S2.1 P1 Status — Nested RF + strip finalizer + memory-budgeted nested full job

**asof:** 2026-11-01 · **final_acceptance:** false · **branch:** `feat/siax-r3-nested-peep-vm-v0.1`

## Scope (opened)

| Item | Status |
| --- | --- |
| RF measure (core=64) | **DONE** · rec context **24** · using **32** conservative |
| Nested compute runner | **DONE** · `tools/nested_compute_siax.py` (subprocess \| inprocess, resume, VM emit) |
| Strip finalizer | **DONE** · `src/ige/upscale/strip_finalize.py` (preview-never-primary, size/path asserts) |
| Virtual Master schema | **DONE** · `schemas/virtual-master.schema.json` |
| 1-parent smoke L256/C64/ctx32 | **DONE** · peak RSS **630 MiB** · 16 children |
| Full nested L256/32 C64/ctx32 | **IN_PROGRESS** · durable resume driver |

## RF (OBSERVED)

Source: `docs/evidence/S2_1_RF_MEASURE_c64.json`

| margin | mae_vs_ref | inner_mae |
| ---: | ---: | ---: |
| 0 | 1.754 | 1.495 |
| 8 | 0.752 | 0.706 |
| 16 | 0.462 | 0.419 |
| 24 | 0.307 | 0.284 |
| 32 | 0.128 | 0.115 |
| 40 | 0.025 | 0.020 |
| 48 | 0.000 | 0.000 |

**recommended_compute_context = 24** (conservative production cell uses **32**).

## Smoke nested (OBSERVED)

- cell_id: `nested_L256/32_C64/ctx32` (1 parent only)
- peak_rss_mb: **630.18**
- model_rss_after_load_mb: **411.36**
- isolation: inprocess + resume
- equivalence_to_single_forward_logical: **NOT_CLAIMED**
- evidence: `docs/evidence/S2_1_P1_SMOKE_NESTED_SUMMARY.json`

## Full job

- job-dir: `runs/siax_validation_r2/S2_1/p1/nested_L256_32_C64_ctx32`
- planned children ≈ 448 (28 parents × 16)
- driver: `/tmp/p1_full_nested_driver.sh` with resume + foreign-agent kill
- primary out: `OUT_NESTED_PRIMARY.png` via strip finalizer when complete
- **NOT** labeled as recovered single-forward 256/32

## Explicit non-claims

- final_acceptance remains false
- PR #7 evidence untouched
- Nested cell is a **new** experimental cell ID
