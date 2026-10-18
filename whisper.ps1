<#
.SYNOPSIS
  Transcribe audio/video with whisper.cpp (large-v3, CUDA first, CPU fallback).

.EXAMPLE
  .\transcribe.ps1 meeting.m4a
  .\transcribe.ps1 D:\recordings -Lang zh -Format srt,txt
  .\transcribe.ps1 talk.mp4 -Lang en -Translate        # translate to English
  .\transcribe.ps1 a.wav -Cpu                           # force CPU
#>
param(
    [Parameter(Mandatory = $true, Position = 0, ValueFromRemainingArguments = $true)]
    [string[]]$Path,
    [string]$Lang = "auto",                 # auto / zh / en / ja ...
    [string[]]$Format = @("srt", "txt"),    # txt srt vtt lrc csv json words
    [string]$Model = "",                    # default: models\ggml-large-v3.bin
    [string]$Prompt = "",                   # initial prompt: terms, names, style hints
    [int]$BeamSize = 5,
    [switch]$Translate,
    [switch]$Cpu,
    [switch]$NoVad,
    [string]$OutDir = ""                    # default: next to the input file
)

$ErrorActionPreference = "Stop"
if (-not $Model) { $Model = "$PSScriptRoot\models\ggml-large-v3.bin" }
$bin = "$PSScriptRoot\whisper.cpp\build\bin"
$cli = "$bin\whisper-cli.exe"
$vadModel = "$PSScriptRoot\models\ggml-silero-v6.2.0.bin"
$native = @(".wav", ".mp3", ".flac", ".ogg")   # decoded directly by whisper-cli
$media = $native + @(".m4a", ".mp4", ".mkv", ".mov", ".webm", ".aac", ".wma", ".opus", ".avi", ".flv", ".ts")

if (-not (Test-Path $cli))   { throw "whisper-cli not found: $cli  (run build.cmd)" }
if (-not (Test-Path $Model)) { throw "Model not found: $Model" }

# CUDA runtime DLLs (cudart/cublas) come from the toolkit
$cudaBin = Get-ChildItem "$env:ProgramFiles\NVIDIA GPU Computing Toolkit\CUDA\*\bin\x64" -Directory -ErrorAction SilentlyContinue |
    Sort-Object FullName -Descending | Select-Object -First 1
if ($cudaBin) { $env:PATH = "$($cudaBin.FullName);$(Split-Path $cudaBin.FullName);$env:PATH" }

$ffmpeg = (Get-Command ffmpeg -ErrorAction SilentlyContinue).Source

# Simplified Chinese with punctuation needs a hint, otherwise output is often traditional / unpunctuated
if (-not $Prompt -and $Lang -eq "zh") { $Prompt = "以下是普通话的句子，使用简体中文和标点符号。" }

$files = foreach ($p in $Path) {
    $item = Get-Item -LiteralPath $p
    if ($item.PSIsContainer) {
        Get-ChildItem -LiteralPath $item.FullName -File -Recurse | Where-Object { $media -contains $_.Extension.ToLower() }
    } else { $item }
}
if (-not $files) { throw "No audio/video files found." }

foreach ($f in $files) {
    Write-Host "`n=== $($f.FullName)" -ForegroundColor Cyan
    $outBase = if ($OutDir) { New-Item -ItemType Directory -Force $OutDir | Out-Null; Join-Path $OutDir $f.BaseName }
               else { Join-Path $f.DirectoryName $f.BaseName }

    $inFile = $f.FullName
    $tmp = $null
    if ($native -notcontains $f.Extension.ToLower()) {
        if (-not $ffmpeg) { Write-Warning "Skipping $($f.Name): needs ffmpeg (scoop install ffmpeg)"; continue }
        $tmp = Join-Path $env:TEMP ("whisper_" + [guid]::NewGuid() + ".wav")
        & $ffmpeg -hide_banner -loglevel error -y -i $inFile -vn -ar 16000 -ac 1 -c:a pcm_s16le $tmp
        if ($LASTEXITCODE -ne 0) { Write-Warning "ffmpeg failed on $($f.Name)"; continue }
        $inFile = $tmp
    }

    $cliArgs = @("-m", $Model, "-f", $inFile, "-l", $Lang, "-bs", $BeamSize, "-bo", 5,
              "-of", $outBase, "-pp", "-sns")
    foreach ($fmt in ($Format -split ",")) {
        switch ($fmt.Trim().ToLower()) {
            "txt"   { $cliArgs += "-otxt" }  "srt"  { $cliArgs += "-osrt" }  "vtt"   { $cliArgs += "-ovtt" }
            "lrc"   { $cliArgs += "-olrc" }  "csv"  { $cliArgs += "-ocsv" }  "json"  { $cliArgs += "-ojf" }
            "words" { $cliArgs += "-owts" }
            default { throw "Unknown format: $fmt" }
        }
    }
    if ($Prompt)    { $cliArgs += @("--prompt", $Prompt) }
    if ($Translate) { $cliArgs += "-tr" }
    if ($Cpu)       { $cliArgs += "-ng"; $cliArgs += @("-t", [Environment]::ProcessorCount) }
    if (-not $NoVad -and (Test-Path $vadModel)) { $cliArgs += @("--vad", "-vm", $vadModel) }

    try {
        & $cli @cliArgs
        if ($LASTEXITCODE -ne 0) { Write-Warning "whisper-cli exited with $LASTEXITCODE" }
        else { Write-Host "-> $outBase.{$($Format -join ',')}" -ForegroundColor Green }
    } finally {
        if ($tmp) { Remove-Item $tmp -ErrorAction SilentlyContinue }
    }
}
