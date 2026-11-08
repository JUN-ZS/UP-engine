# IGE-SHQ — Execution Truth, Evidence Grade and Release Gates

## 1. Evidence grading

| Grade | Meaning | What it does not mean |
|---|---|---|
| `PASS_COMMAND_EXIT_0` | A command returned exit code 0 | The method is correct, independent, or visually accepted |
| `PASS_PREFLIGHT` | Source assets match expected manifest SHA and dimensions | Runtime generation was performed |
| `PASS_REGISTRY` | Registry schema / IDs validated | Method algorithms independently passed |
| `PASS_CONTRACT_ONLY` | Backend interface / anti-spoofing contract verified | Siax, NCNN, ComfyUI, Flux or a GPU backend executed |
| `PASS_SYNTHETIC` | A synthetic/demo case passed | Real user data or unseen scene generalizes |
| `PASS_SHARED_PIPELINE` | A method wrapper consumed a result from shared pipeline context | This method independently computed/verified its claimed function |
| `PASS_INDEPENDENT` | The criterion passed on independent holdout data with source, target, and test evidence | Universal generalization beyond that holdout |
| `BLOCKED` | A mandatory precondition is missing | An algorithm failed; it has not been tested |
| `FAIL` | A real assertion or execution failed | Other unrelated methods failed |

The Canvas and Grok Chat report must use these grades. Never condense every result to a single PASS badge.

## 2. Findings from the uploaded source package

These are source-code audit findings, not guesses about future patched behavior.

| Area | Observed in source | Consequence |
|---|---|---|
| M01–M22 wrappers | Each method wrapper delegates to `methods.common_runtime.execute_core_role()` | 22 method IDs / entrypoint files, but not 22 independent algorithm engines |
| Shared context | `get_shared_pipeline_context()` computes/caches L0–L4; subsequent wrappers can reuse it | One shared result may be decorated with multiple method receipts |
| Receipt status | `execute_core_role()` writes literal `"status": "PASS"` | A PASS receipt is not necessarily derived from that method's acceptance assertions |
| Recipe status | Recipes loop through method receipts and derive `all_pass` from each status string | Recipes are not yet a robust typed artifact DAG with verified output handoffs |
| S3 permission | Shared context calls `run_layer2_s3_human_permission_compiler(..., human_verified=True)` | Runtime bypasses the intended human-verification boundary |
| M11 | Code uses deterministic resize/filter operations (including Lanczos / bilateral / Gaussian / cubic); no live neural checkpoint is loaded | Do not call it actual neural SR inference without new backend wiring and model receipt |
| M12/M16 | Existing high-resolution donor assets are aligned with optical flow / remapping | This is donor-driven deterministic transfer, not live Imagine/Flux generation |
| M13 | Detail layer includes high-pass / tiling operations on a provided texture sheet | Do not present as a generative model call |
| M19 | Receipt says live Siax checkpoint is not loaded | Contract guard only |
| M20 | Receipt says live ComfyUI is not executed | Contract guard only |
| M07 | Implementation uses phase correlation; the name contains ECC but source does not call `findTransformECC` | Rename or implement real ECC, then test it |
| M09 | Some topology state/route metrics are static declarations rather than demonstrated broken-topology negative tests | Needs adversarial input that proves fail-closed routing |
| M10 | Inpaint branch uses a synthetic occlusion demo | Mark demo/synthetic; do not claim automatic content-aware occlusion routing is proven |
| M21 | Coverage gap / halo-write metrics include literal constants rather than measured real tile file I/O | Not yet proof of a production tile read/write compositor |
| M22 | Some alpha metrics are constants; boundary ring can be changed by deterministic pattern injection | Not proof of native alpha preservation or AI-generated boundary detail |
| Cache | Existing master PNG + report can be reused without validating all input asset hashes against the report | Stale result risk; use a content-addressed cache key |

## 3. Source-level changes required before image-write execution

### Gate A — S3 human authority

Replace the hard-coded boolean with a verifiable approval artifact. Minimum schema:

```json
{
  "schema": "ige-shq-human-approval/1.0",
  "reviewer_id": "human-controlled identifier",
  "approved_at_utc": "ISO-8601 timestamp",
  "scope": "single_part | part_set | full_scene",
  "approved_part_ids": ["B1_P08_GOLDMESH_CARBON_TORSO"],
  "source_keep_sha256": "...",
  "source_remove_sha256": "...",
  "mask_sha256": "...",
  "preserve_mask_sha256": "...",
  "decision": "APPROVE",
  "signature": "detached signature or independently verifiable approval proof"
}
```

The verifier must check signature, scope, current source SHA, current mask SHA, timestamp and approved parts. Missing, stale, mismatched, or unsigned approval => `BLOCK`. One part approval must not authorize every part.

### Gate B — Content-addressed cache

Cache identity should include at minimum:

`SHA256(canonical_json({source_asset_sha256s, registry_sha256, code_version, params, model_sha256s, backend_ids}))`

Reusing a cache requires verifying the exact output SHA and every source hash. Any mismatch => recompute or BLOCK. Existing output/report presence alone is not sufficient.

### Gate C — Method status from real assertions

Each method must declare:

- exact input artifact IDs + SHA;
- the computation actually performed;
- output artifact IDs + SHA;
- acceptance assertions and measured values;
- holdout / synthetic / production evidence grade;
- backend and model/checkpoint identity, if applicable.

A method must return `BLOCKED` if required metric is absent. `PASS` must not be a string literal independent of metrics.

### Gate D — Recipe as typed dataflow DAG

Each recipe step consumes a typed prior output, validates schema and SHA, and emits its own artifact plus receipt. A successful upstream status string is not enough. If any required assertion fails, downstream image writes stop.

### Gate E — Genuine backend and algorithm labels

- M11 either loads a named neural checkpoint / runtime and records its SHA, or is renamed to deterministic interpolation/filter base.
- M07 either calls actual ECC with a test proving its convergence criteria, or is renamed to phase-correlation alignment.
- M09 needs a negative topology test proving high-frequency operations are actually blocked.
- M10 must label the test synthetic until real occlusion detection and routing are demonstrated.
- M19/M20 stay `PASS_CONTRACT_ONLY` until real Siax/NCNN or ComfyUI/Flux execution evidence is attached.
- M21 requires actual tile input/output artifacts, measured core coverage, halo isolation, and bit-exact outside-ROI checks.
- M22 must measure a real alpha channel if alpha preservation is claimed; remove synthetic checkerboard edge alteration from the acceptance metric; compare against independent geometry/texture references.

## 4. Alternative architecture if a monolithic M01–M22 runner is the wrong abstraction

1. **Typed artifact DAG** — M IDs are user-facing capability names; each real operation has an implementation ID; each output artifact carries schema, dimensions, coordinate frame, permission scope and SHA. This provides traceability and supports independent backends.
2. **Backend adapter layer** — deterministic OpenCV, local Siax/NCNN, ComfyUI/Flux, and Imagine donor generation are separate adapters with explicit availability checks. Missing backend means `BLOCKED`, not silent interpolation fallback.
3. **Human-authority service** — S3 permissions are separate from image enhancement. Review artifacts are signed, scoped per part and bound to exact source/mask hashes. The image pipeline cannot grant its own permission.

These replace the current assumption that one shared context and 22 receipts imply 22 separately validated methods.
