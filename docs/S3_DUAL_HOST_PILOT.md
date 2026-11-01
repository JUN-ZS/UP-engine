# S3.5 Dual-Host Pilot Protocol (optional · not auto-run)

**status:** DOCUMENTED_NOT_RUN  
**does not claim:** quality PASS · E3 speed · S2.1 decision flip

## Goal

Prove capability-aware multi-host Siax child execution + rebuild integrity on **shared job directory** (NFS/SMB) or pull-agent transport (future).

## Preconditions

1. Both hosts can read BASE + checkpoint with matching SHA-256.
2. Job root is a shared filesystem with atomic rename, **or** object-store transport is implemented.
3. Each host reports capability JSON (RAM/VRAM/model SHA/max_inflight).
4. S2.1 Nested quality remains INCONCLUSIVE; pilot uses a **new** job id.

## Procedure

```bash
# Host A — controller (once)
python tools/s3_multi_worker_sim.py \
  --job-dir /shared/s3_pilot_job \
  --base BASE.jpg \
  --mode siax \
  --region 0,0,256,256 \
  --compute-core 64 --compute-context 16 \
  --workers "gpu-a:cuda:24000,cpu-b:cpu:8000" \
  --confirm-model-license-review \
  --out-report docs/evidence/S3_DUAL_HOST_PILOT.json
```

For true dual-host, split into controller enqueue + per-host worker_loop processes (future CLI split). v0 sim runs multi-process on one machine as structural rehearsal.

## Pass criteria (pilot only)

| Check | Required |
| --- | --- |
| All assigned children have receipts | yes |
| Rebuild coverage complete | yes |
| Pixel match children ↔ primary | yes |
| Model SHA matches on both hosts | yes |
| quality_qualified | **false** (unless separate Same-SHA QC) |
| e3_speed_claim | **false** |

## Explicit non-goals

- Average-splitting tiles without capability scores  
- Treating pilot wall time as E3  
- Rewriting PR #8 quality decision  
