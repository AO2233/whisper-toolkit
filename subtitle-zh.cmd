@echo off
rem Chinese subtitles (Whisper large-v3, simplified Chinese + punctuation). Drag video/audio files or folders here.
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0whisper.ps1" %* -Lang zh -Format srt,txt
echo.
pause
