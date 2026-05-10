# RagSnip — Windows build script
#
# Produces windows\Output\RagSnip-Setup-<version>.exe
#
# Prerequisites:
#   - Python 3.9+ on PATH (`python --version`)
#   - Inno Setup 6 (https://jrsoftware.org/isdl.php  or  `choco install innosetup`)
#
# Usage:
#   powershell -ExecutionPolicy Bypass -File .\build.ps1

$ErrorActionPreference = "Stop"
Push-Location $PSScriptRoot
try {
    Write-Host "[1/3] Ensuring Python build deps (PyInstaller, Pillow)..."
    & python -m pip install --user --quiet --upgrade pyinstaller Pillow

    Write-Host "[2/3] Building RagSnip.exe with PyInstaller..."
    & python -m PyInstaller `
        --noconsole `
        --onefile `
        --name RagSnip `
        --icon ragsnip.ico `
        --clean `
        --distpath dist `
        --workpath build `
        --specpath . `
        ragsnip.py

    if (-not (Test-Path "dist\RagSnip.exe")) {
        throw "PyInstaller did not produce dist\RagSnip.exe"
    }
    Write-Host "    -> dist\RagSnip.exe"

    Write-Host "[3/3] Building installer with Inno Setup..."
    $iscc = (Get-Command iscc.exe -ErrorAction SilentlyContinue).Source
    if (-not $iscc) {
        $candidates = @(
            "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe",
            "${env:ProgramFiles}\Inno Setup 6\ISCC.exe"
        )
        foreach ($c in $candidates) {
            if (Test-Path $c) { $iscc = $c; break }
        }
    }
    if (-not $iscc -or -not (Test-Path $iscc)) {
        throw @"
Inno Setup compiler (ISCC.exe) not found.
Install it from https://jrsoftware.org/isdl.php
or with Chocolatey:  choco install innosetup
"@
    }

    & $iscc RagSnip.iss
    if ($LASTEXITCODE -ne 0) { throw "ISCC failed (exit $LASTEXITCODE)" }

    $installer = Get-ChildItem -Path "Output\RagSnip-Setup-*.exe" |
                 Sort-Object LastWriteTime -Descending |
                 Select-Object -First 1
    Write-Host ""
    Write-Host "Installer built: $($installer.FullName)"
    Write-Host ""
    Write-Host "Next: upload this file to a GitHub Release at"
    Write-Host "      $($installer.Name)"
}
finally {
    Pop-Location
}
