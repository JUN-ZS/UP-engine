# S3.1–S3.4 Results

**asof:** `2026-11-01T15:45:53Z` · **branch:** `feat/upscale-s3-heterogeneous-runner-v0.1`  
**final_acceptance:** false · **e3_speed_claim:** false · **quality_qualified:** false

## Delivered

| Step | Status | Evidence |
| --- | --- | --- |
| S3.0 schemas + architecture | DONE | `docs/S3_HETEROGENEOUS_UPSCALE_ENGINE.md` |
| S3.1 FS lease / heartbeat / expire / fail | DONE | `src/ige/upscale/s3/transport_fs.py` + unit tests |
| S3.2 capability scheduler | DONE | `scheduler.py` / `capability.py` |
| S3.3 Siax adapter wired | DONE | `adapter_siax.py` real forward + receipt |
| S3.4 multi-worker sim | DONE | synthetic 16-child + Siax mini 4-child |
| S3.5 dual-host pilot | DOCUMENTED_NOT_RUN | `docs/S3_DUAL_HOST_PILOT.md` |

## Observed runs

### Synthetic multi-worker (16 children · 256×256 region · nearest 4×)

- workers: `w_fast` 9 · `w_slow` 7
- pending 0 · failed 0
- rebuild 1024×1024 · pixel match **ok**
- SHA: `72b562cea6041c52…`
- evidence: `docs/evidence/S3_SIM_SYNTHETIC_MULTI_WORKER.json`

### Siax mini multi-worker (4 children · 128×128 region · real model)

- workers: `w1` 2 · `w2` 2 (true dual process)
- rebuild 512×512 · pixel match **ok**
- SHA: `28c5751a483a3166…`
- evidence: `docs/evidence/S3_SIM_SIAX_MINI_MULTI_WORKER.json`
- **not** Nested full-frame quality · **not** E3

## Boundaries (unchanged)

- PR #8 / S2.1 quality remains **INCONCLUSIVE**
- S3 does not flip that decision
- Dual-host pilot is optional and separate

## Code entry points

- `tools/s3_multi_worker_sim.py`
- `src/ige/upscale/s3/`
- `tests/test_s3_scheduler_transport.py`
