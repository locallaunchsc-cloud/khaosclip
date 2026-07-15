$ErrorActionPreference = "Stop"
$root = "C:\Users\sauce\khaosclip"
Set-Location $root

Write-Host "NameiT installer build" -ForegroundColor Green

if (-not (Test-Path "packaging\bin\ffmpeg.exe")) {
    Write-Host "ffmpeg.exe missing from packaging\bin\" -ForegroundColor Red
    exit 1
}

pip install -e ".[all]" pyinstaller --quiet
pyinstaller packaging\nameit.spec --noconfirm --clean

$iscc = "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe"
if (-not (Test-Path $iscc)) { $iscc = "$env:ProgramFiles\Inno Setup 6\ISCC.exe" }
if (-not (Test-Path $iscc)) {
    Write-Host "Inno Setup not found - run: winget install JRSoftware.InnoSetup" -ForegroundColor Yellow
    exit 1
}

& $iscc packaging\installer.iss
Write-Host "Done: packaging\out\NameiT-Setup.exe" -ForegroundColor Green
