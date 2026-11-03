# Real multi-view holdout v0.3 (GO-3)

**Status:** geometry candidate evidence only.  
`quality_qualified=false` · `final_acceptance=false` · `native_4k_success=false` · not E3 speed.

## Source

- Run: `runs/n1/gen_v3_chain4`
- Tiles: `n1_0012` … `n1_0015` (512×512 on 3840×2160 plan)
- These are **N1 native-canvas generative tiles**, not full-frame 4× Siax ESRGAN of a single plate.

## Packs

| Pack | Anchors | Meaning |
|------|---------|---------|
| `N1_CHAIN4_OPERATOR_GEOM_*` | Operator grid on planned canvas overlap | Tests recovery of **declared N1 layout** (axis-aligned translation) |
| `N1_CHAIN4_SIFT_CANDIDATE_*` | SIFT+RANSAC on adjacent tiles | Appearance candidates; may track hard-locked overlap texture |

## CLI

```bash
python tools/siax_multiview_model_holdout_compare.py \
  --anchors-json docs/evidence/siax_real_multiview_holdout_v03/N1_CHAIN4_OPERATOR_GEOM_anchors.json \
  --specs-json docs/evidence/siax_real_multiview_holdout_v03/N1_CHAIN4_OPERATOR_GEOM_specs.json \
  --out docs/evidence/siax_real_multiview_holdout_v03/CLI_OPERATOR_GEOM_REPORT.json \
  --holdout-fraction 0.25 --seed 42
```

Rebuild pack:

```bash
python tools/siax_build_n1_real_holdout_pack.py \
  --stitch runs/n1/gen_v3_chain4/OUT_CHAIN_chain4.n1_stitch.json \
  --out docs/evidence/siax_real_multiview_holdout_v03 \
  --with-sift
```

## Observed (holdout_fraction=0.25, seed=42)

Operator geometry: all three models ~0 holdout p95 (plan is pure translation).  
**Best (tie-break):** similarity — preferred as lowest-DOF model matching the plan.

SIFT candidates: residuals also ~0 on this run (overlap texture highly consistent after hard-lock / continuation).  
Does **not** prove semantic seam continuity (N1_SEAM_CONTINUITY still FAIL historically).

## Interpretation

1. Real multi-image **CLI path works** with manual/operator anchors JSON.
2. On axis-aligned N1 chain geometry, **similarity is the correct model**; homography is unnecessary DOF.
3. Next real stress case should use **true multi-view peeps with parallax** (different camera / different depth), not only N1 tile grid.
