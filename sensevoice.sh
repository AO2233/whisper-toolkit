#!/usr/bin/env bash
# SenseVoiceSmall (sherpa-onnx, CUDA): sensevoice.sh <file-or-folder> [--lang zh] [--format srt,txt] [--cpu]
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec "$here/sensevoice/.venv-linux/bin/python" "$here/sensevoice/asr.py" "$@"
