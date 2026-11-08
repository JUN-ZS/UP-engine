# Build / smoke evidence — 2026-11-08

## Input archive

- Uploaded source file: `IGE_SHQ_Modular_Methods_Toolkit_v2.0 (2).zip`
- SHA-256: `28a48d49ca71adf4ec7bd5e51f45bf3682fb76230d1e50f56e4054ff28b86664`
- Extracted the original 89-file source package directly from the uploaded ZIP. The original source files were not patched by this conversion.

## Environment used for this package smoke test

- Python: `3.13.5`
- NumPy: `2.3.5`
- OpenCV: `4.13.0`

## Executed in this build session

| Check | Result | Scope |
|---|---|---|
| `python grok_shq_runner.py --doctor` | Ran; status `BLOCKED` | Dependencies available; S3 approval and possible cache-pair blockers detected |
| `python grok_shq_runner.py --audit` | `READ_ONLY_CHECKS_PASS_EXECUTION_BLOCKED` | Preflight exit 0, 13/13 source images verified; Registry exit 0, 22 method IDs, 0 errors; no image-write methods invoked |
| `python grok_shq_runner.py --catalog` | Exit 0 | Method / recipe catalog readable |
| `python grok_shq_runner.py --info M12` | Exit 0 | Method metadata readable |
| `python grok_shq_runner.py --run M12` | Exit 3, expected | Launcher refused image-write execution because current source gate is unsafe |

The original uploaded ZIP includes a master JPG proof board and traceability JSON, but does not include a PNG at `outputs/SHQ_BATTLEFIELD_SELF_PARTS_4X_MASTER_5504x3072.png`. Therefore `--verify-master` is a post-generation helper and was not counted as a pass in this clean-source build.

## Source blockers identified

- `source/IGE_SHQ_GitHub_Verifiable_Package_v1.0/methods/common_runtime.py:127` hard-codes `human_verified=True`.
- `methods/common_runtime.py:130` reuses a master/report pair when both files exist, without validating all source hashes.
- `methods/common_runtime.py:898` writes a literal `"status": "PASS"` in the method receipt.

## Important non-claims

- No Grok account, Grok Bot cloud computer, Grok Canvas session, or Imagine generation job was accessed from this build environment.
- No live Imagine donor was generated.
- No M01–M22 write method or R01–R03 recipe was run by the new launcher.
- No Siax/NCNN or ComfyUI/Flux live inference was executed.
- The 13/13 and 22/0 results are current read-only checks only; they do not constitute 22 independent algorithm acceptance results.
