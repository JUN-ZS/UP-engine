# Hub notes — IGE_SHQ_GitHub_Verifiable_Package_v1.0

**Status:** research-only reference implementation. **Not** wired into `src/ige` production.

**Provenance:** Gemini share [`XMyk6HVn2J9S`](../../docs/sources/gemini-share-XMyk6HVn2J9S/) (battlefield self-part / dense registration / five-layer package turn; continues nutr + hC9 packs). The Hub-stored ZIP has its own historical SHA-256: `5ef8601d818c4ffb05b1fb25182cee600668be71ccd021d5d5065f4c84f4ba1c`. It is **not** byte-identical to the separately attached candidate ZIP audited below.

**What this is:** portable five-layer Python package (`src/ige_shq/l0`→`l4`) + relative-path assets + Method Registry + unit tests + one-command runner. External AI/engineer can unzip (or clone this tree) and run:

```bash
python3 registry/validate_registry.py registry/method_registry.json
python3 run_all_verifications.py --strict
```

**Stored Hub report:** records registry PASS (22 methods), **12/12** runner unit tests, **8/8** strict stage gates and `exit_code = 0`. Treat this as historical evidence; every external AI must run a fresh `preflight_check.py` and `run_all_verifications.py --strict` and hash the newly generated outputs.

**Three DEBUG root causes fixed in this package (vs earlier single-script fossils):**

1. Upper-only self-part crop applied to full-body bbox → add `B0_LOWER` / `B1_LOWER` so 5 HR plates cover P01–P18.
2. Coarse whole-character scale without per-part dense registration → Layer 3 `matchTemplate` + Farneback optical flow per part.
3. Hardcoded absolute `/working_dir/...` paths → five relative-path modules + portable runner.

**Layer map (quick):** L0=S0 four-way anti-hole → L1=S1/S2 18-part + geometry lock → L2=S3 permission + registry → L3=Skills A/B/C dense reg + \(L+M+H\) → L4=Skill D Rule 01380 return + S7 disk reverse QA.

**External candidate ZIP audit (2026-11-08):** attached SHA-256 `6f13bd5c45f99db1541f236991dbd9e07d7bb637f9d02138563f85ff7f63b2e8`. All 10 baseline asset hashes match. Hub preflight returns `BLOCK` (exit 2): the ZIP lacks the newly required `preflight_check.py`, `requirements.txt`, both geometry-locked HR images (`assets/s4_self_part_hr_b0_geometry_locked_1200x896.jpg` and `assets/s4_self_part_hr_b2_geometry_locked_1200x896.jpg`) and `assets/geometry_locked_hr_manifest.json`. Registry validation passes (22 methods) and package Registry tests pass (4/4), but its `--strict` run fails at L3. Do not substitute `B0_UPPER` / `B2_FULL`, do not silently resize, and do not promote this ZIP over the Hub baseline until the exact files and `assets/geometry_locked_hr_manifest.json` with real SHA-256 / 1200×896 evidence are committed.

**External AI instructions:** [`docs/SHQ_OTHER_AI_STEP_BY_STEP_RUNBOOK.md`](../../docs/SHQ_OTHER_AI_STEP_BY_STEP_RUNBOOK.md). Preflight script: [`preflight_check.py`](./preflight_check.py). Pinned dependencies: [`requirements.txt`](./requirements.txt).

See also: [`docs/SHQ_AI_USAGE_GUIDE.md`](../../docs/SHQ_AI_USAGE_GUIDE.md) §9; [`docs/SHQ_OBJECT_GEOMETRY_LOCK_PROGRAM_GUIDANCE.md`](../../docs/SHQ_OBJECT_GEOMETRY_LOCK_PROGRAM_GUIDANCE.md) §10.6; package [`README.md`](./README.md).
