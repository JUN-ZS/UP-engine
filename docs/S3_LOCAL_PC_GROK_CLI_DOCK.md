# S3 本機 PC × Grok 對接文（Local Grok CLI Dock）

**status:** DOCK_SPEC_v1  
**branch:** `feat/upscale-s3-heterogeneous-runner-v0.1`  
**目標:** 用 **你本機的 CPU / RAM** 當 S3 Worker；遠端 Grok（HERE sandbox）當 **Controller 協調 / 驗收**，不是偷你本機算力的 socket 木馬。

**不宣稱:** quality PASS · E3 speed · S2.1 翻盤 · 已完成 physical dual-host（除非雙方真的跑起來並交證據）。

---

## 0. 先講清楚「實時對接」能到哪

| 層級 | 是什麼 | 實時程度 | 誰跑推論 |
| --- | --- | --- | --- |
| **A · Shared FS dock（推薦）** | 兩邊看同一個 `job-dir`（Syncthing / NFS / SMB / 雲同步盤） | **近實時**（秒級 heartbeat + claim） | **你的 PC** |
| **B · 本機 Grok CLI 包一層** | CLI 只是啟動 `s3_dock_local_pc.py` + 印 handshake | 同 A | **你的 PC** |
| **C · 手動貼 handshake / 狀態 JSON** | 你把 JSON 貼進這個 chat | **非實時**（人工節奏） | 你的 PC 或你手動 |
| **D · 反向 WebSocket 進 sandbox** | 遠端 Grok 直接連你家 PC | **本環境做不到** | — |

**硬事實：**

1. 遠端 Grok sandbox **沒有** 路徑可以主動打開你家 PC 的 CPU/RAM。  
2. **必須** 你本機先跑一個 **pull-based agent**（主動登記、領任務、heartbeat、交 receipt）。  
3. 「與 Grok 實時對接」在本設計 = **共享 job 狀態機**，不是 chat 裡直接 `import torch` 用你 RAM。

```
┌─────────────────────┐         shared job-dir          ┌──────────────────────┐
│  HERE / Grok chat   │◄──── Syncthing / NFS / 貼文 ────►│  你的 PC             │
│  (Controller 協調)  │      queue/ registry/ dock/     │  s3_dock_local_pc.py │
│  tools/s3_controller│                                  │  → s3_worker_agent   │
└─────────────────────┘                                  └──────────────────────┘
        不跑重推論（或只跑輕量）                              使用本機 CPU/RAM
```

---

## 1. 對接契約（Dock Contract）

### 1.1 角色

| 角色 | 進程 | 責任 |
| --- | --- | --- |
| **Controller (HERE)** | `tools/s3_controller.py` 或 Grok 代跑指令 | `init` / `schedule` / `wait` / `rebuild` / 驗 SHA |
| **Local PC Worker** | `tools/s3_dock_local_pc.py` → `s3_worker_agent.py` | 回報能力、claim、推論、heartbeat、寫 receipt |
| **Human / Grok CLI** | 你本機終端 | 啟動 dock、保證 job-dir 同步、把 handshake 貼給 Grok（可選） |

### 1.2 共享目錄布局

```
JOB_DIR/
  job_manifest.json
  plan.json
  assignment.json
  dock/
    local_pc_handshake.json    # 本機 dock 寫入
    here_controller.json       # 可選：HERE 寫入 session 標記
  registry/workers/<id>.json
  queue/{pending,lease,done,failed,dead,heartbeats,rejects}/
  children/*.png
  OUT_PRIMARY.png
  controller_report.json
```

### 1.3 Handshake 檔

- Schema: `schemas/s3-dock-handshake.schema.json`
- 本機寫入: `JOB_DIR/dock/local_pc_handshake.json`
- 內容含: `worker_id`, 實測/偵測 RAM·CPU, device, `dock_mode`, `status`

Grok 在 chat 裡若讀到你貼的 handshake，即可把 `worker_id` 當作 schedule 目標之一，**不會**因此獲得你 PC 的 shell。

---

## 2. 本機 Grok CLI 怎麼接（你要複製的指令）

以下假設 repo 在本機：

```bash
git clone https://github.com/JUN-ZS/UP-engine.git
cd UP-engine
git checkout feat/upscale-s3-heterogeneous-runner-v0.1
python -m pip install -e .
```

### 2.1 一鍵探測（只印 handshake，不跑 agent）

```bash
python tools/s3_dock_local_pc.py \
  --job-dir /path/to/shared/s3_job \
  --print-handshake-only
```

把 stdout 的 JSON **貼回這個 Grok 對話**，即完成「對接宣告」。

### 2.2 正式用本機 CPU/RAM 當 worker

**Windows PowerShell / macOS / Linux 通用：**

```bash
# 與 HERE 約定同一個 JOB_DIR（同步盤路徑）
set JOB=D:\s3_share\job01          # Windows 例
# export JOB=$HOME/s3_share/job01  # Unix 例

python tools/s3_dock_local_pc.py \
  --job-dir "$JOB" \
  --worker-id localpc_main \
  --mode synthetic \
  --device cpu \
  --dock-mode shared_fs \
  --lease-seconds 90 \
  --idle-exit-s 300
```

Siax（真模型，須你確認授權）：

```bash
python tools/s3_dock_local_pc.py \
  --job-dir "$JOB" \
  --worker-id localpc_siax \
  --mode siax \
  --device cpu \
  --checkpoint models/4x_NMKD-Siax_200k.pth \
  --confirm-model-license-review \
  --dock-mode shared_fs
```

有 NVIDIA：

```bash
  --device cuda
```

### 2.3 若你說的「本機 Grok CLI」是包裝器

在本機建 `grok-s3-dock.cmd` / `grok-s3-dock`：

```bash
#!/usr/bin/env bash
# grok-s3-dock — thin wrapper: local Grok CLI entry → S3 PC worker
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
exec python "$ROOT/tools/s3_dock_local_pc.py" "$@"
```

之後：

```bash
grok-s3-dock --job-dir "$JOB" --mode synthetic --device cpu
```

**CLI 不需要** 持有 `XAI_API_KEY` 才能當 S3 worker；那是 READ/Imagine 路徑。S3 dock 只用本機 Python +（可選）torch/Siax。

---

## 3. HERE / 遠端 Grok 側（我這邊）怎麼對

當你貼了 handshake 或 shared 路徑就緒：

```bash
# 在能看見同一個 JOB_DIR 的機器上（可以是你 PC，或另一台同步節點）
python tools/s3_controller.py init \
  --job-dir "$JOB" \
  --base /path/to/BASE.jpg \
  --mode synthetic \
  --region 0,0,128,128 \
  --compute-core 64 \
  --lease-seconds 90

# 等 registry 出現 localpc_*
python tools/s3_controller.py schedule \
  --job-dir "$JOB" \
  --wait-workers 1 \
  --wait-timeout-s 60 \
  --lease-seconds 90

python tools/s3_controller.py wait \
  --job-dir "$JOB" \
  --timeout-s 3600 \
  --reassign-every-s 3 \
  --lease-seconds 90

python tools/s3_controller.py rebuild --job-dir "$JOB" --lease-seconds 90
```

**雙機真實 pilot：**  
- Host A = 你 PC（worker，可兼 controller）  
- Host B = 另一 worker 或僅 HERE 只做文件驗收  

若 HERE sandbox **看不到** 你的 disk：由 **你本機跑 controller + worker**，只把 `controller_report.json` / handshake / SHA **貼回 chat** 給我核對。這仍算 **本機算力**；physical dual-host 要兩台 OS + 共享 FS。

---

## 4. 推薦同步方式（沒有 NFS 時）

| 方案 | 做法 | 注意 |
| --- | --- | --- |
| **Syncthing** | 兩邊同步 `JOB_DIR` | 關閉「覆寫衝突不通知」；`queue/` 依賴 atomic rename，同步延遲會拉長 lease |
| **SMB/NFS** | 真共享磁碟 | 最接近 S3.6 設計 |
| **雲盤 (OneDrive/Dropbox)** | 僅小 pilot | **不建議** 高頻 rename；lease 要加長（≥120s） |
| **rsync loop** | 本機 cron 每 2s rsync | `dock_mode=rsync_pull`；證據級，非正式生產 |
| **只貼 JSON** | 無共享盤 | 只能做宣告 / 離線驗收，**不是** 實時領任務 |

**lease 建議：** 同步延遲 p95 若約 5s，lease ≥ 60–90s，heartbeat 1s。

---

## 5. 對接檢查清單（貼給 Grok 用）

本機執行後，回覆這份（可直接複製填空）：

```text
S3_DOCK_CHECKLIST
worker_id: localpc_...
hostname: ...
ram_available_mib: ...
cpu_threads: ...
device: cpu|cuda
dock_mode: shared_fs|rsync_pull|manual_paste
job_dir: ...
handshake_path: .../dock/local_pc_handshake.json
agent_running: yes|no
controller_where: local_pc | other_host | here_cannot_see_disk
sync: syncthing|nfs|smb|none
ready_for_schedule: yes|no
```

我收到後只會：

1. 確認 handshake 欄位  
2. 給出下一個 `s3_controller` 指令（或請你本機跑）  
3. 核對 `done` 數、receipt、rebuild SHA  
4. **不** 宣告 quality PASS / E3

---

## 6. 安全邊界

- Dock **不** 要求你關防火牆對 inbound 開埠（pull 模型）。  
- **不要** 把 agent 跑成對公網暴露的 RCE。  
- Siax 權重與授權仍是你的責任；`--confirm-model-license-review` 必須你本人確認。  
- 本機 agent 只寫 `JOB_DIR` 下約定路徑，不掃全盤。

---

## 7. 與「另一 Grok Canvas / VM」的關係

| 問題 | 答 |
| --- | --- |
| 另一 Canvas 能否當第二台 host？ | **不能自動**；除非那個 session 的 sandbox 也掛了同一 `JOB_DIR`（通常沒有）。 |
| 本機 Grok CLI 能否「把 RAM 借給遠端 Grok」？ | **否**；是 **本機進程** 自己算，遠端只協調/驗收。 |
| 怎樣才算 physical dual-host？ | 兩台獨立機器（或你 PC + 真雲 VM）+ 共享 job-dir + 證據 JSON。 |

---

## 8. 檔案索引

| 檔 | 用途 |
| --- | --- |
| `docs/S3_LOCAL_PC_GROK_CLI_DOCK.md` | 本文 |
| `tools/s3_dock_local_pc.py` | 本機 dock 啟動器（自動 RAM/CPU + handshake + agent） |
| `tools/s3_worker_agent.py` | 真正 worker |
| `tools/s3_controller.py` | Controller CLI |
| `schemas/s3-dock-handshake.schema.json` | Handshake schema |
| `docs/S3_DUAL_HOST_PILOT.md` | 雙機 pilot 總則 |

---

## 9. 最小成功標準（Dock pilot）

1. 本機印出 handshake，`status=online|working`  
2. `registry/workers/<worker_id>.json` 出現且未 stale  
3. schedule 後本機 claim ≥1 child  
4. `queue/done` 有 receipt；rebuild 可選  
5. 報告寫明 `physical_dual_host` 真假；`final_acceptance=false`；`e3_speed_claim=false`
