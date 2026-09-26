"""Groq Whisper Large v3 Turbo — free ASR via GroqCloud (no card, instant key).

Endpoint: POST https://api.groq.com/openai/v1/audio/transcriptions
Free tier: 8 hrs/day of audio transcription, 2,000 req/day.

Whisper large-v3 handles Hindi well; Maithili/Magahi/Vajjika are covered only
as Hindi code-mixing (not native languages to Whisper). Still the best free,
no-bureaucracy cloud option.
"""

from __future__ import annotations

import asyncio
import base64
import io
import logging
import wave
from typing import Optional

import httpx

from config import settings

logger = logging.getLogger(__name__)

GROQ_URL = "https://api.groq.com/openai/v1/audio/transcriptions"

# Groq validates the prompt against an 896-unit cap — empirically UTF-8 BYTES,
# not characters (a 650-char Devanagari-heavy prompt rejected as "926 chars").
# Stay well under it.
_PROMPT_MAX_BYTES = 850


def _prompt_utf8_limited(text: str, max_bytes: int = _PROMPT_MAX_BYTES) -> str:
    """Truncate to max_bytes from the FRONT so trailing domain terms survive."""
    raw = text.encode("utf-8")
    if len(raw) <= max_bytes:
        return text
    # Cut the oldest bytes; errors="ignore" drops a split leading char.
    return raw[-max_bytes:].decode("utf-8", errors="ignore").lstrip()

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
        context: str = "",
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
            # MUST be "segment": asking for "word" granularity returns a `words`
            # array with no confidence fields AND suppresses `segments` entirely,
            # so avg_logprob / no_speech_prob / compression_ratio were never
            # available and every downstream gate silently passed.
            "timestamp_granularities[]": (None, "segment"),
        }
        if context and context.strip():
            # Groq's prompt is token-limited (~224 tokens) even though the HTTP
            # char cap is 896. A long transcript tail eats the budget and the
            # domain terms get truncated off, silently degrading Hindi output.
            # Keep the tail short and ALWAYS end with the domain vocabulary
            # (handler appends hi_prompt_terms last), so the bias words survive
            # the token window intact.
            words = context.strip().split()
            tail = " ".join(words[-140:])  # ~140 words ≈ 160-210 tokens
            files["prompt"] = (None, _prompt_utf8_limited(tail))

        empty = {"text": "", "speaker": "unknown", "confidence": 0.0}
        attempts = max(1, int(getattr(settings, "asr_max_attempts", 3)))
        timeout = float(getattr(settings, "asr_timeout_s", 15.0))
        backoff = float(getattr(settings, "asr_retry_backoff_s", 0.6))
        last_error = "unknown"

        for attempt in range(1, attempts + 1):
            try:
                async with httpx.AsyncClient(timeout=timeout) as client:
                    resp = await client.post(GROQ_URL, headers=headers, files=files)
                if resp.status_code in (200, 201):
                    if attempt > 1:
                        logger.info(
                            "Groq: chunk recovered on attempt %d/%d", attempt, attempts
                        )
                    return self._parse_response(resp.json())

                body = resp.text[:300]
                # 429 and 5xx are transient; any other 4xx is a credential or
                # request problem that will fail identically on every retry.
                transient = resp.status_code == 429 or resp.status_code >= 500
                last_error = f"HTTP {resp.status_code}: {body}"
                if not transient:
                    logger.error("Groq transcription error: %s", last_error)
                    return empty
                logger.warning(
                    "Groq transcription attempt %d/%d failed (transient): %s",
                    attempt, attempts, last_error,
                )
            except Exception as e:
                # Log the TYPE as well as the message: several httpx/asyncio
                # exceptions stringify to an empty string, which produced the
                # useless log line "Groq transcription failed:" with nothing
                # after it and made this undiagnosable in the field.
                last_error = f"{type(e).__name__}: {e}".strip()
                logger.warning(
                    "Groq transcription attempt %d/%d raised %s",
                    attempt, attempts, last_error,
                    exc_info=(attempt == attempts),
                )

            if attempt < attempts:
                await asyncio.sleep(backoff * (2 ** (attempt - 1)))

        logger.error("Groq transcription failed after %d attempts: %s", attempts, last_error)
        return empty

    def _parse_response(self, result: dict) -> dict:
        text = result.get("text", "") or ""
        segments = result.get("segments", []) or []
        # Missing metrics MUST stay None. These used to default to 0.0, which
        # is the *best possible* value for every downstream gate (0.0 > 0.6 is
        # False, 0.0 < -1.5 is False, 0.0 > 2.4 is False), so a response with no
        # segments at all was treated as maximally confident and bypassed every
        # check. None makes the gates skip, as they already do for providers
        # that expose no confidence metrics.
        avg_logprob: Optional[float] = None
        no_speech_prob: Optional[float] = None
        compression_ratio: Optional[float] = None
        logprobs = []
        no_speech_probs = []
        compression_ratios = []
        for s in segments:
            if not isinstance(s, dict):
                continue
            if s.get("avg_logprob") is not None:
                logprobs.append(float(s["avg_logprob"]))
            if s.get("no_speech_prob") is not None:
                no_speech_probs.append(float(s["no_speech_prob"]))
            if s.get("compression_ratio") is not None:
                compression_ratios.append(float(s["compression_ratio"]))
        if logprobs:
            avg_logprob = sum(logprobs) / len(logprobs)
        if no_speech_probs:
            no_speech_prob = sum(no_speech_probs) / len(no_speech_probs)
        if compression_ratios:
            compression_ratio = max(compression_ratios)
        # Groq verbose_json returns words at top level (not inside segments).
        words = result.get("words", []) or []
        if not words and len(segments) == 1 and isinstance(segments[0], dict):
            words = segments[0].get("words", []) or []

        return {
            "text": text,
            "speaker": "unknown",
            "confidence": avg_logprob,
            "avg_logprob": avg_logprob,
            "no_speech_prob": no_speech_prob,
            "compression_ratio": compression_ratio,
            "words": words,
            "language": result.get("language", ""),
            "utterances": segments or result.get("words", []) or [],
        }