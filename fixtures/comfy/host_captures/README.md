# Host captures (not CI-produced)

These JSON files were produced by running `ige capture-model-inventory` on a named host.
CI unit tests do **not** re-read the host disk; they use tiny temp files only.
`inventory_live_verified` in a checked-in audit snapshot is historical host evidence, not a standing CI claim.

- `DESKTOP-GNMQ0PF_2026-11-08_model_inventory_capture_receipt.json` — disk_capture of Dev FP8 + Siax
- `DESKTOP-GNMQ0PF_2026-11-08_static_audit_with_capture.json` — audit with that receipt; execution_allowed=false
