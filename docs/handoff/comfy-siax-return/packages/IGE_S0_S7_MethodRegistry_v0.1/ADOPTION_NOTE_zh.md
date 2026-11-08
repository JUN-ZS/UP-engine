# 採納說明（PR #12 最高層契約）— Method Registry Loader v0.1

## 結論

接受你對架構上下級關係的修正：

**PR #12（S0–S7 Geometry Lock / AI Usage Guide）> PR #15 > PR #5 > PR #11 > PR #7/#9/#10**

各 PR 仍保持獨立分支與測試歷史，**不硬合併**。本包只完成你 §8 開發次序的 **第 1 步**：把 Registry 從「文件契約」變成 **可查詢、fail-closed 的執行前解析器**。

上一輪 Workflow v0.3 的優化（SIAX → 全圖 → TTP → Batch Sampler → VAE Decode）仍然有用，但必須降級為 **從屬於 S0–S7 契約** 的一條後端路線候選，而不是系統最高層。

## 本步已交付

| 產物 | 作用 |
|---|---|
| `src/ige/method_registry.py` | 載入版本化 JSON、結構驗證、按 method_id / stage / capability / backend_id / implementation_status 查詢；`resolve()` fail-closed |
| `contracts/IGE_S0_S7_METHOD_REGISTRY_V0.1.json` | 九種方法的版本化種子（與包內 `method_registry.json` 同源） |
| `tests/test_method_registry.py` | 延續原 `test_registry.py` 模式：重複 ID、缺 test_ids、禁止 AI 自授 `edit_permission`、load+query |

硬性政策：

- `default_edit_permission = false`
- 每個 method 的 `edit_permission` 必須為 `false`
- loader **永不**把 `edit_permission` 設成 `True`（DIFF ≠ edit_permission；寫入權限只來自 S3 人工編譯）
- 四態 HOLE/REMOVE/DIFF/GENERATE 是 **Router 可選方法族**，不是每張圖必經流水線
- 三條後端保持分離：`SIAX4X_TILE_CORE_SR` / `FLUX_HR_TILE_IMG2IMG` / `ALL24_AI_DONOR_MULTIBAND_TRANSFER`

## 明確非宣稱（non-claims）

- **未**把 Registry 接進 UP-engine 主幹或任何 PR 分支的 runtime import path
- **未**宣稱 research/shq_v9 fossils 已 production-wired
- **未**新建或改動 ComfyUI custom nodes / workflow JSON
- **未**跑 GPU / Flux / Siax 推理，也未做 S7 實圖驗收
- **未**合併 PR #12/#15/#5/#11
- 既有 `route_skill_by_state(..., registry_path=...)` 參數缺口（有 path 但不讀檔、Method ID 硬編碼）**尚未**在 fossils 內修掉——那是下一步把 loader 接到 PR #5 READ/Router 時的工作

## 與 Comfy PC 模型下載的關係

較早在 Comfy Desktop 環境下載的 Flux 權重（如 `flux1-dev` 等）屬 **後端資產備料**，與本步 Registry loader **正交**：有模型 ≠ 已接通 S0–S7；有 Registry ≠ 已跑通 HR tile diffusion。

## 建議下一階段（對齊你的 §8）

1. ~~Registry → 可查詢執行系統~~（本步）
2. 將 PR #5 READ 接到 S0–S3（觀察不可自授權限）
3. 將 PR #11 Geometry Contract / Core-Halo 接入 S4
4. SIAX / Flux Tile / Donor 分成獨立 Backend Adapter
5. 改造 S6，驗證 TTP 是否真 Core-only；必要時獨立確定性回位
6. S7 獨立 fail-closed 驗收程式
7. 之後才做 Per-Subset Conditioning 與 Global Noise Field

## 狀態標記

`production_wired: false` · `registry_version: 0.1.0-draft` · 權威：`PR12_S0_S7_CONTRACT`
