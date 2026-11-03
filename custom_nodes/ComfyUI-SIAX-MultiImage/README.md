# ComfyUI-SIAX-MultiImage

Experimental custom nodes for DDXX-derived multi-image geometry registration.

## Install

In the ComfyUI Python environment, from the UP-engine repository root:

\`\`\`bash
python -m pip install -e ".[registration]"
\`\`\`

Copy this folder into \`ComfyUI/custom_nodes/ComfyUI-SIAX-MultiImage\`, restart ComfyUI, then open the workflow under \`workflows/\`.

## Nodes

- \`SIAX Multi-Image Feature Matches\`: mutual SIFT / ratio / RANSAC candidate links (2–8 images).
- \`SIAX Multi-Image Geometry Registration\`: pairwise DDXX weighted similarity fits and global pose graph solve.
- \`SIAX Apply Geometry Transform\`: requires \`geometry_gate=pass\`; outputs image and validity mask.
- \`SIAX Multi-Image Stitch\`: basic feather candidate plus coverage and overlap masks.
- \`SIAX JSON Report Preview\`: renders JSON diagnostics in the execution output.

A positive, project-validated p95 pixel threshold must be supplied. For 3+ images, unverified graph bridges are blocked unless explicitly waived. Each IMAGE socket takes one image (batch size 1).

## Scope

This is not final image acceptance, it does not generate missing scene content, and feathering is not an advanced seam optimizer. Perspective, parallax and local non-rigid geometry are not supported in v0.1. See \`docs/SIAX_MULTIVIEW_GEOMETRY_ENGINE.md\`.
