# S3.5 Reliable Distributed Control

**asof:** `2026-11-01T16:00:39Z` · **status:** DONE (control-plane gate)  
**final_acceptance:** false · **e3_speed_claim:** false · **quality:** not in scope

## Bugs fixed (from S3.1–S3.4 prototype)

| Issue | Fix |
| --- | --- |
| Scheduler hint not binding | `assigned_worker` hard filter in `claim()` |
| No fencing | UUID `fencing_token` per claim attempt |
| Heartbeat only before/after forward | background `_HeartbeatThread` during `run_child` |
| Stale complete after requeue | `complete` requires live lease + matching token; else reject log |
| Unbounded retry | `max_attempts` → `dead/` letter |
| Shared `--device` | per-worker `device` in worker specs |

## Acceptance evidence

### Hard assignment fidelity
- 16 synthetic children · `w_fast` assigned 8 completed 8 · `w_slow` 8/8
- `assignment_mismatches: []` · pixel integrity ok
- `docs/evidence/S3_5_SYNTHETIC_HARD_ASSIGN.json`

### Fault inject
- claim → no heartbeat → expire requeue → new token
- stale token `complete` → **rejected** (`rejects_n >= 1`)
- live token → single final receipt
- `docs/evidence/S3_5_FAULT_INJECT.json`

### Unit tests
- `tests/test_s3_control_plane.py` (assignment block, stale complete, HB during long work, fidelity)

## Not yet
- S3.6 true dual-host (separate machines)
- S3.7 full 448 Siax distributed replay + Nested SHA compare

## PR note
PR #9 remains Draft; large cumulative diff vs main; do not merge as “S3 complete”.
