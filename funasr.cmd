@echo off
rem Most accurate file transcription for Mandarin/dialects/Cantonese/English/Japanese:
rem SenseVoice + Fun-ASR-Nano (GPU). Drag files/folders here, or: funasr.cmd <file> [--format srt,txt]
"%~dp0sensevoice\.venv\Scripts\python.exe" "%~dp0sensevoice\asr.py" --nano %*
echo.
pause
