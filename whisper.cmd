@echo off
rem Whisper large-v3 (whisper.cpp, CUDA). Drag files/folders here, or: whisper.cmd <file> [-Lang zh] [-Format srt,txt]
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0whisper.ps1" %*
echo.
pause
