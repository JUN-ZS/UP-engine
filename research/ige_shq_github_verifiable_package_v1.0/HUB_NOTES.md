# Hub notes — IGE_SHQ_GitHub_Verifiable_Package (v1.1 Complete13Assets)

**Status:** research-only reference implementation. **Not** wired into `src/ige` production.

**Folder name:** `research/ige_shq_github_verifiable_package_v1.0/` (kept for PR continuity).  
**Content version:** **v1.1 Complete13Assets** — full **13** image assets including Geometry-Locked donors `B0_GL` + `B2_GL`, `assets/asset_manifest.json`, and `preflight_check.py`.

**Zip artifacts in this folder:**
- `IGE_SHQ_GitHub_Verifiable_Package_v1.1_Complete13Assets.zip` (canonical complete package)
- `IGE_SHQ_GitHub_Verifiable_Package_v1.0.zip` (same bytes / continuity name)

**Provenance:** Gemini share [`XMyk6HVn2J9S`](../../docs/sources/gemini-share-XMyk6HVn2J9S/). Earlier Hub ZIP SHA-256 `5ef8601d…` was incomplete relative to the Geometry-Locked preflight contract.

## Historical blocker (candidate / incomplete ZIP)

An earlier attached candidate lacked `B0_GL`, `B2_GL`, bundled `preflight_check.py` / `requirements.txt`, and a complete manifest. Hub preflight correctly returned **BLOCK** (exit 2). Do **not** substitute `B0_UPPER` / `B2_FULL` for Geometry-Locked donors.

## Why previous ZIP missed B0_GL / B2_GL

**Root cause — FUSE / virtual FS `Path.rglob` directory-entry cache:** after writing new Geometry-Locked donors, direct `cv2.imread(path)` could read the new files, but packaging via `Path.rglob("*")` still saw a **stale** directory listing (first ~10 images). The published ZIP therefore omitted:

- `assets/s4_self_part_hr_b0_geometry_locked_1200x896.jpg` (`B0_GL`)
- `assets/s4_self_part_hr_b2_geometry_locked_1200x896.jpg` (`B2_GL`)

**Fix:** rebuild on native `/tmp`, include all 13 JPGs + `asset_manifest.json` + `preflight_check.py`, then re-verify from a **fresh blank extract** before publishing.

## Anti-spoofing (Geometry-Locked donors)

| Asset | Role | SHA-256 (prefix) | Must differ from |
|-------|------|------------------|------------------|
| `s4_self_part_hr_b0_geometry_locked_1200x896.jpg` | `B0_GL` | `bf9c57e884f9ce8f…` | `B0_UPPER` (`234b3eb7ad8bd672…`) |
| `s4_self_part_hr_b2_geometry_locked_1200x896.jpg` | `B2_GL` | `deac10fc09dd2859…` | `B2_FULL` (`c389e0e439d86384…`) |

`preflight_check.py` enforces existence, decode, exact dimensions, exact SHA-256, and **B0_GL ≠ B0_UPPER** / **B2_GL ≠ B2_FULL**. Failure → `status=BLOCK`, **exit code 2**.

## Hub verification (v1.1 on this PR)

Fresh extract: `/tmp/clean_verify_v1.1` (not FUSE-cached packaging). Deps: `opencv-python-headless`, `numpy`.

| Command | Result |
|---------|--------|
| `python3 preflight_check.py` | **PASS** · exit **0** · 13/13 |
| `python3 registry/validate_registry.py registry/method_registry.json` | **PASS** · exit **0** · 22 methods |
| `python3 -m unittest discover -s tests -v` | **OK** · exit **0** |
| `python3 run_all_verifications.py --strict` | **PASS** · exit **0** · 8/8 · `accept_full_hd=true` |

**Runtime boundary:** verifies donor windowing, dense registration, \(L+M+H\), Rule 01380 return, S7 disk reverse QA. Does **not** invoke live Siax/NCNN or ComfyUI/Flux — do not claim live diffusion.

## Companion modular toolkit

[`../ige_shq_modular_methods_toolkit_v2.0/`](../ige_shq_modular_methods_toolkit_v2.0/) — M01–M22 + R01–R03 + `invoke_method.py` (research-only).

## Docs

- Package runbook: [`SHQ_OTHER_AI_STEP_BY_STEP_RUNBOOK.md`](./SHQ_OTHER_AI_STEP_BY_STEP_RUNBOOK.md) (Fail-Closed 1→8)
- Hub AI guide: [`docs/SHQ_AI_USAGE_GUIDE.md`](../../docs/SHQ_AI_USAGE_GUIDE.md) §9 / §10
- Program guidance: [`docs/SHQ_OBJECT_GEOMETRY_LOCK_PROGRAM_GUIDANCE.md`](../../docs/SHQ_OBJECT_GEOMETRY_LOCK_PROGRAM_GUIDANCE.md) §10.6
- External AI runbook (hub copy if present): [`docs/SHQ_OTHER_AI_STEP_BY_STEP_RUNBOOK.md`](../../docs/SHQ_OTHER_AI_STEP_BY_STEP_RUNBOOK.md)
