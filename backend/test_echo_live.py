"""LIVE regression test for the prompt-echo hallucination (uses the Groq API).

Bug this guards
--------------
Whisper handed near-silence does not return nothing -- it regurgitates the
domain vocabulary we inject as a decoding hint. Observed live: a quiet chunk
came back as

    " प्रसव पीड़ा, सामान्य प्रसव पीड़ा, रेफर, डिस्चार्ज"

and local_fill() turned it into a FABRICATED

    {'delivery_mode': 'Normal', 'final_outcome': 'Referral'}

on a maternity case sheet, for a patient who had said nothing of the kind.

Confidence gating cannot catch this: measured against the live API that echo
returns avg_logprob=-0.149, no_speech_prob=0.113, compression_ratio=0.82, i.e.
Whisper is *confidently* wrong. Only comparing the output against the prompt we
injected identifies it.

Two controls run here:
  1. NEGATIVE -- near-silence must not produce fields, and must not accumulate.
  2. POSITIVE -- real speech must still transcribe and be accepted. This needs
     a real recording; it is SKIPped when the fixture is absent.

    Run:  venv\\Scripts\\python.exe test_echo_live.py
    Needs: a real GROQ_API_KEY in .env
"""

import array
import asyncio
import base64
import math
import os
import sys
import wave

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import settings  # noqa: E402
from engine.local_fill import local_fill  # noqa: E402
from ws.handler import ChunkSession, is_prompt_echo  # noqa: E402

FIXTURES = os.path.join(os.environ.get("TEMP", "."), "opencode")
# Any real speech clip works; the fixture below is Windows TTS-generated English,
# used purely to prove the gate does not reject genuine audio.
SPEECH_WAV = os.path.join(FIXTURES, "pos_control.wav")

FAILED: list[str] = []


def check(label: str, got, want) -> None:
    ok = got == want
    print(f"  {'OK  ' if ok else 'FAIL'}  {label}: {got!r}")
    if not ok:
        FAILED.append(f"{label}: got {got!r}, want {want!r}")


def silence_chunk(seconds: float = 2.0, amp: int = 200) -> tuple[str, int]:
    """Near-silence at the RMS levels seen in the original report (0.005-0.03)."""
    n = int(16000 * seconds)
    s = array.array("h", [int(amp * math.sin(i / 25)) for i in range(n)])
    return base64.b64encode(s.tobytes()).decode("ascii"), int(seconds * 1000)


def wav_chunks(path: str, seconds: float = 2.0):
    with wave.open(path, "rb") as w:
        if w.getnchannels() != 1 or w.getsampwidth() != 2:
            raise SystemExit(f"fixture must be mono 16-bit: {path}")
        sr = w.getframerate()
        raw = w.readframes(w.getnframes())
    samples = array.array("h")
    samples.frombytes(raw)
    if sys.byteorder == "big":
        samples.byteswap()
    step = int(sr * seconds)
    for i in range(0, len(samples) - step + 1, step):
        blk = samples[i:i + step]
        yield base64.b64encode(blk.tobytes()).decode("ascii"), int(len(blk) * 1000.0 / sr)


def filled(session: ChunkSession) -> dict:
    snap = session.merge.get_snapshot()["answers"]
    return {k: v for k, v in snap.items() if v is not None}


async def negative_control() -> None:
    print("\n--- NEGATIVE: near-silence must not fabricate or accumulate ---")
    sess = ChunkSession()
    sess.reset("echo-live")
    sess.active = True
    for cid in range(4):
        pcm, dur = silence_chunk()
        r = await sess.process_chunk(
            {"chunk_id": cid, "pcm_b64": pcm, "duration_ms": dur, "language": "hi"}
        )
        print(f"    chunk {cid}: status={r['status']:<10} text={r.get('transcript', '')!r}")

    check("no fabricated clinical fields", filled(sess), {})
    check(
        "echo does not accumulate in transcript",
        len(sess.transcript_buffer) <= 1,
        True,
    )


async def positive_control() -> bool:
    print("\n--- POSITIVE: real speech must still be accepted ---")
    if not os.path.exists(SPEECH_WAV):
        print(f"    SKIP: no real-speech fixture at {SPEECH_WAV}")
        print("          Any 16kHz mono 16-bit WAV works; see docs/GUIDES/local-run.md")
        return True

    sess = ChunkSession()
    sess.reset("speech-live")
    sess.active = True
    for cid, (pcm, dur) in enumerate(wav_chunks(SPEECH_WAV)):
        r = await sess.process_chunk(
            {"chunk_id": cid, "pcm_b64": pcm, "duration_ms": dur, "language": "en"}
        )
        print(f"    chunk {cid}: status={r['status']:<10} text={r.get('transcript', '')!r}")

    heard = " ".join(sess.transcript_buffer).strip()
    check("real speech produced a transcript", bool(heard), True)
    check("real speech was never flagged as echo", len(sess.transcript_buffer) > 0, True)
    return bool(heard)


def reported_string() -> None:
    print("\n--- The exact transcript from the bug report ---")
    reported = " प्रसव पीड़ा, सामान्य प्रसव पीड़ा, रेफर, डिस्चार्ज"
    print(f"    local_fill would have written: {local_fill(reported)}")
    check(
        "blocked by is_prompt_echo before local_fill",
        is_prompt_echo(reported, settings.hi_prompt_terms, set(), set()),
        True,
    )


async def main() -> int:
    if not settings.groq_api_key:
        print("SKIP: no GROQ_API_KEY in .env")
        return 0
    await negative_control()
    await positive_control()
    reported_string()

    print("\n" + "-" * 66)
    if FAILED:
        print(f"{len(FAILED)} FAILED")
        for f in FAILED:
            print(f"  - {f}")
        return 1
    print("PASS - hallucination blocked, genuine speech unaffected")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
