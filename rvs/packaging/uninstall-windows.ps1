# Remove the per-user installation. Projects and settings (%APPDATA%\rvs) are not touched; -PurgeSettings removes the settings too.
param([switch]$PurgeSettings, [string]$Prefix = "$env:LOCALAPPDATA\Programs\rvs-studio")
$ErrorActionPreference = "Stop"
if ((Test-Path $Prefix) -and -not (Test-Path (Join-Path $Prefix ".install-prefix"))) { throw "$Prefix was not installed by install.ps1; refusing to delete it." }
if (Test-Path $Prefix) { Remove-Item -Recurse -Force $Prefix }
$lnk = Join-Path $env:APPDATA "Microsoft\Windows\Start Menu\Programs\Requirements & Verification Studio.lnk"
if (Test-Path $lnk) { Remove-Item -Force $lnk }
if ($PurgeSettings) { Remove-Item -Recurse -Force (Join-Path $env:APPDATA "rvs") -ErrorAction SilentlyContinue }
Write-Host "RVS was removed. Your projects were not touched."
