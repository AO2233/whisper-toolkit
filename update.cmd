@echo off
rem Fast-forward to latest whisper.cpp master, record the revision, and rebuild.
if not exist "%~dp0whisper.cpp\.git" (call "%~dp0build.cmd" %* & exit /b)
git -C "%~dp0whisper.cpp" fetch origin master || exit /b 1
git -C "%~dp0whisper.cpp" merge --ff-only origin/master || exit /b 1
git -C "%~dp0whisper.cpp" rev-parse HEAD > "%~dp0whisper-version.txt" || exit /b 1
call "%~dp0build.cmd" %*
