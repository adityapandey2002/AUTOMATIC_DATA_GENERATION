"""Quick Bhashini ASR connectivity test — run AFTER adding your key/User-ID to .env."""

import asyncio
import base64
import io
import os
import sys
import wave

import httpx


def make_test_wav_b64(duration_sec: float = 3.0, sample_rate: int = 16000):
    """Generate a silent WAV with a 440Hz beep. CMS-API needs audio >= ~1-2 sec."""
    import math

    frames = int(duration_sec * sample_rate)
    pcm = bytearray()
    for i in range(frames):
        # simple tone, low volume
        val = int(4000 * math.sin(2 * math.pi * 440 * i / sample_rate))
        pcm += int(val).to_bytes(2, "little", signed=True)
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(sample_rate)
        wav.writeframes(bytes(pcm))
    return base64.b64encode(buf.getvalue()).decode("ascii")


async def main(key: str, user_id: str) -> None:
    url = "https://dhruva-api.bhashini.gov.in/services/inference/pipeline"
    headers = {
        "Authorization": key,
        "User-ID": user_id,
        "Content-Type": "application/json",
    }
    payload = {
        "pipelineTasks": [
            {
                "taskType": "asr",
                "config": {
                    "serviceId": "ai4bharat/conformer-hi-v2",
                    "language": {"sourceLanguage": "hi"},
                    "audioFormat": "wav",
                    "samplingRate": 16000,
                },
            }
        ],
        "inputData": {
            "input": [{"source": ""}],
            "audio": [{"audioContent": make_test_wav_b64(3.0)}],
        },
    }

    print(f"Testing Bhashini ASR at {url}")
    print(f"Audio: 3s tone WAV (base64, ~96KB)")
    async with httpx.AsyncClient(timeout=45) as client:
        try:
            resp = await client.post(url, headers=headers, json=payload)
            print(f"HTTP status: {resp.status_code}")
            if resp.status_code in (200, 201):
                print("SUCCESS — Bhashini responded with:", resp.text[:400])
            else:
                print("FAILED — response body:", resp.text[:400])
        except Exception as e:
            print("EXCEPTION:", type(e).__name__, e)


if __name__ == "__main__":
    key = os.getenv("BHASHINI_API_KEY", "")
    uid = os.getenv("BHASHINI_USER_ID", "")
    if not key or not uid:
        print("Error: Set BHASHINI_API_KEY and BHASHINI_USER_ID env vars or .env first.")
        sys.exit(1)
    asyncio.run(main(key, uid))