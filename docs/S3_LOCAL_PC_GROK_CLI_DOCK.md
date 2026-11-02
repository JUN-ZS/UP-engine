# S3 本機 PC × Grok 對接文 v1.1（Local PC Dock）

**status:** DOCK_SPEC_v1.1 · RUNNABLE  
**branch:** `feat/upscale-s3-heterogeneous-runner-v0.1`  
**目標:** 用 **你本機的 CPU / RAM** 當 S3 Worker；遠端 Grok（HERE）只做協調／驗收（若看不到磁碟，連 controller 也在本機跑）。

**不宣稱:** quality PASS · E3 · 自動 physical dual-host · Grok CLI plugin

---

## 0. 角色邊界（必讀）

| 名稱 | 是什麼 | 不是什麼 |
| --- | --- | --- |
| `tools/s3_worker_agent.py` | pull worker：registry + claim + heartbeat | Grok plugin |
| `tools/s3_controller.py` | init / schedule / wait / rebuild / status | 遠端佔用本機 RAM 的通道 |
| `tools/s3_dock_local_pc.py` | 本機 dock 啟動器（偵測 RAM/CPU、handshake、轉 agent） | 獨立 Grok CLI |
| `ige` | UP-engine 引擎 CLI | Grok CLI |
| handshake JSON | **離線宣告**（可貼 chat） | **排程輸入** |

**排程只看** `registry/workers/<id>.json`，**不看** handshake。

**實時** = 共享 `job-dir` 上的 claim / heartbeat。  
遠端 Grok **不能** 直接占用這台 PC 的 CPU/RAM。Chat 貼 JSON 只是離線宣告。

---

## 1. v1.1 相對 ff19211 的修正

| 問題 | v1.1 行為 |
| --- | --- |
| `init` 要求 job-dir 全空 | 允許先存在 `dock/`、`registry/workers/*.json`、空的 `queue/` / `children/`；已有 manifest / plan / receipt 仍拒絕 |
| Worker 只等 manifest ~5s | 持續 heartbeat，預設等 **600s**（`--wait-manifest-s`） |
| registry `cpu_threads` 寫死 1 | `--cpu-threads` 寫入 registry（dock 自動偵測並傳入） |
| `dock_mode=shared_fs` ⇒ `physical_dual_host=true` | **預設 false**；只有 `--claim-physical-dual-host` 才為 true（操作者聲明） |
| bash `\` 續行當 PowerShell 用 | 文件改為 **PowerShell 一行一參數** 範例 |

**排程門檻（不變）:**

`ram_available_mib >= est_peak_rss_mib + 256`

- synthetic `est_peak_rss_mib = 200` → 需要 **可用 RAM > 456 MiB**
- Controller 與 worker 的 **`--lease-seconds` 必須相同**

---

## 2. 可落地順序（worker 可先開）

```
1) 本機：s3_dock_local_pc（或 s3_worker_agent）先跑 → 寫 dock/ + registry heartbeat
2) 本機：s3_controller init（允許 dock/registry 已存在）
3) 本機：s3_controller schedule --wait-workers 1
4) 本機：s3_controller wait
5) 本機：s3_controller rebuild
6) 可選：把 handshake / controller_report / checklist 貼回 Grok chat 做核對
```

這是 **單機 pull** 也能跑的順序；**不是** 兩台機器 physical dual-host。

---

## 3. PowerShell（本機）

Repo：`C:\Users\user\Documents\GitHub\UP-engine`  
**不要** 為了對接再 checkout 回 ff19211；用含 v1.1 的工作樹。

```powershell
cd C:\Users\user\Documents\GitHub\UP-engine
$JOB = "D:\s3_share\job01"
$LEASE = 90

# 探測：只印 handshake（可貼 chat；controller_where/sync 會是 unknown）
python tools/s3_dock_local_pc.py --job-dir $JOB --print-handshake-only

# 視窗 A：本機 worker（用本機 CPU/RAM）
python tools/s3_dock_local_pc.py `
  --job-dir $JOB `
  --worker-id localpc_main `
  --mode synthetic `
  --device cpu `
  --dock-mode shared_fs `
  --lease-seconds $LEASE `
  --wait-manifest-s 600 `
  --idle-exit-s 300

# 視窗 B：controller（HERE 看不到磁碟時必須在本機）
python tools/s3_controller.py init `
  --job-dir $JOB `
  --base path\to\BASE.jpg `
  --mode synthetic `
  --region 0,0,128,128 `
  --compute-core 64 `
  --lease-seconds $LEASE

python tools/s3_controller.py schedule `
  --job-dir $JOB `
  --wait-workers 1 `
  --wait-timeout-s 60 `
  --lease-seconds $LEASE

python tools/s3_controller.py wait `
  --job-dir $JOB `
  --timeout-s 3600 `
  --reassign-every-s 3 `
  --lease-seconds $LEASE

python tools/s3_controller.py rebuild --job-dir $JOB --lease-seconds $LEASE
python tools/s3_controller.py status --job-dir $JOB
```

PowerShell 續行用 **反引號 `` ` ``**，不是 bash 的 `\`。  
也可以全部寫成單行（去掉 `` ` ``）。

Siax 另加：

```powershell
python tools/s3_dock_local_pc.py --job-dir $JOB --worker-id localpc_siax --mode siax --device cpu --checkpoint models\4x_NMKD-Siax_200k.pth --confirm-model-license-review --lease-seconds $LEASE
```

---

## 4. 貼回 chat 的探測

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
controller_where: local_pc | other_host | here_cannot_see_disk | unknown
sync: syncthing|nfs|smb|none|unknown
ready_for_schedule: yes|no
lease_seconds: 90
physical_dual_host: false
final_acceptance: false
e3_speed_claim: false
```

Handshake 的 `controller_where` / `sync` 預設 **unknown**（本進程看不到另一台機器）。  
HERE 看不到你的磁碟 → **controller 在你這台跑**；算力仍是這台 PC。

---

## 5. 安全與誠實

- pull 模型，不要求對公網開 inbound。
- `physical_dual_host` 預設 false；真雙機要另交證據 + 明確 `--claim-physical-dual-host`。
- 單機 tmp 目錄 pull 測試 ≠ 兩台機器。
- quality / E3 永不因 dock 成功而翻 true。

## 6. 測試

```powershell
python -m pytest tests/test_s3_local_pc_dock.py tests/test_s3_control_plane.py -q
```

`test_s3_local_pc_dock.py`：handshake → worker 先開 → init → schedule → wait → rebuild（synthetic，單機）。
