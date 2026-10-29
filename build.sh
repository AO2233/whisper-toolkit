#!/usr/bin/env bash
# Build whisper.cpp into whisper.cpp/build-linux (Windows uses whisper.cpp/build).
# build.sh        CUDA, default architecture sm_120 (override: CUDA_ARCHITECTURES=89 ./build.sh)
# build.sh cpu    CPU only
set -e
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
command -v git >/dev/null || { echo "Install git first."; exit 1; }
command -v cmake >/dev/null || { echo "Install cmake first (sudo apt install cmake ninja-build)."; exit 1; }
command -v ninja >/dev/null || { echo "Install ninja first (sudo apt install ninja-build)."; exit 1; }
if [ ! -d "$here/whisper.cpp/.git" ]; then
  [ -e "$here/whisper.cpp" ] && { echo "whisper.cpp exists but is not a Git checkout."; exit 1; }
  git clone --no-checkout https://github.com/ggml-org/whisper.cpp "$here/whisper.cpp"
  git -C "$here/whisper.cpp" checkout "$(tr -d '\r\n' < "$here/whisper-version.txt")"
fi
cd "$here/whisper.cpp"
if [ "${1,,}" = "cpu" ]; then
  cuda_args=(-DGGML_CUDA=OFF)
else
  nvcc="$(command -v nvcc || ls -d /usr/local/cuda/bin/nvcc 2>/dev/null || true)"
  [ -n "$nvcc" ] || { echo "nvcc not found: install the CUDA Toolkit, or run ./build.sh cpu"; exit 1; }
  cuda_args=(-DGGML_CUDA=ON "-DCMAKE_CUDA_ARCHITECTURES=${CUDA_ARCHITECTURES:-120}" "-DCMAKE_CUDA_COMPILER=$nvcc")
fi
cmake -B build-linux -G Ninja -DCMAKE_BUILD_TYPE=Release \
  "${cuda_args[@]}" \
  -DGGML_BACKEND_DL=ON -DGGML_CPU_ALL_VARIANTS=ON -DGGML_NATIVE=OFF \
  -DBUILD_SHARED_LIBS=ON -DWHISPER_BUILD_TESTS=OFF
cmake --build build-linux -j
