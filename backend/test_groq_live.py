import asyncio
import base64
import io
import os
import sys
import wave

import numpy as np
import soundfile as sf

from ws.groq_asr import GroqWhisperASR

# Fixture lives in the per-user temp dir. This used to be a hardcoded
# C:\Users\ADITYA\... path, which only resolved on the machine that authored it.
FIXTURES = os.path.join(os.environ.get("TEMP", "."), "opencode")
MP3_PATH = os.path.join(FIXTURES, "groq_test_hi.mp3")


def mp3_to_pcm16_b64(path: str) -> str:
    data, sr = sf.read(path, dtype="float32")
    if sr != 16000:
        n = int(len(data) * 16000 / sr)
        x = np.interp(np.linspace(0, len(data), n, endpoint=False), np.arange(len(data)), data)
        data, sr = x.astype("float32"), 16000
    pcm = (np.clip(data, -1.0, 1.0) * 32767).astype(np.int16)
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(16000)
        wav.writeframes(pcm.tobytes())
    return base64.b64encode(pcm.tobytes()).decode("ascii"), len(pcm) * 1000.0 / 16000.0


async def main():
    if not os.path.exists(MP3_PATH):
        print(f"SKIP: no fixture at {MP3_PATH}")
        print("      Put a Hindi speech clip there, or see docs/GUIDES/local-run.md")
        return 0
    pcm_b64, dur = mp3_to_pcm16_b64(MP3_PATH)
    print(f"PCM duration: {dur:.0f} ms")
    groq = GroqWhisperASR()
    print(f"groq configured: {groq._configured}")
    result = await groq.transcribe_chunk(pcm_b64, language="hi", duration_ms=dur)
    print("RESULT:", result)
    # These must be real numbers, not the 0.0 defaults that silently bypassed
    # every confidence gate (0.0 > 0.6 / 0.0 < -1.5 / 0.0 > 2.4 are all False).
    for k in ("avg_logprob", "no_speech_prob", "compression_ratio"):
        v = result.get(k)
        print(f"  metric {k:19}: {'MISSING' if v is None else f'{v:.3f}'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))