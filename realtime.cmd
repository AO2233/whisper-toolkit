@echo off
setlocal
rem Real-time mic transcription (SenseVoiceSmall, GPU). Options: --lang zh  --device N  --list-devices  --cpu
"%~dp0sensevoice\.venv\Scripts\python.exe" "%~dp0sensevoice\realtime.py" %*
set "asr_exit=%errorlevel%"
if not "%asr_exit%"=="0" pause
exit /b %asr_exit%
