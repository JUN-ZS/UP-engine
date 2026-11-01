# S2 · Tile/Halo Quality Matrix (SPM-approx)

**asof:** 2026-11-01  
**phase:** E2  
**final_acceptance:** false

## Question

Which of {128/8, 128/16, 256/16, 256/32} is quality-qualified enough to become the formal E3 timing config?

## SPM logic (rough · not full import)

Legacy **SPM §0.12.39 = SIAX 探針匹配** (default probe 48×64 on BASE) remains documented-only full stack.  
S2 uses **SPM-approx diagnostics only**:

| Probe | Meaning |
| --- | --- |
| Across-seam 1px strip MAE | boundary jump |
| Near-seam band HF (Laplacian energy) | residual energy on seam band |
| Interior HF | same energy away from seams |
| Ratio near/interior | ~1 preferred; not sole gate |
| Rank score | strip_mae + 10·max(0, ratio−1) · lower better · diagnostic |

**Not** full residual peep match · **not** SWP · **not** identity/topology.

Also report classic stitcher seam mean (diagnostic).

## Per cell

1. Single-process `upscale-siax` with that tile/pad (quality reference)  
2. SPM-approx diag on 4× PNG  
3. Optional later: distributed arm SHA check vs single  

128/8 reuses S1-C master SHA `3289e3e0…` (already proven).

## Accept (soft ranking)

- Prefer low strip MAE **and** HF ratio near 1 without killing interior detail  
- Human 400% blind still required before E6  
- Do **not** pick by seam mean alone  

## Next

E3 formal speed on the chosen tile/halo under S1-C thread budget.
