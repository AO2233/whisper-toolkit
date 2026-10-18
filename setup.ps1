param(
    [switch]$Cpu,
    [ValidateSet("sensevoice", "nano", "whisper")]
    [string[]]$Models = @("sensevoice", "nano", "whisper"),
    [switch]$SkipModels
)
$ErrorActionPreference = "Stop"
Push-Location $PSScriptRoot
try {
    if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
        throw "Install 64-bit Python 3.14 and add it to PATH first."
    }
    if (-not (Get-Command ffmpeg -ErrorAction SilentlyContinue)) {
        throw "Install ffmpeg and add it to PATH first (for example: scoop install ffmpeg)."
    }
    $python = Join-Path $PSScriptRoot "sensevoice\.venv\Scripts\python.exe"
    if (-not (Test-Path -LiteralPath $python)) {
        & python -m venv (Join-Path $PSScriptRoot "sensevoice\.venv")
        if ($LASTEXITCODE -ne 0) { throw "Failed to create Python virtual environment." }
    }
    $requirements = if ($Cpu) { "requirements-cpu.txt" } else { "requirements.txt" }
    & $python -m pip install -r $requirements
    if ($LASTEXITCODE -ne 0) { throw "Failed to install Python dependencies." }
    if (-not $SkipModels) {
        & $python scripts\download_models.py --only @Models
        if ($LASTEXITCODE -ne 0) { throw "Model download failed. Rerun setup.cmd to retry." }
    }
    Write-Host "Setup complete. Whisper launchers also need build.cmd; CPU users should pass --cpu / -Cpu." -ForegroundColor Green
} finally {
    Pop-Location
}
