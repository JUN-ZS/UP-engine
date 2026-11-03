# NEXT FRAME Engine · Charter (NFE)

asof: 2026-11-04  
status: **LOCKED_GOAL · scaffold v0**  
`quality_qualified=false` · `final_acceptance=false` · `cinematic_product=false`

## 1. Goal (what this IS)

A **still-unit temporal engine** that generates the next frame as an image, conditioned on prior stills and state:

\[
F_{t+1} = G(F_t, F_{t-1}, K, \Delta S_t, C_t)
\]

- \(G\): single-step **I2I next-still generator** (one image per call)
- \(K\): identity / master lock (periodic re-anchor)
- \(\Delta S_t\): allowed motion for this step (Motion Compiler)
- \(C_t\): scene + history context (Temporal State)

**Target capability:** given \(F_0\), produce \(F_1, F_2, \ldots\) **without I2V**, each accepted only after temporal validation.

## 2. Non-goals (what this is NOT)

| Forbidden as a substitute | Why |
|---------------------------|-----|
| Image-to-Video (I2V) as the generator \(G\) | Hides per-frame control; not still-unit autonomous next-frame |
| Optical-flow morph between sparse stills as “360 next frames” | Playback continuity ≠ generation continuity |
| Spatial EXTEND / N1 tile pan | Spatial peep, not temporal \(t \to t+1\) |
| DDXX alone as full continuity | Geometry only; not identity / joint / dynamics |
| Claiming `not_image_to_video=true` cleans provenance | Only means **this encode step** skipped I2V; frame **bank origin** must be labeled |

## 3. Provenance rule (mandatory)

Every frame bank and report MUST declare:

```json
{
  "frame_origin": "i2i_next_still | procedural_cv | extracted_from_video | i2v_source | unknown",
  "not_image_to_video_this_encode": true,
  "never_touched_by_i2v_in_lineage": false
}
```

- `not_image_to_video_this_encode=true` alone is **insufficient** for a “pure still pipeline” claim.
- v12 MAE≈5.16 / flow≈0.224 is a **reference observation** on one 24fps extract, **not** a universal physics floor for all still generators.

## 4. Anchor split (geometry vs dynamics)

| Class | Examples | Role |
|-------|----------|------|
| **Static anchors** | camera, ground, fixed props, buildings | Lock world / camera (DDXX similarity/homography/mesh) |
| **Dynamic anchors** | head, shoulders, elbows, wrists, hammer, cape, splash | Track trajectories; **do not** force-align motion away |

If DDXX rigidly aligns all body anchors, true motion can be **erased**. Static and dynamic MUST use separate gates.

## 5. Pipeline slots

| Slot | Name | Duty |
|------|------|------|
| C0 | Temporal State | \(F_t, F_{t-1}, K\), camera, phase, identity hashes |
| C0.1 | Motion Compiler | text/phase → per-part \(\Delta S_t\) |
| C0.2 | I2I Next-Still \(G\) | **one** next still; no I2V |
| C0.3 | Temporal Validator | static DDXX · dynamic · identity · residual · flow |
| C0.4 | Accept / Reject / Retry | reject does **not** advance \(t\) |
| C1–C5 | FrameBank / Metrics / Layout / Encode / Report | only **accepted** frames |

Periodic re-lock to \(K\) (master) every \(N\) steps to limit drift.

## 6. What 60fps × 6s really means

| Claim | Condition |
|-------|-----------|
| “360 next-frame generations” | 360 successful C0.2 accepts |
| “5 keyframes + flow → 360 playable frames” | **Playback only** — not 360 generations |
| “v12 continuity locked” | Cross-key and consecutive accept gates pass under declared thresholds |

## 7. Relation to existing code

| Existing | Role under NFE |
|----------|----------------|
| `tools/siax_next_frame_f2f_verify.py` | **Validator / metrics** on ordered stills (not generator) |
| `tools/still_sequence_f2f_kit.py` | C1–C5 encode after accept |
| `src/ige/registration/*` DDXX | Static geometry gate inside C0.3 |
| N1 joint/chain | Spatial continuity research — **orthogonal** to NFE time axis |

## 8. First experimental milestone (not 360)

**NFE-P0:** \(F_0 \to F_1 \to F_2 \to F_3\) sequential I2I with state file, reject/retry, dual anchor report.  
Only then scale toward dense 24fps, then optional 60fps **if** accepts are real next-stills.

## 9. GitHub honesty

Local tools may exist before PR sync. PR Draft status does not equal “NFE complete.” Evidence JSON without generators in branch = incomplete integration.
