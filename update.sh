#!/usr/bin/env bash
# Fast-forward to latest whisper.cpp master, record the revision, and rebuild.
set -e
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if [ ! -d "$here/whisper.cpp/.git" ]; then exec "$here/build.sh" "$@"; fi
git -C "$here/whisper.cpp" fetch origin master
git -C "$here/whisper.cpp" merge --ff-only origin/master
git -C "$here/whisper.cpp" rev-parse HEAD > "$here/whisper-version.txt"
exec "$here/build.sh" "$@"
