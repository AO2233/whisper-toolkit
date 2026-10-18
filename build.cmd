@echo off
setlocal
where git >nul 2>&1 || (echo Install Git first. & exit /b 1)
if not exist "%~dp0whisper.cpp\.git" (
  if exist "%~dp0whisper.cpp" (echo whisper.cpp exists but is not a Git checkout. & exit /b 1)
  git clone --no-checkout https://github.com/ggml-org/whisper.cpp "%~dp0whisper.cpp" || exit /b 1
  for /f "usebackq delims=" %%r in ("%~dp0whisper-version.txt") do git -C "%~dp0whisper.cpp" checkout %%r
  if errorlevel 1 exit /b 1
)
where cl >nul 2>&1
if errorlevel 1 (
  if not exist "%ProgramFiles(x86)%\Microsoft Visual Studio\Installer\vswhere.exe" (echo Install Visual Studio C++ build tools first. & exit /b 1)
  for /f "usebackq delims=" %%i in (`"%ProgramFiles(x86)%\Microsoft Visual Studio\Installer\vswhere.exe" -latest -products * -requires Microsoft.VisualStudio.Component.VC.Tools.x86.x64 -property installationPath`) do call "%%i\VC\Auxiliary\Build\vcvars64.bat" >nul
  if errorlevel 1 exit /b 1
)
cd /d "%~dp0whisper.cpp"
chcp 65001 >nul
set "cuda_args=-DGGML_CUDA=ON -DCMAKE_CUDA_ARCHITECTURES=120"
if /i "%~1"=="cpu" set "cuda_args=-DGGML_CUDA=OFF"
if defined CUDA_ARCHITECTURES if /i not "%~1"=="cpu" set "cuda_args=-DGGML_CUDA=ON -DCMAKE_CUDA_ARCHITECTURES=%CUDA_ARCHITECTURES%"
cmake -B build -G Ninja -DCMAKE_BUILD_TYPE=Release ^
  %cuda_args% ^
  -DGGML_BACKEND_DL=ON -DGGML_CPU_ALL_VARIANTS=ON -DGGML_NATIVE=OFF ^
  -DBUILD_SHARED_LIBS=ON -DWHISPER_BUILD_TESTS=OFF || exit /b 1
cmake --build build -j || exit /b 1
