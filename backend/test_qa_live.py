import asyncio
import base64
import io
import json
import sys

import numpy as np
import soundfile as sf
import websockets

GNM = r"C:\Users\ADITYA\AppData\Local\Temp\opencode\qa_gnm.mp3"
PATIENT = r"C:\Users\ADITYA\AppData\Local\Temp\opencode\qa_patient.mp3"
WS_URL = "ws://127.0.0.1:8765/ws/chunks"


def load_16k(path: str):
    data, sr = sf.read(path, dtype="float32")
    if sr != 16000:
        n = int(len(data) * 16000 / sr)
        x = np.interp(np.linspace(0, len(data), n, endpoint=False), np.arange(len(data)), data)
        data = x.astype("float32")
    return data


async def main():
    g = load_16k(GNM)
    p = load_16k(PATIENT)
    gap = np.zeros(2400, dtype="float32")  # 150ms between speakers
    audio = np.concatenate([g, gap, p, gap])
    pcm = (np.clip(audio, -1.0, 1.0) * 32767).astype(np.int16)
    pcm_b64 = base64.b64encode(pcm.tobytes()).decode("ascii")
    dur = len(pcm) * 1000.0 / 16000.0

    print(f"Sending {dur:.0f} ms Q&A conversation...")

    async with websockets.connect(WS_URL) as ws:
        await ws.send(json.dumps({"type": "session_start", "encounter_id": "e2e-qa"}))
        await ws.send(json.dumps({
            "chunk_id": 0,
            "pcm_b64": pcm_b64,
            "sample_rate": 16000,
            "channels": 1,
            "mic_channel": 0,
            "start_sample": 0,
            "end_sample": len(pcm),
            "duration_ms": dur,
            "language": "hi",
        }))
        resp = json.loads(await asyncio.wait_for(ws.recv(), timeout=120))
        print("=== transcript ===")
        print(resp.get("transcript", ""))
        print("=== filled answers (live) ===")
        filled = {k: v for k, v in (resp.get("answers") or {}).items() if v not in (None, "")}
        print(json.dumps(filled, indent=2, ensure_ascii=False))

        await ws.send(json.dumps({"type": "finalize"}))
        fin = json.loads(await asyncio.wait_for(ws.recv(), timeout=120))
        print("=== finalize_result answers ===")
        final = {k: v for k, v in (fin.get("answers") or {}).items() if v not in (None, "")}
        print(json.dumps(final, indent=2, ensure_ascii=False))
        print("alerts:", fin.get("alerts"))


if __name__ == "__main__":
    asyncio.run(main())