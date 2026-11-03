# SIAX Multi-View Geometry Models v0.2

**Status:** experimental geometry candidate. Not SIAX final acceptance. Not quality PASS. Not E3 speed.

## Why

v0.1 only solved a **global 2D similarity** pose graph. That is correct for scale/rotation/translation, but wrong as a universal formula when:

- the scene is approximately planar with perspective (needs **homography**)
- multi-depth parallax appears (needs **multi-plane / local mesh**, later true depth)

This release makes the geometry model **explicit and switchable**, and adds **holdout residual** as the selection signal.

## API

```python
from ige.registration import register_multiview

result = register_multiview(
    image_specs, matches,
    geometry_model="similarity",   # or "homography" | "local_mesh"
    holdout_fraction=0.25,         # optional; splits anchors per edge
    holdout_seed=0,
    local_mesh_grid=(2, 2),        # only for local_mesh
    acceptance_threshold_px=None,  # still required for geometry_gate=pass
)
```

Schema: `siaux-multiview-transform/0.2`  
Legacy similarity-only solver remains as `register_multiview_similarity`.

## Models

| ID | Algorithm | DOF / image | Fit | Canvas |
|----|-----------|-------------|-----|--------|
| `similarity` | DDXX Umeyama + Huber + joint LM pose graph | 4 | train anchors | similarity |
| `homography` | DLT + Huber IRLS per edge, graph composition | 8 | train anchors | homography |
| `local_mesh` | spatial similarity tiles per edge + similarity backbone | tiles + 4 | train anchors | similarity backbone |

### Gate rules (unchanged spirit)

- No `acceptance_threshold_px` → `pending_threshold_not_declared`
- Global p95 / cycle-checked edge closure vs threshold
- Bridge edges → `pending_unverified_bridge_edges` unless waived
- Fail closed on degenerate anchors / disconnected graphs

### Holdout

When `holdout_fraction` is set:

1. Each edge randomly keeps a train subset for fitting.
2. Held-out anchors never enter the fit.
3. `result["holdout"]` reports holdout p95 / RMSE.

**Rule:** choose models by **holdout p95**, not by train residual.

## Counterfactual CLI

```bash
python tools/siax_multiview_model_holdout_compare.py \
  --out runs/geometry_holdout/REPORT.json \
  --holdout-fraction 0.25
```

Synthetic scenes:

1. pure similarity triangle  
2. projective homography triangle  
3. multiplane parallax proxy (two depth shifts)

Optional real anchors: `--anchors-json` + `--specs-json`.

## What is still not claimed

- No joint projective LM for multi-image homography (composition-only global refine).
- local_mesh is **not** a true deformable multi-plane mesh.
- No real SIAX image quality / seam PASS.
- ComfyUI node gains a model dropdown; live UI import still not certified here.

## ComfyUI

`SIAX Multi-Image Geometry Registration` accepts `geometry_model` and optional `holdout_fraction`.
