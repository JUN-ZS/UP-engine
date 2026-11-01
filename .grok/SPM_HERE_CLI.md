# Grok CLI · HERE 抓圖 → 本機 Siax（v1.1 命名）

## 以後怎麼 CALL

在 repo 根目錄（已 `git pull`、`.venv` 可選）：

```powershell
cd C:\Users\user\Documents\GitHub\UP-engine
git pull
.\.venv\Scripts\Activate.ps1   # 有 torch+cuda 的 venv

# 1) 看有哪些 package
.\tools\spm_cli.ps1 list
# 或:  python tools\spm_here_grab.py --list

# 2) 只抓圖（不跑 Siax）
.\tools\spm_cli.ps1 grab -Package warrior_mud_hammer -Variant base

# 3) 抓圖 + 本機 Siax（商用 cell 建議）
.\tools\spm_cli.ps1 run -Package warrior_mud_hammer -Variant base -Cell 256/16

# 等價 python：
python tools\spm_here_grab.py --package warrior_mud_hammer --variant base --run-siax --cell 256/16
```

Grok CLI 若只能跑 shell 指令，讓它執行 **同一條** `spm_cli.ps1 run ...` 或 `python tools/spm_here_grab.py ...` 即可（**不要**再手動另存聊天圖成衝突檔名）。

## 命名規則（修 errno 22／覆蓋錯）

| | 規則 |
| --- | --- |
| **輸入** | `D:\s3_share\spm_in\{package}_{variant}.jpg` |
| **輸出** | `D:\s3_share\spm_handoff\outbox\{package}_{variant}_t{T}p{P}_{request_id}.png` |
| **同 SHA** | 輸入已存在且雜湊相同 → **跳過複製**（不重存） |
| **不同 SHA** | 寫入 `_{sha8}` 後綴，除非 `--force-dest` |
| **禁止預設** | 固定覆蓋 `warrior_SIAX4X.png`（易鎖檔 → errno 22） |

跑完把 `outbox\*_result.json` **貼回 HERE chat**。

## 與 watch

可另開：`python tools\spm_here_pull.py --watch`  
`run` 模式會自己 `process_one`，**不必**與 watch 同時搶同一 request。
