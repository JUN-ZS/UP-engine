# IGE-SHQ × Grok / Imagine / Canvas — Start Here v1.0

本包把原本的 IGE-SHQ Modular Methods Toolkit v2.0 包裝成可交給 Grok 按步執行的專案流程。**原始 `IGE_SHQ_GitHub_Verifiable_Package_v1.0` 以原樣保留在 `source/`，沒有偷偷修改原方法程式。** 新增的啟動器、Grok 提示、Canvas 工作板和 Imagine 提示，全部位於本包頂層或 `docs/`。

## 先理解四個角色，不要把它們當成同一個執行器

| 環境 | 在本專案負責什麼 | 能否直接跑 22 個 Python 方法 |
|---|---|---|
| **Grok Chat / Grok AI** | 總控、讀 ZIP、規劃步驟、審核結果、撰寫修正 | 只有在該工作階段真的提供 code execution / 工具時才可；單純對話不等於本機 Python |
| **Grok Canvas** | 保存 Master Plan、方法規格、提示詞、任務板、程式碼草稿和驗收紀錄 | Canvas 本身不等於終端機或 Python runtime |
| **Grok Imagine** | 生成／編輯圖片，製作額外的材質 donor 參考圖 | **不能**執行 Python、OpenCV、registry 或 recipe |
| **Grok Bot** | 透過獨立的雲端電腦、terminal、filesystem 真正解壓、安裝依賴和執行程式 | **可以**，前提是帳戶與任務介面有雲端電腦能力；它與 Grok Chat 是不同產品介面 |

官方文件：Grok Chat 的功能包含上傳檔案及 Imagine；Imagine 提供圖片／影片生成與編輯；Grok Bot 則有雲端電腦、瀏覽器、命令列與檔案系統。Canvas 在 Grok 產品說明中定位為寫作／編輯表面，不能把它視為已證實的 Python 執行器。見 [Grok overview](https://docs.x.ai/grok/overview)、[Imagine overview](https://docs.x.ai/developers/model-capabilities/imagine)、[Grok Bot overview](https://docs.x.ai/grok-bot/overview)、[Grok Bot computer and apps](https://docs.x.ai/grok-bot/computer-and-apps)。

## 最短起步流程

1. 將整個 `GROK_IGE_SHQ_RUNNABLE_v1.0.zip` 上傳到 **Grok Bot**，或把 ZIP 解壓到 Grok Bot 的 `/workspace/` 專案目錄。若你只有 Grok Chat + Canvas + Imagine，先用 Chat 讀文件、Canvas 保存工作板、Imagine 製作 donor；真正 Python 執行要另有 code execution 環境。
2. 在 Grok Chat 貼上 `docs/GROK_CHAT_MASTER_PROMPT.md` 的完整提示詞，並要求它先閱讀 `docs/GROK_BOT_EXECUTION.md`。
3. Grok Bot 解壓後執行：

```bash
python grok_shq_runner.py --doctor
python grok_shq_runner.py --audit
```

4. 在 Canvas 建立專案板：把 `docs/GROK_CANVAS_PROJECT_BOARD.md` 全文貼入 Canvas。Canvas 只記錄任務、狀態、SHA、輸出路徑和驗收，不可把未執行的步驟標成 PASS。
5. 需要額外高清材質來源時，打開 Imagine，按 `docs/GROK_IMAGINE_PROMPTS.md` 逐張生成；再把生成圖上傳到 Grok Bot，登記：

```bash
python grok_shq_runner.py --register-donor /workspace/path/to/imagine_output.png --label gold_mesh_donor
```

注意：登記 donor 只會保存圖像、SHA 和尺寸，**目前原 M12/M13 尚未自動讀取 `assets/imagine_donors/`**。不能把「已登記」說成「已進入升清管線」。

## 目前安全狀態：可以驗證素材與 Registry，但方法寫入先 BLOCK

我已審核原工具包程式。原始共用 pipeline 在 `methods/common_runtime.py` 中硬編碼 `human_verified=True`，而且若 master PNG 與 traceability JSON 已存在，可能沿用舊輸出摘要，沒有以全部來源 SHA 建立可靠的 content-addressed cache。這兩點未修好之前，不應讓 22 個方法或 R01–R03 自動寫入／覆蓋主圖。

因此本包的 `grok_shq_runner.py` **刻意只開放安全檢查與證據工具**：

- `--doctor`：環境和執行閘門診斷。
- `--preflight`：核對 13 張正式素材與 SHA／尺寸。
- `--registry`：核對 22 個方法登記表。
- `--audit`：只跑 Preflight + Registry，寫出 JSON 報告；不跑圖像方法、不覆蓋主圖。
- `--catalog` / `--info M12`：列出方法和方法規格。
- `--register-donor`：把 Imagine 生成的圖像保存成額外 donor，計算 SHA；不會自動修改原始素材。
- `--verify-master`：檢查既有 master PNG 是否能解碼、尺寸是否為 5504×3072，並計算 SHA。
- `--run M12` / `--recipe R01`：現階段會回傳 `BLOCKED`，不執行原始寫入方法。不是故障，而是有意保留的權限閘門。

這不是宣稱 22 個方法已經失敗；是現有程式的 S3 人工批准流程未能證明真實人工授權，故寫入執行尚未具備可信前提。先修正 S3 權限證據、快取鍵和方法收據，再開放執行。

## 原始工具包的有效邊界

原工具包含 5 個方法分類、M01–M22、R01–R03、13 張圖像素材和既有輸出。其本地測試與既有報告可以作為**該次套件測試證據**，但 `22/22 PASS` 不能解讀為 22 個各自獨立算法已通過獨立驗收：22 個 wrapper 最終共用同一 `execute_core_role()` / shared pipeline，方法 receipt 的 `status` 是固定字面 `PASS`，不同方法可能只是在同一 cached context 上產生不同收據。

實際的 4× master 目標為 5504×3072；不是 8K。M11 當前實作並非 neural checkpoint inference；M19、M20 是 Siax／ComfyUI 的契約守衛，不代表已載入 Siax 或執行 Flux。詳見 `docs/EXECUTION_TRUTH_AND_GATES.md`。

## 專案交付路徑

- 原始程式與素材：`source/IGE_SHQ_GitHub_Verifiable_Package_v1.0/`
- Grok Chat 總控提示：`docs/GROK_CHAT_MASTER_PROMPT.md`
- Canvas 工作板：`docs/GROK_CANVAS_PROJECT_BOARD.md`
- Imagine 材質生成提示：`docs/GROK_IMAGINE_PROMPTS.md`
- Grok Bot 真正執行步驟：`docs/GROK_BOT_EXECUTION.md`
- 真實性／阻斷條件：`docs/EXECUTION_TRUTH_AND_GATES.md`
- 機器可讀任務契約：`docs/grok_task_manifest.json`
- Grok 安全啟動器：`grok_shq_runner.py`
