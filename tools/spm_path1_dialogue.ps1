# PATH1: Dialogue tools — local Siax HTTP + MCP /mcp for Grok custom connector
# Usage:
#   .\tools\spm_path1_dialogue.ps1              # start server (foreground)
#   .\tools\spm_path1_dialogue.ps1 -Port 8765
# Then in another window: cloudflared or ngrok (see docs)

param(
  [int]$Port = 8765,
  [string]$Token = $env:SPM_LOCAL_TOKEN
)

$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

$venvPy = Join-Path $Root ".venv\Scripts\python.exe"
if (-not (Test-Path $venvPy)) {
  Write-Error "Missing .venv — create/activate repo .venv with torch+cuda first"
  exit 1
}

if (-not $Token) {
  $Token = -join ((1..24) | ForEach-Object { '{0:x}' -f (Get-Random -Max 16) })
  $env:SPM_LOCAL_TOKEN = $Token
  Write-Host "Generated SPM_LOCAL_TOKEN (save this): $Token"
} else {
  $env:SPM_LOCAL_TOKEN = $Token
  Write-Host "Using existing SPM_LOCAL_TOKEN"
}

Write-Host @"

PATH1 steps after server is up:
  1) Other window tunnel, e.g.:
       cloudflared tunnel --url http://127.0.0.1:$Port
     or:
       ngrok http $Port
  2) Public base URL example: https://xxxx.trycloudflare.com
  3) grok.com/connectors → New Connector → Custom
       URL:  https://xxxx.trycloudflare.com/mcp
       If auth offered: Bearer $Token
  4) New chat: ask to call local_pc_status only (no execute yet)
  5) If tools list works, then spm_local_execute on D:\s3_share\spm_in\small_BASE.jpg

Local smoke (no tunnel):
  curl http://127.0.0.1:$Port/health
  curl -H "Authorization: Bearer $Token" http://127.0.0.1:$Port/local_pc_status

"@

& $venvPy tools\spm_local_executor.py http --host 127.0.0.1 --port $Port
