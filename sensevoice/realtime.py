"""Real-time ASR, following sherpa-onnx's simulate-streaming-sense-voice-microphone.py:
audio -> Silero VAD -> SenseVoiceSmall (GPU). While speech is active the buffer is
re-decoded every 0.2 s (live text); when VAD closes a segment it is decoded once more
and finalized. Finalized lines are also appended to transcripts/realtime-*.txt.

Usage:
  realtime.cmd [--system] [--lang auto|zh|en|ja|ko|yue] [--device N|name] [--list-devices] [--cpu]
"""
import argparse
import contextlib
import ctypes
import os
import queue
import re
import sys
import threading
import time
from datetime import datetime
from pathlib import Path

from asr import (NANO_DIR, AutoGain, ROOT, SR, VAD_MODEL, add_cuda_dll_dirs, clean_text, load_nano,
                 load_sensevoice, refine)
from terminal_display import TerminalDisplay


def is_noise(text):
    """Punctuation-only results ('.', '。') come from noise between sentences."""
    return not re.search(r"\w", text)


def open_mic(sd, device):
    """Callback-based input stream (works on every Windows host API). Returns (stream, rate, read)."""
    try:
        sd.check_input_settings(device=device, channels=1, dtype="float32", samplerate=SR)
        rate = SR
    except Exception:
        rate = int(sd.query_devices(device)["default_samplerate"])
    q = queue.Queue()
    stream = sd.InputStream(device=device, channels=1, dtype="float32", samplerate=rate,
                            blocksize=int(0.1 * rate), callback=lambda d, *_: q.put(d[:, 0].copy()))

    def read():
        try:
            return q.get(timeout=0.5)   # timeout keeps Ctrl+C responsive on Windows
        except queue.Empty:
            return None
    return stream, rate, read


def open_loopback(sc, speaker):
    """WASAPI loopback of a speaker: what the PC plays, independent of volume/mute.
    Recorded on its own thread (as the official example does for the mic): if decoding/display
    ever stalls the main loop, the WASAPI buffer would overflow and audio would be lost."""
    rate, block = 48000, 4800
    q = queue.Queue()
    stop = threading.Event()

    def run():
        if os.name == "nt":
            ctypes.windll.ole32.CoInitializeEx(None, 0)   # COM is per-thread; WASAPI needs it
            source = str(speaker.name)
        else:
            source = f"{speaker.id}.monitor"   # PulseAudio/PipeWire monitor source of the sink
        with sc.get_microphone(id=source, include_loopback=True).recorder(
                samplerate=rate, channels=1, blocksize=block) as rec:
            while not stop.is_set():
                q.put(rec.record(numframes=block)[:, 0])

    @contextlib.contextmanager
    def capture():
        t = threading.Thread(target=run, daemon=True)
        t.start()
        try:
            yield
        finally:
            stop.set()

    def read():
        try:
            return q.get(timeout=0.5)
        except queue.Empty:
            return None
    return capture(), rate, read


def main():
    ap = argparse.ArgumentParser(description="SenseVoice real-time transcription")
    ap.add_argument("--system", action="store_true", help="transcribe PC audio output instead of a microphone")
    ap.add_argument("--device", default=None, help="mic index/name, or speaker name with --system")
    ap.add_argument("--list-devices", action="store_true")
    ap.add_argument("--lang", default="auto", choices=["auto", "zh", "en", "ja", "ko", "yue"])
    ap.add_argument("--cpu", action="store_true", help="run on CPU (INT8 model, no Fun-ASR-Nano)")
    ap.add_argument("--fast", action="store_true", help="finalize with SenseVoice only (no Fun-ASR-Nano)")
    ap.add_argument("--silence", type=float, default=0.5, help="pause (s) that ends a sentence")
    ap.add_argument("--outdir", default=str(ROOT / "transcripts"))
    args = ap.parse_args()

    import sounddevice as sd
    import soundcard as sc

    if args.list_devices:
        print("Microphones (probed; 'unavailable' = nothing connected behind that port):")
        for i, d in enumerate(sd.query_devices()):
            if d["max_input_channels"] > 0:
                try:
                    with sd.InputStream(device=i, channels=1, dtype="float32",
                                        samplerate=d["default_samplerate"], callback=lambda *a: None):
                        pass
                    state = "ok"
                except Exception:
                    state = "unavailable"
                name = " ".join(d["name"].split())
                print(f"  {i:3}  {state:11}  {name}  [{sd.query_hostapis(d['hostapi'])['name']}]")
        print("Speakers (--system --device <name>):")
        for s in sc.all_speakers():
            print(f"       {s.name}")
        return

    if args.system:
        speaker = sc.default_speaker()
        if args.device:
            speaker = next((s for s in sc.all_speakers() if args.device.lower() in s.name.lower()), None)
            if speaker is None:
                sys.exit(f"No speaker matching '{args.device}' (see --list-devices)")
        capture, rate, read = open_loopback(sc, speaker)
        source = f"system audio: {speaker.name}"
    else:
        device = args.device
        if device is None:
            device = sd.default.device[0]
            if device is None or device < 0:
                sys.exit("No default microphone. Pick one with --device (see --list-devices).")
        elif device.isdigit():
            device = int(device)
        capture, rate, read = open_mic(sd, device)
        source = f"mic: {sd.query_devices(device)['name']}"

    provider = "cpu" if args.cpu else "cuda"
    if provider == "cuda":
        add_cuda_dll_dirs()

    import numpy as np
    import sherpa_onnx

    recognizer, _ = load_sensevoice(sherpa_onnx, provider, args.lang, int8=args.cpu)
    # live text: SenseVoice (~25 ms); finalized sentence: Fun-ASR-Nano (~0.5-2 s, more accurate)
    nano = None if args.fast or args.cpu or not NANO_DIR.exists() else load_nano(sherpa_onnx, provider)

    config = sherpa_onnx.VadModelConfig()
    config.silero_vad.model = str(VAD_MODEL)
    config.silero_vad.threshold = 0.5
    config.silero_vad.min_silence_duration = args.silence   # official example: 0.1 (splits sentences mid-way)
    config.silero_vad.min_speech_duration = 0.25
    config.silero_vad.max_speech_duration = 20
    config.sample_rate = SR
    window_size = config.silero_vad.window_size
    vad = sherpa_onnx.VoiceActivityDetector(config, buffer_size_in_seconds=100)

    resampler = None
    if rate != SR:
        import soxr
        resampler = soxr.ResampleStream(rate, SR, 1, dtype="float32")

    out_dir = Path(args.outdir)
    out_dir.mkdir(parents=True, exist_ok=True)
    out_file = out_dir / f"realtime-{datetime.now():%Y%m%d-%H%M%S}.txt"

    agc = AutoGain()
    display = TerminalDisplay()
    preroll = int(0.5 * SR)   # audio kept before speech onset; VAD fires after the first syllable
    buffer = np.zeros(0, dtype=np.float32)
    # history: everything fed to the VAD, hist[0] is absolute sample hist_base. VAD segments carry
    # their absolute start (front.start), so the pre-roll is cut from history at the true onset,
    # independent of how late is_speech_detected() fires.
    hist = np.zeros(0, dtype=np.float32)
    hist_base = 0
    live_from = 0   # absolute sample where the live (in-progress) text starts
    started = False
    started_time = None
    last_speech_end = None

    def cut(start, end=None):
        a = max(start - hist_base, 0)
        return hist[a:] if end is None else hist[a:max(end - hist_base, a)]

    with contextlib.ExitStack() as stack:
        try:
            stack.enter_context(capture)
        except Exception as e:
            sys.exit(f"Cannot open {source}: {e}\n"
                     "Nothing is connected behind this device. Run with --list-devices and pick one marked 'ok'.")
        fout = stack.enter_context(open(out_file, "a", encoding="utf-8"))
        try:
            while True:
                samples = read()
                if samples is None:
                    continue
                if resampler is not None:
                    samples = resampler.resample_chunk(samples)
                samples = agc(samples)

                buffer = np.concatenate([buffer, samples])
                while len(buffer) >= window_size:
                    win, buffer = buffer[:window_size], buffer[window_size:]
                    vad.accept_waveform(win)
                    hist = np.concatenate([hist, win])
                    if not started and vad.is_speech_detected():
                        started = True
                        started_time = time.time()
                        # detection lags the onset by ~min_speech_duration
                        live_from = hist_base + len(hist) - int(config.silero_vad.min_speech_duration * SR) - preroll

                if not started and len(hist) > 2 * preroll:
                    hist_base += len(hist) - 2 * preroll
                    hist = hist[-2 * preroll:]

                if started and time.time() - started_time > 0.2:
                    stream = recognizer.create_stream()
                    stream.accept_waveform(SR, cut(live_from))
                    recognizer.decode_stream(stream)
                    text = clean_text(stream.result.text)
                    if text:
                        display.update(text)
                    started_time = time.time()

                while not vad.empty():
                    # the VAD segment starts a little after the real onset (first syllable gets
                    # dropped), so decode it with pre-roll taken from history
                    seg_start = vad.front.start
                    seg_end = seg_start + len(vad.front.samples)
                    vad.pop()
                    stream = recognizer.create_stream()
                    seg = cut(seg_start - preroll, seg_end)
                    stream.accept_waveform(SR, seg)
                    recognizer.decode_stream(stream)
                    text = refine(nano, stream.result, seg)
                    if is_noise(text):
                        text = ""
                    if text:
                        when = datetime.now()
                        fout.write(f"[{when:%H:%M:%S}] {text}\n")
                        fout.flush()
                        gap = 0.0 if last_speech_end is None else (seg_start - last_speech_end) / SR
                        display.finalize(text, when=when, gap=gap)
                        last_speech_end = seg_end
                    else:
                        display.finalize("")
                    started = False
                    started_time = None
        except KeyboardInterrupt:
            display.close()
            print(f"Saved: {out_file}")
        finally:
            display.close()


if __name__ == "__main__":
    main()
