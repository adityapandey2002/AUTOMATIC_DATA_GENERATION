"""Confirm the local faster-whisper fallback is usable offline.

This used to be the reason a Groq blip killed transcription outright:

    LocalWhisper transcription failed: The cached snapshot for
    'Systran/faster-whisper-small' ... is incomplete: 1 file(s) are missing
    (model.bin). The Hub could not be reached (ConnectError: getaddrinfo failed)

Every other provider was inert, so with Groq alone a single dropped request
ended the encounter's transcription. model.bin is now cached (461MB, fetched
with HF_HUB_DISABLE_XET=1 after the Xet/CAS backend failed with
"File reconstruction error").

Loads the model and transcribes a real WAV fixture if present. No network.
"""

from __future__ import annotations

import os
import sys
import time
import wave
from array import array
from pathlib import Path

BACKEND = Path(__file__).resolve().parent
sys.path.insert(0, str(BACKEND))

from config import settings  # noqa: E402

MODEL_DIR = Path.home() / ".cache" / "huggingface" / "hub" / "models--Systran--faster-whisper-small"
# Optional speech fixture, if the live-ASR test scripts left one behind.
FIXTURE = Path(os.getenv("TEMP", "/tmp")) / "opencode" / "pos_control.wav"


def report(ok: bool, msg: str) -> bool:
    print(f"  {'PASS' if ok else 'FAIL'}  {msg}")
    return ok


def main() -> int:
    good = True

    print("=== model cache on disk ===")
    bins = list(MODEL_DIR.rglob("model.bin")) if MODEL_DIR.exists() else []
    incomplete = list(MODEL_DIR.rglob("*.incomplete")) if MODEL_DIR.exists() else []
    size_mb = bins[0].stat().st_size / 1e6 if bins else 0
    good &= report(bool(bins), f"model.bin present ({size_mb:.1f} MB)")
    good &= report(not incomplete, f"no .incomplete blobs left ({len(incomplete)} found)")

    print("\n=== loads offline (HF_HUB_OFFLINE) ===")
    import asyncio
    import base64
    import os

    os.environ["HF_HUB_OFFLINE"] = "1"
    os.environ["HF_HUB_DISABLE_XET"] = "1"
    try:
        t0 = time.monotonic()
        from ws.local_asr import LocalWhisperASR  # noqa: E402

        asr = LocalWhisperASR()
        silence = base64.b64encode(array("h", [0] * 16000).tobytes()).decode("ascii")
        r = asyncio.run(asr.transcribe_chunk(silence, language="hi", duration_ms=1000))
        print(f"  PASS  model loaded + ran in {time.monotonic() - t0:.1f}s")
        print(f"        silence -> {r['text']!r}")
        good &= report(r["text"] == "", "digital silence yields no text")
        good &= report(asr.enabled, "fallback still enabled after a clean silence chunk")
    except Exception as e:
        good &= report(False, f"offline load failed: {type(e).__name__}: {e}")
        return 1

    print(f"\n  model     : {asr.model_size}")
    print(f"  device    : {asr.device} / {asr.compute_type}")

    if FIXTURE.exists():
        print("\n=== transcribes real speech ===")
        with wave.open(str(FIXTURE), "rb") as w:
            raw = w.readframes(w.getnframes())
            rate = w.getframerate()
            nch = w.getnchannels()
        if nch > 1:
            samples = array("h")
            samples.frombytes(raw)
            mono = array("h", [sum(samples[i : i + nch]) // nch for i in range(0, len(samples), nch)])
            raw = mono.tobytes()
        b64 = base64.b64encode(raw).decode("ascii")
        t0 = time.monotonic()
        r = asyncio.run(
            asr.transcribe_chunk(b64, language="en", duration_ms=int(len(raw) / 2 / rate * 1000))
        )
        dur = len(raw) / 2 / rate
        print(f"  PASS  {dur:.1f}s of speech in {time.monotonic() - t0:.1f}s")
        print(f"        {r['text']!r}")
        print(f"        avg_logprob={r.get('avg_logprob')!r} no_speech_prob={r.get('no_speech_prob')!r}")
        if not r["text"].strip():
            good &= report(False, "real speech produced no text")
        good &= report(
            r.get("avg_logprob") is None or r["avg_logprob"] < 0,
            "avg_logprob is a real logprob (None, never a fabricated 0.0)",
        )
    else:
        print("\n  SKIP  no speech fixture (pos_control.wav) present")

    print(f"\n{'OK' if good else 'PROBLEMS FOUND'}")
    return 0 if good else 1


if __name__ == "__main__":
    raise SystemExit(main())
