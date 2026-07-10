# KhaosClip one-shot setup for Windows.
# Run from the repo root:  powershell -ExecutionPolicy Bypass -File scripts\setup.ps1

$ErrorActionPreference = "Stop"
Write-Host ""
Write-Host "  KHAOSCLIP setup" -ForegroundColor Red
Write-Host "  ---------------"

# ---- 1. Python check -------------------------------------------------------
$py = Get-Command python -ErrorAction SilentlyContinue
if (-not $py) {
    Write-Host "  [X] Python not found. Install 3.10+ from https://python.org (check 'Add to PATH')." -ForegroundColor Red
    exit 1
}
Write-Host "  [OK] Python: $((python --version) 2>&1)"

# ---- 2. ffmpeg check -------------------------------------------------------
$ff = Get-Command ffmpeg -ErrorAction SilentlyContinue
if (-not $ff) {
    Write-Host "  [!] ffmpeg not found. Installing via winget..." -ForegroundColor Yellow
    winget install --id Gyan.FFmpeg -e --accept-source-agreements --accept-package-agreements
    Write-Host "  [!] If ffmpeg still isn't found, restart this terminal and re-run setup." -ForegroundColor Yellow
} else {
    Write-Host "  [OK] ffmpeg found"
}

# ---- 3. Virtual env + install ----------------------------------------------
if (-not (Test-Path ".venv")) {
    Write-Host "  [..] Creating virtual environment"
    python -m venv .venv
}
& .\.venv\Scripts\Activate.ps1
Write-Host "  [..] Installing KhaosClip + voice + hotkey extras"
pip install --quiet --upgrade pip
pip install --quiet -e ".[voice,hotkey]"
Write-Host "  [OK] Package installed"

# ---- 4. Vosk voice model ----------------------------------------------------
$modelDir = "models\vosk-model-small-en-us-0.15"
if (-not (Test-Path $modelDir)) {
    Write-Host "  [..] Downloading Vosk voice model (~40MB, runs fully offline)"
    New-Item -ItemType Directory -Force -Path models | Out-Null
    $zip = "models\vosk-model.zip"
    Invoke-WebRequest -Uri "https://alphacephei.com/vosk/models/vosk-model-small-en-us-0.15.zip" -OutFile $zip
    Expand-Archive -Path $zip -DestinationPath models -Force
    Remove-Item $zip
    Write-Host "  [OK] Voice model installed"
} else {
    Write-Host "  [OK] Voice model already present"
}

# ---- 5. .env ----------------------------------------------------------------
if (-not (Test-Path ".env")) {
    Copy-Item .env.example .env
    Write-Host "  [!] Created .env — open it and fill in:" -ForegroundColor Yellow
    Write-Host "      - OBS_WS_PASSWORD  (OBS > Tools > WebSocket Server Settings)"
    Write-Host "      - OBS_REPLAY_DIR   (OBS > Settings > Output > Recording path)"
    Write-Host "      - X_* keys         (developer.x.com — see docs\SETUP_X_API.md)"
} else {
    Write-Host "  [OK] .env exists"
}

# ---- 6. Pre-flight ----------------------------------------------------------
Write-Host ""
Write-Host "  Running pre-flight check..." -ForegroundColor Cyan
khaosclip doctor

Write-Host ""
Write-Host "  Next: fix any FAILs above, then run  " -NoNewline
Write-Host "khaosclip run" -ForegroundColor Red
Write-Host ""
