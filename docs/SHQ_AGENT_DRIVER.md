# SHQ Agent Driver v0.1

## Purpose

This branch introduces a central Python control plane for AI-proposed SHQ work. The AI submits a manifest; Python re-reads files, verifies hashes and human evidence, resolves only reviewed callable entrypoints, and records the stage reached. The Driver never grants future edit permission.

## Commands

Plan only (default; no model inference):

    ige agent-run path/to/agent_run_manifest.json --out run/agent_run_report.json

Execute an explicitly eligible registered adapter:

    ige agent-run path/to/agent_run_manifest.json --execute --out run/agent_run_report.json

The current callable allowlist contains only the existing pinned Siax 4x adapter. FLUX_HR_TILE_IMG2IMG is always blocked while its Registry maturity is workflow_candidate; a static workflow audit, disk model capture or synthetic test cannot override this.

## Required evidence

The manifest schema is schemas/agent_run_manifest.schema.json. It binds:
- S0 source path and SHA-256
- S1 candidate-only READ receipt and human-verified topology state
- S2 human-verified coordinate canvas, its SHA-256, coordinate frame and independent model/object/tile parameters
- S3 human-reviewed permission, source/canvas binding, binary approved/protected masks and reviewer metadata
- S4 tile plan matching the geometry contract
- backend checkpoint SHA, pinned model SHA, and explicit license-review acknowledgement

The Driver checks that masks are binary, non-empty, disjoint and match the coordinate canvas dimensions. It also checks that the geometry canvas dimensions equal source dimensions × model scale. The current Siax adapter is restricted to exact 4x.

## Stage semantics

- S0–S4 PASS means evidence was re-read and verified by this process.
- S5 PASS means an allowlisted adapter actually ran and returned a matching output SHA. Siax emits a per-tile read/core trace; the Driver turns it into a Core/Halo ledger.
- S6 remains NOT_RUN. A separate compose/return audit must bind the ledger to S2's coordinate frame and canvas SHA and prove protected pixels.
- S7 remains NOT_RUN until an independent disk reload and human visual review occur.

The command never reports a candidate as accepted. Its post-execution state is S5_COMPLETE_AWAITING_S6_S7.

## Security boundary

Registry entrypoint strings are untrusted data. The Dispatcher does not eval or import arbitrary Registry strings. Each callable must be added to CALLABLE_ALLOWLIST in code and covered by tests. Unknown, documented-only, research-only, experimental and workflow-candidate methods are blocked.

## ComfyUI claim boundary

No ComfyUI execution is implemented by this Driver. It does not call a Comfy server, submit API prompts, or infer tiles. A later Comfy adapter must separately prove: live node inventory, loaded model hashes, true sampler-to-conditioning routes, coordinate-indexed global noise, instrumented core-only writes, and independent S7. Until all of those exist, Flux remains workflow_candidate.

## Comfy Cloud diagnostic adapter

The separate [Comfy Cloud adapter](./COMFY_CLOUD_LIVE_ADAPTER.md) can query the remote node/model catalog, audit the API graph and, only with explicit `--diagnostic-submit`, run a diagnostic-only Cloud job. That command is deliberately outside the production Callable Dispatcher.

A real Cloud job receipt is not a production method acceptance. FLUX remains `workflow_candidate` until coordinate-indexed global noise, weight identity evidence, exact-once core composition, protected-pixel S6 and independent S7 are all proven.
