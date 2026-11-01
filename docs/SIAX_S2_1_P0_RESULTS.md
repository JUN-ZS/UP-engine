# S2.1 P0 Results — COMPLETE

**Status:** `DONE_P0` · **overall final_acceptance:** `false`  
**Branch:** `feat/siax-r3-nested-peep-vm-v0.1`  
**PR:** Draft #8 · PR #7 evidence base remains frozen at `463cce1`

P0's requested scope was to implement and run an isolated staged peak-RSS harness, create a fixed SPM-A probe bank, and run seam-control diagnostics across 128/8, 128/16 and 256/16. That scope is complete.

**P0 does not require a full-image 256/32 rerun or intentionally triggering another OOM. Do not hold P0 open for that test.**

## 1. Staged peak-RSS — OBSERVED / COMPLETE

Pinned Siax model, synthetic float32 RGB input, one thread, each size isolated in a child process:

| Model input | Cell | max RSS | Forward wall |
|---|---|---:|---:|
| 144×144 | 128/8 | **663.67 MiB** | 9.263 s |
| 160×160 | 128/16 | **725.57 MiB** | 10.022 s |
| 288×288 | 256/16 | **1,473.67 MiB** | 39.235 s |
| 320×320 | 256/32 | **1,664.96 MiB** | 44.464 s |

The isolated 320×320 forward **completed** on the 1.9 GiB host. Each size was subprocess-isolated, so a child failure would not take down the parent. The 7168×4032 uint8 canvas was measured at approximately 82.69 MiB.

**Interpretation:** a 320×320 pinned-Siax forward can run in isolation, but its approximately 1.66 GiB high-water mark leaves little headroom on a 1.9 GiB machine. This supports the memory-pressure hypothesis for the earlier full-job OOM. It does not identify the exact stage of that historical full-job kill, because the profile used synthetic input and did not replay the full BASE job.

The goal was to measure the risk without destroying the host. That goal was met. No further full 256/32 OOM replay is required for P0.

Evidence: `docs/evidence/S2_1_RAM_PROFILE.json`.

## 2. SPM-A fixed 48 probes — OBSERVED / COMPLETE

- Fixed bank: 48 probes × 48×64 BASE pixels.
- Bank SHA-256: `1267b78b1b957cb16057b978e2aabe720a5e1d69712eb6edcec8636aa7837af9`.
- Real pinned-Siax crop output compared with Lanczos baseline.

| Metric | Value |
|---|---:|
| Residual MAE p50 | **3.8869** |
| Residual MAE p95 | **6.6636** |
| Residual HF p50 | **6.3790** |
| Residual HF p95 | **10.6339** |

This completes the fixed reference fingerprint bank for BASE e283. It is a diagnostic fingerprint, not a standalone identity, topology or whole-frame quality acceptance.

Evidence: `docs/evidence/S2_1_PROBE_BANK_48.json`, `docs/evidence/S2_1_SPM_A_REPORT.json`.

## 3. Seam controls — OBSERVED / COMPLETE

Fixed sample fractions along seams, each seam sample paired with a same-row/column nearby non-seam control:

| Cell | Excess p50 | Excess p95 | Pairs |
|---|---:|---:|---:|
| 128/8 | **−0.0339** | 4.604 | 160 |
| 128/16 | **≈0.0000** | 5.146 | 160 |
| 256/16 | **0.4531** | 6.867 | 72 |

Within each cell, these are observed seam-vs-control diagnostics. The values indicate little median seam excess for 128/8 and 128/16, with a somewhat higher median for 256/16.

**Comparability caveat:** the historical P0 runner used tile-dependent control offsets (256, 288 and 512 output pixels respectively). Thus the p50 order is a directional diagnostic, not a strict same-distance cross-cell ranking. The later tool update supports a common BASE-space offset; regenerating all three reports is an optional evidence refinement, not a reason to re-open P0 or run another OOM test.

Evidence: `docs/evidence/S2_1_SEAM_128_8.json`, `docs/evidence/S2_1_SEAM_128_16.json`, `docs/evidence/S2_1_SEAM_256_16.json`.

## 4. P0 acceptance

| Requested P0 deliverable | Status |
|---|---|
| Isolated staged peak-RSS harness and four per-size forward measurements | **DONE_P0** |
| Fixed 48×64 SPM-A probe bank and real Siax residual fingerprint | **DONE_P0** |
| Seam-control diagnostics for 128/8, 128/16, 256/16 | **DONE_P0** |
| Full BASE 256/32 rerun / deliberate OOM | **NOT REQUIRED** |
| Exact attribution of the old full-job OOM stage | **UNKNOWN / outside P0 scope** |
| Overall Siax quality acceptance | **FALSE / separate gate** |

The full-image RAM profiler added later is an optional diagnostic only; it is not a P0 completion requirement and must not be run solely to change the P0 status.

## 5. Next phase

P0 is closed. Continue with P1 Nested Compute Tile, Virtual Master/native-child integrity, and quality re-acceptance. Use the measured small compute-core architecture; do not return to an unguarded 320×320 full-job memory stress test.

PR #7 evidence remains untouched. PR #8 remains Draft. No final acceptance is implied.
