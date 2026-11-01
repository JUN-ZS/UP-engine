# S2.1 P1 Status — Nested Compute + Virtual Master

**asof:** `2026-11-01T15:03:49Z` · **P0:** DONE · **final_acceptance:** false

## Scope (locked)

- Do **not** re-run original 256/32 OOM as work item.
- Nested cell is a **new experimental cell**, not “256/32 recovered”.
- Runner remote orchestration is a **separate later phase** (PR #7 FS queue already exists).

## Cell

| Field | Value |
| --- | --- |
| cell_id | `nested_L256/32_C64/ctx32` |
| logical | core 256 · halo 32 |
| compute | core 64 · context 32 (RF rec 24, conservative) |
| isolation | inprocess + resume driver |
| children | **448** |
| peak RSS | **663.79 MiB** |
| primary PNG | 7168×4032 · 43 281 047 B |
| SHA256 | `5b7ca844e72b64e6c9e9fff5bf1f74e450b4c518003b096cd77bc2c8fa632656` |
| strip finalizer | uint8 canvas · preview never primary · dim/size asserts OK |
| Virtual Master | `vm_nested_L256_32_C64_ctx32` · 448 native children |

## Evidence

- `docs/evidence/S2_1_P1_NESTED_FULL_SUMMARY.json`
- `docs/evidence/S2_1_RF_MEASURE_c64.json`
- run dir: `runs/siax_validation_r2/S2_1/p1/nested_L256_32_C64_ctx32/`

## Explicit non-claims

- Not single-forward 256/32 success
- Not quality-qualified (SPM-A / seam / continuity pending S2.1.5)
- Not final_acceptance

## Optional bonus (not a gate)

Full-image 128/8 stage profile completed on HERE after P0 closed:
peak RSS **741.3 MiB** @ `tile_forward`; output SHA `3289e3e0…`.  
Recorded only as optional envelope data — **not** P0 completion criterion, **not** 256/32 OOM replay.

## Next

1. S2.1.5 quality reaccept on **this nested cell only** (SPM-A fixed probes + seam bank + continuity).
2. Optionally resume dual-host FS worker pilot (PR #7) as **separate** phase — not mixed into quality gate.
