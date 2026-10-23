"""Sarvam AI Saaras v3 — ASR adapter (REST batch, per audio chunk)."""

from __future__ import annotations

import base64
import io
import logging
import struct
import wave
from typing import Optional

import httpx

from config import settings
from ws.asr import AsrError

logger = logging.getLogger(__name__)

# REST endpoint for Saaras v3 speech-to-text (NOT /asr, NOT /v1)
SARVAM_ASR_URL = "https://api.sarvam.ai/speech-to-text"

_PLACEHOLDER_KEYS = {"", "your_sarvam_api_key", "YOUR_SARVAM_API_KEY"}

# Internal lang tags -> Sarvam BCP-47 codes (required; "hi" alone is rejected).
LANG_MAP = {
    "hi": "hi-IN",
    "hindi": "hi-IN",
    "mai": "mai-IN",
    "mag": "mag-IN",
    "bho": "bho-IN",
    "en": "en-IN",
}


def _pcm_bytes_to_wav(pcm_bytes: bytes, sample_rate: int = 16000, channels: int = 1) -> bytes:
    """Wrap raw 16-bit PCM bytes into a WAV file suitable for Sarvam."""
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wav:
        wav.setnchannels(channels)
        wav.setsampwidth(2)  # 16-bit
        wav.setframerate(sample_rate)
        wav.writeframes(pcm_bytes)
    return buf.getvalue()


class SarvamASR:
    name = "sarvam"
    priority = 20
    min_chunk_ms = 0

    def __init__(self) -> None:
        self.api_key = settings.sarvam_api_key

    @property
    def _configured(self) -> bool:
        return bool(self.api_key) and self.api_key not in _PLACEHOLDER_KEYS

    @property
    def available(self) -> bool:
        return self._configured

    def supports(self, language: str) -> bool:
        return False

    async def transcribe_chunk(
        self,
        pcm_b64: str,
        language: str = "hi-IN",
        duration_ms: int | None = None,
        context: str = "",
    ) -> dict:
        """Send a single audio chunk to the Sarvam REST speech-to-text API.

        `context` is accepted for seam uniformity and ignored: Sarvam has no
        prompt-biasing input.
        """
        if not self._configured:
            return {"text": "", "speaker": "unknown", "confidence": 0.0}

        try:
            pcm = base64.b64decode(pcm_b64)
            wav_bytes = _pcm_bytes_to_wav(pcm, sample_rate=16000, channels=1)
        except Exception as e:
            raise AsrError(f"could not decode audio chunk: {e}", retryable=False) from e

        headers = {
            "api-subscription-key": self.api_key,
        }

        files = {
            "file": ("chunk.wav", wav_bytes, "audio/wav"),
            "language_code": (None, LANG_MAP.get((language or "").lower(), "hi-IN")),
            "model": (None, "saaras:v3"),
            "mode": (None, "transcribe"),
            "with_timestamps": (None, "false"),
            "with_diarization": (None, "false"),
        }

        timeout = float(getattr(settings, "asr_timeout_s", 15.0))
        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                resp = await client.post(
                    SARVAM_ASR_URL,
                    headers=headers,
                    files=files,
                )
        except Exception as e:
            raise AsrError(f"{type(e).__name__}: {e}".strip(), retryable=True) from e

        if resp.status_code not in (200, 201):
            body = resp.text[:300]
            retryable = resp.status_code == 429 or resp.status_code >= 500
            raise AsrError(f"HTTP {resp.status_code}: {body}", retryable=retryable)
        return self._parse_response(resp.json())

    def _parse_response(self, result: dict) -> dict:
        transcript = ""
        speaker = "unknown"
        confidence = 0.0

        if isinstance(result, dict):
            transcript = result.get("transcript") or result.get("text") or ""
            utterances = result.get("utterances") or []
            if utterances and isinstance(utterances[0], dict):
                spk = utterances[0].get("speaker")
                if spk == 1:
                    speaker = "patient"
                elif spk == 2:
                    speaker = "gnm"
                confidence = utterances[0].get("confidence", 0.0)

        return {
            "text": transcript,
            "speaker": speaker,
            "confidence": confidence,
            "language": result.get("language", "") if isinstance(result, dict) else "",
            "utterances": result.get("utterances", []) if isinstance(result, dict) else [],
        }
