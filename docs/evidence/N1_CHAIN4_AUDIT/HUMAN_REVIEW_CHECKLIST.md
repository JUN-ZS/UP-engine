# Chain4 human review (operator)

Fill after viewing `OUT_CHAIN_region_preview.png` and per-tile PNGs.

| ID | Check | Pass/Fail/NA | Notes |
| --- | --- | --- | --- |
| face_identity | 12–14 same person / camera as seed | | |
| hammer_geometry | hammer continuity if present | | |
| armor_continuity | gold scale armor 12–14 | | |
| hair_flow | continuous hair motion | | |
| lightning_scene | same storm scene vs empty mud drift | | |
| perspective_horizon | stable horizon / FOV | | |
| rightward_drift | 14→17 cumulative empty-mud drift | | |

**Rule:** Do **not** set `N1_SEAM_CONTINUITY_OK=true` from frontier MAE alone.

After review, append results into `N1_CHAIN4_AUDIT.json` → `human_review.checklist[].result`.
