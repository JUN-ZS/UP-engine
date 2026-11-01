# Next architecture (not started): Global Scene State Memory

**After** Chain4 audit only. Not an excuse to paint more tiles yet.

## Problem

Chain4 frontier MAE rises ~12 → ~32 left-to-right; content shifts toward mud-empty.
Passing only the previous tile image accumulates **composition drift**.

## Proposal

Each extension carries a **scene state vector** (explicit, versioned), not only pixels:

| Field | Example |
| --- | --- |
| subject_bbox_canvas | face/torso in 3840×2160 |
| hammer_polyline | handle + head keypoints |
| camera | FOV, pitch, pan |
| horizon_y | float |
| light | key direction, lightning flash id |
| palette / weather | rain density, mud spray |
| tile_id just filled | |
| parent_sha | previous tile SHA |

Generator prompt / conditioning must bind to this state. Hard-lock remains geometric safety net only.

## Non-goals

- Claiming PASS by more tiles  
- Replacing human review  
- 4× Siax path
