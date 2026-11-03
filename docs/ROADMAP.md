# Roadmap

## P0 — contract-first foundation (completed scaffold)

- [x] typed task and asset roles
- [x] PEEP manifest schema and validator
- [x] state-aware, fail-closed router
- [x] hard gates separated from soft quality
- [x] CI and deterministic tests

## P1 — READ engine (v0.3 executable; inference still partial)

- [x] source provenance, EXIF orientation, raster diagnostics
- [x] region semantic_type independent from editable/protected permission
- [x] tagged object/context/identity-anchor/contact-surface regions
- [x] safe mask law: editable whitelist; all other pixels effectively protected
- [x] local READ Studio polygon and relation annotation
- [x] preview PNG, per-region masks and machine-readable READ report
- [x] optional SAM3 text segmentation provider; masks stay unreviewed
- [x] optional Qwen3.8 visual reasoner; nodes and relations stay unreviewed
- [x] strict reasoning JSON parser with normalized evidence boxes and surface constraints
- [x] typed relation graph with candidate/human_verified/rejected states
- [x] contacts_at requires both named surfaces; part_of cycles rejected
- [x] task-scoped generation mask and exact protected complement
- [x] source image SHA-256 and per-region mask integrity checks before packet creation
- [x] only human-verified relations enter geometry locks
- [ ] browser UI for reviewing VLM candidate boxes/relations and promoting selected candidates
- [ ] benchmark SAM3/Qwen model candidates against hand-corrected masks and geometry labels on the actual project image set

## P2 — one end-to-end generation/reconstruction path

- [ ] select one validated image-edit model adapter (preserve the rest as separate candidates)
- [ ] generation adapter consumes generation_packet.json and emits a separate candidate layer
- [ ] registration manifest with transform/residual and strict BASE coordinate checks
- [x] deterministic task-mask compositor writes only within the generation mask and exports an audit report
- [x] protected-region pixel-diff hard gate verified after lossless PNG write/read-back
- [ ] benchmark one complete edit loop against immutable BASE and human ground truth

## P3 — legacy skill migration

- [x] provenance-pinned REF snapshot: 81 UUID/L artifact IDs + 160 short aliases from 9 legacy source documents, with searchable context and unique-prefix resolution
- [ ] full historical binary asset materialization / donor suitability validation (UUIDs and proof IDs are still metadata references, not image bytes)
- [x] evidence-based skill planner with topology-first stop rules and candidate/human_verified distinction
- [x] independent 12-family, state-dependent upscale strategy portfolio (candidate planner only; non-imported methods remain blocked/conditional)
- [x] Grok Vision skill-defect diagnosis adapter + `ige diagnose-image` command (candidate-only; live API and gold-set accuracy not yet validated)
- [x] optional Siax 4x inference adapter (pinned hash; memory-efficient uint8 output canvas and tiled 128/8 default; actual run requires optional runtime, checkpoint and license review)
- [~] DETAIL6 partial execution path: Siax-master material-mask residual, face/skin/eye protection and q98/q100 4:4:4 exports; full GRID_CLEAN/BEAT donor selection + clarity proof still open
- [ ] complete REF ingestion/materialization for legacy image assets (UUIDs are not local binary assets)
- [ ] donor pipeline (ZYF/ETZ/SCD)
- [ ] identity-protected PATH1E plate + ECC executor
- [ ] garment reconstruction (TEX4/RRT/P_G)
- [ ] object accumulation (OBA)
- [ ] GRID×SIAX / SWP / SPM hybrid execution and project-specific clarity comparison
- [ ] SIAX R3 / S2.1: Nested Compute Tile + Virtual Master + staged RAM profile + true SPM-A (see docs/SIAX_R3_NESTED_PEEP_VIRTUAL_MASTER.md); do not treat S2 256/32 OOM as quality fail
- [ ] DETAIL6 native 4608/quality proof and human-reviewed clarity benchmark
- [ ] PIXEL_CTRL per-pixel classification and proof

## P4 — new-image and temporal generation

- master-first generation
- camera/identity/geometry anchors
- state-transition contracts and multi-frame validation

## Exit criteria

A phase is not complete because a document or demo exists. It requires executable tests, evidence outputs, reproducible fixtures, and explicit failure cases. No generated image is accepted solely because the model returns an image.


## S3 Heterogeneous Upscale Execution (2026-11)

- **S2.1 frozen** on PR #8 (`docs/SIAX_S2_1_FREEZE.md`): Integrity PASS · Quality INCONCLUSIVE · `final_acceptance=false`.
- **S3** isolated branch `feat/upscale-s3-heterogeneous-runner-v0.1`: capability scheduler · lease transport · model adapters · artifact integrity.
- S3 does **not** flip Nested quality or claim E3 speed.
- Design: `docs/S3_HETEROGENEOUS_UPSCALE_ENGINE.md`



## NFE · Next Frame Engine (2026-11-04)

- **Goal:** still-unit \(F_{t+1}=G(F_t,F_{t-1},K,\Delta S_t,C_t)\) I2I only.
- **Not:** I2V-as-G, optical-flow-as-generation, spatial EXTEND as time.
- **Scaffold:** `src/ige/nfe/*`, `tools/nfe_next_frame_pilot.py`, `docs/NEXT_FRAME_ENGINE_CHARTER.md`.
- **P0 milestone:** F0→F1→F2→F3 accept/reject — not 360fps claim.
- `quality_qualified=false`.
