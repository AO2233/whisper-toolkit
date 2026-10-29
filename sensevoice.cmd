@echo off
rem SenseVoiceSmall (sherpa-onnx, CUDA). Drag files/folders here, or: sensevoice.cmd <file> [--lang zh] [--format srt,txt] [--cpu]
"%~dp0sensevoice\.venv\Scripts\python.exe" "%~dp0sensevoice\asr.py" %*
echo.
pause
