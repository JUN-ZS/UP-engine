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

- [x] curated provenance-pinned reference metadata snapshot + REF Resolver / search CLI (initial seed only; full legacy catalog crawl remains open)
- [x] evidence-based skill planner with topology-first stop rules and candidate/human_verified distinction
- [x] Grok Vision skill-defect diagnosis adapter + `ige diagnose-image` command (candidate-only; live API and gold-set accuracy not yet validated)
- [x] optional Siax 4x inference adapter (pinned hash; actual run requires optional runtime, checkpoint and license review)
- [~] DETAIL6 partial execution path: Siax-master material-mask residual, face/skin/eye protection and q98/q100 4:4:4 exports; full GRID_CLEAN/BEAT donor selection + clarity proof still open
- [ ] complete REF ingestion/materialization for legacy image assets (UUIDs are not local binary assets)
- [ ] donor pipeline (ZYF/ETZ/SCD)
- [ ] identity-protected PATH1E plate + ECC executor
- [ ] garment reconstruction (TEX4/RRT/P_G)
- [ ] object accumulation (OBA)
- [ ] GRID×SIAX / SWP / SPM hybrid execution and project-specific clarity comparison
- [ ] DETAIL6 native 4608/quality proof and human-reviewed clarity benchmark
- [ ] PIXEL_CTRL per-pixel classification and proof

## P4 — new-image and temporal generation

- master-first generation
- camera/identity/geometry anchors
- state-transition contracts and multi-frame validation

## Exit criteria

A phase is not complete because a document or demo exists. It requires executable tests, evidence outputs, reproducible fixtures, and explicit failure cases. No generated image is accepted solely because the model returns an image.
