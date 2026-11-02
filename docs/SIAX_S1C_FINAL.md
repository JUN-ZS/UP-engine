# S1-C Final (controlled thread budget · 3 rounds)

**asof:** `2026-11-01T11:54:56Z` · **final_acceptance:** false  
**canonical:** `docs/evidence/S1C_FINAL_REPORT.json`

## Design
| Arm | Threads | Affinity |
|---|---|---|
| A single | 2 | 0,1 |
| B dual | 1+1 | 0 \| 1 |

Pilot R1 (uncontrolled dual 0.69×) **not** pooled.

## Wall inference

| Round | Single | Dual | Speedup |
|---:|---:|---:|---:|
| 1 | 699.272 | 548.238 | 1.275× |
| 2 | 687.336 | 555.686 | 1.237× |
| 3 | 697.072 | 550.116 | 1.267× |
| **median** | **697.072** | **550.116** | **1.267×** |

## Verdict
- Correctness: **PASS** (all SHA = master `3289e3e0…`)
- Same-host dual speed: **PASS** (median **1.267×** vs single under same N=2 budget)
- Siax final_acceptance: **not yet** → next **E2 S2** quality matrix

Finding: affinity-controlled dual fixes pilot oversubscription. Do not re-run S1 blindly; go S2 next.
