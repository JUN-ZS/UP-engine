<#
.SYNOPSIS
  NFE 一鍵：bolt → bootstrap → STICK → (可選 procedural / encode)
.EXAMPLE
  .\tools\nfe_one_click.ps1 -Master D:\s3_share\F0.png -JobId nfe_e107 -OutDir runs\nfe\e107
  .\tools\nfe_one_click.ps1 -BoltOnly
#>
param(
  [string]$Master = "",
  [string]$JobId = "nfe_job",
  [string]$OutDir = "runs\nfe\default",
  [string]$AssetId = "",
  [int]$MaxSide = 1280,
  [int]$ProceduralSteps = 0,
  [int]$Fps = 24,
  [switch]$Encode,
  [switch]$VerifyF2f,
  [switch]$BoltOnly
)
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
if (-not (Test-Path $Root)) { $Root = Get-Location }
Set-Location $Root
$py = $null
foreach ($c in @(
  ".\.venv\Scripts\python.exe",
  "py",
  "python"
)) {
  if ($c -eq "py" -or $c -eq "python") {
    try { & $c -3 -c "import sys" 2>$null; if ($LASTEXITCODE -eq 0) { $py = "$c -3"; break } } catch {}
    try { & $c -c "import sys" 2>$null; if ($LASTEXITCODE -eq 0) { $py = $c; break } } catch {}
  } elseif (Test-Path $c) { $py = $c; break }
}
if (-not $py) { throw "No python found. Prefer .\.venv\Scripts\python.exe" }

$argsList = @("tools\nfe_one_click.py")
if ($BoltOnly) {
  $argsList += "--bolt-only"
} else {
  if (-not $Master) { throw "-Master required unless -BoltOnly" }
  $argsList += @("--master", $Master, "--job-id", $JobId, "--out-dir", $OutDir, "--max-side", "$MaxSide")
  if ($AssetId) { $argsList += @("--asset-id", $AssetId) }
  if ($ProceduralSteps -gt 0) { $argsList += @("--procedural-steps", "$ProceduralSteps") }
  if ($Encode) { $argsList += "--encode"; $argsList += @("--fps", "$Fps") }
  if ($VerifyF2f) { $argsList += "--verify-f2f" }
}

Write-Host "NFE one-click :: $py $($argsList -join ' ')"
if ($py -match "^-") { throw "bad py" }
# invoke
$exe = $py
$rest = $argsList
if ($py -eq "py -3") {
  & py -3 @argsList
} else {
  & $exe @argsList
}
exit $LASTEXITCODE
