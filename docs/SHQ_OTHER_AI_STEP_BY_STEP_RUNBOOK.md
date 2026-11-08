# SHQ / IGE — Other-AI Step-by-Step Runbook

**Purpose:** let another AI agent clone the Hub branch, check the package, run each stage, and return verifiable evidence without guessing, substituting assets, or claiming a stale report as a fresh run.

**Normative order:** `SHQ_INDEX.md` → `SHQ_OBJECT_GEOMETRY_LOCK_PROGRAM_GUIDANCE.md` → `SHQ_AI_USAGE_GUIDE.md` → this runbook → package README / code / registry.

**Current Hub branch:** `feat/shq-geometry-lock-program-guidance-v0.1` (PR #12, Draft; do not merge to `main`).

---

## 0. Identify which package you have before running

There are two different artifacts that have both been called `IGE_SHQ_GitHub_Verifiable_Package_v1.0`. Do not assume they are byte-identical.

| Artifact | What it contains | Current status |
|---|---|---|
| **Hub expanded baseline**: `research/ige_shq_github_verifiable_package_v1.0/` | Five HR self-part plates (`B0_UPPER`, `B0_LOWER`, `B1_UPPER`, `B1_LOWER`, `B2_FULL`), 10 hashed image assets, Registry, L0–L4 modules, tests, runner and stored reports | The Hub's stored traceability report records 12 unit tests and 8/8 strict checks PASS. Re-run it locally; the stored report is historical evidence, not a substitute for a fresh run. |
| **Newly attached ZIP inspected 2026-11-08** | Same 10 baseline assets, but its updated runner also references `B0_GL` and `B2_GL` whole-body geometry-locked HR images | **BLOCKED**: these two files are absent from the ZIP. Registry validation and its 4 package tests pass, but `run_all_verifications.py --strict` fails in Layer 3 when `cv2.imread` returns `None`. ZIP SHA-256: `6f13bd5c45f99db1541f236991dbd9e07d7bb637f9d02138563f85ff7f63b2e8`. |

The two missing files are:

```text
assets/s4_self_part_hr_b0_geometry_locked_1200x896.jpg
assets/s4_self_part_hr_b2_geometry_locked_1200x896.jpg
```

Do **not** rename `B0_UPPER` to `B0_GL` or `B2_FULL` to `B2_GL`. They are not equivalent source images. Do not generate placeholder files, resize another plate, or edit the runner to silently fall back. Until the exact two images are committed and their SHA-256 values added to the manifest, the attached ZIP must remain `BLOCK` and must not replace the Hub baseline.

## 1. Clone the Hub branch

Run from a clean working directory:

```bash
git clone --depth 1 --branch feat/shq-geometry-lock-program-guidance-v0.1 --single-branch https://github.com/JUN-ZS/UP-engine.git
cd UP-engine/research/ige_shq_github_verifiable_package_v1.0
```

Do not use `main` as the run target: PR #12 is still Draft and intentionally not merged.

## 2. Create an isolated Python environment

Use Python 3.11–3.13. On Windows PowerShell:

```powershell
py -3.13 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

On macOS / Linux:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

The reference audit environment was Python 3.13.5, NumPy 2.3.5 and OpenCV 4.13.0.92.

## 3. Run fail-closed package preflight

```bash
python preflight_check.py
```

Expected for the Hub five-plate baseline: `status = PASS`, all 10 baseline assets match their registered SHA-256 values, and all required code files exist.

To inspect a separately extracted candidate ZIP without changing the Hub baseline:

```bash
python preflight_check.py --root /absolute/path/to/IGE_SHQ_GitHub_Verifiable_Package_v1.0
```

If the runner references `B0_GL` / `B2_GL`, preflight automatically requires the two extra geometry-locked files. Missing files or a hash mismatch return `BLOCK` and exit code `2`.

## 4. Validate the Method Registry

```bash
python registry/validate_registry.py registry/method_registry.json
```

Check the JSON output, not just the process message. Required conditions: `status=PASS`, `method_count=22`, `errors=[]`, and every method has `edit_permission=false` by default.

## 5. Run package-level unit tests

```bash
python -m unittest discover -s tests -v
```

Expected package-level result: `4/4` Registry schema tests pass. These tests validate Registry structure and policy; they do not prove the image pipeline or generation backend.

## 6. Run the complete five-layer pipeline

```bash
python run_all_verifications.py --strict
```

This is the only command in this package intended to run L0→L4 end-to-end and create a fresh master, board and traceability report. Do not copy an old report into the current run folder and present it as the result of this execution.

### Stage-to-Python map

| Stage | Entrypoint | Required evidence |
|---|---|---|
| L0 / S0 | `run_layer0_s0_four_way_anti_hole` | KEEP / REMOVE / DIFF / HOLE / anti-HOLE, frozen input SHA, complementary masks; `DIFF` never grants edit permission |
| L1 / S1–S2 | `run_layer1_s1_self_18part_decompose_read`; `run_layer1_s2_self_part_4x_geometry_lock` | 18-part partition, independent reference comparison, no sibling overlap, exact 4× coordinate transforms and five-parameter separation |
| L2 / S3 | `run_layer2_s3_human_permission_compiler` | Candidate vs human-approved permissions; edit and preserve masks disjoint; Registry loaded and validated |
| L3 / S4-A/B/C | `run_layer3_s4a_skill_a_neural_sr_base`; `run_layer3_s4b_s4c_self_part_material_and_detail` | Per-part HR source localization, dense optical-flow registration, L/M/H receipts and per-part metrics |
| L4 / S5–S7 | `run_layer4_s5_s6_s7_composite_return_and_reverse_qa` | Hard geometry return, Rule 01380, saved-PNG disk reread, independent reverse mask and S7 audit |

## 7. Verify fresh outputs

After a successful run, inspect these newly written files and their timestamps / hashes:

```text
outputs/SHQ_BATTLEFIELD_SELF_PARTS_4X_MASTER_5504x3072.png
outputs/SHQ_GITHUB_LAYERED_SELF_PART_VERIFICATION_BOARD.png
outputs/SHQ_GITHUB_LAYERED_TRACEABILITY_REPORT.json
```

In the fresh report, check at minimum:

```text
strict_diag_summary.strict_mode == true
strict_diag_summary.total_checks == 8
strict_diag_summary.unittest_total_ran == 12
strict_diag_summary.unittest_all_passed == true
strict_diag_summary.counts.PASS == 8
strict_diag_summary.counts.FAIL == 0
strict_diag_summary.counts.BLOCK == 0
strict_diag_summary.counts.WARN == 0
strict_diag_summary.counts.SKIP == 0
strict_diag_summary.accept_full_hd == true
strict_diag_summary.exit_code == 0
```

Also inspect `s5_s6_s7_return_and_reverse_qa_summary`: expected master dimensions `5504×3072`, 18 returned parts, `alpha_xor_pixels=0`, `soft_alpha_pixels=0`, `feather_px=0`, `max_outside_hole_rgb_diff_4x=0`, and reverse-QA / silhouette / boundary metrics. Verify the saved master's SHA-256 against the actual file on disk.

A `PASS` report without the corresponding newly written master, board and matching SHA is not a fresh acceptance.

## 8. Important capability boundary — what this package does and does not run

This package performs the five-layer image processing, part registration, frequency-layer transfer, geometry-locked composition and reverse QA using **already-generated HR self-part images supplied under `assets/`**.

The Python runner does not call Siax/NCNN, ComfyUI/Flux, Imagine or another live diffusion endpoint. Its `L_base` implementation includes OpenCV resizing / filtering; the material and detail layers consume pre-generated image donors. Therefore:

- It can be used to verify the self-part registration / transfer / return path against the bundled HR inputs.
- It does **not** by itself prove that an AI image-generation backend was invoked during this run.
- Do not describe the run as live ComfyUI / Flux tile diffusion, live Siax inference, native 8K generation, or an end-to-end generative model run unless a separate adapter log proves the actual backend, model/weight SHA, seed, parameters and generated output SHA.
- `detail_gain`, Sobel energy or frequency RMS alone are diagnostics; they do not establish semantic detail correctness.

This distinction is mandatory even when every package test passes.

## 9. Fail-closed behaviour

| Condition | Required action |
|---|---|
| Missing file / wrong SHA / wrong dimensions | `BLOCK`; do not substitute or resize silently |
| Registry schema invalid / unknown `method_id` | Stop before routing / writing |
| S3 permission not verified | Keep result as candidate; no mutation |
| Geometry / topology / identity gate fails | Stop downstream SR / material / detail for the affected part; return to the root cause |
| Runner exits non-zero | Record the exact stage and traceback; do not call the run PASS |
| Any WARN / SKIP / missing evidence | Do not count as PASS |
| S7 fails | Do not publish master as accepted; preserve failed outputs and receipts for diagnosis |

## 10. Required AI hand-back report

Every agent must return a compact machine-readable report containing:

```json
{
  "repository": "JUN-ZS/UP-engine",
  "branch": "feat/shq-geometry-lock-program-guidance-v0.1",
  "package_path": "research/ige_shq_github_verifiable_package_v1.0",
  "package_sha256": "<actual zip or tree artifact hash>",
  "environment": {"python": "...", "numpy": "...", "opencv": "..."},
  "preflight": "PASS|BLOCK",
  "registry": "PASS|FAIL",
  "unit_tests": {"passed": 0, "failed": 0, "skipped": 0},
  "pipeline": "PASS|FAIL|BLOCK|NOT_RUN",
  "exit_code": 0,
  "fresh_output_sha256": {
    "master": "...",
    "board": "...",
    "report": "..."
  },
  "backend_invoked": false,
  "claim_boundary": "pre-generated self-part donor transfer; no live generator invocation"
}
```

Use `NOT_RUN` when the full pipeline was not executed. Never turn a historical report, source-code claim, or pre-generated board into a current run receipt.

---

## Current attachment audit (2026-11-08)

Observed in this session against the newly attached ZIP:

- ZIP SHA-256: `6f13bd5c45f99db1541f236991dbd9e07d7bb637f9d02138563f85ff7f63b2e8`.
- Registry validator: `PASS`, 22 methods, zero schema errors.
- Package Registry tests: `4/4 PASS`.
- Full strict runner: `FAIL` in Layer 3 because `B0_GL` and `B2_GL` are referenced but absent; `cv2.imread` returns `None`, followed by a `NoneType` subscript error.
- The ZIP's stored report records 8/8 PASS and 12 tests, but that report was not reproducible from the attached archive in this audit.

This audit supersedes any assumption that the newly attached ZIP is already a complete, runnable replacement for the Hub baseline.

---