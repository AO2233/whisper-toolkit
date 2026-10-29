#!/usr/bin/env bash
# Real-time transcription of what the PC is playing (PulseAudio/PipeWire monitor). Options: --lang zh  --device <speaker name>
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec "$here/sensevoice/.venv-linux/bin/python" "$here/sensevoice/realtime.py" --system "$@"
