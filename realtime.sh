#!/usr/bin/env bash
# Real-time mic transcription (SenseVoiceSmall, GPU). Options: --lang zh  --device N  --list-devices  --cpu
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec "$here/sensevoice/.venv-linux/bin/python" "$here/sensevoice/realtime.py" "$@"
