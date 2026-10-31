# Legacy skill map and execution status

The old constitution is the source of truth for skill order and failure rules. This file records which pieces have become executable in UP-engine; a name in a map is not an implementation.

## Reference and routing layer

| Legacy concept | Engine implementation | Current status | Cannot substitute for |
|---|---|---|---|
| REF / asset UUID references | Offline reference catalog + ref-search CLI | **81 source identifiers + 160 short aliases**, with searchable context | Actual image bytes, SHA verification or donor suitability |
| MSR | Evidence-bearing diagnosis + state-aware skill planner | Partial; semantic observations require evidence | Human review or pixel validator |
| OTL0 | Topology gate contract | Contract-only | Full object reconstruction |
| PATH1E | a8b face plate, ECC and protected composite | Documented-only | Executed identity proof |
| ZYF / ETZ / SCD | Donor preparation | Documented-only | Final compositor |
| TEX4 / RRT / P_G | Garment/topology reconstruction | Documented-only | Detail enhancement |
| OBA | Layered object accumulation | Documented-only | Immutable BASE |
| SWP / SPM / SIAX | Multi-scale detail enhancement | SIAX4X runtime adapter conditional; GRID/SWP still documented-only | Structural repair |
| PIXEL_CTRL | Pixel class and eye-white protection | Documented-only; DETAIL6 enforces face/skin/eye masks for its own residual stage | Full face repair |
| DETAIL6 | Siax master, material-mask residual and q98/q100 4:4:4 | Partial execution path; full GRID_CLEAN/BEAT donor selection and clarity proof remain open | Perceptual quality or identity approval |
| GOU / V5 / GCS / ECC / WHOLE | Registration/reconstruction | Existing registration is dimension-only; residual/warp incomplete | Geometry acceptance |
| DAMD / HTFC | Temporal state transitions | P4 not implemented | Single-image detail restoration |

| Grok skill diagnosis | xAI Vision multi-image task adapter + `ige diagnose-image` | Code + mock tests; live API E2E NOT RUN; all findings remain candidate | Human verification or project gold benchmark |

## Provenance and execution rules

- Source repository: JUN-ZS/ai-image-gen-logic-review, snapshot commit 2cdb22bf6ef8ed68a88dc0fc23d0c33ce1e6d62e.
- Each seeded reference stores its original path and constitution section. Binary assets are not copied; records remain external_asset_reference_only or legacy_manifest_reference_only.
- No URI/UUID is treated as a fetched image. Local materialization requires a matching file; known hashes are verified.
- A present diagnosis needs evidence. Grok Vision/other model observations marked candidate cannot authorize skill execution.
- Structural/topology errors route before detail work and block later enhancement stages.
- SIAX4X is pinned to model file SHA-256 560424d9f68625713fc47e9e7289a98aabe1d744e1cd6a9ae5a35e9957fd127e; checkpoint is not vendored and license review remains explicit.
- DETAIL6 does not inflate bytes. It writes material-zone residuals only, excludes face/skin/eye_white masks, measures zone deltas and reports a byte gate.
- Skills labelled documented-only are not silently replaced with generic sharpening or free-form image generation.
