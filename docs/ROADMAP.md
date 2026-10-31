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

- donor pipeline (ZYF/ETZ/SCD)
- garment reconstruction (TEX4/RRT/P_G)
- object accumulation (OBA)
- detail stack (SWP/SPM/SIAX) only after topology gate

## P4 — new-image and temporal generation

- master-first generation
- camera/identity/geometry anchors
- state-transition contracts and multi-frame validation

## Exit criteria

A phase is not complete because a document or demo exists. It requires executable tests, evidence outputs, reproducible fixtures, and explicit failure cases. No generated image is accepted solely because the model returns an image.
