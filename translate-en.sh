#!/usr/bin/env bash
# Translate any-language speech to English subtitles (Whisper large-v3).
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec "$here/whisper.sh" "$@" -Translate -Format srt,txt
