# Install Requirements & Verification Studio for the current user (no administrator rights, no network).
# Run from the unpacked release folder:  powershell -ExecutionPolicy Bypass -File install.ps1 [-NoSelfTest] [-Prefix DIR]
# Default folder: %LOCALAPPDATA%\Programs\rvs-studio. The PATH is not changed; a Start-menu shortcut is created.
# NOTE: written for Windows but not yet tested on Windows (docs/DEVIATIONS.md V22).
param([switch]$NoSelfTest, [string]$Prefix = "$env:LOCALAPPDATA\Programs\rvs-studio")
$ErrorActionPreference = "Stop"
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
if ([string]::IsNullOrWhiteSpace($Prefix)) { throw "The prefix is empty." }
$Prefix = [System.IO.Path]::GetFullPath($Prefix).TrimEnd('\')
if ($Prefix.Length -le 3 -or $Prefix -eq $env:USERPROFILE.TrimEnd('\')) { throw "Refusing to use $Prefix as the installation folder." }
if (Test-Path -LiteralPath $Prefix) {
    $marker = Join-Path $Prefix ".install-prefix"
    if (-not (Test-Path -LiteralPath $marker) -and (Get-ChildItem -LiteralPath $Prefix -Force | Select-Object -First 1)) {
        throw "$Prefix is not empty and was not installed by this script, so it is left alone. Choose another -Prefix."
    }
}
$app = Join-Path $here "rvs-studio"
if (-not (Test-Path -LiteralPath (Join-Path $app "rvs-studio.exe"))) { $app = $here }
if (-not (Test-Path -LiteralPath (Join-Path $app "rvs-studio.exe")) -or -not (Test-Path -LiteralPath (Join-Path $app "rvs.exe"))) {
    throw "rvs-studio.exe and rvs.exe were not found next to this script. Run it from the unpacked release."
}

# 1. Integrity: every file must match MANIFEST.sha256, and no other file may be present.
$manifest = Join-Path $app "MANIFEST.sha256"
if (-not (Test-Path -LiteralPath $manifest)) { throw "MANIFEST.sha256 is missing, so the files cannot be verified. Nothing was installed." }
$listed = @{}
foreach ($line in [System.IO.File]::ReadAllLines($manifest, [System.Text.Encoding]::UTF8)) {
    if ($line -eq "") { continue }
    $digest, $rel = $line -split "  ", 2
    if (-not $rel) { throw "MANIFEST.sha256 has a line that cannot be read. Nothing was installed." }
    $file = Join-Path $app $rel
    if (-not (Test-Path -LiteralPath $file) -or (Get-FileHash -LiteralPath $file -Algorithm SHA256).Hash.ToLower() -ne $digest) {
        throw "$rel differs from MANIFEST.sha256; the download is damaged or was altered. Nothing was installed."
    }
    $listed[$rel.Replace('\', '/')] = $true
}
$root = (Resolve-Path -LiteralPath $app).Path.TrimEnd('\')
foreach ($f in Get-ChildItem -LiteralPath $app -Recurse -File -Force) {
    $rel = $f.FullName.Substring($root.Length + 1).Replace('\', '/')
    if ($rel -ne "MANIFEST.sha256" -and $rel -ne ".install-prefix" -and -not $listed.ContainsKey($rel)) {
        throw "$rel is not in MANIFEST.sha256; nothing was installed."
    }
}

# 2. Copy next to the target, mark it as ours, then swap. The two temporary folders get a fresh name that does not
#    exist yet, and only folders created here are ever deleted (a folder that already carries a similar name is not ours).
$parent = Split-Path -Parent $Prefix
New-Item -ItemType Directory -Force -Path $parent | Out-Null
$leaf = Split-Path -Leaf $Prefix
$token = [guid]::NewGuid().ToString("N").Substring(0, 8)
$staging = Join-Path $parent "$leaf.$token.new"
$old = Join-Path $parent "$leaf.$token.old"
if ((Test-Path -LiteralPath $staging) -or (Test-Path -LiteralPath $old)) { throw "$staging or $old already exists; run the installer again." }
$movedOld = $false
try {
    New-Item -ItemType Directory -Path $staging -ErrorAction Stop | Out-Null   # fails instead of reusing an existing folder
    Get-ChildItem -LiteralPath $app -Force | Copy-Item -Destination $staging -Recurse -Force
    Set-Content -LiteralPath (Join-Path $staging ".install-prefix") -Value $Prefix -Encoding UTF8
    if (Test-Path -LiteralPath $Prefix) { Move-Item -LiteralPath $Prefix -Destination $old; $movedOld = $true }
    Move-Item -LiteralPath $staging -Destination $Prefix
    $staging = $null
} catch {
    # put the previous installation back if the swap stopped half-way, and remove only what this script created
    if ($movedOld -and -not (Test-Path -LiteralPath $Prefix) -and (Test-Path -LiteralPath $old)) { Move-Item -LiteralPath $old -Destination $Prefix }
    if ($staging -and (Test-Path -LiteralPath $staging)) { Remove-Item -LiteralPath $staging -Recurse -Force }
    throw
}
if ($movedOld) {
    try { Remove-Item -LiteralPath $old -Recurse -Force } catch { Write-Warning "The previous installation could not be removed completely; delete $old yourself." }
}

# 3. Start-menu shortcut.
$menu = Join-Path $env:APPDATA "Microsoft\Windows\Start Menu\Programs"
$shell = New-Object -ComObject WScript.Shell
$link = $shell.CreateShortcut((Join-Path $menu "Requirements & Verification Studio.lnk"))
$link.TargetPath = Join-Path $Prefix "rvs-studio.exe"
$link.Save()
Write-Host "Installed to $Prefix. Command line: $Prefix\rvs.exe --help"
if (-not $NoSelfTest) {
    Push-Location $env:TEMP
    try { & (Join-Path $Prefix "rvs.exe") selftest --manifest $Prefix } finally { Pop-Location }
    if ($LASTEXITCODE -ne 0) { throw "The installation check reported a problem." }
}
