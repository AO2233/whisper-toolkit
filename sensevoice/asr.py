"""File transcription with sherpa-onnx: ffmpeg decode -> Silero VAD -> batched SenseVoiceSmall (GPU)
-> optional Fun-ASR-Nano re-decode per segment (--nano) -> srt/txt.

Usage:
  sensevoice.cmd <file-or-folder> [...] [--lang auto|zh|en|ja|ko|yue] [--format srt,txt]
                 [--cpu] [--int8] [--outdir DIR]
  funasr.cmd     <file-or-folder> [...]          (same, with --nano)
"""
import argparse
import difflib
import glob
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MODELS = ROOT / "models"
FP32_DIR = MODELS / "sherpa-onnx-sense-voice-zh-en-ja-ko-yue-2024-07-17"
INT8_DIR = FP32_DIR  # same package ships model.int8.onnx
VAD_MODEL = MODELS / "silero_vad.onnx"
SR = 16000
MEDIA = {".wav", ".mp3", ".flac", ".ogg", ".m4a", ".mp4", ".mkv", ".mov", ".webm",
         ".aac", ".wma", ".opus", ".avi", ".flv", ".ts"}


# SenseVoice sometimes emits spaces between Japanese/Chinese tokens ("中学 は 弁当 制").
# CJK text never uses spaces, so drop a space whose neighbours are both CJK/kana/fullwidth/digits.
_CJK = r"　-〿぀-ヿㇰ-ㇿ㐀-䶿一-鿿豈-﫿＀-￯"
_CJK_SPACE = re.compile(rf"(?<=[{_CJK}])\s+(?=[{_CJK}0-9])|(?<=[{_CJK}0-9])\s+(?=[{_CJK}])")


def clean_text(text):
    return _CJK_SPACE.sub("", text).strip()


NANO_DIR = MODELS / "sherpa-onnx-funasr-nano-2025-12-30"
# Fun-ASR-Nano-2512 covers Mandarin (+ dialects), Cantonese, English, Japanese. On Korean it
# writes kana and on other languages it produces unrelated text, so those stay with SenseVoice.
NANO_LANGS = {"zh", "yue", "en", "ja"}


def _letters(text):
    return re.sub(r"[\W_]+", "", text.lower())


def load_sensevoice(sherpa_onnx, provider, lang="auto", int8=False):
    model = FP32_DIR / ("model.int8.onnx" if int8 else "model.onnx")
    rec = sherpa_onnx.OfflineRecognizer.from_sense_voice(
        model=str(model), tokens=str(FP32_DIR / "tokens.txt"),
        num_threads=os.cpu_count() if provider == "cpu" else 2,
        use_itn=True, language=lang, provider=provider)
    return rec, model


def load_nano(sherpa_onnx, provider):
    """Fun-ASR-Nano (encoder + Qwen3-0.6B). More accurate than SenseVoice on Mandarin, dialects,
    far-field, lyrics and technical terms; ~0.5-2 s per sentence on an RTX 5080."""
    return sherpa_onnx.OfflineRecognizer.from_funasr_nano(
        encoder_adaptor=str(NANO_DIR / "encoder_adaptor.onnx"), llm=str(NANO_DIR / "llm.fp32.onnx"),
        embedding=str(NANO_DIR / "embedding.onnx"), tokenizer=str(NANO_DIR / "Qwen3-0.6B"),
        provider=provider, num_threads=4,
        max_new_tokens=160)   # a 20 s VAD segment needs ~100; caps the cost of a decoding loop


def refine(nano, sv_result, samples):
    """Re-decode a segment with Fun-ASR-Nano and use it as a correction of SenseVoice's text.
    Nano is an LLM: on noise / music / very short segments it can invent fluent sentences
    that were never said, or loop. So if its text differs from SenseVoice's by more than half
    (character similarity < 0.5) it is not trusted. Unsupported languages stay with SenseVoice."""
    text = clean_text(sv_result.text)
    if nano is None or not text or sv_result.lang.strip("<|>") not in NANO_LANGS:
        return text
    st = nano.create_stream()
    st.accept_waveform(SR, samples)
    nano.decode_stream(st)
    better = clean_text(st.result.text)
    similar = difflib.SequenceMatcher(None, _letters(text), _letters(better)).ratio()
    return better if better and similar >= 0.5 else text


class AutoGain:
    """Peak-tracking AGC. Loopback audio is captured after the Windows volume slider (and mics
    vary a lot); at ~-55 dBFS Silero VAD misses speech, so bring the level up before VAD/ASR.
    Gain drops instantly on loud input (no clipping) and recovers over a few seconds."""

    def __init__(self, target=0.5, max_gain=100.0, decay=0.98):
        self.target, self.max_gain, self.decay, self.env = target, max_gain, decay, 0.0

    def __call__(self, chunk):
        peak = float(abs(chunk).max()) if len(chunk) else 0.0
        self.env = max(self.env * self.decay, peak)
        return chunk * min(self.target / max(self.env, 1e-9), self.max_gain)


def add_cuda_dll_dirs():
    # CUDA 12 runtime / cuBLAS / cuDNN shipped as nvidia-* pip packages inside the venv
    site = Path(sys.prefix) / "Lib" / "site-packages" / "nvidia"
    dirs = [d for d in glob.glob(str(site / "*" / "bin"))]
    for d in dirs:
        os.add_dll_directory(d)
    os.environ["PATH"] = os.pathsep.join(dirs + [os.environ.get("PATH", "")])
    # sm_120 kernels are JIT-compiled from PTX on first run (~45 s); keep them in the driver cache
    os.environ.setdefault("CUDA_CACHE_MAXSIZE", str(4 * 1024 ** 3))


def load_audio(path, np):
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        sys.exit("ffmpeg not found (scoop install ffmpeg)")
    cmd = [ffmpeg, "-nostdin", "-hide_banner", "-loglevel", "error", "-i", str(path),
           "-vn", "-ac", "1", "-ar", str(SR), "-f", "f32le", "-"]
    out = subprocess.run(cmd, capture_output=True, check=True).stdout
    return np.frombuffer(out, dtype=np.float32)


def vad_segments(samples, sherpa_onnx):
    cfg = sherpa_onnx.VadModelConfig()
    cfg.silero_vad.model = str(VAD_MODEL)
    cfg.silero_vad.threshold = 0.5
    cfg.silero_vad.min_silence_duration = 0.5   # shorter splits sentences; Nano needs the context
    cfg.silero_vad.min_speech_duration = 0.25
    cfg.silero_vad.max_speech_duration = 20
    cfg.sample_rate = SR
    window = cfg.silero_vad.window_size
    vad = sherpa_onnx.VoiceActivityDetector(cfg, buffer_size_in_seconds=60)

    segs = []
    preroll = int(0.5 * SR)   # VAD segments start after the real onset; same pre-roll as realtime.py
    prev_end = 0

    def drain():
        nonlocal prev_end
        while not vad.empty():
            start = max(vad.front.start - preroll, prev_end)
            end = vad.front.start + len(vad.front.samples)
            segs.append((start / SR, samples[start:end]))
            prev_end = end
            vad.pop()

    for i in range(0, len(samples), window):
        vad.accept_waveform(samples[i:i + window])
        drain()
    vad.flush()
    drain()
    return segs


def fmt_ts(t):
    ms = int(round(t * 1000))
    h, ms = divmod(ms, 3600000)
    m, ms = divmod(ms, 60000)
    s, ms = divmod(ms, 1000)
    return f"{h:02}:{m:02}:{s:02},{ms:03}"


def collect(paths):
    for p in map(Path, paths):
        if p.is_dir():
            yield from sorted(f for f in p.rglob("*") if f.suffix.lower() in MEDIA)
        elif p.exists():
            yield p
        else:
            print(f"Not found: {p}", file=sys.stderr)


def main():
    ap = argparse.ArgumentParser(description="SenseVoiceSmall + sherpa-onnx transcription")
    ap.add_argument("paths", nargs="+")
    ap.add_argument("--lang", default="auto", choices=["auto", "zh", "en", "ja", "ko", "yue"])
    ap.add_argument("--format", default="srt,txt", help="comma list of srt,txt")
    ap.add_argument("--cpu", action="store_true", help="run on CPU (uses INT8 model)")
    ap.add_argument("--int8", action="store_true", help="force INT8 model")
    ap.add_argument("--nano", action="store_true",
                    help="re-decode each segment with Fun-ASR-Nano (more accurate zh/yue/en/ja, slower)")
    ap.add_argument("--outdir", default="", help="default: next to the input file")
    ap.add_argument("--batch", type=int, default=32, help="segments per GPU batch")
    args = ap.parse_args()

    provider = "cpu" if args.cpu else "cuda"
    if provider == "cuda":
        add_cuda_dll_dirs()

    import numpy as np
    import sherpa_onnx

    # FP32 for GPU (INT8 quantized ops fall back to CPU under the CUDA EP); INT8 for CPU
    rec, model = load_sensevoice(sherpa_onnx, provider, args.lang, int8=args.int8 or args.cpu)
    nano = load_nano(sherpa_onnx, provider) if args.nano else None
    print(f"[asr] provider={provider} model={model.relative_to(ROOT)}"
          + (f" + {NANO_DIR.relative_to(ROOT)}" if nano else ""))

    formats = {f.strip().lower() for f in args.format.split(",") if f.strip()}
    files = list(collect(args.paths))
    if not files:
        sys.exit("No audio/video files found.")

    for f in files:
        print(f"\n=== {f}")
        t0 = time.time()
        samples = load_audio(f, np)
        dur = len(samples) / SR
        agc = AutoGain()   # quiet recordings make Silero VAD miss speech
        samples = np.concatenate([agc(samples[i:i + SR // 10]) for i in range(0, len(samples), SR // 10)])
        segs = vad_segments(samples, sherpa_onnx)

        results = []
        for b in range(0, len(segs), args.batch):
            chunk = segs[b:b + args.batch]
            streams = []
            for _, s in chunk:
                st = rec.create_stream()
                st.accept_waveform(SR, s)
                streams.append(st)
            rec.decode_streams(streams)
            for (start, s), st in zip(chunk, streams):
                text = refine(nano, st.result, s)
                if text:
                    results.append((start, start + len(s) / SR, text))
                    print(f"[{fmt_ts(start)}] {text}")

        out_dir = Path(args.outdir) if args.outdir else f.parent
        out_dir.mkdir(parents=True, exist_ok=True)
        base = out_dir / f.stem
        if "txt" in formats:
            base.with_suffix(".txt").write_text("\n".join(r[2] for r in results) + "\n", encoding="utf-8")
        if "srt" in formats:
            srt = "".join(f"{i}\n{fmt_ts(a)} --> {fmt_ts(b)}\n{t}\n\n"
                          for i, (a, b, t) in enumerate(results, 1))
            base.with_suffix(".srt").write_text(srt, encoding="utf-8")
        el = time.time() - t0
        print(f"-> {base}.{{{','.join(sorted(formats))}}}  ({dur:.1f}s audio in {el:.1f}s, RTF {el / max(dur, 1e-6):.3f})")


if __name__ == "__main__":
    main()
