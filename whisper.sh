#!/usr/bin/env bash
# Transcribe audio/video with whisper.cpp (large-v3, CUDA first, CPU fallback). Same options as whisper.ps1:
#   whisper.sh meeting.m4a
#   whisper.sh ~/recordings -Lang zh -Format srt,txt
#   whisper.sh talk.mp4 -Lang en -Translate        # translate to English
#   whisper.sh a.wav -Cpu                           # force CPU
# Options: -Lang -Format -Model -Prompt -BeamSize -OutDir -Translate -Cpu -NoVad (case-insensitive, -- also accepted)
set -e
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
lang=auto format=srt,txt model="" prompt="" beam=5 outdir="" translate=0 cpu=0 novad=0
paths=()
while [ $# -gt 0 ]; do
  opt="${1,,}"; [[ "$opt" == --* ]] && opt="${opt#-}"
  case "$opt" in
    -lang) lang="$2"; shift ;;
    -format) format="$2"; shift ;;
    -model) model="$2"; shift ;;
    -prompt) prompt="$2"; shift ;;
    -beamsize) beam="$2"; shift ;;
    -outdir) outdir="$2"; shift ;;
    -translate) translate=1 ;;
    -cpu) cpu=1 ;;
    -novad) novad=1 ;;
    -*) echo "Unknown option: $1"; exit 1 ;;
    *) paths+=("$1") ;;
  esac
  shift
done
[ ${#paths[@]} -gt 0 ] || { sed -n '2,7p' "$0"; exit 1; }

[ -n "$model" ] || model="$here/models/ggml-large-v3.bin"
bin="$here/whisper.cpp/build-linux/bin"
cli="$bin/whisper-cli"
vad_model="$here/models/ggml-silero-v6.2.0.bin"
native=" wav mp3 flac ogg "   # decoded directly by whisper-cli
media="$native m4a mp4 mkv mov webm aac wma opus avi flv ts "

[ -x "$cli" ] || { echo "whisper-cli not found: $cli  (run build.sh)"; exit 1; }
[ -f "$model" ] || { echo "Model not found: $model"; exit 1; }

# Simplified Chinese with punctuation needs a hint, otherwise output is often traditional / unpunctuated
[ -z "$prompt" ] && [ "$lang" = zh ] && prompt="以下是普通话的句子，使用简体中文和标点符号。"

ext() { local e="${1##*.}"; echo "${e,,}"; }
files=()
for p in "${paths[@]}"; do
  if [ -d "$p" ]; then
    while IFS= read -r -d '' f; do
      [[ "$media" == *" $(ext "$f") "* ]] && files+=("$f")
    done < <(find "$p" -type f -print0 | sort -z)
  elif [ -e "$p" ]; then files+=("$p")
  else echo "Not found: $p" >&2
  fi
done
[ ${#files[@]} -gt 0 ] || { echo "No audio/video files found."; exit 1; }

fmt_args=()
IFS=, read -ra fmts <<< "$format"
for fmt in "${fmts[@]}"; do
  fmt="${fmt// /}"
  case "${fmt,,}" in
    txt) fmt_args+=(-otxt) ;; srt) fmt_args+=(-osrt) ;; vtt) fmt_args+=(-ovtt) ;;
    lrc) fmt_args+=(-olrc) ;; csv) fmt_args+=(-ocsv) ;; json) fmt_args+=(-ojf) ;;
    words) fmt_args+=(-owts) ;;
    *) echo "Unknown format: $fmt"; exit 1 ;;
  esac
done

for f in "${files[@]}"; do
  f="$(realpath "$f")"
  printf '\n\033[36m=== %s\033[0m\n' "$f"
  name="$(basename "$f")"
  if [ -n "$outdir" ]; then mkdir -p "$outdir"; out_base="$outdir/${name%.*}"
  else out_base="$(dirname "$f")/${name%.*}"
  fi

  in_file="$f" tmp=""
  if [[ "$native" != *" $(ext "$f") "* ]]; then
    command -v ffmpeg >/dev/null || { echo "Skipping $name: needs ffmpeg" >&2; continue; }
    tmp="$(mktemp --suffix=.wav)"
    if ! ffmpeg -nostdin -hide_banner -loglevel error -y -i "$f" -vn -ar 16000 -ac 1 -c:a pcm_s16le "$tmp"; then
      echo "ffmpeg failed on $name" >&2; rm -f "$tmp"; continue
    fi
    in_file="$tmp"
  fi

  args=(-m "$model" -f "$in_file" -l "$lang" -bs "$beam" -bo 5 -of "$out_base" -pp -sns "${fmt_args[@]}")
  [ -n "$prompt" ] && args+=(--prompt "$prompt")
  [ $translate = 1 ] && args+=(-tr)
  [ $cpu = 1 ] && args+=(-ng -t "$(nproc)")
  [ $novad = 0 ] && [ -f "$vad_model" ] && args+=(--vad -vm "$vad_model")

  if "$cli" "${args[@]}"; then printf '\033[32m-> %s.{%s}\033[0m\n' "$out_base" "$format"
  else echo "whisper-cli exited with $?" >&2
  fi
  if [ -n "$tmp" ]; then rm -f "$tmp"; fi
done
