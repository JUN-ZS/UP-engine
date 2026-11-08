# SHQ_AI_USAGE_GUIDE.md — 理解規約、宣稱邊界與驗收判斷方法

## 1. 閱讀順序（強制）
1. `SHQ_OTHER_AI_STEP_BY_STEP_RUNBOOK.md`：其他 AI 逐步執行手冊與停機規則。
2. `SHQ_INDEX.md`：套件目錄、五層模組責任與 13 張素材索引。
3. `registry/method_registry.json`：22 個方法之 `method_id -> entrypoint -> test_ids -> acceptance` 契約。

## 2. 嚴格「宣稱」邊界（Verified Claims vs Explicit Non-Claims）
- **允許宣稱（須附當次執行之 SHA-256 與測試數據）**：
  - 13 張隨附素材完整通過 `preflight_check.py`（`exit_code == 0`，含 `B0_GL` 與 `B2_GL` 原位幾何鎖定母本）。
  - 五層 Python 模組（`L0 -> L1 -> L2 -> L3 -> L4`）完成 18 個自身部件之配準、三層頻率合成（$L_{\text{base}} + M_{\text{material}} + H_{\text{detail}}$）、`Rule 01380` 硬邊 `100%` 升清回位，並通過 `S7` 磁碟重讀反扣驗收。
- **嚴禁宣稱（Explicit Non-Claims）**：
  - 嚴禁將預生成之 `1200×896` 母本配準轉移宣稱為「執行期即時呼叫 ComfyUI/Flux 或 Siax/NCNN 擴散推理」。
  - 嚴禁宣稱 `1200×896` 或 `1376×768` 為原生 `8K`（`4×` 母本尺寸為 `5504×3072`）。
  - 嚴禁在 `preflight_check.py` 失敗時拿歷史報告冒充當次通過。
