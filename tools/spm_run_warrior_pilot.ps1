# Full-frame local Siax pilot for HERE warrior BASE (1792x1008 -> 4x)
# Prerequisite: save the HERE image as D:\s3_share\spm_in\warrior_BASE.jpg
param(
  [string]$Input = "D:\s3_share\spm_in\warrior_BASE.jpg",
  [string]$OutPng = "D:\s3_share\spm_handoff\outbox\warrior_SIAX4X.png",
  [string]$HandoffRoot = "D:\s3_share\spm_handoff",
  [int]$Tile = 128,
  [int]$Pad = 8
)
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root
$py = Join-Path $Root ".venv\Scripts\python.exe"
if (-not (Test-Path $py)) { throw "Missing .venv python: $py" }
if (-not (Test-Path $Input)) { throw "Missing input — save HERE image to: $Input" }

New-Item -ItemType Directory -Force -Path (Split-Path $OutPng) | Out-Null
New-Item -ItemType Directory -Force -Path "$HandoffRoot\inbox","$HandoffRoot\outbox","$HandoffRoot\done" | Out-Null

& $py tools\spm_here_request.py `
  --input $Input `
  --output $OutPng `
  --device auto `
  --tile-size $Tile `
  --tile-pad $Pad `
  --note "warrior full-frame SPM local pilot" `
  --source-asset-hint "cd5c430d-f261-4f9f-aa3b-d5782d9f5ced" `
  --inbox "$HandoffRoot\inbox"

$env:SPM_HANDOFF_ROOT = $HandoffRoot
& $py tools\spm_here_pull.py --once --root $HandoffRoot

Write-Host "Done. Paste the newest *_result.json from $HandoffRoot\outbox back to Grok chat."
Get-ChildItem "$HandoffRoot\outbox\*result.json" | Sort-Object LastWriteTime -Descending | Select-Object -First 1 | ForEach-Object { Write-Host $_.FullName }
