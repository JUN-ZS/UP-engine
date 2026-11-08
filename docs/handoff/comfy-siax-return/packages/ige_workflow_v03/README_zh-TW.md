# IGE / SIAX Workflow v0.3 — 結構優化補丁

## 目的

這個補丁不是重寫 SIAX，也不是把流程改成 Single-ROI。它保留原本的：

`Full Image → NMKD-Siax → 16MP Lanczos → TTP 2×3 Tiles → Batch Sampler → VAE Decode → TTP Assembly`

並保留 A（原始分支）及 B（IGE 分支）。優化重點是讓 A/B 比較能分辨問題發生在生成控制還是重組階段。

## 套用方式

```powershell
python .\apply_ige_workflow_v03_patch.py .\original_workflow.json .\workflow_ige_v03.json
```

先執行內置結構測試：

```powershell
python .\apply_ige_workflow_v03_patch.py --self-test
```

腳本只使用 Python 標準函式庫，不需要 pip 安裝。

**注意：** 本次對話收到的是貼在訊息中的 JSON 文字，沒有收到可直接修改的原始 `.json` 檔案。因此交付的是針對該節點 ID／資料流的可重現 patcher，而不是冒稱已直接改寫並驗證了完整原檔。請對原始 ComfyUI workflow JSON 匯出檔套用。

## v0.3 做了甚麼

1. **修正模型欄位雙重記錄不一致**
   - Node 77 `UNETLoader`: `widgets_values_named.unet_name` 同步為 `flux1-dev.safetensors`。
   - Node 31 `VAELoader`: `widgets_values_named.vae_name` 同步為 `ae.safetensors`。
   - 不改實際模型選擇；仍是 Dev FP8 baseline，不是 CC_V1 parity。

2. **固定可重現 Seed**
   - 保留 Node 70 Seed `909424749197426`。
   - `control_after_generate` 從 `randomize` 改為 `fixed`。
   - 這避免每次重跑都改變 Seed，令 A/B replay 失去可比性。

3. **修正比較圖的來源尺寸**
   - 原 Node 245 的 image A 原本來自 Node 233（原始低解析度輸入）。
   - 改為 Node 34（16MP SIAX/Lanczos 畫布），避免拿不同解析度比較。

4. **增加 B-Gated Tiles 的同一 TTP Assembly 支線**
   - 新 Node 327 使用與 A 的 Node 127 相同 `TTP_Image_Assy`、相同位置 Metadata 及 padding=125。
   - 新 Node 328 比較 A 與 B 的同一 TTP 重組結果。
   - 新 Node 329 比較 B 的 TTP Assembly 與 B 的 Global Reconciler。
   - 新 Node 340 比較 16MP Source 與 B 的 Global 最終圖。
   - 新 Node 341 直接比較 A 原始最終圖與 B Global 最終圖。
   - 因此可分解：
     - A vs B / same TTP：差異主要來自 Global Conditioning、Noise Mask、Logic Gate 等生成控制層。
     - B / TTP vs Global Reconciler：差異來自全局重組／仲裁層。

5. **讓 LogicMapPreview 真正執行**
   - 原 Node 306 沒有下游連線，可能不會在執行圖中被排程。
   - 新 Node 331 把它接到 SaveImage，輸出 Logic Map 預覽。

6. **將 8 類診斷資料放到 UI**
   - Contract report
   - Tile subset tasks
   - Execution groups
   - Noise mask report
   - Logic gate report
   - Reconcile report
   - Global audit report
   - Next iteration state

   使用 `ShowText|pysssss` 節點顯示。這些輸出方便人工檢查與複製；**下一輪狀態仍需手動帶回 Node 300，沒有宣稱已自動寫檔或自動回灌**。

## 沒有做、亦不會假裝已完成的部分

- 沒有把 `assistant_provisional` 提升為正式幾何。
- 沒有把 `GEOMETRY_GUARD` 未經核對就接到不存在的 Node input。
- 沒有宣稱 IGE Contract 一定包含完整 Geometry Guard；必須讀取 IGE Python 實作確認。
- 沒有宣稱目前具備 Shared Global Latent / Global Noise Field。
- 沒有把 FP8 說成 INT4、GGUF 或 Distilled。
- 沒有把 `ae.safetensors` 宣稱為 `ae.sft` 的 SHA／Tensor 等價品。
- 沒有修改 Steps=47、Denoise=0.33、Guidance=6.2、Sampler、Tile Grid、Overlap 或 Padding。
- 沒有執行真實 Cloud／GPU 推理。

## 執行前阻擋條件

1. ComfyUI 能載入所有 workflow 節點，包括 SIAX、TTP、KJNodes、rgthree、LayerUtility、IGE 及 `ShowText|pysssss`。
2. IGE Python 實作證明 Global Logic Compiler 的 Geometry Guard 已包含於 Contract，且 Projector 會把 Guard 正確投影到 `TILE_SUBSETS`。Node 300 的 `GEOMETRY_GUARD` 獨立輸出目前沒有直接連線，不能單憑 workflow 外觀判定它已生效。
3. `object_geometry.provisional.json` 座標必須已註冊到 Node 34 的 16MP 全局畫布。若幾何資料仍是原圖、ROI 或其他尺寸座標，必須先明確轉換。
4. 實際執行後，核對 Noise Mask 報告：PRESERVE／REFINE／GUARDED_REFINE／GENERATE 面積比例、遮罩尺寸、Batch 次序、每個 Tile 的 mask 對位。
5. 每個 A/B 分支都要保存原始 Tile、B Gate 後 Tile、B-TTP 合成、B-Global 合成、Logic Map、各 JSON 報告及 SHA-256。
6. `GlobalAcceptanceAudit` 必須能讀取人工 observations；空 `{}` 不等於人類觀察已通過。

## 驗收標籤

- `PATCH_SELF_TEST_PASS`: 只代表 patcher 的合成圖測試通過。
- `WORKFLOW_JSON_STATIC_PASS`: 對實際原 workflow 套用後，節點／連線反向引用檢查通過。
- `NODE_IMPORT_PASS`: ComfyUI 實際載入所有 Node。
- `DRY_RUN_PASS`: 執行前資料流及輸出路徑檢查通過。
- `GPU_RUN_COMPLETE`: 真實推理有 Job ID、原始輸出及執行日誌。
- `GEOMETRY_ACCEPTED`: 幾何指標及人工 observations 均正式通過。

以上狀態不可互相代替。本補丁只完成 patcher 自測，尚未取得後五項結果。
