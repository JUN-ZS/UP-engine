#Requires -Version 5.1
<#
.SYNOPSIS
  Run ige capture-model-inventory against the local ComfyUI models root.

.NOTES
  Disk capture only. No GPU. Never unlocks Flux execution.
#>
param(
  [string]$ModelsRoot = "C:\Users\user\Documents\ComfyUI\models",
  [string]$Out = $(Join-Path $env:USERPROFILE "Desktop\高清探\model_inventory_capture_receipt.json")
)

$ErrorActionPreference = "Stop"

if (-not (Test-Path -LiteralPath $ModelsRoot)) {
  throw "models-root not found: $ModelsRoot"
}

$outDir = Split-Path -Parent $Out
if ($outDir -and -not (Test-Path -LiteralPath $outDir)) {
  New-Item -ItemType Directory -Path $outDir | Out-Null
}

Write-Host "Capturing model inventory from: $ModelsRoot"
Write-Host "Writing receipt to: $Out"

& ige capture-model-inventory --models-root $ModelsRoot --out $Out
if ($LASTEXITCODE -ne 0) {
  throw "capture-model-inventory failed with exit code $LASTEXITCODE"
}

Write-Host "Done. evidence_grade=disk_capture; execution_allowed remains false."
