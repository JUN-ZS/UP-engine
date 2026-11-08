# ComfyUI · Siax升清回位 — Peer-AI Handoff Pack

**READ THIS FIRST.** This pack IS the prior **Siax upscale → IGE geometry lock → return** line already pushed as UP-engine Draft PRs. It is **not** a new ComfyUI project.

Pack path in-repo: `docs/handoff/comfy-siax-return/`

---

## 1. Identity

| Item | Value |
|------|--------|
| Line | Desktop `高清探\` + `ComfyUI_IGE_GlobalLogicCoordinator` + UP-engine SHQ/IGE stack |
| Role | Geometry & permission authority over Comfy/Siax tiles; core-only return |
| Not | A greenfield Flux production pipeline |

Logical dependency (docs/guidance → runtime):

- [#12](https://github.com/JUN-ZS/UP-engine/pull/12) — AI Guide / Program Guidance / research (base: `main`; **logic** dependency, not Git parent of #17)
- [#17](https://github.com/JUN-ZS/UP-engine/pull/17) — Method Registry / Skill Router / S0–S7 gates
- [#18](https://github.com/JUN-ZS/UP-engine/pull/18) — Static audit + evidence chain (disk capture, S6 ledger, Noise Synthetic≠Live)
- [#20](https://github.com/JUN-ZS/UP-engine/pull/20) — Agent Driver (`ige agent-run`; audited callables only)
- [#21](https://github.com/JUN-ZS/UP-engine/pull/21) — Comfy Cloud HTTP adapter (diagnostic path)
- [#22](https://github.com/JUN-ZS/UP-engine/pull/22) — SHQ geometry ↔ Cloud tiles + **local** S6 core-only compositor

**Continuous Git feature stack:** `#17 → #18 → #20 → #21 → #22`  
**#12** remains a separate Draft vs `main` (keep logic dep; do not invent false ancestry).

Captured stack tip when this pack was published (verify live if later):

- PR #22 head branch: `feat/comfy-shq-geometry-locked-runtime-v0.1`
- PR #22 tip SHA: `2d5977abd02cb1fcd472217455ab833183f4afe7`
- Flux / `FLUX_HR_TILE_IMG2IMG`: still **`workflow_candidate`**
- Driver: **`execution_allowed=false`** until explicit human authorize
- Core-only S6 ≠ cross-tile **semantic** continuity
- No Cloud GPU job in this docs PR; do not unlock Flux

---

## 2. Live PC error (2026-11-09, Asia/Hong_Kong)

`IGE_GlobalLogicCompiler` → `ige_logic.core.ContractError`:

```text
Geometry canvas (5376, 3024) != source canvas (3862, 2172);
explicit coordinate transform required
```

| Side | Size (W×H) | Provenance |
|------|------------|------------|
| Geometry JSON `source` | **5376×3024** | `object_geometry.provisional.json` → `city_scene_16mp_lanczos.png` (Pillow Lanczos **3×** from 1792×1008; SHA `f75d9d2f…943f8`) |
| IMAGE into node 300 | **3862×2172** | Live candidate found: `C:\Users\user\Documents\ComfyUI\output\ComfyUI_00001_.png` SHA `104b898b…110b` |

Ratio 3862/5376 ≈ **1.392 ≠ 3**. Do **not** assume Lanczos-3× alone explains the mismatch — verify full resize/crop/pad history.

**Forbidden:**

- Patch `ige_logic/core.py` / `compile_contract` to allow size mismatch
- Relabel JSON width/height without transforming every polygon / mask / ROI / landmark into that frame

**Required next step:** pick **one** canonical canvas; align Load Image / upscale output / geometry / masks / tile bounds to that frame; only then consider Global Noise / Shared Latent A·B·C (separate experiments).

---

## 3. PC paths (owner machine)

| What | Path |
|------|------|
| Work folder | `C:\Users\user\Desktop\高清探\` |
| Packaged IGE node (desktop) | `...\高清探\IGE_Global_Logic_Coordinator_v0.2\` |
| **Live installed** custom node | `C:\Users\user\Documents\ComfyUI\custom_nodes\ComfyUI_IGE_GlobalLogicCoordinator\` (`ige_logic\core.py` → `compile_contract`) |
| Comfy Desktop | port **8000**; RTX 3070 Ti **8GB** VRAM — prevent OOM (tile/VAE/FP8 offload; do not force full 5K+ Flux in one shot) |

---

## 4. Obligations for the other AI

1. **Grab this pack + local files** — do not invent a parallel Comfy/geometry stack.
2. If another node or helper program is required, **install/wire it** (or give exact install/wire steps and run them with the user) — not “should research” only.
3. **OOM guard** on 8GB: tile size, sequential decode, FP8, unload; fail closed with BLOCK rather than silent interpolate.
4. **Until authorized:** canvas alignment only; keep `workflow_candidate` / `execution_allowed=false`; no Flux production claim; no force-skip of geometry gates.
5. A/B/C noise/latent experiments are **after** GlobalLogic accepts matching canvases, and remain `diagnostic_only`.

---

## 5. What is in this pack

```text
docs/handoff/COMFY_SIAX_RETURN_PACK_README.md          ← you are here
docs/handoff/comfy-siax-return/
  BINARY_ASSETS_SHA_ONLY.json                          ← large images: filename+SHA+WxH+PC path only
  pc_高清探/                                           ← workflows, geometry, inventories, cloud JSON
  packages/
    IGE_Global_Logic_Coordinator_v0.2/                 ← desktop packaged node + tests/docs
    ComfyUI_IGE_GlobalLogicCoordinator/                ← LIVE install snapshot (Documents\ComfyUI\custom_nodes)
    IGE_S0_S7_MethodRegistry_v0.1/                     ← method registry contracts
    ige_workflow_v03/                                  ← v03 patch scripts / notes
```

Key PC files mirrored under `pc_高清探/`:

- `workflow_ige_v03_dev_fp8.json`, `workflow_ige_v03_dev_fp8_local.json`, `workflow_ige_v03_from_v02.json`
- `original_siax_with_ige_logic_coordinator_v0.2_dev_fp8_baseline.json`, `..._local.json`
- `object_geometry.provisional.json`
- `Geometry_Locked_Two_Tile_Flux_Refinement_CLOUD_v0.5.json`, `workflow_cloud_api_prompt_v0.5.json`
- `ASSET_SHA256_MANIFEST.json`, `ASSET_SHA256SUMS.txt`
- `model_inventory_capture_receipt.json`, `backend_model_inventory_partial.jsonl`
- tile task JSON, V05 summary, preflight / README notes

**Not committed (SHA-only):** `city_scene_16mp_lanczos.png` (~19MB), tiles, `source_original.jpg`, `ComfyUI_00001_.png` (3862×2172 mismatch candidate), other large media.

---

## 6. PR links

- https://github.com/JUN-ZS/UP-engine/pull/12  
- https://github.com/JUN-ZS/UP-engine/pull/17  
- https://github.com/JUN-ZS/UP-engine/pull/18  
- https://github.com/JUN-ZS/UP-engine/pull/20  
- https://github.com/JUN-ZS/UP-engine/pull/21  
- https://github.com/JUN-ZS/UP-engine/pull/22  

One-liner for peers: *Follow UP-engine #12→#22 and Desktop 高清探 Siax+IGE return; current blocker is canvas mismatch 5376 vs 3862 — fix alignment, do not bypass core.*

## Follow-on Draft patch: geometry preflight + resource gate

See [PREFLIGHT_RESOURCE_GUARD_V0.1.md](PREFLIGHT_RESOURCE_GUARD_V0.1.md) and the new `*_preflight.json` workflow variants. These add a fail-closed source/hash/geometry/authorization barrier before TTP/VAE/samplers and a conservative one-tile/free-memory admission gate. The existing source workflows remain unchanged. The one-tile gate intentionally BLOCKs the legacy all-tiles batch until a sequential tile runner is implemented; it is not an OOM-proof claim.
