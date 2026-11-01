# N1.gen v3 — Joint A∪B Plate

| | |
| --- | --- |
| **Status** | experiment tool + HERE trial |
| **≠** | masked continuation · hard-lock · 4× Siax · full 4K |

## Why

v1: independent A/B recompose → seam FAIL  
v2: `V2_POSTGEN_HARDLOCK` — freezes A, generates B, pastes 64px; **does not** prove model continuation  

v3: **one generation** covering A∪B box, then split by canvas coords.

## Metrics (required)

1. **overlap_equality_mae** — must be ~0 after split (same plate)  
2. **generation_frontier_mae** — A last col vs B first free col (informative only)  
3. **semantic continuity** — human: hair, armor, camera plane  

## CLI

```bash
python tools/n1_gen_v3_joint_plate.py prep --plan runs/n1/plan.json --tile-a ... --tile-b ... --global-ref ...
# generate JOINT then:
python tools/n1_gen_v3_joint_plate.py split --joint-png ... --allow-resize-joint
python tools/n1_gen_v3_joint_plate.py metrics --tiles-dir ...
```
