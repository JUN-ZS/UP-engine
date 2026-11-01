# S2 Tile/Halo · SPM-approx Results

**asof:** `2026-11-01T12:46:37Z` · **status:** `PARTIAL_3_OF_4_CELLS` · **final_acceptance:** false

## SPM logic (rough)

Legacy **SPM §0.12.39 SIAX 探針匹配** (probe 48×64 BASE) full stack = documented-only.

S2 approx: across-seam strip MAE · near-seam vs interior HF · rank = strip_mae + 10·max(0, ratio−1).

## Matrix

| Cell | OK | Wall (s) | Seam V/H mean | Strip MAE | HF ratio | Rank ↓ | SHA prefix |
| --- | --- | ---: | ---: | ---: | ---: | ---: | --- |
| 128x8 | yes | 0.0 | 4.528/4.991 | 4.792 | 1.090 | **5.693** | `3289e3e0…` |
| 128x16 | yes | 569.429 | 4.573/4.967 | 4.830 | 1.099 | **5.823** | `b7ea35b5…` |
| 256x16 | yes | 937.604 | 4.908/5.182 | 4.854 | 1.191 | **6.766** | `23990646…` |
| 256x32 | **OOM** | — | — | — | — | — | blocked 1.9Gi |

## Rank (ok cells only)

128x8 → 128x16 → 256x16

**Best by SPM-approx:** `128x8`

## Caveats

- 256/32 **OOM_BLOCKED** on this 1.9Gi host (single + distributed worker).
- Rank is diagnostic, not E6 acceptance.
- Human 400% blind still required before locking E3 config.
- Different tile/pad produce different SHAs by design.

## Next

- Optional: re-run 256/32 on larger RAM host
- E3 formal speed on chosen cell under S1-C thread budget
