# SIAX R3 — Memory-aware Nested Tile Executor + Virtual Master

**asof:** 2026-11-01  
**base:** `463cce1` (PR #7 Siax evidence locked)  
**status:** design draft · **not** Siax final_acceptance · **not** a re-run of S2  

## Why this exists (from S2, not from “need more RAM”)

| Cell | Result | May claim |
| --- | --- | --- |
| 128/8 | SPM-approx rank best | temporary ranking only |
| 128/16 | very close to 128/8 | not proven loser |
| 256/16 | worse under current diag | temporary |
| 256/32 | OOM | **quality unknown** · host-blocked |

### Three separate problems (do not collapse)

1. **Inference peak (Hypothesis)** — 256/32 crop 320×320 (~4.94× area of 128/8 144×144) inflates ESRGAN mid-layer activations. Worker already does one-tile-at-a-time; stitch uint8 canvas (~83 MiB at 7168×4032) alone does **not** explain 1.9 GiB kill. **Needs staged peak-RSS proof**, not guesswork.
2. **SPM-approx bias** — current `s2_spm_diag.py` is Laplacian/strip MAE, **not** §0.12.39 residual fingerprint + Lanczos base. Interior probe sampling falls back differently for 128 vs 256 tiles → HF ratio not fully comparable. Natural edges ≠ seams without matched non-seam controls.
3. **Asset / master management** — full float master, wrong primary path, preview mistaken for primary are **Virtual Master** problems, not solved by larger RAM alone.

**Decision:** evolve architecture → **S2.1 / SIAX R3**. Do **not** treat “buy RAM and re-run 256/32” as the main path.

## What Virtual Master is **not**

| Virtual Master **is** | Virtual Master **is not** |
| --- | --- |
| Coordinate system + native child asset library | A way to make any OOM disappear |
| Parent/child transform + SHA registry | A substitute for Siax inference quality |
| Optional strip/streaming finalizer to full PNG | License to claim full-frame 256/32 success without running it |
| Zoom/preview generation on demand | Primary deliverable (JPG preview never replaces primary) |

**STREAM** reduces intermediate buffer residency.  
**Nested Compute Tile** attacks single-forward activation peak.  
**Model/runtime profile** decides safe parallelism.  
Three different levers — do not merge into one slogan.

## Layer duties (hard separation)

| Layer | Duty | Must not pretend to be |
| --- | --- | --- |
| **Siax** | True 4× CNN/GAN SR executor | Generative micro-detail invention |
| **SPM** | Real HF residual fingerprint + match | Identity / pose / topology acceptance |
| **NCPG / PEEP / Virtual Master** | Semantic ROI, context, native child plates, parent–child coords, rebuild | The model’s generative ability |

Never collapse these into one score.

## Nested PEEP: logical tile ≠ physical compute tile

### Keep logical experiment definition

```
Parent (logical) PEEP
  logical_core   e.g. 256
  logical_halo   e.g. 32
  fixed parent coordinates on BASE
  full input provenance
```

### Split physical compute

```
Compute children
  compute_core      e.g. 64 | 96 | 128  (measured, not guessed)
  compute_context   internal context from receptive-field measurement
  one child per forward · write native PNG · free activations
```

| Parameter | Meaning |
| --- | --- |
| `logical_core` | What the experiment claims to evaluate (e.g. 256) |
| `compute_core` | What the model actually sees as core |
| `logical_halo` | Original experiment halo (e.g. 32) at parent boundary |
| `compute_context` | Extra interior context so children are not naive 128 splits of 256 |

**Critical:** splitting 256/32 into four 128/32 without RF measurement is **not** equivalent to original 256/32.  
Nested config is a **new experimental cell** with its own ID, SHA, and acceptance — never label it as “256/32 recovered” until equivalence is measured.

### Equivalence gate (before claiming quality)

1. Measure effective receptive field via **overlap-output** tests (same content, shifted windows).  
2. Set `compute_context ≥` required RF margin.  
3. Compare Nested Parent reconstruct vs single-forward Parent on a **RAM-feasible** proxy (or larger host) with pixel + SPM-A metrics.  
4. Only then attach “quality-qualified for E3” to that nested cell ID.

## Virtual Master asset model

| Asset | Storage |
| --- | --- |
| Global Master index | Manifest only (no mandatory full float canvas in RAM) |
| Parent PEEP | Parent PNG + coords / mask / halo |
| Child PEEP | One native output PNG per compute child |
| Transform | Parent↔child scale, offset, halo, logical ids |
| Acceptance | Per-child SHA, stage status, quality flags |
| Preview | Zoom-level derivatives — **not** primary |

### Primary rules

- Child native pixels are first-class primary assets.  
- Full lossless 4× PNG is **optional delivery** via strip / streaming finalizer / memmap.  
- Dimension assert: registered primary must match declared out size (block hyb256-into-hyb512 class of bug).  
- Path assert: primary URI must not silently resolve to preview / intermediate.  
- Sub-1 MB “4× full frame” must fail size gate for known full dims (R1 evidence: 7168×4032 · 42 995 025 B).

## Memory-aware runner

### Peak model (profiled, not hand-waved)

\[
M_{\mathrm{peak}} =
M_{\mathrm{model}} +
M_{\mathrm{activation}}(W,H) +
M_{\mathrm{buffers}} +
M_{\mathrm{runtime}}
\]

Each model + device + dtype gets a **measured** profile table of peak RSS vs input \(W\times H\).

### Stage-tagged OOM

| Stage | Failure meaning | Response |
| --- | --- | --- |
| Model load | weights / runtime too heavy | load manager / alternate runtime |
| Tile forward | single activation too large | Nested Compute Tile / smaller compute_core |
| Output stitch | full canvas too large | Virtual Master + memmap / strip |
| Final encode | PNG encode peak | strip encode |

Exit 137 without stage tag is incomplete evidence.

### Dispatch

Before claim: available RAM − safety margin − other workers’ profiled peaks → max safe concurrency.  
Never assume “2 workers always OK”.

## True SPM (replace approx as acceptance diagnostic)

### SPM-A — fixed probe bank

- 48 fixed BASE probes (metal / cloth / contour / detail junctions, etc.).  
- Each probe: **real** Siax 4× forward → HF residual fingerprint vs Lanczos (or declared) base.  
- Same coordinates for every tile/halo cell.

### S2 seam bank — matched controls

For each seam sample:

- seam-centered probe  
- parallel non-seam control at same material / semantic class  
- report p50 / p95, not only mean rank  

Separate:

- **SPM-A fingerprint score** (detail character)  
- **Seam control score** (tile boundary artifact)  

Do not average into one vanity number.

## S2.1 execution order

| Step | Work | Done when |
| --- | --- | --- |
| 1 | Fix diagnostic credibility (fixed probes, matched seam controls, separate SPM-A vs Laplacian) | Re-score 128/8 · 128/16 · 256/16 under one sample geometry |
| 2 | Stage peak-RSS on 256/32 path (load / forward / post / stitch) | OOM stage labeled or safe path proven |
| 3 | Nested Compute Tile (logical 256/32 kept; RF measured) | Nested cell ID + equivalence metrics |
| 4 | Virtual Master store (native child PNG, transform, SHA, strip finalizer) | Manifest + size/path asserts |
| 5 | S2 quality re-accept (SPM-A + seam bank + 400% blind + continuity) | quality-qualified cell list |
| 6 | E3 formal speed only on qualified cells | S1-C kept; no blind re-run |

## Relation to PR #7

| PR #7 (`feat/siax-distributed-runner-v0.1`) | This branch |
| --- | --- |
| R1 correctness · S1-C speed · S2 partial SPM-approx | R3 design + S2.1 implementation track |
| Draft Siax core acceptance path | Isolated Draft · must not rewrite PR #7 evidence |
| `final_acceptance=false` still | New features do not flip PR #7 gates |

Base freeze for this branch: **`463cce1`**.  
Merge strategy: PR #7 stays Siax executor evidence; R3 lands as follow-on PR after design + measured gates.

## Explicit non-goals (this draft)

- Claiming 256/32 quality without a completed run under a defined cell ID  
- Using Virtual Master as universal OOM eraser  
- Substituting SPM-approx Laplacian rank for §0.12.39 SPM-A  
- Opening PR #8 / new SR families before Siax path is honestly gated  
- Mixing identity / topology gold into Siax executor PASS  

## First implementation slices (code later)

1. `schemas/virtual-master.schema.json` + transform manifest  
2. `tools/ram_profile_siax.py` — staged RSS for load/forward/stitch  
3. `tools/s2_spm_a_probes.py` — fixed 48 probes + real residual  
4. `tools/s2_seam_controls.py` — matched seam/non-seam banks  
5. Nested plan API: `logical_*` + `compute_*` fields on job manifest  
6. Strip finalizer writing full PNG without full float canvas  

Status of this document: **architecture lock for S2.1 / R3**. Implementation starts only after probe geometry + RAM stage harness land.
