# SPM / HERE local CLI entry (Windows). Use from Grok CLI shell or PowerShell.
#   .\tools\spm_cli.ps1 list
#   .\tools\spm_cli.ps1 pack -Package street_v1 -Image D:\path\to\new.jpg
#   .\tools\spm_cli.ps1 grab -Package street_v1
#   .\tools\spm_cli.ps1 run  -Package street_v1 -Cell 256/16
param(
  [Parameter(Position=0)]
  [ValidateSet("list","grab","run","pack","help")]
  [string]$Cmd = "help",
  [string]$Package = "warrior_mud_hammer",
  [ValidateSet("base","master")]
  [string]$Variant = "base",
  [string]$Cell = "256/16",
  [string]$Image = "",
  [switch]$ForceDest
)
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root
$py = Join-Path $Root ".venv\Scripts\python.exe"
if (-not (Test-Path $py)) { $py = "py"; $pyArgs = @("-3") } else { $pyArgs = @() }

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
  "list" {
    & $py @pyArgs tools\spm_here_grab.py --list
    & $py @pyArgs tools\spm_here_pack.py list
    exit 0
  }
  "pack" {
    if (-not $Image) { throw "pack requires -Image path\to\BASE.jpg" }
    if (-not $Package -or $Package -eq "warrior_mud_hammer") {
      Write-Host "Tip: use a NEW -Package id for new art, e.g. -Package street_rain_v1"
    }
    & $py @pyArgs tools\spm_here_pack.py create --package $Package --image $Image --variant $Variant --cell-default $Cell
    exit $LASTEXITCODE
  }
  "grab" { Invoke-Grab; exit $LASTEXITCODE }
  "run"  { Invoke-Grab -Run; exit $LASTEXITCODE }
  default {
    Write-Host @"
SPM HERE CLI

  # 旧示例包（第一张雷暴战锤图的 id，不是唯一永久名字）
  .\tools\spm_cli.ps1 run -Package warrior_mud_hammer -Cell 256/16

  # 新图：先登记 package，再 run
  .\tools\spm_cli.ps1 pack -Package my_new_scene -Image D:\path\to\BASE.jpg
  .\tools\spm_cli.ps1 run  -Package my_new_scene -Cell 256/16

  .\tools\spm_cli.ps1 list
"@
  }
}
