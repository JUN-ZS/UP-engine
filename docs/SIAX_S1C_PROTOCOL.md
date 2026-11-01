# S1-C Controlled Thread-Budget Fair Compare

**asof:** `2026-11-01T11:54:56Z`  
**status:** **COMPLETE** (3 rounds) · evidence `docs/evidence/S1C_FINAL_REPORT.json`  
**host:** 2 logical CPUs (Xeon Platinum 8481C KVM) · N=2  
**order:** Pilot R1 (uncontrolled) ≠ S1-C median. Do not pool R1 into S1-C.

## Why R1 dual was slow

Uncontrolled: each worker may use all torch/OMP threads → 2× full-CPU model instances on **2 cores** → oversubscription.  
Hypothesis (supported by S1-C, not sole cause proven): thread contention + dual model instances on shared cores.

## S1-C design

| Arm | Threads | Affinity | Model instances | Tiles |
| --- | --- | --- | --- | --- |
| A single | N=2 | CPU 0,1 | 1 | 112 |
| B dual | N/2=1 each | A: CPU0 · B: CPU1 | 2 | 56+56 |

Fixed: BASE e283 · ckpt SHA 560424d9… · tile 128/8 · same torch/spandrel.

**3 rounds**, alternate order: R1 A→B, R2 B→A, R3 A→B.

Metrics recorded: inference wall, stitch, peak RSS (children max), threads, affinity, output SHA.  
Gaps: model load not split; CPU util % not sampled; dual RSS not summed.

Success **speed**: median dual wall < median single wall under same total thread budget → **PASS 1.267×**.  
Success **correctness**: output SHA == R1 master → **PASS**.

## Pass/fail separation

- Correctness PASS + speed FAIL is a valid outcome (keep single-process multi-thread; multi-host separate).
- Pilot uncontrolled FAIL does not invalidate controlled dual.
- S1-C does **not** re-open for blind re-runs; next is **E2 S2** quality matrix, then **E3** final perf on chosen tile/halo.
