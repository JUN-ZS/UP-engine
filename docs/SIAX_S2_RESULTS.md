# S2 · Tile/Halo SPM-approx Results

**asof:** `2026-11-01T13:57:30Z` · **final_acceptance:** false

## Host constraint

- Free/`nproc` host shows ~1.9Gi RAM, but **cgroup memory.max ≈ 1.02GiB**
- True 256/32 window (≤320²) fp16 peak ~1.25GiB → **OOM** on this host
- 256/32 **not** quality-ranked (incomplete)

## SPM-approx table (lower rank better)

| Cell | strip MAE | p95 | HF ratio | interior HF | rank | wall_s | notes |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| 128x8 | 4.7923 | 9.5944 | 1.0901 | 6.7 | **5.6929** | None | reuse_S1C_r1_single_master |
| 128x16 | 4.8297 | 9.5525 | 1.0993 | 6.7894 | **5.8229** | 569.429 | single_process_upscale_siax |
| 256x16 | 4.854 | 9.0073 | 1.1912 | 6.7115 | **6.7662** | 937.604 | single_process_1thread_fullframe |
| 256x32 | — | — | — | — | n/a | — | OOM / incomplete on cgroup 1.02GiB |

## Ranking

1. **128x8** rank=5.6929
2. **128x16** rank=5.8229
3. **256x16** rank=6.7662

## Verdict

- Prefer **128x8** as E3 formal timing config among completed cells
- 128/16 does **not** beat 128/8 on SPM-approx
- 256/16 worse seam metrics → do not pick for quality
- 256/32 needs ≥~1.5GiB cgroup headroom (or nested compute executor) — **not** a model reject
- Still **not** final_acceptance; no identity/topology claim

## Next

E3 · re-time single vs dual under S1-C affinity using recommended tile/halo
