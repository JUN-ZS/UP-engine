param(
  [ValidateSet("base","master")][string]$Variant = "base",
  [string]$Cell = "256/16",
  [switch]$GrabOnly
)
$ErrorActionPreference = "Stop"
$here = $PSScriptRoot
if ($GrabOnly) {
  & "$here\spm_cli.ps1" grab -Package warrior_mud_hammer -Variant $Variant
} else {
  & "$here\spm_cli.ps1" run -Package warrior_mud_hammer -Variant $Variant -Cell $Cell
}
