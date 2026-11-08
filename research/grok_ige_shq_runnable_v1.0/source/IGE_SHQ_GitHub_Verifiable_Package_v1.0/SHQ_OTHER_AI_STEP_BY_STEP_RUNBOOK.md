# SHQ_OTHER_AI_STEP_BY_STEP_RUNBOOK.md — 其他 AI 逐步執行與逐關停機手冊

本手冊為外部 AI 及工程師對 `IGE_SHQ_GitHub_Verifiable_Package_v1.0`（對齊 `UP-engine` PR #12 分支 `feat/shq-geometry-lock-program-guidance-v0.1`）進行獨立驗證的第一入口。

## 一、硬性紅線（嚴禁越權與冒充）
1. **逐關停機（Fail-Closed）**：必須按 1 → 8 順序逐步執行。任何一關出現 `BLOCK` 或 `FAIL`（例如 `preflight_check.py` 回傳 `exit code 2`），必須立即停機回報，**嚴禁跳關或把歷史報告冒充新驗收結果**。
2. **禁止假冒 Geometry-Locked 母本**：
   - `assets/s4_self_part_hr_b0_geometry_locked_1200x896.jpg` (`B0_GL`) 與 `assets/s4_self_part_hr_b2_geometry_locked_1200x896.jpg` (`B2_GL`) 為必須具備的 `1200×896` 原位幾何鎖定母本。
   - **嚴禁用 `B0_UPPER` 假冒 `B0_GL`，亦嚴禁用 `B2_FULL` 假冒 `B2_GL`**。`preflight_check.py` 與 `Layer 3` 均設有 SHA-256 及像素陣列不相等檢查。
3. **執行邊界誠實揭露（No Live Diffusion Spoofing）**：
   - 本五層 Python 套件驗證的是：**既有高清母本之子視窗定位、稠密光流配準、三層頻率轉移（$L_{\text{base}} + M_{\text{material}} + H_{\text{detail}}$）、Rule 01380 幾何回位與 S7 磁碟唯讀反扣驗收**。
   - 本套件在執行期**不會**呼叫即時 `Siax/NCNN` 或 `ComfyUI/Flux` 擴散生成後端；嚴禁將本套件之執行宣稱為即時擴散推理。

## 二、標準執行指令（Clone / 解壓後依序執行）

```bash
python3 -m pip install -r requirements.txt
python3 preflight_check.py
python3 registry/validate_registry.py registry/method_registry.json
python3 -m unittest discover -s tests -v
python3 run_all_verifications.py --strict
```

## 三、八階段逐步檢查清單（1 → 8）

1. **Step 1 — Preflight（素材、SHA、尺寸與 Manifest 閘門）**：
   - 執行 `python3 preflight_check.py`，核對 `assets/asset_manifest.json` 內全部 13 張圖像之存在性、尺寸（`1376×768` 與 `1200×896`）及 SHA-256；若缺件或被替換則回傳 `BLOCK · exit code 2`。
2. **Step 2 — Registry（方法 ID、權限與 Schema 驗證）**：
   - 執行 `python3 registry/validate_registry.py registry/method_registry.json`，確認 22 個方法全部 `edit_permission == False`（預設不自動授權）且 `status == PASS`。
3. **Step 3 — Layer 0 (`l0_s0_four_way_anti_hole.py`)**：
   - 執行 `S0` 生／除／扣／洞／反洞，驗證 `camera_shift_px <= 0.10 px`、`(m_hole ^ m_anti_hole) == 255` 且 `diff_grants_edit_permission == False`。
4. **Step 4 — Layer 1 (`l1_s1_s2_part_hierarchy_and_geometry_lock.py`)**：
   - 執行 `S1` 18 個自身部件分割（`pairwise_overlap == 0`、`guillotine_cuts == 0`、對照獨立 Keep-Only GrabCut `IoU >= 0.90`）與 `S2` 遞迴幾何鎖 $T_{\text{scene}\leftarrow\text{leaf}} = T_{\text{scene}\leftarrow L_1} \cdot T_{L_1\leftarrow L_2}$。
5. **Step 5 — Layer 2 (`l2_s3_s4_permission_and_registry_router.py`)**：
   - 編譯 `S3` 人工核實寫入權限（未核實候選強制清零）並動態載入 `method_registry.json`。
6. **Step 6 — Layer 3 (`l3_s4_self_part_dense_registration_and_3freq_engine.py`)**：
   - 執行 `Skill A` ($L_{\text{base}}$)、`Skill B` ($M_{\text{material}}$)、`Skill C` ($H_{\text{detail}}$) 逐部件光流配準（`min_ncc >= 0.94`）與望遠鏡三層頻率分解。
7. **Step 7 — Layer 4 (`l4_s5_s6_s7_rule01380_return_and_reverse_qa.py`)**：
   - 執行 `Skill D`、`Rule 01380` 硬邊 `100%` 升清（`eroded_low_res_border_pixels == 0`）、18 部件回位合成 `5504×3072` 母本，並由磁碟重讀 PNG 執行唯讀 `S7` 反扣驗收（`IoU >= 0.999`）。
8. **Step 8 — 驗收回報（Fresh Artifacts & SHA Report）**：
   - 輸出新生成的 `outputs/SHQ_BATTLEFIELD_SELF_PARTS_4X_MASTER_5504x3072.png`、`outputs/SHQ_GITHUB_LAYERED_SELF_PART_VERIFICATION_BOARD.png`、`outputs/SHQ_TRUE_AI_HD_IN_4X_MASTER_MACRO_PROOF_BOARD.png` 及 `outputs/SHQ_GITHUB_LAYERED_TRACEABILITY_REPORT.json`。
