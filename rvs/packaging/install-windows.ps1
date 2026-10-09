# Install Requirements & Verification Studio for the current user (no administrator rights, no network).
# Run from the unpacked release folder:  powershell -ExecutionPolicy Bypass -File install.ps1 [-NoSelfTest]
# NOTE: written for Windows but not yet tested on Windows (docs/DEVIATIONS.md).
param([switch]$NoSelfTest, [string]$Prefix = "$env:LOCALAPPDATA\Programs\rvs-studio")
$ErrorActionPreference = "Stop"
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
$app = Join-Path $here "rvs-studio"
if (-not (Test-Path (Join-Path $app "rvs-studio.exe"))) { $app = $here }
if (-not (Test-Path (Join-Path $app "rvs-studio.exe")) -or -not (Test-Path (Join-Path $app "rvs.exe"))) {
    throw "rvs-studio.exe and rvs.exe were not found next to this script. Run it from the unpacked release."
}

# 1. Integrity: every file must match MANIFEST.sha256.
$manifest = Join-Path $app "MANIFEST.sha256"
if (Test-Path $manifest) {
    foreach ($line in Get-Content $manifest) {
        $digest, $rel = $line -split "  ", 2
        if (-not $rel) { continue }
        $file = Join-Path $app $rel
        if (-not (Test-Path $file) -or (Get-FileHash $file -Algorithm SHA256).Hash.ToLower() -ne $digest) {
            throw "$rel differs from MANIFEST.sha256; the download is damaged or was altered. Nothing was installed."
        }
    }
} else { Write-Warning "No MANIFEST.sha256 found; skipping the integrity check." }

# 2. Copy the program.
if (Test-Path $Prefix) { Remove-Item -Recurse -Force $Prefix }
New-Item -ItemType Directory -Force -Path (Split-Path $Prefix) | Out-Null
Copy-Item -Recurse -Force $app $Prefix
Set-Content -Path (Join-Path $Prefix ".install-prefix") -Value $Prefix

# 3. Start-menu shortcut.
$menu = Join-Path $env:APPDATA "Microsoft\Windows\Start Menu\Programs"
$shell = New-Object -ComObject WScript.Shell
$link = $shell.CreateShortcut((Join-Path $menu "Requirements & Verification Studio.lnk"))
$link.TargetPath = Join-Path $Prefix "rvs-studio.exe"
$link.Save()
Write-Host "Installed to $Prefix. Command line: $Prefix\rvs.exe --help"
if (-not $NoSelfTest) { & (Join-Path $Prefix "rvs.exe") selftest; if ($LASTEXITCODE -ne 0) { throw "The installation check reported a problem." } }
