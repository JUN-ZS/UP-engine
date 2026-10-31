# REF Resolver, Skill Router and DETAIL6

## Scope

This implementation imports a **reviewed metadata slice** of the legacy reference library. It does not copy the legacy repository, fetch Imagine assets implicitly, or assume that an asset UUID is an available image. Every seeded record carries source repository, source commit, source path and constitution section.

Legacy source snapshot: `JUN-ZS/ai-image-gen-logic-review` at `2cdb22bf6ef8ed68a88dc0fc23d0c33ce1e6d62e`.

## REF resolver

- `ige ref-search --skill SKIN_MAT` resolves P1/P2/P3/P4 to their recorded roles and source sections.
- `ige ref-search --query a8b` finds the canonical face identity reference.
- `ige ref-search --query 2ce5fabe` resolves the historical short prefix to its canonical full UUID when unique.
- `ige ref-search --query 'plate ECC'` searches the source-context snippets, not only hand-authored labels.
- `--asset-root` checks whether a referenced local file has been materialized. A reference-only UUID is not reported as a fetched image.
- The current snapshot indexes 81 distinct full UUID/L artifact identifiers and 160 explicit short aliases extracted from nine source documents (including the master formulas and the main constitution). Each record carries source path, section and up to six source-context snippets. Short aliases resolve to canonical IDs only when unique. This remains a metadata index, not a complete historical binary asset corpus.

## Evidence-first skill routing

`ige skill-plan IMAGE --diagnosis diagnosis.json` accepts evidence-bearing observations. Every present finding requires evidence and provenance. Grok Vision findings should be marked `source=grok_vision`, `verification=candidate`; those findings stay in review and cannot authorize execution.

Topology defects are routed ahead of detail work. When topology is reported wrong, SIAX/GRID/DETAIL6 are blocked until the structural issue is corrected. This encodes the legacy rule that sharpening cannot repair wrong topology.

Raster width/height and SHA-256 are measured automatically. Semantic conditions such as face drift, garment topology, metal weave weakness or skin noise are not inferred from generic image statistics.

## Grok Vision diagnosis

`ige diagnose-image BASE --out RUN_DIR` uses the active Grok Vision provider to inspect structural, identity, material and image-quality issues, then runs the evidence-aware skill planner. It writes `diagnosis.json` and `skill_plan.json`.

Optionally provide the canonical identity reference as a second image:

```bash
ige diagnose-image BASE.png --out runs/diagnosis-a8b --identity-reference references/a8b.png --identity-reference-id a8b78fe5-2654-4f6f-84e3-c1dfbee61004
```

Without a supplied identity reference, identity drift is forced to `unknown`. Every model finding remains `source=grok_vision`, `verification=candidate`; no finding creates permission, geometry locks or accepted skill execution. The model confidence is uncalibrated. The endpoint is mock-tested, but a live xAI request and project-image gold benchmark remain NOT RUN.

## Multi-family method selection

The strategy portfolio is separate from the legacy skill map: one method family may be implemented by several models; one legacy skill may chain multiple methods. The router returns 12 candidate families, gating them by defect type, topology status, material donor availability, identity reference availability, frame registration, depth/normal/mesh availability, masks and Siax checkpoint/master state. It does not auto-run a candidate or pick a winner before comparable outputs exist. See `docs/UPSCALE_STRATEGY_PORTFOLIO.md` for details.

## Siax 4x inference

Optional install: `python -m pip install -e .[upscale]`.

Checkpoint reference:

- File: `4x_NMKD-Siax_200k.pth`
- Pinned SHA-256: `560424d9f68625713fc47e9e7289a98aabe1d744e1cd6a9ae5a35e9957fd127e`
- Mirror revision: `aadb8d07077a0818db0f43000b05442074b413be`
- File source: https://huggingface.co/uwg/upscaler/resolve/aadb8d07077a0818db0f43000b05442074b413be/ESRGAN/4x_NMKD-Siax_200k.pth

The mirror repository labels its content MIT. That label is not treated as conclusive proof of the original model's terms; the runtime requires an explicit license-review acknowledgement. The checkpoint is not committed to Git. Spandrel loads the file; the adapter requires an ESRGAN architecture and exact scale 4, then applies tile inference and writes an immutable-provenance sidecar. The output is assembled directly into a uint8 RGB canvas to avoid retaining a full 4x float32 image buffer; default tile settings are 128 pixels with an 8-pixel context pad and can be overridden.

Example:

```bash
python -m pip install -e '.[upscale]'
ige upscale-siax BASE.png --checkpoint models/4x_NMKD-Siax_200k.pth --out runs/SIAX4X.png --confirm-model-license-review
```

The sidecar includes BASE hash, checkpoint hash, output hash, model architecture, exact scale, tile parameters, runtime/device and license-review status. A sidecar does not prove visual quality or identity.

## DETAIL6

The current implementation is a partial §0.12.19 execution slice: verified 4x Siax master → material-zone residual → zone-limited detail gain → q98/q100 JPEG 4:4:4 → size gate. Full GRID_CLEAN/BEAT donor selection and legacy clarity proof are not yet migrated.

Mask manifest shape:

```json
{
  "mask_version": "1.0",
  "masks": {
    "metal": "masks/metal.png",
    "stone": "masks/stone.png",
    "text": "masks/text.png",
    "fire": "masks/fire.png",
    "face": "masks/face.png",
    "skin": "masks/skin.png",
    "eye_white": "masks/eye_white.png"
  }
}
```

At least one material/detail mask is required. All three protection masks are mandatory; use an empty black mask when a protected class is absent from a particular image. Masks may be at BASE or exact 4x dimensions; BASE-size masks are expanded with nearest-neighbor only.

Example:

```bash
ige detail6 BASE.png --upscaled runs/SIAX4X.png --masks runs/masks.json --out runs/DETAIL6 --minimum-bytes 30000000
```

`--minimum-bytes` defaults to 6,000,000 per the legacy SIZE_GATE. The 30MB example is an explicit target, not a guaranteed outcome. The program never pads files, creates synthetic metadata bytes, or enlarges a low-resolution preview to pass the gate.

Outputs:

- `DETAIL6_WORKING.png`: lossless working result. The exact protected-pixel audit is performed against the verified Siax master.
- `DETAIL6_FULL_q98.jpg` and `DETAIL6_FULL_q100.jpg`: JPEG quality 98/100, chroma subsampling 0 (4:4:4). These are lossy delivery files and are not claimed to be pixel-identical.
- `DETAIL6_REPORT.json`: output bytes, dimensions, masks, zone HF diagnostics before/after, protected-pixel deltas and technical execution gates. HF diagnostics are not proof of clarity.

DETAIL6 is not an identity, geometry, pose, topology or temporal validator. HF energy increase is diagnostic only, not proof that the result looks clearer. Full visual clarity proof and human comparison remain unimplemented. Human comparison against the prior stage remains required.

## Explicitly not yet migrated

PATH1E, PIXEL_CTRL, GRID_CLEAN/BEAT, SWP/SPM full stack, ZYF/ETZ/SCD donor pipeline, TEX4/RRT/P_G and OBA remain documented-only. The router makes those gaps visible and refuses to silently substitute generic sharpening.

## Related legacy rules

- `BOUNDARY_WALKER_UNIFIED_RULES.md` §0.12.15–§0.12.19
- `GRID_SIAX_CORRECT_PROCESS.md`
- `PIXEL_CTRL_LAW.md`
- `PATH1E_PLATE_ECC_LAW.md`
- `FOUR_SKILL_TEX_ALIGN.md` §0.12.50
