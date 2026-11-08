# Grok Bot — 真正執行 Python 的步驟

## 0. 先確認入口是 Grok Bot，不是只開了 Grok Chat

Grok Bot 是獨立工作介面，具有雲端 computer、terminal、filesystem；它和 Grok app/chat 不是同一個 app。若你只有普通 Grok Chat 對話而沒有 terminal/code execution 工具，請不要假裝能執行 bash 或 Python。可先做檔案閱讀和產生命令，然後交給 Grok Bot 或具備 xAI code-execution tool 的 agentic API 工作流。

官方文件：
- [Grok Bot overview](https://docs.x.ai/grok-bot/overview)
- [Use the computer and apps](https://docs.x.ai/grok-bot/computer-and-apps)
- [Files and results](https://docs.x.ai/grok-bot/files-and-results)
- [Code execution tool](https://docs.x.ai/developers/tools/code-execution)
- [Chat with files + code execution](https://docs.x.ai/developers/model-capabilities/files/chat-with-files)

## 1. 解壓

把 `GROK_IGE_SHQ_RUNNABLE_v1.0.zip` 上傳到 Grok Bot，並要求它把包解壓至 `/workspace/GROK_IGE_SHQ_RUNNABLE_v1.0/`。如果它已經在目標資料夾，先檢查而不要重複覆蓋。

```bash
cd /workspace/GROK_IGE_SHQ_RUNNABLE_v1.0
find . -maxdepth 3 -type f | sort | head -200
```

必須看到：

- `grok_shq_runner.py`
- `source/IGE_SHQ_GitHub_Verifiable_Package_v1.0/preflight_check.py`
- `source/IGE_SHQ_GitHub_Verifiable_Package_v1.0/assets/asset_manifest.json`
- `docs/GROK_CHAT_MASTER_PROMPT.md`

## 2. 安裝相依套件

```bash
python --version
python -m pip install -r source/IGE_SHQ_GitHub_Verifiable_Package_v1.0/requirements.txt
```

原始 `requirements.txt` 只有 `numpy` 和 `opencv-python-headless`。若 pip 安裝失敗，停止並回報完整錯誤；不要使用不同版本偷偷替換結果。

## 3. 執行只讀檢查

```bash
python grok_shq_runner.py --doctor
python grok_shq_runner.py --preflight
python grok_shq_runner.py --registry
python grok_shq_runner.py --audit
python grok_shq_runner.py --catalog
python grok_shq_runner.py --info M12
```

輸出證據放在：

`source/IGE_SHQ_GitHub_Verifiable_Package_v1.0/outputs/grok_runs/`

每次執行都會保留 JSON 和 stdout/stderr log。`--audit` 不執行圖像方法，也不覆蓋 master。

## 4. 現階段禁止繞過的命令

```bash
# 目前預期回傳 BLOCKED，不應繞過：
python grok_shq_runner.py --run M12
python grok_shq_runner.py --recipe R01 --part P08
```

原因是原 shared pipeline 將 `human_verified=True` 硬編碼，而 M01–M22 不是 22 個隔離、獨立 runtime；多數入口都會進入同一共用 pipeline。方法執行也可能沿用舊 master/report cache。先修好 S3 approval verifier、cache key 和 receipt，再由使用者批准開啟。

## 5. 修正後，原始 CLI 的目標調用方式（僅作未來目標，不代表目前可用）

完成 source patch 和重新驗收後，才使用：

```bash
cd /workspace/GROK_IGE_SHQ_RUNNABLE_v1.0/source/IGE_SHQ_GitHub_Verifiable_Package_v1.0
python invoke_method.py --list
python invoke_method.py --list-parts
python invoke_method.py --info M12
python invoke_method.py --run M12 --part P08
python invoke_method.py --recipe R01 --part P08
```

完整戰場 R02 必須先有 18 個獨立 part approval receipts；不可由一個全域 `human_verified=true` 代替。

## 6. Imagine donor 交接

```bash
python grok_shq_runner.py --register-donor /workspace/grok_imagine_donors/donor.png --label B1_P08_gold_mesh
```

目前只會登記、複製與計算 SHA；不會自動注入 M12/M13。新增 donor 的程式整合需要獨立 patch 和 holdout 測試。

## 7. 完成時的最低交付內容

- 使用的 ZIP SHA-256。
- Python version、numpy version、OpenCV version。
- Preflight exit code 和 13 張素材核驗結果。
- Registry validator exit code、方法數、錯誤數。
- 每條實際命令的 stdout/stderr 檔案路徑。
- `BLOCKED` gate 原因及 source file/line。
- 不可只附一張 screenshot；要附 JSON 和 PNG 的實際路徑與 SHA。
