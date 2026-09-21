import asyncio
import base64
import io
import wave

import numpy as np
import soundfile as sf

from ws.groq_asr import GroqWhisperASR

MP3_PATH = r"C:\Users\ADITYA\AppData\Local\Temp\opencode\groq_test_hi.mp3"


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
    pcm_b64, dur = mp3_to_pcm16_b64(MP3_PATH)
    print(f"PCM duration: {dur:.0f} ms")
    groq = GroqWhisperASR()
    print(f"groq configured: {groq._configured}")
    result = await groq.transcribe_chunk(pcm_b64, language="hi", duration_ms=dur)
    print("RESULT:", result)


if __name__ == "__main__":
    asyncio.run(main())