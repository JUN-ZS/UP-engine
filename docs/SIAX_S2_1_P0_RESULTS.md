# S2.1 P0 Results — RAM profile + SPM-A + seam controls

**asof:** `2026-11-01T13:34:46Z` · **final_acceptance:** false

## 1. Staged RAM profile (OBSERVED)

Synthetic single-forward peaks (1 thread, subprocess-isolated):

| Model input | Label | maxrss MiB | wall s |
| --- | --- | ---: | ---: |
| 144×144 | 128/8 | **663.67** | 9.263 |
| 160×160 | 128/16 | **725.57** | 10.022 |
| 288×288 | 256/16 | **1473.67** | 39.235 |
| 320×320 | 256/32 | **1664.96** | 44.464 |

- Isolated 320 forward **succeeds** (~1.66 GiB peak) on 1.9 GiB host.
- Full-job 256/32 OOM still explained by **peak near ceiling + other residency** (model ~391 MiB baseline, canvas ~83 MiB, BASE tensor, fragmentation) — refined Hypothesis, not “320 impossible”.
- Evidence: `docs/evidence/S2_1_RAM_PROFILE.json`

## 2. SPM-A fixed 48 probes (OBSERVED)

Bank SHA `1267b78b1b957cb1…` · probe 48×64 · real Siax vs Lanczos residual

| metric | value |
| --- | ---: |
| mae residual p50 | 3.887 |
| mae residual p95 | 6.664 |
| residual HF p50 | 6.379 |
| residual HF p95 | 10.634 |

Fingerprint bank for BASE e283 — **not** full-frame quality rank alone.

## 3. Matched seam controls (OBSERVED)

Fixed sample fracs; seam strip MAE − control strip MAE:

| Cell | excess p50 | excess p95 | n pairs |
| --- | ---: | ---: | ---: |
| 128/8 | -0.0339 | 4.604 | 160 |
| 128/16 | 0.0000 | 5.146 | 160 |
| 256/16 | 0.4531 | 6.867 | 72 |

Rank by excess p50 (lower better): **128_8 → 128_16 → 256_16**

## Tools

- `tools/ram_profile_siax.py`
- `tools/s2_build_probe_bank.py`
- `tools/s2_spm_a_run.py`
- `tools/s2_seam_controls.py`

## Next

P1: Nested compute RF measurement · strip finalizer · memory-budgeted 256/32 full job attempt.
