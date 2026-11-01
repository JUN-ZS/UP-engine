# S1-C Results (controlled thread budget)

**asof:** 2026-11-01T11:54:56Z  
**host:** N=2 CPUs (Xeon Platinum 8481C KVM)  
**canonical report:** `docs/evidence/S1C_FINAL_REPORT.json`

## Design

| Arm | Threads | Affinity |
| --- | --- | --- |
| Single | 2 | 0,1 |
| Dual | 1+1 | 0 \| 1 |

Pilot R1 uncontrolled dual (0.694×) is **not** pooled into this median.

**Wall inference** = harness wall around worker process(es).  
**Do not** use `workers[].runtime_seconds` as dual wall — that field is per-worker tile-sum CPU time (e.g. R3 dual-a ≈421s), not parallel wall.

## Wall inference (s)

| Round | Order | Single | Dual | Speedup |
| --- | --- | --- | --- | --- |
| 1 | A→B | 699.272 | 548.238 | 1.275× |
| 2 | B→A | 687.336 | 555.686 | 1.237× |
| 3 | A→B | 697.072 | 550.116 | 1.267× |
| **median** | | **697.072** | **550.116** | **1.267×** |

All 6 arms **SHA-identical** to master `3289e3e0…fd181`.

## Also recorded

| Metric | Single (range) | Dual (range) |
| --- | --- | --- |
| Stitch wall s | 19.5–19.8 | 18.9–19.1 |
| Peak RSS children MB | 666–706 | 667–707 |
| Threads / affinity | enforced via OMP + taskset | enforced |

## Measurement gaps (honest)

- **Model load** not split from inference wall (included in `wall_inference_s`).
- **CPU utilization %** not sampled (affinity + thread caps only).
- **Dual peak RSS** is max(children), not sum of both workers — total RAM cost understated.
- No TORCH_NUM_THREADS explicit pin beyond OMP/MKL env (torch may still default).

## Conclusion

| Gate | Result |
| --- | --- |
| Correctness (byte SHA) | **PASS** |
| Same-host dual speed under fixed N=2 budget | **PASS** (median **1.267×**) |
| Uncontrolled same-host dual (pilot) | **FAIL** (0.694×) — oversubscription |
| `final_acceptance` | **false** |

Finding: affinity/thread budget is **required** for same-host multi-worker; without it dual is slower, not faster.

Next: **E2 / S2** tile/halo quality matrix (not S1 re-runs).
