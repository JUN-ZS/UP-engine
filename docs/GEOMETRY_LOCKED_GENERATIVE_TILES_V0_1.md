# Geometry-Locked Generative Tiles v0.1

**Status:** first executable experiment scaffold. Tile planning and geometry auditing are implemented; model generation is not yet automated or accepted.

## Why this is separate from Siax SR and multi-view registration

- Siax SR changes sampling resolution; it does not own object geometry.
- Multi-view registration aligns images into a shared coordinate frame; it does not constrain what a diffusion model redraws inside a tile.
- This experiment fixes one human-verified object's geometry in a global high-resolution canvas, derives local geometry for two overlapping generation crops, and audits generated observations against that contract.

The global object contract is authoritative. A tile is a compute region, not a new coordinate system in which the object may be resized or reinterpreted.

## Object contract

Create a JSON file with this structure:

    {
      "schema_version": "ige-object-geometry/1.0",
      "geometry_status": "human_verified",
      "source": {
        "sha256": "<SHA-256 of the exact source image bytes>",
        "width": 3840,
        "height": 2160
      },
      "object": {
        "id": "hammer-head",
        "bbox_xyxy": [1600, 700, 2300, 1120],
        "polygon_xy": [[1600, 760], [1680, 700], [2220, 700], [2300, 760],
                       [2300, 1040], [2220, 1120], [1680, 1120], [1600, 1040]],
        "landmarks": {
          "left_end": [1600, 910],
          "contact_center": [1950, 910],
          "right_end": [2300, 910]
        }
      },
      "tolerances": {
        "bbox_iou_min": 0.95,
        "silhouette_iou_min": 0.95,
        "landmark_max_px": 3.0,
        "overlap_silhouette_iou_min": 0.95,
        "overlap_landmark_max_px": 2.0
      },
      "provenance": {"source": "human_annotation"}
    }

Coordinates are global canvas pixels, after EXIF orientation correction. The bbox must tightly enclose the polygon; landmarks must lie inside the bbox. The exact source-image SHA and dimensions are mandatory. A model-originated candidate cannot be used as a lock.

The tolerance values above are examples for an experiment, not validated universal thresholds. Set them from the pixel scale and the specific object being tested.

## Plan two tiles

    ige geometry-tile-plan source_4k.png object_geometry.json \
      --out runs/geometry_tiles_001 --split-x 1950 --overlap-px 192

The split line must cross the object's global bbox and silhouette. The planner writes:

- tile_left.png / tile_right.png: overlapping source crops.
- tile_left.task.json / tile_right.task.json: local object geometry, crop origin, write core and ComfyUI prompt handoff.
- plan.json: source hash, global contract, exact tile geometry and acceptance tolerances.

Each tile has a disjoint write core. The overlap is context and reconciliation only. Global-to-local mapping is translation by the crop origin; no object-scale transform is applied.

## ComfyUI handoff — current boundary

Open each tile PNG in the existing high-resolution img2img workflow and use its matching task JSON prompt/geometry as conditioning context. Keep the tile's exact pixel dimensions. Use the same checkpoint, LoRA stack, sampler, scheduler, steps, denoise and fixed seed for both tiles in the first controlled run. Do not randomize the seed between the left and right tile in this baseline.

**The workflow API JSON is not yet bound to an automatic queue adapter.** The planner exports ready-to-use tile packets; it does not submit jobs to a local ComfyUI instance. The prompt is only a hint: no diffusion prompt can be treated as a hard geometry constraint.

## Geometry observations and audit

After generating each tile, annotate the visible object fragment in that tile's local pixel coordinates. Store:

    {
      "observations": [
        {
          "tile_id": "tile_left",
          "bbox_xyxy": [/* measured tile-local bbox */],
          "polygon_xy": [[/* measured local points */]],
          "landmarks": {"contact_center": [/* x, y */]}
        },
        {
          "tile_id": "tile_right",
          "bbox_xyxy": [/* measured tile-local bbox */],
          "polygon_xy": [[/* measured local points */]],
          "landmarks": {"contact_center": [/* x, y */]}
        }
      ]
    }

Then run:

    ige geometry-tile-audit runs/geometry_tiles_001/plan.json observations.json \
      --out runs/geometry_tiles_001/audit.json

Reconstruct the full candidate by copying only each tile's disjoint write core (no blending or resizing):

    ige geometry-tile-stitch runs/geometry_tiles_001/plan.json \
      runs/geometry_tiles_001/generated_left.png runs/geometry_tiles_001/generated_right.png \
      --out runs/geometry_tiles_001/generated_master.png

The stitcher requires exact generated crop dimensions and writes a SHA-256 sidecar. Its output status remains COMPOSITE_CANDIDATE_NOT_GEOMETRY_ACCEPTED; run the geometry audit separately.

The audit measures tile-local bbox IoU, silhouette IoU and landmark displacement, then compares both generated silhouettes and any shared landmarks in global overlap coordinates. Missing tile observations are incomplete, never PASS.

The annotation source can be a human-marked polygon/landmark set or a segmentation proposal that has been independently reviewed. A VLM's self-reported geometry or prompt-following statement is not measurement evidence.

## Experiment sequence

1. Fix model, workflow, seed and generation parameters; generate left/right tiles.
2. Audit per-tile shape and cross-tile overlap continuity.
3. Repeat with a different seed while keeping the same global contract.
4. Repeat with a changed split/overlap while keeping object geometry and source fixed.
5. Only after this baseline, test stronger conditioning (ControlNet/edge/depth/segmentation or shared-coordinate latent noise) one factor at a time.

The falsification condition is simple: if changing split position or tile size changes the reconstructed object's global bbox, silhouette or landmarks beyond declared tolerances, the current conditioning is not geometry-stable.

## Acceptance boundary

A geometry audit pass means only that the supplied measurements fall within the explicitly declared thresholds. It does not prove perceptual detail quality, identity, material fidelity, physical 3D truth, seam quality outside the measured object, or that the generation model obeys the geometry contract in general. No GPU inference or ComfyUI UI replay is claimed by the planner tests.

## Next integration gate

Export the ComfyUI workflow in API format, bind its input-image and generation-parameter nodes to the task packet, submit both tiles through one controlled runner, collect generated outputs, and feed independently measured observations back to this audit. Do not mark that integration live until a real local ComfyUI replay has produced output files and hashes.


## Provisional annotation gate

A visually traced but not yet operator-confirmed object may use `geometry_status: assistant_provisional`. The planner emits `geometry_gate=pending_operator_confirmation`. Even perfect measured observations return `MEASURED_WITHIN_TOLERANCES_PENDING_OPERATOR_CONFIRMATION`, never an acceptance PASS. Model-generated proposals remain rejected as locks. Change the contract to `human_verified` only after an operator confirms/corrects the target polygon, bbox and landmarks.

## Object-focused ROI mode

For a single-object crossing test, pass an explicit global ROI:

    ige geometry-tile-plan source_16mp.png object_geometry.json \
      --out runs/object-roi --split-x 2680 --overlap-px 144 \
      --region 1664 960 3696 1984

The two tiles cover only the ROI while the geometry contract remains in full-canvas coordinates. The ROI stitcher verifies the original source SHA and preserves every pixel outside the ROI from the exact source master. This prevents a one-object geometry experiment from allocating two unnecessarily large half-frame diffusion jobs.
