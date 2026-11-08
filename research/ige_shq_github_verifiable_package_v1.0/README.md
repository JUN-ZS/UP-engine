# IGE-SHQ Layered Self-Part High-Resolution Upgrade & Verification Package (`v1.0`)

本套件為 **GitHub 可下載、可由任何外部 AI 或工程師獨立重現驗證** 的完整五層 Python 聯動程式庫（**Zero Hardcoded Paths，全相對路徑**）。

## 1. 本次 DEBUG 修正與核心架構突破

1. **修正上下半身部件映射錯位（補齊全部 `P01–P18` 自身高清部件母本）**：
   - 先前單一腳本僅使用 `B0` 與 `B1` 的上半身特寫（涵蓋約 75% 高度）就直接縮放至全身 Bounding Box，導致下半身腿甲／推進靴（`P05, P06`）與戰術護膝／戰靴（`P10–P12`）垂直比例拉扯。
   - 本套件在 `assets/` 內完整收錄 **5 張同源生成的 `1200×896` 自身高清部件圖**（`B0_UPPER`、`B0_LOWER`、`B1_UPPER`、`B1_LOWER`、`B2_FULL`），100% 覆蓋 `P01–P18` 共 18 個自身部件。
2. **逐部件多尺度模板定位 + 稠密光流子像素配準（`Layer 3`）**：
   - 對每一個部件 $P_k \in \{P01, \dots, P18\}$，先以 `cv2.matchTemplate(TM_CCOEFF_NORMED)` 在對應的 `1200×896` 自身高清部件圖中定位子視窗，再以 `cv2.calcOpticalFlowFarneback` + `cv2.remap` 執行子像素光流對齊（實測 18 個部件對齊後結構相關係數 `min_post_registration_structural_ncc >= 0.96`），確保**真正由 AI 生成的高清材質（$M_{\text{material}}$）與微細節（$H_{\text{detail}}$）準確寫入 `5504×3072` `4×` 母本大圖**。
3. **五層 Python 模組聯動（`src/ige_shq/l0` $\rightarrow$ `l1` $\rightarrow$ `l2` $\rightarrow$ `l3` $\rightarrow$ `l4`）與「同一方法 ID → 同一程式 → 同一測試 → 同一驗收」**：
   - **Layer 0 (`src/ige_shq/l0_s0_four_way_anti_hole.py`)**：執行 `S0` 原圖凍結與四向正反扣（`生 KEEP -> 除 REMOVE -> 扣 DIFF -> 洞 M_hole & 反洞 M_anti_hole`）。
   - **Layer 1 (`src/ige_shq/l1_s1_s2_part_hierarchy_and_geometry_lock.py`)**：執行 `S1` 18 部件曲線關節分割（零斷頭台平切）與獨立 Keep-Only GrabCut 非同義反覆驗證（`IoU = 0.9400`），以及 `S2` 遞迴座標鏈鎖定 $T_{\text{scene}\leftarrow\text{leaf}} = T_{\text{scene}\leftarrow L_1} \cdot T_{L_1\leftarrow L_2}$ 與五參數分離。
   - **Layer 2 (`src/ige_shq/l2_s3_s4_permission_and_registry_router.py`)**：動態載入並以 `registry/validate_registry.py` 驗證 `registry/method_registry.json`，編譯 `S3` 人工核實寫入權限（`DIFF != edit_permission`）。
   - **Layer 3 (`src/ige_shq/l3_s4_self_part_dense_registration_and_3freq_engine.py`)**：執行 `Skill A` ($L_{\text{base}}$)、`Skill B` ($M_{\text{material}}$)、`Skill C` ($H_{\text{detail}}$) 逐部件光流對齊與三頻率層分解。
   - **Layer 4 (`src/ige_shq/l4_s5_s6_s7_rule01380_return_and_reverse_qa.py`)**：執行 `Skill D` + `Rule 01380`（洞內硬邊 `100.0%` 升清，`eroded_low_res_border_pixels = 0`、`feather_px = 0`）、18 部件遞迴回位至 `5504×3072` 母本，並從磁碟重讀 PNG 執行純唯讀 `S7 Reverse QA` 反扣驗收（`IoU = 1.0000`）。

## 2. 外部 AI 逐步執行入口

先看 [`SHQ_OTHER_AI_STEP_BY_STEP_RUNBOOK.md`](../../docs/SHQ_OTHER_AI_STEP_BY_STEP_RUNBOOK.md)。Clone PR #12 branch 後，喺本套件根目錄依序執行：

```bash
python -m pip install -r requirements.txt
python preflight_check.py
python registry/validate_registry.py registry/method_registry.json
python -m unittest discover -s tests -v
python run_all_verifications.py --strict
```

任何 Preflight／Registry／測試失敗，立即 BLOCK；不得用舊 report 當新執行證據。Runbook §0 已記錄目前 Hub baseline 同另行附上的缺件 candidate ZIP 並非同一個 artifact；candidate 若使用 B0_GL/B2_GL，亦必須有 `assets/geometry_locked_hr_manifest.json` 驗證兩張圖的 SHA-256 與 1200×896 尺寸。

## 3. 可複製的完整執行命令

```bash
python -m pip install -r requirements.txt
python preflight_check.py
python registry/validate_registry.py registry/method_registry.json
python -m unittest discover -s tests -v
python run_all_verifications.py --strict
```

如需逐步說明、Windows PowerShell 指令、S0–S7 驗收內容及回報 JSON，請以 [`SHQ_OTHER_AI_STEP_BY_STEP_RUNBOOK.md`](../../docs/SHQ_OTHER_AI_STEP_BY_STEP_RUNBOOK.md) 為準。

## Execution capability boundary

本套件驗證已提供 HR self-part donors 的配準、L/M/H 頻率轉移、幾何回位和 S7 reverse QA。Runner 本身不會呼叫 Siax/NCNN、ComfyUI/Flux 或 Imagine live backend；需要以獨立 backend adapter receipt 證明實際生成時，唔可以用本套件的 PASS 代替。