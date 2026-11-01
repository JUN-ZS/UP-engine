# S3 — Heterogeneous Upscale Execution Engine

**asof:** 2026-11-01  
**branch:** `feat/upscale-s3-heterogeneous-runner-v0.1`  
**relation to S2.1 / PR #8:** isolated follow-on · **does not rewrite** S2.1 quality decision  
**final_acceptance:** false · **not** E3 speed qualification

## Why S3 (not more S2.1)

S2.1 delivered a **SHA-locked, 448-child pixel-traceable** 4× candidate under RAM limits, with:

- Integrity **PASS**
- Quality **INCONCLUSIVE** (frozen)

The next *architectural* problem is different:

> How does one large image job automatically assign work across machines with different RAM / VRAM / throughput, and still rebuild a **verifiable** full output?

That is more valuable than micro-optimizing a single host.

## Non-goals (hard)

| Non-goal | Why |
| --- | --- |
| Flip INCONCLUSIVE → PASS | Only same-SHA human QC (workstream B) |
| Claim E3 speed from S3 prototypes | Speed gate is separate and quality-qualified only |
| Average-split 448 tiles as “optimization” | Ignores load, model load cost, transfer latency |
| Collapse models into one score | Siax ≠ SUPIR ≠ others; no cross-model vanity rank |
| Require shared NFS for all deployments | Transport is pluggable |

## Architecture (four layers)

```
┌──────────────────────────────────────────────────────────┐
│ Job Controller                                            │
│  image · model adapter · tile/context policy · QC policy  │
└───────────────┬──────────────────────────────────────────┘
                │ capability-aware plan
    ┌───────────┼────────────┬─────────────────┐
    ▼           ▼            ▼                 ▼
 Local      FIT Runner   Other Workers    (future)
 CPU/GPU    remote GPU   pluggable hosts
    │           │            │
    └───────────┴────────────┘
                │ native child artifacts
                ▼
┌──────────────────────────────────────────────────────────┐
│ Artifact & Verification Layer                             │
│  child_id · input SHA · model SHA · output SHA · boxes    │
│  coverage · no-overlap · Virtual Master · optional primary│
└──────────────────────────────────────────────────────────┘
```

### Three mechanisms (do not merge)

| Module | Problem |
| --- | --- |
| **Capability Scheduler** | Assign work from live \(RAM_i, VRAM_i, Throughput_i, Queue_i, Model_i\) |
| **Reliable Job Transport** | Shared FS **or** object store **or** pull-agent; lease · heartbeat · retry · resume |
| **Artifact Integrity** | Stable child IDs + SHAs + coords + rebuild proof (S2.1 strict integrity pattern) |

\[
Worker_i = f(RAM_i,\ VRAM_i,\ Throughput_i,\ Queue_i,\ Model_i)
\]

### Unified Upscale Engine Adapter

Scheduler **must not** know model internals.

| Adapter contract | Meaning |
| --- | --- |
| `model_id` + weight SHA | Exact binary identity |
| `capability_profile` | max safe core, context, dtype, device kinds |
| `run_child(spec) → native PNG + receipt` | One forward unit |
| `receipt` | input_box, core_box, output_box, SHAs, wall_s, peak RSS/VRAM if known |

- **Siax** is the first adapter (ESRGAN 4×, existing nested/distributed code).
- Future SUPIR / other families plug in with their own tile/context/VRAM needs.
- **Virtual Master** normalizes native children into a rebuildable asset graph.

License, quality, and cross-model non-comparability remain **hard boundaries**.

## Relation to PR #7 distributed runner

PR #7 already has: `plan` · `claim/rename worker` · `stitch` on a **filesystem tile queue**.

S3 **extends** that into:

1. Capability registration (not anonymous workers)
2. Lease + heartbeat + requeue
3. Pluggable transport (FS is one backend)
4. Model adapter boundary
5. Virtual Master + strict integrity as default rebuild path

## Acceptance boundaries

| Claim | When allowed |
| --- | --- |
| Synthetic dispatch/retry/dedupe/resume works | S3 unit/integration tests |
| Multi-host Siax rebuild SHA-stable | Measured pilot, still `final_acceptance=false` |
| E3 speed | Only quality-qualified cells, separate protocol |
| Quality PASS for Nested SHA | Same-SHA QC only — **not** S3 |

## First slices (implementation order)

1. Schemas: worker capability · job · child receipt · adapter descriptor  
2. In-process / FS transport with lease+heartbeat (upgrade of PR #7 claim)  
3. Capability scheduler (greedy by remaining budget + throughput estimate)  
4. Siax adapter wrapping existing nested/distributed forward  
5. Rebuild via Virtual Master + `s2_nested_integrity` pixel equality  
6. Synthetic multi-worker simulation before real dual-host pilot  

Status: **architecture lock for S3**. Implementation starts on this branch only.
