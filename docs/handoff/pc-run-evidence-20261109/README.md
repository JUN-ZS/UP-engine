# PC Run Evidence 2026-11-09 — Peer AI 驗證包

**先讀呢份。** 呢個 pack 係 **本地 ComfyUI 實跑證據**（console log + operator 確認嘅 A/B 出圖），畀另一個 AI 對照 PR #25 preflight／BudgetGuard 行為。  
**唔係** Flux promote、**唔係** merge `main`、**唔係** 完成 sequential tile runner。

Pack path: `docs/handoff/pc-run-evidence-20261109/`  
Binaries (full PNG): GitHub Release tag **`pc-run-evidence-20261109`**（prerelease zip）

---

## 0. One-liner for peer AI

> Verify PC ComfyUI `canvas_align` dual A/B run on RTX 3070 Ti 8GB: gates blocked (ContractError 5376≠5461 → Preflight BLOCK → BudgetGuard count=6 vs max_tiles=1) then final Prompt executed in 00:39:35 with two 8-step Flux passes + Siax; operator-confirmed outputs are the two chat PNGs (5376×3024); Flux stays `workflow_candidate`; do not merge main.

---

## 1. Identity / 身份

| Item | Value |
|------|--------|
| Workflow | `workflow_ige_v03_dev_fp8_local_preflight_canvas_align.json` |
| Shape | **A／B 雙路徑並行**（Baseline A + Candidate B）— **一次 Queue 出兩張主結果** |
| Host | ComfyUI **0.44.0** · Python 3.12.9 · pytorch 2.10.0+cu130 · RTX **3070 Ti 8GB** · `http://127.0.0.1:8000` |
| Stack tip | Draft PR **#25** `fix/comfy-siax-preflight-gate-v0.1`（preflight + BudgetGuard）on top of #23 handoff |
| Flux | 仍然 **`workflow_candidate` / 未 promote** |

Logical chain（唔改）: #12 → #17 → #18 → #20 → #21 → #22 → #23 → #24/#25

---

## 2. 要驗證咩 / What to verify

1. **Gate sequence 真實發生過**（見 `comfyui_console_log.txt`）  
   - ContractError: geometry **5376×3024** ≠ source **5461×3072**  
   - `IGE_PREFLIGHT_BLOCKED`（operator confirm／registration／auth 未齊）  
   - Unsupported iteration state schema  
   - Preflight **PASS**（短 prompt ~1–2s；另有 `ige_preflight_pass_00001_.png`）  
   - `IGE_RESOURCE_BUDGET_BLOCKED`: `tile_batch.count=6` vs **`max_tiles_per_batch=1`**（VRAM/RAM 本身夠；係 tile **數量**擋）  
   - Flux 47-step 路徑被 cancel（~441s interrupt）  
   - **FINAL**: `Prompt executed in 00:39:35` — 兩個 **8-step** Flux pass（~18m + ~21m）+ `4x_NMKD-Siax_200k` RRDBNet

2. **Output 圖**  
   - Primary = operator 喺 chat 確認嘅兩張（見 Release zip `operator_attached_A.png` / `_B.png`）  
   - 同時提供 disk `output\IGE\` SHA 對照（**byte SHA 唔同**，但 A 與 disk `B_TTP_GatedTiles_00001_.png` **像素全等**；B 與 `ComfyUI_00002_.png` 像素全等，與 disk `GlobalLogic_Candidate_B_00001_.png` 近乎相同 mean_abs_diff≈1）  
   - 詳見 `OUTPUT_MANIFEST.json`

3. **Claim boundaries（唔好超讀）**  
   - ❌ 唔代表 Flux 已 promote / production  
   - ❌ BudgetGuard 仍然 `max_tiles=1`；**sequential runner 仍 pending**  
   - ❌ 唔代表可 merge `main`  
   - ❌ 唔代表 Cloud GPU / 多 tile OOM-proof  
   - ✅ 只證明：閘會 BLOCK；operator confirm + single-tile／canvas_align 路徑後，A／B 雙 Flux×8 + Siax 喺 8GB 跑完約 39m35s，並有 operator 確認視覺輸出

---

## 3. 檔案表 / Files

```text
docs/handoff/pc-run-evidence-20261109/
  PEER_VERIFY_README.md          ← 你喺呢度
  comfyui_console_log.txt        ← boot + run sequence 證據敘事
  OUTPUT_MANIFEST.json           ← 全部 SHA / size / WxH / operator vs disk
  previews/                      ← 1280px JPEG（repo 內可直接睇）
    operator_A_preview_1280.jpg
    operator_B_preview_1280.jpg
    ComfyUI_00002_preview_1280.jpg
    ige_preflight_pass_preview_1280.jpg
```

**Full PNG binaries** → Release **`pc-run-evidence-20261109`** asset  
`pc-run-evidence-20261109-binaries.zip`（內含 operator A/B、disk IGE 三張、`ComfyUI_00002_`、preflight pass、manifest、log）

---

## 4. SHA quick reference（primary）

| Role | File | SHA-256 | WxH | Bytes |
|------|------|---------|-----|-------|
| Operator A (primary) | `operator_attached_A.png` | `cfc057d21f8657bf555206dac1bdb933059f7dc5510bd73b0146dfcbd8c2f6a1` | 5376×3024 | 25176815 |
| Operator B (primary) | `operator_attached_B.png` | `874f6839967a00a79ae59040780d33b2e8a628ba9b4c1ed09e80b29a6ecc6f35` | 5376×3024 | 25035073 |
| Disk IGE A | `B_TTP_GatedTiles_00001_.png` | `f4afbb9d960cda86813920ee4a8275a9740e41a08db3eb6a4ee04681a7546208` | 5376×3024 | 20080980 |
| Disk IGE B | `GlobalLogic_Candidate_B_00001_.png` | `190b1130181964f708cd4c2afa219fb824b100f061a7eb08b8dc70465a2ee850` | 5376×3024 | 20077010 |
| Disk root | `ComfyUI_00002_.png` | `e743d92352493edbf621dfb985ace652d5a9d0c698fe14de079e1fe111398baa` | 5376×3024 | 19980385 |
| Preflight img | `ige_preflight_pass_00001_.png` | `b93622e0f0e94181b39dd0196c197f1611e55d156303065f4b10cf65924e2ab5` | 5376×3024 | 19920855 |
| Map | `GlobalLogicMap_00004_.png` | `2c66208af39d65fdb45f0e8a3e3f9eb95300efda3f00cfd6f4d37fe55a9d1687` | 5376×3024 | 131935 |

Operator note: chat 兩張係 operator 確認嘅視覺 A／B；同 disk IGE 檔 **SHA 唔同**（likely UI re-export），唔好當「唔係今次 run」。

---

## 5. PC paths

| What | Path |
|------|------|
| Comfy root | `C:\Users\user\Documents\ComfyUI\` |
| IGE outputs | `...\output\IGE\` |
| Workflow (align) | Desktop / handoff `workflow_ige_v03_dev_fp8_local_preflight_canvas_align.json` |
| Live IGE node | `...\custom_nodes\ComfyUI_IGE_GlobalLogicCoordinator\` |

---

## 6. Related PRs

- https://github.com/JUN-ZS/UP-engine/pull/25 — preflight + BudgetGuard（本證據對準）  
- https://github.com/JUN-ZS/UP-engine/pull/24 — execution gate / resource preflight  
- https://github.com/JUN-ZS/UP-engine/pull/23 — Siax-return docs handoff  

**Do not merge to `main`.** Keep Draft.

---

## 7. English short

Peer verification pack for a live PC ComfyUI run of the `canvas_align` dual A/B workflow. Console evidence shows fail-closed gates (geometry contract, preflight, BudgetGuard `max_tiles=1` vs batch count 6), then a completed ~39m35s run with two 8-step Flux passes and Siax. Operator-confirmed primary images are the two chat attachments (release zip); disk IGE SHAs differ due to re-encode. Flux remains `workflow_candidate`. Sequential multi-tile runner still pending. Not a promotion and not a `main` merge.
