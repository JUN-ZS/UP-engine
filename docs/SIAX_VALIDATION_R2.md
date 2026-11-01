# SIAX VALIDATION R2

**asof:** `2026-10-31T23:58:42Z`  
**order lock:** finish Siax quality+perf acceptance before other models / PR#8.

## Principle

Distributed Siax success ≠ HD generation success.  
Siax = one divisible **CNN/GAN SR executor** under UP-engine. Generative re-detail, ROI hybrid, identity lock, Virtual Master remain separate.

## R1 (HERE) — PASS candidate_only

| Item | Result |
| --- | --- |
| BASE | e283276e… |
| Checkpoint SHA | MATCH `560424d9…` |
| Tiles | 112 (128/8) |
| Workers | 2×CPU · 56+56 |
| Out | 7168×4032 · 42995025 B |
| vs Single A | **byte-identical** SHA `3289e3e0…` |
| final_acceptance | **false** |

Proved: real weights · disjoint multi-worker · stitch · pixel-reproducible vs single A.  
Not proved: speedup · tile matrix · CPU/GPU mix · multi-host.

## R2 order

1. **S1** single-machine fair timing (1 vs 2 CPU workers × 3 rounds, median)
2. **S2** tile/halo quality matrix 128/8 · 128/16 · 256/16 · 256/32
3. **S3** CPU/GPU mix + quantitative delta (when GPU available)
4. **S4** multi-host only after lease/heartbeat/reclaim

## Engineering gate before S4

SIGKILL can leave `in_progress`; need lease + heartbeat + expire reclaim + no double-complete.

## Do not

- Open PR#8 for other SR families before S1–S2 (min) complete
- Equate Siax distributed PASS with SET creation / identity gold
