# S2.1.5 Quality Diagnostics — Nested cell only

**asof:** `2026-11-01T15:15:49Z`  
**cell_id:** `nested_L256/32_C64/ctx32`  
**primary SHA-256:** `5b7ca844e72b64e6c9e9fff5bf1f74e450b4c518003b096cd77bc2c8fa632656`  
**quality_qualified:** false · **final_acceptance:** false · **≠ original 256/32**

## Locked target

Only this Nested primary (workspace path below). Not 128/8, not 128/16, not a regenerated image.

- path: `runs/siax_validation_r2/S2_1/p1/nested_L256_32_C64_ctx32/OUT_NESTED_PRIMARY.png`
- 7168×4032 · 43 281 047 B
- Git does not store the PNG; SHA is the binding.

## 1. Integrity (OBSERVED_PASS)

| check | result |
| --- | --- |
| children in VM | 448 |
| children verified (file + SHA + size) | 448 |
| coverage | complete · 0 missing base px |
| overlap | none |
| primary SHA | match |

Evidence: `docs/evidence/S2_1_P1_NESTED_INTEGRITY.json`

## 2. SPM-A candidate (OBSERVED)

Method: crop Nested PNG at fixed 48 probes × Lanczos BASE residual — **no re-inference**.

| metric | value |
| --- | ---: |
| mae residual p50 | 3.9973 |
| mae residual p95 | 7.0422 |
| residual HF p50 | 6.6996 |
| residual HF p95 | 11.8527 |

P0 fingerprint delta (advisory only): delta_mae p50 **0.0857** · p95 **0.6554**  
(context differs; not a pass gate)

Evidence: `docs/evidence/S2_1_SPM_A_CANDIDATE_nested_L256_32_C64_ctx32.json`

## 3. Seam / continuity — compute grid 64/32 (OBSERVED)

| field | value |
| --- | --- |
| tile_size / pad | 64 / 32 |
| control_offset_base_px | 96 |
| image_sha256 | locked to primary |
| n_pairs | 336 |
| excess strip MAE p50 | -0.1042 |
| excess strip MAE p95 | 5.6849 |

Diagnostic only. Evidence: `docs/evidence/S2_1_SEAM_nested_L256_32_C64_ctx32.json`

## 4. Virtual Master quality index

448 native children indexed; each of 48 probes lists covering `child_id`s for localization.  
Evidence: `docs/evidence/S2_1_P1_VM_QUALITY_INDEX.json`

## 5. 400% blind (PENDING_HUMAN)

Not automated. Sample: cross-child seams, subject detail, contour junctions.

## Decision

| claim | allowed? |
| --- | --- |
| Nested execution + primary/VM produced | yes (prior P1) |
| Integrity of this SHA | yes |
| Diagnostic SPM-A / seam observed | yes |
| quality_qualified | **no** (until criteria + blind) |
| final_acceptance | **no** |
| original 256/32 single-forward success | **no** |

Next: set explicit pass criteria for SPM-A / seam / blind, or declare quality_qualified only after human 400% review.
