import asyncio
import base64
import json
import sys

import numpy as np
import soundfile as sf
import websockets

MP3_PATH = r"C:\Users\ADITYA\AppData\Local\Temp\opencode\groq_test_hi.mp3"
WS_URL = "ws://127.0.0.1:8765/ws/chunks"


def mp3_to_pcm_b64(path: str):
    data, sr = sf.read(path, dtype="float32")
    n = int(len(data) * 16000 / sr)
    x = np.interp(np.linspace(0, len(data), n, endpoint=False), np.arange(len(data)), data)
    pcm = (np.clip(x, -1.0, 1.0) * 32767).astype(np.int16).tobytes()
    return base64.b64encode(pcm).decode("ascii"), len(pcm) * 1000.0 / 32000.0


async def main():
    language = sys.argv[1] if len(sys.argv) > 1 else "hi"
    pcm_b64, dur = mp3_to_pcm_b64(MP3_PATH)
    print(f"Sending {dur:.0f} ms of real speech (language={language})...")

    async with websockets.connect(WS_URL) as ws:
        await ws.send(json.dumps({"type": "session_start", "encounter_id": f"e2e-{language}"}))
        await ws.send(
            json.dumps(
                {
                    "chunk_id": 0,
                    "pcm_b64": pcm_b64,
                    "sample_rate": 16000,
                    "channels": 1,
                    "mic_channel": 0,
                    "start_sample": 0,
                    "end_sample": int(16000 * dur / 1000),
                    "duration_ms": dur,
                    "language": language,
                }
            )
        )
        resp = json.loads(await asyncio.wait_for(ws.recv(), timeout=90))
        print("=== transcript ===")
        print(resp.get("transcript", ""))
        print("=== filled answers ===")
        filled = {k: v for k, v in (resp.get("answers") or {}).items() if v not in (None, "")}
        print(json.dumps(filled, indent=2, ensure_ascii=False))
        print("=== alerts ===")
        print(json.dumps(resp.get("alerts", []), indent=2, ensure_ascii=False))


if __name__ == "__main__":
    asyncio.run(main())