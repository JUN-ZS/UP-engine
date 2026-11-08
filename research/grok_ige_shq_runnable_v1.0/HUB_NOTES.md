# Hub notes — GROK_IGE_SHQ_RUNNABLE_v1.0

**Status:** research-only. **Not** wired into `src/ige` production.

**What it is:** Grok AI × Imagine × Canvas **ops layer** over the IGE-SHQ modular / verifiable stack. Original package tree is preserved unmodified under `source/IGE_SHQ_GitHub_Verifiable_Package_v1.0/`. New top-level pieces: `grok_shq_runner.py`, `README_GROK_START_HERE.md`, and `docs/` (Chat master prompt, Canvas board, Imagine prompts, Bot execution, Execution Truth & Gates).

**Zip (sibling in this folder):** `GROK_IGE_SHQ_RUNNABLE_v1.0.zip`  
**ZIP SHA-256:** `310c15d986885bbaa8e33c2ab37516367391cc4156e22a23a4ca859083912a11`

## Role split (do not collapse into one executor)

| Surface | Role | Runs M01–M22 / R01–R03? |
|---------|------|-------------------------|
| **Grok AI (Chat)** | Orchestration: read pack, pick steps, analyze receipts, propose code fixes | Only if the session truly has code execution; chat alone ≠ local Python |
| **Imagine** | High-res material donors (gold mesh, carbon, white titanium, copper coils, micro-detail) | **No** — image gen/edit only |
| **Canvas** | Project board: five-layer map, method list, SHA, test results, acceptance, fix proposals | **No** — document surface only |
| **Grok Bot / Python runtime** | Unzip, install OpenCV, run `grok_shq_runner.py`, emit JSON receipts | **Yes** — terminal + filesystem required |

Imagine and Canvas do **not** execute the 22 Python methods.

## Hub first-round commands (venv Python; write gate kept BLOCKED)

Run from this folder after recreating a venv (see below):

```bash
python grok_shq_runner.py --doctor
python grok_shq_runner.py --audit
python grok_shq_runner.py --catalog
python grok_shq_runner.py --info M12
```

| Command | Exit | Result (2026-11-08 Hub box) |
|---------|------|------------------------------|
| `--doctor` | **0** | cv2 OK; `execution_gate` **BLOCKED** (expected) |
| `--audit` | **0** | `READ_ONLY_CHECKS_PASS_EXECUTION_BLOCKED`; preflight **13/13 PASS**; registry **22** methods PASS, `errors=[]` |
| `--catalog` | **0** | M01–M22 + R01–R03 listed |
| `--info M12` | **0** | `SKILL_B_GEOMETRY_LOCKED_MATERIAL_GEN` |

**Do not** enable `--run` / recipe write paths on Hub until S3 / cache / receipt repairs land. The runner intentionally returns `BLOCKED` for write methods.

## Why write execution is intentionally BLOCKED

`source/.../methods/common_runtime.py` (as shipped in this pack) has three trust issues the runner refuses to bypass:

1. **Hardcoded `human_verified=True`** (≈ line 127) — no real human-approval credential / S3 evidence.
2. **Cache reuse without content-addressed source SHA** (≈ line 130) — may reuse existing master/report without full provenance hashing.
3. **Fixed `PASS` method receipts** (≈ line 898) — receipt status is a literal PASS, not an independent acceptance measurement.

`grok_shq_runner.py` therefore opens read-only doctor / audit / catalog / info / donor-register / verify-master paths, and keeps `--run` / `--recipe` blocked until those are fixed.

## Recreate venv (Hub tree excludes `.venv/`)

`.venv/` is **not** committed (disk + reproducibility). Recreate:

```bash
cd research/grok_ige_shq_runnable_v1.0
python3 -m venv .venv
.venv/bin/pip install -U pip
# Prefer package requirements if present under source; OpenCV is required for preflight/doctor:
.venv/bin/pip install opencv-python-headless
# If source ships requirements.txt:
# .venv/bin/pip install -r source/IGE_SHQ_GitHub_Verifiable_Package_v1.0/requirements.txt
.venv/bin/python grok_shq_runner.py --doctor
```

## Related research trees

- Verifiable L0–L4 package: [`../ige_shq_github_verifiable_package_v1.0/`](../ige_shq_github_verifiable_package_v1.0/) (v1.1 Complete13Assets)
- Modular M01–M22 toolkit: [`../ige_shq_modular_methods_toolkit_v2.0/`](../ige_shq_modular_methods_toolkit_v2.0/)

Ops entry docs in this pack: `README_GROK_START_HERE.md`, `docs/GROK_BOT_EXECUTION.md`, `docs/EXECUTION_TRUTH_AND_GATES.md`.
