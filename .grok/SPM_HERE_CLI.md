# Grok CLI · HERE 抓圖 → 本機 SPM

Images prepared in the HERE Grok chat are **shipped in git** under `packages/spm_here/` so the local Grok CLI / shell can grab them without grok.com OAuth MCP.

## Grab warrior package (default BASE)

```powershell
cd C:\Users\user\Documents\GitHub\UP-engine
git pull
.\.venv\Scripts\Activate.ps1
python tools\spm_here_grab.py --list
python tools\spm_here_grab.py --package warrior_mud_hammer --variant base
```

Copies to `D:\s3_share\spm_in\warrior_BASE.jpg` (see package manifest).

## Grab + run local Siax 4×

```powershell
python tools\spm_here_grab.py --package warrior_mud_hammer --variant base --run-siax
```

Paste `outbox\here_*_result.json` back to the HERE chat.

## Variants

- `base` — original HERE still (default SPM input)
- `master` — polished still

Share links (view only; **files in package are source of truth for CLI**):
- base: https://grok.com/imagine/post/cd5c430d-f261-4f9f-aa3b-d5782d9f5ced?source=agent
- master: https://grok.com/imagine/post/4ac69625-ed8d-4666-b778-e93227a3c48d?source=agent
