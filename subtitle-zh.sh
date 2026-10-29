#!/usr/bin/env bash
# Chinese subtitles (Whisper large-v3, simplified Chinese + punctuation).
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec "$here/whisper.sh" "$@" -Lang zh -Format srt,txt
