@echo off
rem Real-time transcription of what the PC is playing (works even when muted). Options: --lang zh  --device <speaker name>
"%~dp0sensevoice\.venv\Scripts\python.exe" "%~dp0sensevoice\realtime.py" --system %*
echo.
pause
