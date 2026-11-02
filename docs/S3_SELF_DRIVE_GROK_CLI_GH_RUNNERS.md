# S3 自走驗證流程 · Grok CLI × GitHub Runners × Docker

**status:** SPEC_v1  
**goal:** 你本機 Grok CLI / `gh` / 一條命令，**後台跑完** S3 驗證鏈，不必人工逐步貼指令。  
**不宣稱:** quality PASS · E3 · 遠端 Grok chat 被 CLI 當 live brain 呼叫

---

## 0. 先拆清三件事（常被混在一起）

| 機制 | 能做什麼 | 不能做什麼 |
| --- | --- | --- |
| **GitHub Actions 雙 Runner** | 兩台 self-hosted 同 workflow、共享 job-dir、同步做工 | 自動等於 Siax 品質通過 |
| **Docker compose 雙 worker** | **一台機**上兩個容器 + volume，CI 可自走 | **不是** physical dual-host |
| **Grok CLI →「呼叫你（HERE chat）」** | CLI 可跑腳本、`gh workflow run`、貼結果 | **不能** 把這個 chat session 當常駐遠端 API 佔用 sandbox 替你算完所有 job |

**正確自走模型：**

```text
Grok CLI / 你
    │  觸發（一條命令）
    ▼
tools/s3_self_drive.py     或     gh workflow run s3-self-drive.yml
    │
    ├─ unit tests
    ├─ single_pull（本機/CI 單機）
    ├─ docker_dual（可選，同機雙容器）
    └─ dual self-hosted（可選，真雙機 runner）
    │
    ▼
evidence JSON / Actions artifact
    │  可選貼回 chat 給 Grok 核對
    ▼
Grok（HERE）只做審閱，不假裝已 remote 控制你的 PC
```

GitHub「雙 runner 異機同工」≈ S3 的 **Capability Scheduler + 共享 queue + 兩 worker**；  
差別是 GH 管 **CI job 圖**，S3 管 **tile children**。我們用 **同一套 agent/controller**，讓 GH runner 當 host A/B。

---

## 1. 一鍵自走（本機 · 給 Grok CLI 後台呼叫）

### PowerShell

```powershell
cd C:\Users\user\Documents\GitHub\UP-engine
$env:PYTHONUNBUFFERED = "1"

# 後台 job（不擋 CLI）
Start-Process -NoNewWindow -FilePath "py" -ArgumentList @(
  "-3", "tools/s3_self_drive.py",
  "--stages", "unit,single_pull,self_hosted_hint",
  "--lease-seconds", "90",
  "--evidence-out", "docs/evidence/S3_SELF_DRIVE_LOCAL.json"
) -RedirectStandardOutput "D:\s3_share\self_drive_out.log" `
  -RedirectStandardError "D:\s3_share\self_drive_err.log"

# 或前景跑完
py -3 tools/s3_self_drive.py `
  --stages unit,single_pull,self_hosted_hint `
  --lease-seconds 90 `
  --evidence-out docs/evidence/S3_SELF_DRIVE_LOCAL.json
```

### 若 Grok CLI 只能跑「一條 shell」

```text
py -3 tools/s3_self_drive.py --stages unit,single_pull,self_hosted_hint --evidence-out docs/evidence/S3_SELF_DRIVE_LOCAL.json
```

跑完把 `S3_SELF_DRIVE_LOCAL.json` 貼回 chat → Grok 驗收標籤（仍 false quality/E3）。

---

## 2. GitHub 自走（推薦當「後台」）

```powershell
gh workflow run s3-self-drive.yml -f stages=unit,single_pull,self_hosted_hint
gh run watch
gh run download -n s3-self-drive-evidence
```

| Input | 含義 |
| --- | --- |
| `stages` | `unit,single_pull,self_hosted_hint` |
| `run_docker_dual=true` | 在 ubuntu-latest 上試 Docker 雙 worker（**同機**） |
| `run_dual_self_hosted=true` | 真雙 self-hosted runner（需標籤 + 共享盤） |

### 真雙 runner 前置

1. 兩台機器安裝 [GitHub self-hosted runner](https://docs.github.com/en/actions/hosting-your-own-runners)  
2. 標籤：`s3-host-a`、`s3-host-b`  
3. 兩邊能讀寫同一路徑（NFS/SMB），設 repo variable：`S3_SHARED_JOB=/shared/s3_jobs/ci_job`  
4. `gh workflow run s3-self-drive.yml -f run_dual_self_hosted=true`  

這才是對齊「GitHub 雙 runner 異機同工」的 S3 版；**Docker 不能替代這步的 physical 宣稱**。

---

## 3. Docker 嗎？

| | |
| --- | --- |
| **用途** | CI／本機快速驗「兩 worker + 一 controller + 共享 volume」 |
| **命令** | `docker compose -f docker/s3-dual-worker/docker-compose.yml run --rm controller` |
| **或** | `s3_self_drive.py --stages docker_dual` |
| **標籤** | `physical_dual_host=false` · `container_dual_on_one_machine` |

有 Docker 就多一層自走；**沒有 Docker 不阻塞** unit + single_pull +（有 runner 時）self-hosted dual。

---

## 4. 「Grok CLI 後台呼叫你」的誠實答案

| 期望 | 現實 |
| --- | --- |
| CLI 喚醒 **這個 chat** 連跑 448 Siax | **不支援** 當常駐 job runner |
| CLI 後台跑 **腳本 / Actions**，結果給你核對 | **支援**（本文件） |
| CLI 用 **xAI API** 問模型決策 | 那是 API，不是 HERE sandbox 的 S3 worker |
| Automations 排程 prompt | 可排「之後提醒驗收」，仍不替你佔本機 RAM |

**自走主路徑 = `s3_self_drive.py` + `s3-self-drive.yml`，不是 chat RPC。**

---

## 5. 建議驗證階梯（自走可選 stages）

```text
1 unit                 ← 每次必跑
2 single_pull          ← 你已手動證明；納入自走回歸
3 docker_dual          ← 有 Docker 時
4 dual self-hosted     ← 兩 runner + 共享盤（真 dual-host 候選）
5 siax_mini            ← S3_CONFIRM_MODEL_LICENSE=1 + checkpoint
6 S3.7 448             ← 另開，不塞進預設 self-drive
```

預設 **不** 跑 448、**不** 跑 Siax full、**不** 翻 quality。

---

## 6. 檔案

| 檔 | 作用 |
| --- | --- |
| `tools/s3_self_drive.py` | 本機/CI 一鍵編排 |
| `.github/workflows/s3-self-drive.yml` | Actions 後台 |
| `docker/s3-dual-worker/docker-compose.yml` | 同機雙容器 |
| `docs/S3_SELF_DRIVE_GROK_CLI_GH_RUNNERS.md` | 本文 |

---

## 7. 與 job01 成功的關係

`D:\s3_share\job01` 手動 pull 成功 = 人工驗收。  
自走流程 = **同一管線可重複、可 CI、可雙 runner**。  
下一輪仍用 **新 job-dir**；自走會自己建 `runs/s3_self_drive_<stamp>/`。
