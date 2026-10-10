# Remove the per-user installation. Projects and settings (%APPDATA%\rvs) are not touched; -PurgeSettings removes the settings too.
# Only a folder holding the marker .install-prefix is deleted.
param([switch]$PurgeSettings, [string]$Prefix = "$env:LOCALAPPDATA\Programs\rvs-studio")
$ErrorActionPreference = "Stop"
if ([string]::IsNullOrWhiteSpace($Prefix)) { throw "The prefix is empty." }
$Prefix = [System.IO.Path]::GetFullPath($Prefix).TrimEnd('\')
if (-not (Test-Path -LiteralPath (Join-Path $Prefix ".install-prefix"))) { throw "$Prefix is not an installation made by install.ps1; nothing was removed." }
Remove-Item -LiteralPath $Prefix -Recurse -Force
$lnk = Join-Path $env:APPDATA "Microsoft\Windows\Start Menu\Programs\Requirements & Verification Studio.lnk"
if (Test-Path -LiteralPath $lnk) { Remove-Item -LiteralPath $lnk -Force }
if ($PurgeSettings) { Remove-Item -LiteralPath (Join-Path $env:APPDATA "rvs") -Recurse -Force -ErrorAction SilentlyContinue }
Write-Host "RVS was removed. Your projects were not touched."
