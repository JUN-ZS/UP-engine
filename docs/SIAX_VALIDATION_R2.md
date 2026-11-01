# SIAX VALIDATION R2 — Locked Order

**asof:** `2026-11-01T18:30:00Z`  
**order lock:** Siax to real acceptance before other models / PR#8.  
**PR:** [#7](https://github.com/JUN-ZS/UP-engine/pull/7) · branch `feat/siax-distributed-runner-v0.1`

## Principle

```
正確性 ≠ 速度 ≠ 影像品質
每一輪只回答一個明確問題，不混成一個 PASS。
Distributed Siax success ≠ HD generation / identity / topology gold.
```

Siax = one divisible **CNN/GAN SR executor** (L2) under UP-engine.  
L3 schedule plane is shared; other models get Adapters later — **not now**.

## R1 finding (pilot · uncontrolled)

| 指標 | 單 Worker | 雙 Worker |
| --- | ---: | ---: |
| Tiles | 112 | 56+56 |
| Inference wall | 451.3s | 650s |
| Stitch | 7.3s | 20.8s |
| Output SHA | same | same |
| Speedup | — | **0.694×** (slower) |

- **Correctness: PASS** (byte-identical to single A, SHA `3289e3e0…`)
- **Performance: FAIL** on this same-host uncontrolled config
- Uncontrolled variable: each worker may take full CPU thread budget → oversubscription on N=2
- Pilot is **not** pooled into S1-C median

Stamp: `docs/SIAX_R1_HERE_RUN_STAMP.json`

## Locked roadmap (E0 → E6)

| Phase | Question | Status |
| --- | --- | --- |
| **E0** Evidence Lock | R1 stamp + BASE/ckpt/SHA + docs on PR branch | **DONE** |
| **E1** S1-C perf | Same total thread budget: single N vs dual N/2+N/2 · 3 rounds · median | **DONE** (PASS speed 1.267×) |
| **E2** S2 quality | Tile/halo matrix 128/8 · 128/16 · 256/16 · 256/32 · SPM-approx | **PARTIAL** (3/4; 256/32 OOM 1.9Gi) |
| **E3** S1 Final perf | Re-time on S2-chosen tile/halo (formal speed number) | PENDING |
| **E4** S3 CPU/GPU | cpu / gpu / mix · SHA or MAE/max/PSNR + visual | BLOCKED_NO_GPU |
| **E5** S4 multi-host | lease/heartbeat/reclaim/retry first · then shared FS · then object store | BLOCKED_NEEDS_LEASE |
| **E6** Siax Final Acceptance | unified gates; still ≠ identity/topology/generative gold | NOT YET |

### E1 result (S1-C) — short

| | Single | Dual |
| --- | ---: | ---: |
| Median wall inference | 697.072s | 550.116s |
| Median pair speedup | | **1.267×** |
| SHA | master | master |

- Affinity + thread split **required** on same-host multi-worker
- Gaps: model_load not split; CPU util % not sampled; dual RSS = max(children) not sum
- Evidence: `docs/evidence/S1C_*.json` · `docs/SIAX_S1C_FINAL.md`

### E2 (S2) design lock

| Tile / Pad | Role |
| --- | --- |
| 128/8 | original baseline |
| 128/16 | more context |
| 256/16 | larger core |
| 256/32 | large core + large context |

Per cell: single-worker reference + distributed output, SHA or quantified delta.  
Accept on 400% detail, seams, gold-line continuity, repeat texture, naturalness.  
**Do not** judge by seam mean alone — compare near-seam vs similar non-seam, plus blind review.


### E2 (S2) result — short

| Cell | SPM rank score ↓ | Notes |
| --- | ---: | --- |
| 128/8 | **5.693** | best of completed; reuses S1-C master |
| 128/16 | 5.823 | more pad, slightly higher strip/HF |
| 256/16 | 6.766 | worse near-seam HF ratio on this BASE |
| 256/32 | — | **OOM_BLOCKED** on 1.9Gi host |

- SPM = rough §0.12.39 probe logic only (48×64 BASE probes) · not full residual peep
- **Candidate for E3:** 128/8 (still needs human 400% blind)
- Evidence: `docs/SIAX_S2_RESULTS.md` · `docs/evidence/S2_SUMMARY.json`

### E3

Only after S2 picks a quality-qualified tile/halo — re-run controlled timing. That number is the formal same-host speed claim.

### E4–E5

- GPU when available; bit-identical not required if precision differs — record MAE / max / PSNR / visual
- Multi-host only after: lease · heartbeat · expired reclaim · max retry · no double-complete · disconnect recovery

### E6 gates (all required)

1. BASE + model + output SHA  
2. Full tile coverage, no missing/dup work  
3. Seam + 400% human blind  
4. Real speedup magnitude (E3)  
5. RAM / VRAM / compute cost  
6. Lossless 4× master + full record  

`final_acceptance=false` until E6. Siax executor PASS ≠ person identity / costume topology / generative micro-detail PASS.

## Architecture boundary (post-Siax)

| Layer | Duty |
| --- | --- |
| L1 | Upscale method family (CNN/GAN, Transformer, Diffusion, Ref-guided) |
| L2 | Executor adapters (Siax, SUPIR, Real-ESRGAN, …) |
| L3 | Schedule plane (CPU/GPU, local/remote workers) — **this PR** |
| L4 | Reconstruct (PEEP, Dense Warp, Virtual Master) |
| L5 | Quality accept (identity, topology, detail, fusion) |

Each future model only needs its Adapter to share L3.  
Siax result = **SR baseline**, not the answer to all detail-generation problems.

## Do not

- Open PR#8 / add new SR families before E2 min (+ E6 for “Siax runner complete”)
- Pool pilot R1 into S1-C median
- Claim final_acceptance, identity/topology, or uncontrolled dual speedup
- Blind re-run S1 when design is already answered
