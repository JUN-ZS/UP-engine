# PREVENT BLUE INJECTION (PBI)

## Goal

**Not** post-hoc blue wash (R9/R10/K holefill).

**Yes**: when generating 4× / HR pixels, forbid wrong blue chroma injection into silver/metal mesh.

Post-hoc detox remains **test evidence only**, never formal MASTER acceptance.

## Poison sites (this repo)

1. `src/ige/upscale/siax.py` — full RGB tile write  
   `tile_out = descriptor(tile)` → all of R,G,B invent detail.
2. `src/ige/upscale/detail6.py` — was  
   `output = source + (source - low) * (gain * alpha[..., None])`  
   **three-channel residual** even under metal mask → re-injects blue after a clean SIAX guard.

## Guard

`src/ige/upscale/material_chroma_guard.py`

Metal / silver (linear-ish RGB):

\[
RGB_{\mathrm{metal}} = C(LP_{4x}) \times Y(SR)
\]

- SIAX: optional `--apply-material-chroma-guard --metal-mask MASK.png`  
  Writes master with guard; raw SR as `*_RAW_SR.png` for diagnosis.
- DETAIL6: **metal always Y-only residual**; stone/text/fire keep RGB residual.

## Acceptance (generation time)

| Gate | Requirement |
|------|-------------|
| New BLUE residual on metal | not above LP-relative threshold |
| Connected navy blotch | controlled area / max CC / count |
| Fixed mesh ROIs | ≥6 positions |
| AUTO_WORST | worst window reported |
| DETAIL6 metal | no RGB chroma residual path |
| Failure | **reject MASTER** — do not wash and PASS |

Keep LP environment tint. Eliminate **SR-added** wrong blue, not “blue = 0 everywhere”.

## NCNN

R6c / NCNN residual compose is not in this tree yet. Same guard API must be wired when that runner lands.

## Related

- Constitution §0.12.55 PREVENT_BLUE_INJECTION
- R9/R10 post-hoc = diagnostic only
