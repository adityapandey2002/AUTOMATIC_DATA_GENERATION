"""Bhashini Government API — fallback ASR for Magahi/Maithili/Bhojpuri.

Production-tested flow (2026):
  POST https://dhruva-api.bhashini.gov.in/services/inference/pipeline
  Headers:  Authorization: <API key>
            User-ID:       <User ID>
            Content-Type:  application/json
  Body:     pipelineTasks[].taskType=asr + inputData.audio[].audioContent=<b64>

No runtime pipeline-resolution needed — the endpoint above is the stable
inference endpoint issued to integrators. Optionally expose a custom pipeline
ID via BHASHINI_PIPELINE_ID if required by your account.
"""

from __future__ import annotations

import base64
import io
import logging
import wave
from typing import Optional

import httpx

from config import settings
from ws.asr import AsrError

logger = logging.getLogger(__name__)

# Stable SaaS inference endpoint for Bhashini ASR (issued to integrators).
BHASHINI_INFER_URL = "https://dhruva-api.bhashini.gov.in/services/inference/pipeline"

_PLACEHOLDER_KEYS = {"", "your_bhashini_api_key", "YOUR_BHASHINI_API_KEY", "your_user_id"}

# Well-known ASR service IDs per language (Indo-Aryan conformer family).
SERVICE_IDS = {
    "hi": "ai4bharat/conformer-hi-v2",
    "mai": "ai4bharat/conformer-multilingual-indo_aryan-gpu--t4",
    "mag": "ai4bharat/conformer-multilingual-indo_aryan-gpu--t4",
    "bho": "ai4bharat/conformer-multilingual-indo_aryan-gpu--t4",
}
LANG_MAP = {
    "hi": "hi",
    "mai": "mai",
    "mag": "mag",
    "bho": "bho",
}


def _pcm_bytes_to_wav(pcm_bytes: bytes, sample_rate: int = 16000) -> bytes:
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(sample_rate)
        wav.writeframes(pcm_bytes)
    return buf.getvalue()


class BhashiniASR:
    name = "bhashini"
    priority = 30
    min_chunk_ms = 0

    def __init__(self) -> None:
        self.api_key = settings.bhashini_api_key
        self.user_id = settings.bhashini_user_id
        self.pipeline_id = getattr(settings, "bhashini_pipeline_id", "") or None

    @property
    def _configured(self) -> bool:
        return (
            bool(self.api_key)
            and self.api_key not in _PLACEHOLDER_KEYS
            and bool(self.user_id)
            and self.user_id not in _PLACEHOLDER_KEYS
        )

    @property
    def available(self) -> bool:
        return self._configured

    def supports(self, language: str) -> bool:
        return False

    async def transcribe_chunk(
        self,
        pcm_b64: str,
        language: str = "hi",
        duration_ms: int | None = None,
        context: str = "",
    ) -> dict:
        """Send audio to Bhashini ASR pipeline (batch only).

        `context` is accepted for seam uniformity and ignored: Bhashini has no
        prompt-biasing input.
        """
        if not self._configured:
            return {"text": "", "speaker": "unknown", "confidence": 0.0}

        try:
            pcm = base64.b64decode(pcm_b64)
            wav_bytes = _pcm_bytes_to_wav(pcm, sample_rate=16000)
            audio_b64 = base64.b64encode(wav_bytes).decode("ascii")
        except Exception as e:
            raise AsrError(f"bad audio chunk: {e}", retryable=False) from e

        bhashini_lang = LANG_MAP.get(language, "hi")
        service_id = SERVICE_IDS.get(bhashini_lang, SERVICE_IDS["hi"])
        if self.pipeline_id:
            service_id = self.pipeline_id

        headers = {
            "Authorization": self.api_key,
            "User-ID": self.user_id,
            "Content-Type": "application/json",
        }

        payload = {
            "pipelineTasks": [
                {
                    "taskType": "asr",
                    "config": {
                        "serviceId": service_id,
                        "language": {"sourceLanguage": bhashini_lang},
                        "audioFormat": "wav",
                        "samplingRate": 16000,
                    },
                }
            ],
            "inputData": {
                "input": [{"source": ""}],
                "audio": [{"audioContent": audio_b64}],
            },
        }

        timeout = float(getattr(settings, "asr_timeout_s", 15.0))
        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                resp = await client.post(
                    BHASHINI_INFER_URL, headers=headers, json=payload
                )
        except Exception as e:
            raise AsrError(f"{type(e).__name__}: {e}".strip(), retryable=True) from e

        if resp.status_code not in (200, 201):
            body = resp.text[:300]
            retryable = resp.status_code == 429 or resp.status_code >= 500
            raise AsrError(f"HTTP {resp.status_code}: {body}", retryable=retryable)
        return self._parse_response(resp.json())

    def _parse_response(self, result: dict) -> dict:
        try:
            output = result.get("pipelineResponse", {}).get("output", [{}])[0]
            text = output.get("target", "") or output.get("source", "") or ""
            if not text and "text" in output:
                text = output["text"]
            return {
                "text": text,
                "speaker": "unknown",
                "confidence": 0.8,
                "language": output.get("targetLanguage", ""),
            }
        except (KeyError, IndexError):
            return {"text": "", "speaker": "unknown", "confidence": 0.0}
