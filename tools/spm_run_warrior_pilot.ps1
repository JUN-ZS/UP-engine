# Grok CLI / human: grab HERE warrior package from git, then local Siax
param(
  [ValidateSet("base","master")][string]$Variant = "base",
  [switch]$GrabOnly
)
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root
$py = Join-Path $Root ".venv\Scripts\python.exe"
if (-not (Test-Path $py)) { throw "Missing .venv: $py" }

& $py tools\spm_here_grab.py --list | Out-Host
if ($GrabOnly) {
  & $py tools\spm_here_grab.py --package warrior_mud_hammer --variant $Variant
} else {
  & $py tools\spm_here_grab.py --package warrior_mud_hammer --variant $Variant --run-siax
}
