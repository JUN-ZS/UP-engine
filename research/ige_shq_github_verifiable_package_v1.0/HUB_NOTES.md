# Hub notes — IGE_SHQ_GitHub_Verifiable_Package_v1.0

**Status:** research-only reference implementation. **Not** wired into `src/ige` production.

**Provenance:** Gemini share [`XMyk6HVn2J9S`](../../docs/sources/gemini-share-XMyk6HVn2J9S/) (battlefield self-part / dense registration / five-layer package turn; continues nutr + hC9 packs). User-attached zip SHA-256: `5ef8601d818c4ffb05b1fb25182cee600668be71ccd021d5d5065f4c84f4ba1c`.

**What this is:** portable five-layer Python package (`src/ige_shq/l0`→`l4`) + relative-path assets + Method Registry + unit tests + one-command runner. External AI/engineer can unzip (or clone this tree) and run:

```bash
python3 registry/validate_registry.py registry/method_registry.json
python3 run_all_verifications.py --strict
```

**Hub verification (this PR):** with `opencv-python-headless` + `numpy` + `Pillow` in a venv: registry PASS (22 methods); **12/12** unittest OK; **8/8** stage gates PASS; `exit_code = 0`. Regenerated `outputs/SHQ_BATTLEFIELD_SELF_PARTS_4X_MASTER_5504x3072.png` kept as run evidence.

**Three DEBUG root causes fixed in this package (vs earlier single-script fossils):**

1. Upper-only self-part crop applied to full-body bbox → add `B0_LOWER` / `B1_LOWER` so 5 HR plates cover P01–P18.
2. Coarse whole-character scale without per-part dense registration → Layer 3 `matchTemplate` + Farneback optical flow per part.
3. Hardcoded absolute `/working_dir/...` paths → five relative-path modules + portable runner.

**Layer map (quick):** L0=S0 four-way anti-hole → L1=S1/S2 18-part + geometry lock → L2=S3 permission + registry → L3=Skills A/B/C dense reg + \(L+M+H\) → L4=Skill D Rule 01380 return + S7 disk reverse QA.

See also: [`docs/SHQ_AI_USAGE_GUIDE.md`](../../docs/SHQ_AI_USAGE_GUIDE.md) §9; [`docs/SHQ_OBJECT_GEOMETRY_LOCK_PROGRAM_GUIDANCE.md`](../../docs/SHQ_OBJECT_GEOMETRY_LOCK_PROGRAM_GUIDANCE.md) §10.6; package [`README.md`](./README.md).
