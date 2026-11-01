# S2.1 P0 — Current Evidence and Remaining Gates

**State:** partial implementation · **final_acceptance=false**  
**Branch:** `feat/siax-r3-nested-peep-vm-v0.1`  
**PR:** Draft #8 · based on frozen PR #7 evidence commit `463cce1`

## 1. What has actually run

### Synthetic single-forward baseline — OBSERVED

Pinned Siax model, one thread, synthetic float32 RGB input, each size isolated in a subprocess:

| Model input | S2 cell label | max RSS |
|---|---|---:|
| 144×144 | 128/8 | 663.67 MiB |
| 160×160 | 128/16 | 725.57 MiB |
| 288×288 | 256/16 | 1,473.67 MiB |
| 320×320 | 256/32 | 1,664.96 MiB |

The isolated 320×320 synthetic forward completed. This establishes a high memory envelope for the pinned model on that host. It does **not** reproduce the full Siax path with the real BASE tensor resident, every tile processed, the output canvas being populated, and PNG encoding. It does not prove the stage responsible for the earlier full-job OOM.

The full 256/32 job was **not** rerun in this P0. No new full-job OOM was intentionally triggered.

### Full-image staged profile tool — IMPLEMENTED, NOT RUN

`tools/ram_profile_siax.py` now invokes the actual `run_siax_upscale()` path in an isolated child process. `src/ige/upscale/siax.py` emits stage events for:

- model load
- input decode / BASE tensor preprocessing
- per-tile forward
- per-tile postprocessing
- output canvas allocation and core writes
- final PNG encode
- sidecar metadata write

It records child RSS and process high-water marks at stage boundaries, parent-side RSS samples, cgroup OOM counter changes when exposed, and separate CUDA allocation/reservation/peak-allocation data when using CUDA.

The profiler has an available-memory preflight, configurable reserve, optional tighter RSS ceiling, and timeout. A reported safety stop is **not** classified as OOM. Because RSS sampling is periodic and the first tile can have a short-lived transient peak, this is budget monitoring—not a hard real-time guarantee. Start with 128/8 and 128/16 on a constrained host. Do not start 256/16 or 256/32 on a small host merely because the synthetic test completed.

Example (operator must provide the actual BASE and checkpoint paths):

```bash
PYTHONPATH=src OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 TORCH_NUM_THREADS=1 \
python tools/ram_profile_siax.py \
  --input runs/fair_e283/BASE.jpg \
  --checkpoint models/4x_NMKD-Siax_200k.pth \
  --out runs/siax_validation_r2/S2_1/RAM_FULL_128_8.json \
  --tile-size 128 --tile-pad 8 --device cpu \
  --reserve-mib 512 --confirm-model-license-review
```

This command was added to the branch as a tool; it has **not** been executed by this GitHub integration against the HERE host. No machine-specific result is claimed.

## 2. SPM-A — OBSERVED reference probes, not cross-cell acceptance

A fixed 48-probe, 48×64 BASE-pixel bank was created. The SPM-A runner performs real pinned-Siax inference on each crop and measures its residual against Lanczos. The reference report records:

| Metric | Value |
|---|---:|
| residual MAE p50 | 3.887 |
| residual MAE p95 | 6.664 |
| residual HF p50 | 6.379 |
| residual HF p95 | 10.634 |

This is a real Siax probe fingerprint for the specified BASE. It is **not** a 128/8 vs 128/16 vs 256/16 comparison: the fixed bank has not yet been applied to each full-frame output and compared probe-by-probe. The tool now requires an explicit model-license review acknowledgement before inference.

## 3. Seam controls — historical values remain provisional

The first P0 seam runs used fixed along-seam sample fractions, but the non-seam control offset changed with tile size/pad:

| Cell | Historical control offset (output px) | Excess strip MAE p50 | p95 | Pairs |
|---|---:|---:|---:|---:|
| 128/8 | 256 | -0.0339 | 4.604 | 160 |
| 128/16 | 288 | 0.0000 | 5.146 | 160 |
| 256/16 | 512 | 0.4531 | 6.867 | 72 |

Therefore the historical order 128/8 → 128/16 → 256/16 is **provisional**, not a clean same-distance control comparison. The seam tool has been changed to use a common configurable offset in BASE pixels, record the candidate image SHA, and fail on dimension mismatch. The three evidence reports must be regenerated with the new same-offset method before cross-cell ranking.

Parallel pixel-line controls are still not semantic/material annotations. Natural edges can remain in both seam and control samples.

## 4. Correct status

| Work | Status |
|---|---|
| Synthetic per-size forward baseline | OBSERVED / complete |
| Real full-image staged RAM profiler | IMPLEMENTED / NOT RUN |
| Fixed 48×64 real Siax probe fingerprint | OBSERVED / reference bank only |
| Same-bank SPM-A comparison across 128/8, 128/16, 256/16 full outputs | NOT RUN |
| Common-offset seam script | IMPLEMENTED / old reports not regenerated |
| 256/32 full-job rerun | NOT RUN |
| OOM stage attribution for the old full job | UNKNOWN |
| Final Siax acceptance | FALSE |

## 5. Next execution order

1. On the actual HERE or GPU/RAM host, run full-image 128/8 and 128/16 profiles first with the reserve enabled.
2. Regenerate all seam reports using the same BASE-space control offset.
3. Apply the same SPM-A bank to the full-frame outputs and compare per-probe residual features.
4. Only attempt 256/16 or 256/32 after checking the target host's measured budget; 256/32 is not a default first run.
5. Then proceed to Nested Compute Tile receptive-field/equivalence work.

PR #7 evidence remains untouched. PR #8 remains Draft. No quality gate has been promoted.
