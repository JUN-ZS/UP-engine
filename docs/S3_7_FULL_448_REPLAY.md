# S3.7 Full 448-child Siax Distributed Replay (planned)

**status:** TODO · **gates:** S3.5 DONE · S3.6 dual-host pilot recommended first  
**not quality PASS · not E3**

## Fixed parameters

| Param | Value |
| --- | --- |
| BASE | 1792×1008 (`runs/fair_e283/BASE.jpg`) |
| compute_core | 64 |
| compute_context | 32 |
| children | 448 |
| scale | 4× |
| output | 7168×4032 |

## Required checks

1. 448 receipts with fencing tokens
2. assigned_worker == completer worker_id
3. coverage complete · no overlap
4. pixel equality children ↔ primary
5. Optional: compare each child SHA vs S2.1 Nested store; if identical → engine replay proven; if not → keep difference report, **do not overwrite** S2.1 evidence

## Explicit non-claims

- Does not flip S2.1 Quality INCONCLUSIVE
- Does not claim E3 speed
- Dual-host success ≠ image quality PASS
