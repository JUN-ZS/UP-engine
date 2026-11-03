# Geometry verify with NEW images v0.4

Controlled verification (not free generative multi-view).

1. Start from real N1 face tile `n1_0013`.
2. Build **new** images:
   - A identity
   - B known similarity (s=0.92, r=7°, t=(28,-16))
   - C known mild homography
3. GT anchors on triangle A–B–C with 25% holdout.
4. Compare similarity / homography / local_mesh.

## Result

| model | gate (thr=2px) | holdout p95 |
|-------|----------------|-------------|
| similarity | FAIL | ~17.9 px |
| **homography** | **PASS** | ~0 |
| local_mesh | FAIL | ~17.9 px |

- `sim_recovers_B_pose=true` (scale/rot/t within tight err)
- Homography correctly preferred when C is projective
- Not quality PASS / not native 4K
