# N1.gen v2 — Neighbor-Conditioned Continuation

| | |
| --- | --- |
| **Status** | `CHARTER + tools` |
| **Baseline** | Dual independent gen seam **FAIL** (`N1_GEN_DUAL_HERE.json`, pair #12) |
| **Goal** | B must **continue A**, not re-compose from BASE alone |

## Labels

| Label | |
| --- | --- |
| N1_GEN_PILOT_OK | **limited** — dual fill+stitch only (v1) |
| N1_SEAM_CONTINUITY_OK | FAIL until v2 proves edge continuity |
| NATIVE_4K_PILOT_OK | not run |

## Protocol

1. Generate **A** once; freeze SHA. Do **not** independently re-roll A when testing B.
2. Extract A’s **right overlap strip** (width = plan.overlap) as **continuation anchor** (immutable in B’s left band).
3. Generate **B** as outpaint / masked continuation: left band locked from A, right is free; global ref + scene lock still allowed.
4. Stitch with `--require-tiles A,B` + `--run-id`; compare seam vs v1 baseline.

## Alt mechanism

If masked continuation weak: generate **one joint A∪B wide plate**, then crop into two exact boxes (same capture → natural seam). Record as `mechanism=joint_plate`.

## Non-goals

- Re-tuning overlap alone  
- Re-running independent A/B as “fix”  
- 45-tile full frame  
- Calling limited pilot full native-res gen success  
