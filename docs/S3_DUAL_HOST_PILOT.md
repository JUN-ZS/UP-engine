# S3.6 Dual-Host / Dual-Agent Pilot

**status:** INTERFACE_DONE · RECOVERY_DONE · PHYSICAL_DUAL_HOST=NOT_RUN  
**requires:** S3.5 control plane  
**does not claim:** quality PASS · E3 · S2.1 flip

## What was proven on this runner

| Capability | Evidence |
| --- | --- |
| Separate Controller (no inference) | `JobController` + `tools/s3_controller.py` |
| Separate Worker Agent | `tools/s3_worker_agent.py` + registry heartbeat |
| Hard assignment + fencing | S3.5 + S3.6 happy |
| Kill worker → expire → reassign → single rebuild | `docs/evidence/S3_6_DUAL_AGENT_KILL_A.json` |
| Happy dual-agent rebuild + pixel match | `docs/evidence/S3_6_DUAL_AGENT_HAPPY.json` |

## Physical two-host procedure (when second machine available)

```bash
# Shared FS mount both hosts can rename on, e.g. /shared/s3_job

# Host A — controller
python tools/s3_controller.py init --job-dir /shared/s3_job --base BASE.jpg \
  --mode siax --region 0,0,256,256 --compute-core 64 --compute-context 32 \
  --lease-seconds 60

# Host A — worker (optional GPU)
python tools/s3_worker_agent.py --job-dir /shared/s3_job --worker-id hostA_gpu \
  --mode siax --device cuda --ram-mib 24000 --throughput-est 40 \
  --confirm-model-license-review

# Host B — worker (CPU or GPU)
python tools/s3_worker_agent.py --job-dir /shared/s3_job --worker-id hostB_cpu \
  --mode siax --device cpu --ram-mib 8000 --throughput-est 6 \
  --confirm-model-license-review

# Host A — schedule after both registries live
python tools/s3_controller.py schedule --job-dir /shared/s3_job --wait-workers 2
python tools/s3_controller.py wait --job-dir /shared/s3_job --timeout-s 7200 --reassign-every-s 5
python tools/s3_controller.py rebuild --job-dir /shared/s3_job
```

Pass criteria: all children receipted · pixel integrity · model SHA match · quality_qualified=false · e3=false.

## Explicit honesty

This CI/runner environment is **one machine**. Dual-agent processes/threads prove the control plane.  
**True multi-host** requires two physical machines + shared FS (or future object store transport).
