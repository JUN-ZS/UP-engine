# v0.5 Fix — Runtime-bound LoadImage inputs

## What failed in v0.4
The live Cloud `/api/object_info` schema exposed `LoadImage.image` choices before the two tile files had been uploaded. The API workflow JSON contains local placeholders `tile_left.png` and `tile_right.png`. The old generic dropdown validator compared those local placeholders with the current Cloud image dropdown and incorrectly reported them missing. The model inventory and API authentication had already passed. No GPU job was queued.

## Correct stage boundary
1. **Read-only preflight:** authenticate; check Cloud core-node classes and input-field declarations; check exact model categories; verify both local tile files exist and match the bundle SHA/dimensions; verify only the two configured `LoadImage.image` slots are runtime-bound. Do not upload, submit or consume credits.
2. **Execute:** upload each tile via `POST /api/upload/image` with `type=input`; require successful response and returned `name`; bind only that returned name into the corresponding `LoadImage.image` field; then submit `/api/prompt`.
3. **Server validation:** the final prompt submission is the authoritative check that the uploaded Cloud names can be loaded. If Cloud rejects the prompt or returns node errors, stop and retain response/logs.

## Narrow exemption
The preflight validator skips dropdown membership only for exact runtime-bound `(node_id, field)` pairs declared in `pc_bot_config.json`:
- `233.image` ← `tile_left.png`
- `5000.image` ← `tile_right.png`

It still verifies the `LoadImage` node exists and the `image` field is declared. Every other workflow dropdown remains subject to strict membership validation. Missing local tiles or hash/dimension mismatches still fail before execute.

## Regression proof
`fake_comfy_cloud_api_test.py` now simulates a Cloud LoadImage dropdown containing only an unrelated previously uploaded image. The read-only preflight must pass with both runtime inputs deferred, must make zero image uploads and zero workflow submissions. Execute must upload both tiles, substitute the Cloud-issued names, submit once and retrieve two outputs. This is a mock API regression test, not live GPU inference.
