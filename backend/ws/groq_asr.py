"""Groq Whisper Large v3 Turbo — free ASR via GroqCloud (no card, instant key).

Endpoint: POST https://api.groq.com/openai/v1/audio/transcriptions
Free tier: 8 hrs/day of audio transcription, 2,000 req/day.

Whisper large-v3 handles Hindi well; Maithili/Magahi/Vajjika are covered only
as Hindi code-mixing (not native languages to Whisper). Still the best free,
no-bureaucracy cloud option.
"""

from __future__ import annotations

import base64
import io
import logging
import wave
from typing import Optional

import httpx

from config import settings

logger = logging.getLogger(__name__)

GROQ_URL = "https://api.groq.com/openai/v1/audio/transcriptions"

_PLACEHOLDER_KEYS = {"", "your_groq_api_key", "YOUR_GROQ_API_KEY"}

# Internal lang tags -> Groq/Whisper ISO-639-1 codes. Whisper has no native
# Maithili/Magahi; route those through Hindi (closest supported language).
LANG_MAP = {
    "hi": "hi",
    "hindi": "hi",
    "mai": "hi",
    "mag": "hi",
    "bho": "hi",
    "vajjika": "hi",
    "en": "en",
}


def _pcm_bytes_to_wav(pcm_bytes: bytes, sample_rate: int = 16000) -> bytes:
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(sample_rate)
        wav.writeframes(pcm_bytes)
    return buf.getvalue()


class GroqWhisperASR:
    def __init__(self) -> None:
        self.api_key = settings.groq_api_key
        self.model = settings.groq_model

    @property
    def _configured(self) -> bool:
        return bool(self.api_key) and self.api_key not in _PLACEHOLDER_KEYS

    @property
    def min_chunk_ms(self) -> int:
        return getattr(settings, "min_chunk_ms_for_cloud", 1500)

    async def transcribe_chunk(
        self,
        pcm_b64: str,
        language: str = "hi",
        duration_ms: int | None = None,
    ) -> dict:
        if not self._configured:
            return {"text": "", "speaker": "unknown", "confidence": 0.0}

        if duration_ms is not None and duration_ms < self.min_chunk_ms:
            return {"text": "", "speaker": "unknown", "confidence": 0.0}

        try:
            pcm = base64.b64decode(pcm_b64)
            wav_bytes = _pcm_bytes_to_wav(pcm, sample_rate=16000)
        except Exception as e:
            logger.error("Groq: bad audio chunk: %s", e)
            return {"text": "", "speaker": "unknown", "confidence": 0.0}

        whisper_lang = LANG_MAP.get(language, "hi")
        headers = {"Authorization": f"Bearer {self.api_key}"}
        files = {
            "file": ("chunk.wav", wav_bytes, "audio/wav"),
            "model": (None, self.model),
            "language": (None, whisper_lang),
            "response_format": (None, "verbose_json"),
            "temperature": (None, "0"),
        }

        async with httpx.AsyncClient(timeout=45) as client:
            try:
                resp = await client.post(GROQ_URL, headers=headers, files=files)
                if resp.status_code not in (200, 201):
                    logger.error(
                        "Groq transcription error: status=%s body=%s",
                        resp.status_code,
                        resp.text[:300],
                    )
                    return {"text": "", "speaker": "unknown", "confidence": 0.0}
                return self._parse_response(resp.json())
            except Exception as e:
                logger.error("Groq transcription failed: %s", e)
                return {"text": "", "speaker": "unknown", "confidence": 0.0}

    def _parse_response(self, result: dict) -> dict:
        text = result.get("text", "") or ""
        segments = result.get("segments", []) or []
        avg_confidence = 0.0
        confidences = [
            float(s.get("avg_logprob", 0.0))
            for s in segments
            if isinstance(s, dict) and s.get("avg_logprob") is not None
        ]
        if confidences:
            avg_confidence = sum(confidences) / len(confidences)

        return {
            "text": text,
            "speaker": "unknown",
            "confidence": avg_confidence,
            "language": result.get("language", ""),
            "utterances": segments,
        }