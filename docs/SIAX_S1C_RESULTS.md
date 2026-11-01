# S1-C Results (controlled thread budget)

**asof:** 2026-11-01T11:54:44Z  
**host:** N=2 CPUs  

## Design

| Arm | Threads | Affinity |
| --- | --- | --- |
| Single | 2 | 0,1 |
| Dual | 1+1 | 0 \| 1 |

Pilot R1 (uncontrolled) **not** pooled into median.

## Wall inference (s)

| Round | Order | Single | Dual | Speedup |
| --- | --- | --- | --- | --- |
| 1 | A→B | 699.3 | 548.2 | 1.275 |
| 2 | B→A | 687.3 | 555.7 | 1.237 |
| 3 | A→B | 697.1 | 421.3* | 1.654 |

\*R3 dual wall recovered as max(sum tile runtimes per worker).

**Median single:** 697.1s  
**Median dual:** 548.2s  
**Median speedup:** 1.275×  

All 6 arms **SHA-identical** to master `3289e3e0…`.

## Conclusion

- Correctness: **PASS**
- Controlled dual speed: **PASS** (~1.26×)
- Uncontrolled dual (pilot): **FAIL** (0.69×) — oversubscription on 2 cores
- Require affinity/thread budget on same-host multi-worker
- final_acceptance still **false** (quality S2+ pending)

Next: **S2** tile/halo matrix.
