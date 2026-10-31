# Roadmap

## P0 — contract-first foundation (completed scaffold)

- typed task and asset roles
- PEEP manifest schema and validator
- state-aware, fail-closed router
- hard gates separated from soft quality
- CI and deterministic tests

## P1 — READ engine (v0.2 executable; inference still partial)

- [x] source provenance, EXIF orientation, raster diagnostics
- [x] region semantic_type independent from editable/protected permission
- [x] tagged object/context/identity-anchor/contact-surface regions
- [x] safe mask law: editable whitelist; all other pixels effectively protected
- [x] preview PNG, per-region masks and machine-readable READ report
- [x] optional SAM3 text segmentation provider adapter; candidates stay unreviewed
- [x] typed relation graph with candidate/human_verified/rejected states
- [x] contacts_at requires both named surfaces; part_of cycles rejected
- [ ] interactive image annotation and relation-review UI
- [ ] VLM reasoner for candidate occlusion/contact/part relations with visual evidence
- [ ] benchmark against human-corrected masks and relation annotations on the actual project image set

## P2 — one end-to-end reconstruction path

- crop/context-ring generation
- one image-edit adapter behind the provider interface
- registration and transform manifest
- protected-region compositor
- hard-gate report and baseline benchmark

## P3 — skill migration

- donor pipeline (ZYF/ETZ/SCD)
- garment reconstruction (TEX4/RRT/P_G)
- object accumulation (OBA)
- detail stack (SWP/SPM/SIAX) only after topology gate

## P4 — new-image and temporal generation

- master-first generation
- camera/identity/geometry anchors
- state-transition contracts and multi-frame validation

## Exit criteria for each phase

A phase is not complete because a document or demo exists. It requires executable tests, evidence outputs, reproducible fixtures, and explicit failure cases.
