@echo off
rem Real-time mic transcription (SenseVoiceSmall, GPU). Options: --lang zh  --device N  --list-devices  --cpu
"%~dp0sensevoice\.venv\Scripts\python.exe" "%~dp0sensevoice\realtime.py" %*
echo.
pause
