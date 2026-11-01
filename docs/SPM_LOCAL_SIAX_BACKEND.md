# SPM 本地 Siax 後端（薄層）· 不重做 Canvas SPM

**status:** ARCH_v1 · FIRST_IMPL  
**branch:** `feat/upscale-s3-heterogeneous-runner-v0.1`  
**原則:** 保留 Grok Canvas 已能運作的 SIAX／SPM；只增加 **本機運算出口**。

---

## 0. 架構修正（對齊你的結論）

| 錯誤方向 | 正確方向 |
| --- | --- |
| 把 SPM 重做成 ComfyUI workflow | **不** 做 ComfyUI |
| 重寫 SPM 創作邏輯 | **保留** Canvas SPM 方法／操作／流程 |
| 先上整套 S3 Scheduler 才能本機算 | **不必**；本機一圖可直打原生 Siax |
| 把 GPU 插入 Grok Imagine 雲端權重 | **不可能**；Imagine 仍在雲端 |

```
Grok Canvas · 現有 SIAX / SPM
        │
        │  運算位置選擇
        ├──────────── Cloud：原有 Grok 可執行生成（Imagine 等）
        │
        └──────────── Local PC（新增）
                        │
                        ▼
              MCP / HTTP / CLI 薄層
                        │
                        ▼
              Local Python Executor
                        │
                        ▼
              UP-engine 原生 Siax（run_siax_upscale / Adapter）
                        │
                        ▼
              結果（路徑 · 尺寸 · SHA）回到 Canvas／對話
```

**只加薄層：**  
`Grok SPM → MCP Tool → Local Python Executor → 原生 Siax`

---

## 1. 關鍵邊界 A / B

| | 能力 | 本機 GPU/RAM |
| --- | --- | --- |
| **A. 雲端圖像生成（Imagine 等）** | Canvas 內可很好用 | **不能** 把本機 VRAM 插入雲端模型 |
| **B. Siax 模型推論** | 可委派本機 Executor | **可以** 用本機 CPU／GPU／RAM |

xAI Custom MCP Connector 可把外部工具接入 **Grok 對話**；本機可 tunnel。  
**Canvas 編輯 UI 是否一定能直接打自訂 MCP：未保證** → 必須做一次 **實際呼叫測試**，不能假設已打通。

---

## 2. 第一版三個接口

| 工具 | 用途 |
| --- | --- |
| `local_pc_status` | 本機 CPU、RAM、GPU、VRAM |
| `spm_local_execute` | 直接跑現有 Siax 推論（一圖） |
| `spm_local_result` | 回傳路徑、尺寸、SHA-256 |

**不做：** ComfyUI · 重寫 SPM · 重設計 Siax 生成邏輯 · 強制 S3 分布式。

---

## 3. 本機怎麼跑

```powershell
cd C:\Users\user\Documents\GitHub\UP-engine

# 狀態（不跑模型）
py -3 tools/spm_local_executor.py cli local_pc_status

# 一圖本機 Siax（須你確認授權；真的用本機算力）
py -3 tools/spm_local_executor.py cli spm_local_execute `
  --input D:\path\to\BASE.jpg `
  --output D:\s3_share\spm_out\OUT.png `
  --device auto `
  --tile-size 128 `
  --tile-pad 8 `
  --confirm-model-license-review

# 取回
py -3 tools/spm_local_executor.py cli spm_local_result --job-id <job_id>

# MCP 實驗：stdio JSON-RPC
py -3 tools/spm_local_executor.py stdio

# Tunnel 實驗：本機 HTTP（再 ngrok/cloudflared）
py -3 tools/spm_local_executor.py http --port 8765
```

依賴：既有 `ige.upscale.siax.run_siax_upscale` + checkpoint +（可選）CUDA torch。

---

## 4. Canvas / MCP 接線注意

1. 對話裡 Custom MCP 先測 `local_pc_status`（輕量）。  
2. 再測 `spm_local_execute` 一張小圖，對照工作管理員 GPU／RAM。  
3. **Canvas 內嵌是否暴露同一 MCP：** 單獨測；失敗則路徑改為「對話工具 → 本機 → 檔案路徑回 Canvas」。  
4. S3 分布式是 **另一條線**（多 child／多機）；本機一圖出口 **不依賴** S3。

---

## 5. 與 S3 的關係

| 線 | 何時用 |
| --- | --- |
| **SPM Local Backend** | Canvas 創作流、單圖／小圖本機 Siax |
| **S3 Heterogeneous** | 大圖 tile、多機、lease、rebuild |

兩者可共用 **同一原生 Siax 模組**；**不要** 為了本機出口去啟動整套 Scheduler。

---

## 6. 檔案

| 檔 | 作用 |
| --- | --- |
| `docs/SPM_LOCAL_SIAX_BACKEND.md` | 本文 |
| `src/ige/spm_local/` | status / execute / result |
| `tools/spm_local_executor.py` | CLI · stdio · http |
| `schemas/spm-local-tool.schema.json` | 契約 |

**不宣稱:** quality PASS · E3 · Canvas MCP 已打通 · physical dual-host。


---

## 7. First local GPU pilot (observed · not quality)

**status:** OBSERVED_LOCAL_CUDA_ONE_IMAGE  
**not:** quality PASS · Canvas MCP · tunnel · S3

| Item | Value |
| --- | --- |
| Host | DESKTOP-GNMQ0PF · RTX 3070 Ti |
| Python | **repo `.venv`** torch 2.11.0+cu128 (not bare `py -3` without venv) |
| Input | 128×128 synthetic `small_BASE.jpg` |
| Output | 512×512 PNG · job `spm_50001dedfed7` |
| Wall | ~3.6 s · VRAM ~557 MiB peak observed |
| device | request `auto` · **runtime `cuda`** |
| Flags | cloud_imagine=false · comfyui=false · s3_scheduler=false · quality_qualified=false |

Use:

```powershell
.\.venv\Scripts\Activate.ps1
python tools/spm_local_executor.py cli local_pc_status
```

Top-level `device_used` must report **runtime** device (cuda|cpu), with `device_requested` for the call argument.


---

## 8. PATH1 · Dialogue tools (Grok chat MCP)

**Goal:** Grok **對話** 透過 Custom MCP 打到本機 Executor（先 status，再一圖）。  
**Not:** Canvas 內嵌 · quality · S3

### Protocol note

- Grok custom connector needs a **public** MCP URL (not localhost).
- Use tunnel: [xAI custom MCP tunneling](https://x.ai/docs/grok/connectors/custom-mcp-tunneling)
- This executor exposes **POST `/mcp`** for `initialize` / `tools/list` / `tools/call`.
- Set **`SPM_LOCAL_TOKEN`** before tunneling (Bearer auth).

### Windows steps

```powershell
cd C:\Users\user\Documents\GitHub\UP-engine
git pull
.\.venv\Scripts\Activate.ps1

# Window A — server
.\tools\spm_path1_dialogue.ps1 -Port 8765

# Window B — tunnel (pick one)
winget install --id Cloudflare.cloudflared
cloudflared tunnel --url http://127.0.0.1:8765
# OR
winget install ngrok -s msstore
ngrok http 8765
```

Then:

1. Copy HTTPS forwarding URL (e.g. `https://….trycloudflare.com`)
2. Open [grok.com/connectors](https://grok.com/connectors) → **New Connector** → **Custom**
3. Server URL: `https://….trycloudflare.com/mcp`  
   (if connector asks for header: `Authorization: Bearer <SPM_LOCAL_TOKEN>`)
4. **New chat**, ask only: call `local_pc_status` and show GPU name
5. If tools appear and status returns RTX 3070 Ti → PASS for PATH1-status
6. Then: `spm_local_execute` with  
   `input_path=D:\s3_share\spm_in\small_BASE.jpg`  
   `confirm_model_license_review=true`  
   `device=auto`

### Local smoke before tunnel

```powershell
curl http://127.0.0.1:8765/health
curl -H "Authorization: Bearer $env:SPM_LOCAL_TOKEN" http://127.0.0.1:8765/local_pc_status
```

### MCP smoke (optional)

```powershell
$body = '{"jsonrpc":"2.0","id":1,"method":"tools/list","params":{}}'
Invoke-RestMethod -Uri http://127.0.0.1:8765/mcp -Method POST -ContentType 'application/json' -Body $body -Headers @{Authorization="Bearer $env:SPM_LOCAL_TOKEN"}
```

### What to paste back

```text
PATH1_REPORT
tunnel: cloudflared|ngrok|none
connector_added: yes|no
tools_listed: yes|no
local_pc_status_via_chat: yes|no
gpu_name_seen: ...
spm_local_execute_via_chat: yes|no|skipped
job_id: ...
error: (if any)
```

### Failure modes (still useful evidence)

| Symptom | Likely cause |
| --- | --- |
| Connector rejects URL | not public / missing https / wrong path (need `/mcp`) |
| Tools empty | handshake not MCP; check POST /mcp tools/list via curl |
| 401 | token mismatch |
| execute fails path | Grok cloud cannot see `D:\…` — path is on **your** PC; executor runs **locally** so path is OK if server is on that PC |
| SSE errors on cloudflared | use ngrok for SSE transports; our `/mcp` is request/response JSON |

**Cloudflare quick tunnel does not support SSE**; if Grok requires SSE and fails, switch to **ngrok**.
