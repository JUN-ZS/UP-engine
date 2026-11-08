# UP-engine

A standalone image generation and reconstruction engine.

The initial implementation is being prepared in the isolated `bootstrap/initial-engine-scaffold` branch and will be proposed through a draft pull request. `main` is intentionally kept minimal until that review is complete.

## Object geometry lock (docs)

Program guidance for **object-geometry-locked** upscaling (not naïve tile / Lanczos sharpening):

- Start here: [`docs/SHQ_INDEX.md`](docs/SHQ_INDEX.md)
- Other AI: [`docs/SHQ_OTHER_AI_STEP_BY_STEP_RUNBOOK.md`](docs/SHQ_OTHER_AI_STEP_BY_STEP_RUNBOOK.md) — clone, preflight, run L0→L4, verify S7 and report SHA evidence
- Contract: [`docs/SHQ_OBJECT_GEOMETRY_LOCK_PROGRAM_GUIDANCE.md`](docs/SHQ_OBJECT_GEOMETRY_LOCK_PROGRAM_GUIDANCE.md)
- Research fossils (not production-wired): [`research/shq_v9/`](research/shq_v9/)
