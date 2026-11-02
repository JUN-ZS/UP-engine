# Grok CLI / human: background self-drive on Windows
param(
  [string]$Stages = "unit,single_pull,self_hosted_hint",
  [double]$Lease = 90,
  [string]$Evidence = "docs/evidence/S3_SELF_DRIVE_LOCAL.json",
  [switch]$Background
)
Set-Location $PSScriptRoot\..
$env:PYTHONUNBUFFERED = "1"
$argsList = @(
  "-3", "tools/s3_self_drive.py",
  "--stages", $Stages,
  "--lease-seconds", "$Lease",
  "--evidence-out", $Evidence
)
if ($Background) {
  $log = Join-Path $env:TEMP "s3_self_drive_out.log"
  $err = Join-Path $env:TEMP "s3_self_drive_err.log"
  Start-Process -FilePath "py" -ArgumentList $argsList -NoNewWindow `
    -RedirectStandardOutput $log -RedirectStandardError $err
  Write-Host "started background self-drive; logs: $log $err"
} else {
  & py @argsList
  exit $LASTEXITCODE
}
