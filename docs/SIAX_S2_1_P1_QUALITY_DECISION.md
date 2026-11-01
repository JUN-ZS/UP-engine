# S2.1.5 Quality Decision — Nested cell closeout

**asof:** `2026-11-01T15:25:28Z`  
**cell_id:** `nested_L256/32_C64/ctx32`  
**primary SHA-256:** `5b7ca844e72b64e6c9e9fff5bf1f74e450b4c518003b096cd77bc2c8fa632656`

## Formal decision

| Gate | Result |
| --- | --- |
| **Integrity** | **PASS** |
| **Quality (quality_qualified)** | **INCONCLUSIVE** |
| **final_acceptance** | **false** |
| original 256/32 single-forward | **NOT claimed** |

## Why Integrity = PASS

Strict checker (`tools/s2_nested_integrity.py`):

- required child fields including **sha256** (fail-closed if missing)
- 448/448 file SHA match
- complete coverage, no overlap
- **pixel equality**: each child PNG == primary crop at `output_box_hires`
- evidence: `docs/evidence/S2_1_P1_NESTED_INTEGRITY_STRICT.json`

This closes the gap: children are proven composition of this primary, not only geometric cover.

## Why Quality = INCONCLUSIVE

1. **SPM-A** candidate residuals observed (p50≈4.0) but MAE vs Lanczos ≠ true-detail verdict; p09/p13 remain review interest, not auto-fail.
2. **Seam** total excess p50 negative, but **vertical p95 still elevated**; ranked samples recorded with coordinates (no longer summary-only).
3. **400% blind** on 20 anonymous crops: no FAIL-level wrong texture / hard contour destruction found; **mild fabric continuity shifts** at some high-excess vertical seams.
4. Review is **sampled**, not exhaustive full-frame human production QC.

Therefore: usable **integrity-locked candidate**, **not** `quality_qualified`.

## What we stop doing

- No more S2.1.5 metric expansion
- No 128/16 bonus, no RAM OOM replay, no Runner dual-host in this phase
- E3 speed only after a future **PASS** on quality

## Reopen condition

Only human full-frame / expanded 400% on **this same SHA** may upgrade decision to **PASS** or **FAIL**. Do not regenerate a different PNG and rebind.
