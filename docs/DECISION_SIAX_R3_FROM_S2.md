# Decision: S2 OOM → SIAX R3 (not “more RAM”)

**asof:** 2026-11-01  
**base:** `463cce1`

## Decision

Escalate S2’s incomplete 256/32 cell into **architecture work** (Nested PEEP + Virtual Master + memory-aware runner + true SPM), not a host-RAM-only re-run as the primary strategy.

## Accepted facts

- PR #7 Draft HEAD `463cce1` holds R1 / S1-C / S2 partial evidence.
- 256/32 is **OOM_BLOCKED**, quality unknown.
- Current SPM-approx is diagnostic-only and method-biased across tile sizes.
- Worker already processes one filesystem tile at a time; stitch uint8 full frame is not the leading OOM hypothesis for this host size.

## Rejected shortcuts

- Calling Virtual Master an OOM silver bullet  
- Labeling nested compute “original 256/32 success” without RF equivalence  
- Averaging SPM + seam + identity into one score  
- Blind S1-C re-runs  
- Opening new SR-family PRs before Siax path honesty  

## Follow-on branch

`feat/siax-r3-nested-peep-vm-v0.1` — isolated Draft from `463cce1`.  
PR #7 remains the Siax core acceptance evidence surface.
