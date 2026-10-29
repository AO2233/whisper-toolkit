@echo off
rem Translate any-language speech to English subtitles (Whisper large-v3). Drag files or folders here.
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0whisper.ps1" %* -Translate -Format srt,txt
echo.
pause
