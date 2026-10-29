#!/usr/bin/env bash
# Most accurate file transcription for Mandarin/dialects/Cantonese/English/Japanese:
# SenseVoice + Fun-ASR-Nano (GPU). funasr.sh <file-or-folder> [--format srt,txt]
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec "$here/sensevoice/.venv-linux/bin/python" "$here/sensevoice/asr.py" --nano "$@"
