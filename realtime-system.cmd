@echo off
setlocal
rem Real-time transcription of what the PC is playing (works even when muted). Options: --lang zh  --device <speaker name>
"%~dp0sensevoice\.venv\Scripts\python.exe" "%~dp0sensevoice\realtime.py" --system %*
set "asr_exit=%errorlevel%"
if not "%asr_exit%"=="0" pause
exit /b %asr_exit%
