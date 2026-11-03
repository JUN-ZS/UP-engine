# SIAX Multi-Image Geometry Engine v0.1

**Status:** experimental / geometry candidate only. Not SIAX final acceptance. This module does not replace or modify the existing candidate-to-BASE registration gate.

## Purpose

Promote the DDXX weighted semantic-landmark fit into a multi-image registration source. Each pair of images contributes a relative transform; all image poses are then jointly solved in one coordinate frame. The result includes per-image transforms, a shared canvas, residual evidence, cycle/bridge diagnostics and a geometry gate.

The existing \`ige.adapters.registration\` is deliberately unchanged. It checks whether a generated candidate already occupies the exact BASE pixel frame. This new engine is a multi-image scene preprocessor and must not silently authorize arbitrary candidate warps.

## Geometry pipeline

1. **Correspondences:** mutual SIFT ratio-test matches + RANSAC, or manually/semantically supplied paired anchors.
2. **Pair fit:** DDXX-derived weighted Umeyama + Huber IRLS estimates the transform from image B coordinates to image A coordinates.
3. **Graph initialization:** traverse the connected pairwise image graph from a declared root.
4. **Global solve:** jointly refine every non-root image pose against all paired anchors. Do not rely on chained A→B→C transforms alone.
5. **Consistency:** compute all-anchor residuals, per-edge closure residuals, cycle rank and graph bridge edges.
6. **Canvas:** calculate a shared output canvas and image-to-canvas transforms.
7. **Apply / stitch:** only a geometry-gated transform can be applied; source-validity masks remain explicit through basic feather compositing.

Transform convention: \`column_vector_ccw_degrees\`, \(q=sR(\theta)p+t\).

## Acceptance behavior

- A positive \`acceptance_threshold_px\` must be explicitly declared before \`geometry_gate=pass\`; zero/unset remains pending.
- Both global all-anchor p95 residual and the worst cycle-checked edge-closure p95 must be within the declared threshold.
- The shared canvas is capped by \`max_canvas_pixels\` (default 100 million). The ComfyUI control exposes megapixels.
- Every graph bridge (an edge whose removal disconnects the graph) lacks an independent cycle-closure check. In a graph of 3+ images, any such bridge keeps the gate at \`pending_unverified_bridge_edges\` unless explicitly waived.
- Disconnected graphs, fewer than three paired anchors per edge, collinear/degenerate anchors, out-of-frame coordinates and non-finite values fail closed.
- The Huber cutoff is an influence threshold, not a production quality tolerance.
- The DDXX 11-point fixture is a solver regression fixture only. Its ~7.5px RMSE is not a universal image-registration threshold.

## Correspondence providers

### Automatic SIFT + ratio + RANSAC

The feature node attempts every image pair. Reciprocal ratio-test matches are filtered by RANSAC and a spatial occupancy cap prevents the selected anchors collapsing into one tiny texture patch. These remain candidate correspondences: repeated texture, similar objects, reflections and parallax can still produce coherent false matches. Descriptor confidence is not calibrated.

### Manual / semantic anchors

Disconnect the feature node's \`anchors_json\` output and supply JSON using \`siaux-multiview-anchors/1.0-manual\`. Each edge contains \`image_a\`, \`image_b\` and at least three paired anchors with \`xy_a\`, \`xy_b\`, optional \`weight\` and \`confidence\`. Coordinates are original source-image pixel coordinates and must be within each image's bounds.

Manual semantic anchors are useful for stylized imagery, characters, mechanical structures and low-texture regions. Anchor semantics and pair selection must be reviewed by the operator.

## ComfyUI custom nodes

Folder: \`custom_nodes/ComfyUI-SIAX-MultiImage\`

- **SIAX Multi-Image Feature Matches:** 2–8 single-image IMAGE ports; emits anchor JSON and diagnostics.
- **SIAX Multi-Image Geometry Registration:** consumes the images and anchor graph; emits global transforms and registration report.
- **SIAX Apply Geometry Transform:** warps one source into the shared canvas and emits a validity mask. Refuses non-pass geometry.
- **SIAX Multi-Image Stitch:** basic feather blend; emits composite candidate, coverage mask and overlap mask.
- **SIAX JSON Report Preview:** presents matcher and registration JSON in the ComfyUI execution output.

Each image port takes one image (batch size 1). Use different ports for differently sized crops; do not pack different dimensions into an ImageBatch.

## Install

Use the same Python environment as ComfyUI:

\`\`\`bash
python -m pip install -e ".[registration]"
\`\`\`

Copy or symlink \`custom_nodes/ComfyUI-SIAX-MultiImage\` into \`ComfyUI/custom_nodes/ComfyUI-SIAX-MultiImage\`, restart ComfyUI and open \`workflows/SIAX_MultiImage_Geometric_Registration_v0.1.json\`.

The sample workflow deliberately starts with a zero acceptance threshold. Inspect the report and set a project-validated threshold before transforms can be applied. Keep the default bridge gate; only waive it when separate evidence supports a dangling image's relative placement. The canvas cap is a pixel allocation guard, not a VRAM guarantee: the ComfyUI tensor graph may retain several full-size layers.

## What is not claimed

- No perspective homography, parallax, rolling-shutter, lens-distortion or non-rigid solution.
- No synthesis of pixels where no source image provides coverage.
- Feather blend is not graph-cut seam selection, multiband blending or generative inpainting.
- A low residual does not prove semantic identity, object correspondence or correct z-order.
- No live ComfyUI UI import or real project-image acceptance has been claimed by this prototype.

## v0.2 model switch (implemented)

See `docs/SIAX_MULTIVIEW_GEOMETRY_MODELS_V02.md`.

`register_multiview(..., geometry_model=similarity|homography|local_mesh, holdout_fraction=...)`.

Schema `siaux-multiview-transform/0.2`. Holdout residual is the selection signal.

## Next model-family boundary

Do not silently replace similarity with affine/homography/local mesh. Add explicit model IDs only when the data supports their assumptions. Strong parallax may require plane-specific transforms or depth-aware reconstruction, not one homography over the whole scene. Compare inlier residual, held-out anchors, cycle closure, foldover/Jacobian validity and resampling loss; lower training residual alone does not prove a better model.
