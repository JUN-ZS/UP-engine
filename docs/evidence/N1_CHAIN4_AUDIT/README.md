# N1_CHAIN4_AUDIT — freeze baseline

**Decision:** STOP further left/right/down tile expansion until human audit of continuity drift.

## Contents

| Path | What |
| --- | --- |
| `tiles/*.png` | 6 frozen tiles (12–17 on y=448) |
| `joints/*_plate.png` | 4 packed joint plates (R1 R2 R3 L1) |
| `OUT_CHAIN_stitched.png` | fail-closed subset stitch (6 tiles only) |
| `OUT_CHAIN_region_preview.png` | core strip preview |
| `N1_CHAIN4_AUDIT.json` | SHAs, seam recompute, labels |
| `HUMAN_REVIEW_CHECKLIST.md` | operator checklist |

## Labels (locked)

- `N1_GEN_V3_CHAIN4` = experiment_complete  
- `N1_SEAM_CONTINUITY_OK` = **false**  
- `NATIVE_4K_PILOT_OK` = **false**  

Overlap MAE = 0 means hard-lock, **not** model learned continuation.

## Not claimed

- Full 4K canvas  
- Semantic seam PASS  
- Global scene state memory (next arch only)
