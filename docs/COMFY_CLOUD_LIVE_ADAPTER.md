# Comfy Cloud live adapter v0.1

## Scope

This branch adds an actual Comfy Cloud HTTP client, remote node/model preflight, strict API graph audit, and an explicit diagnostic-only submit/poll/download path.

Cloud API protocol reference: [Comfy-Org official Cloud OpenAPI](https://github.com/Comfy-Org/docs/blob/main/openapi-cloud.yaml). Comfy Cloud documents `POST /api/prompt`, `GET /api/object_info`, `GET /api/experiment/models`, `GET /api/jobs/{job_id}`, and `GET /api/view`. The Cloud API is marked experimental; endpoint contracts may change.

## Credentials

Set `COMFY_CLOUD_API_KEY` in the local shell or environment used to run IGE. The key is never stored in:
- the manifest
- workflow JSON
- receipt JSON
- logs

Never commit or paste the key into chat. The adapter fetches signed Cloud output URLs without forwarding the API key to the signed object-storage host.

## Prepare the manifest from local files

No manual SHA copying is needed. From the repository root:

PowerShell:

```powershell
ige comfy-cloud-manifest --workflow fixtures/comfy/workflow_cloud_api_prompt_v0.5.json --tile 233=C:\\path\\to\\tile_left.png --tile 5000=C:\\path\\to\\tile_right.png --out runs/comfy_cloud_run.json
```

The command checks that both node IDs are `LoadImage` nodes, reads the local image bytes, computes SHA-256, and writes a `diagnostic_only=true` manifest. It refuses to create a manifest for an incorrect node binding.

## Preflight

```powershell
$env:COMFY_CLOUD_API_KEY = "YOUR_COMFY_CLOUD_API_KEY"
ige comfy-cloud-preflight runs/comfy_cloud_run.json --out runs/comfy_preflight.json
```

The manifest schema is `schemas/comfy_cloud_run_manifest.schema.json`. It binds every tile input to an explicit LoadImage node and local SHA-256.

Preflight calls the Cloud API to obtain the live object_info catalogue and model folder/model listings. It verifies:
- every workflow node class exists on the Cloud runtime
- all API node references resolve
- each SamplerCustomAdvanced route traverses BasicGuider → FluxGuidance → CLIPTextEncode
- each tile prompt includes an explicit tile ID and global origin
- referenced model filenames exist in Cloud's model catalogue

Cloud's model catalogue supplies filenames/metadata, not cryptographic weight SHA or loaded-tensor hashes. Therefore the adapter cannot claim exact model-weight parity from filename presence alone.

## Diagnostic run

```powershell
ige comfy-cloud-diagnostic runs/comfy_cloud_run.json --diagnostic-submit --timeout 1800
```

This explicit command uploads the bound tile images, submits one workflow job, polls the job, downloads all output images and writes a receipt. It may consume Comfy Cloud credits. The separate `--diagnostic-submit` flag and `diagnostic_only=true` manifest are both required.

The diagnostic path may run even when the current workflow has unresolved gates, but stamps every receipt as:
- `diagnostic_only=true`
- `candidate_accepted=false`
- `execution_allowed=false`
- maturity remains `workflow_candidate`

This is deliberately separate from the production Dispatcher.

## Current known blockers

The checked-in API workflow still fails production acceptance:
1. both samplers reference the same RandomNoise node and seed; this is not proof of a coordinate-indexed global noise tensor or overlap equality
2. the workflow saves separate tile images but has no verified exact-once Core/Halo compositor producing a final master
3. the Cloud model catalogue does not prove exact model weight SHA / loaded tensor identity
4. S7 independent reload and human review are not part of this adapter

Therefore live preflight must report `BLOCKED_WORKFLOW_CANDIDATE`. A diagnostic Cloud job can show that the workflow executes and produce real tile candidates, but cannot promote Comfy/Flux or mark geometry accepted.

## Evidence language

- **Live observed:** Cloud object_info, model filenames, job ID/status, output file bytes and SHA captured by the adapter.
- **Derived:** graph route structure and image SHA values calculated from the downloaded/local bytes.
- **Unknown:** Cloud's actual loaded model weight hash and global noise tensor semantics where the API exposes no suitable proof.
- **Not performed:** S6 exact-once core compositor and S7 independent human acceptance.

No mock test or static audit is labelled as live GPU inference.


## Current execution boundary

A successful diagnostic run is a real Cloud job with downloaded image bytes and hashes. It is not a geometry-locked master. Current hard blockers remain global coordinate-indexed noise, a verified exact-once core compositor, and weight/loaded-tensor SHA evidence. The API is experimental and Cloud credits may be consumed by the diagnostic command.
