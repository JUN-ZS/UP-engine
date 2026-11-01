# S1-C Controlled Thread-Budget Fair Compare

**asof:** `2026-11-01T10:31:28Z`  
**host:** 2 logical CPUs (Xeon Platinum 8481C KVM) · N=2  
**order:** Pilot R1 (uncontrolled) ≠ S1-C median. Do not pool R1 into S1-C.

## Why R1 dual was slow

Uncontrolled: each worker may use all torch/OMP threads → 2× full-CPU model instances on **2 cores** → oversubscription.  
Hypothesis (not yet proven as sole cause): thread contention + 2× model RSS.

## S1-C design

| Arm | Threads | Affinity | Model instances | Tiles |
| --- | --- | --- | --- | --- |
| A single | N=2 | CPU 0,1 | 1 | 112 |
| B dual | N/2=1 each | A: CPU0 · B: CPU1 | 2 | 56+56 |

Fixed: BASE e283 · ckpt SHA 560424d9… · tile 128/8 · same torch/spandrel.

**3 rounds**, alternate order: R1 A→B, R2 B→A, R3 A→B.

Metrics per arm: load+inference wall, stitch, peak RSS, threads, affinity, output SHA.

Success criteria for **speed**: median dual wall < median single wall under same total thread budget.  
Success for **correctness**: output SHA == R1 master (or documented tolerance).

## Pass/fail separation

- Correctness PASS + speed FAIL is a valid outcome (keep single-process multi-thread; multi-host separate).
