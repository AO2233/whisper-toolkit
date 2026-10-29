#!/usr/bin/env bash
# Create sensevoice/.venv-linux, install pinned dependencies and download/verify models.
# setup.sh [--cpu] [--models sensevoice,nano,whisper] [--skip-models]
set -e
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cpu=0 skip=0 models=(sensevoice nano whisper)
while [ $# -gt 0 ]; do
  case "${1,,}" in
    --cpu|-cpu) cpu=1 ;;
    --skip-models|-skipmodels) skip=1 ;;
    --models|-models) shift; IFS=, read -ra models <<< "$1" ;;
    *) echo "Unknown option: $1"; exit 1 ;;
  esac
  shift
done
command -v ffmpeg >/dev/null || { echo "Install ffmpeg first (sudo apt install ffmpeg)."; exit 1; }
venv="$here/sensevoice/.venv-linux"
python="$venv/bin/python"
requirements="$here/requirements.txt"
[ $cpu = 1 ] && requirements="$here/requirements-cpu.txt"
# sounddevice needs the system PortAudio library on Linux
python3 -c 'import ctypes.util, sys; sys.exit(not ctypes.util.find_library("portaudio"))' \
  || echo "Warning: PortAudio not found, real-time mic capture needs it (sudo apt install libportaudio2)."
if command -v uv >/dev/null; then
  [ -x "$python" ] || uv venv --python 3.14 "$venv"
  uv pip install --python "$python" -r "$requirements"
else
  [ -x "$python" ] || python3 -m venv "$venv"
  "$python" -m pip install -r "$requirements"
fi
if [ $skip = 0 ]; then
  "$python" "$here/scripts/download_models.py" --only "${models[@]}" \
    || { echo "Model download failed. Rerun setup.sh to retry."; exit 1; }
fi
echo "Setup complete. Whisper launchers also need build.sh; CPU users should pass --cpu / -Cpu."
