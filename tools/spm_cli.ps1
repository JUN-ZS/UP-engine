# SPM / HERE local CLI entry (Windows). Use from Grok CLI shell or PowerShell.
# Examples:
#   .\tools\spm_cli.ps1 list
#   .\tools\spm_cli.ps1 grab -Package warrior_mud_hammer -Variant base
#   .\tools\spm_cli.ps1 run  -Package warrior_mud_hammer -Variant base -Cell 256/16
#   .\tools\spm_cli.ps1 run  -Package warrior_mud_hammer -Cell 128/8
param(
  [Parameter(Position=0)]
  [ValidateSet("list","grab","run","help")]
  [string]$Cmd = "help",
  [string]$Package = "warrior_mud_hammer",
  [ValidateSet("base","master")]
  [string]$Variant = "base",
  [string]$Cell = "",
  [switch]$ForceDest
)
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root
$py = Join-Path $Root ".venv\Scripts\python.exe"
if (-not (Test-Path $py)) {
  $py = "py"
  $pyArgs = @("-3")
} else {
  $pyArgs = @()
}

function Invoke-Grab {
  param([switch]$Run)
  $a = @("tools\spm_here_grab.py", "--package", $Package, "--variant", $Variant)
  if ($ForceDest) { $a += "--force-dest" }
  if ($Cell) { $a += @("--cell", $Cell) }
  if ($Run) { $a += "--run-siax" }
  & $py @pyArgs @a
  if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
}

switch ($Cmd) {
  "list" { & $py @pyArgs tools\spm_here_grab.py --list; exit $LASTEXITCODE }
  "grab" { Invoke-Grab; exit $LASTEXITCODE }
  "run"  { Invoke-Grab -Run; exit $LASTEXITCODE }
  default {
    Write-Host @"
SPM HERE CLI (local GPU Siax · no grok.com OAuth)

  .\tools\spm_cli.ps1 list
  .\tools\spm_cli.ps1 grab -Package warrior_mud_hammer -Variant base
  .\tools\spm_cli.ps1 run  -Package warrior_mud_hammer -Variant base -Cell 256/16

Naming (v1.1):
  input:  D:\s3_share\spm_in\{package}_{variant}.jpg
  output: D:\s3_share\spm_handoff\outbox\{package}_{variant}_t{T}p{P}_{request_id}.png

Paste outbox\*_result.json back to HERE chat.
"@
  }
}
