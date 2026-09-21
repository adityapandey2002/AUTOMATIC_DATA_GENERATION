"""Local offline ASR fallback using faster-whisper (no API keys, $0).

Runs on the backend host (not the capture laptop). Covers Hindi well but is
weak on Maithili/Vajjika/code-mixing — use only as a fallback when cloud
providers (Bhashini/Sarvam) are unavailable.
"""

from __future__ import annotations

import base64
import logging
import threading
from typing import Optional

from config import settings

logger = logging.getLogger(__name__)

_PLACEHOLDER_KEYS = {"", "your_sarvam_api_key", "YOUR_SARVAM_API_KEY"}

# Language codes passed to faster-whisper (map from our internal tags)
LANG_MAP = {"hi": "hi", "mai": "hi", "mag": "hi", "bho": "hi", "hindi": "hi"}


class LocalWhisperASR:
    """faster-whisper wrapper — lazy-loaded and thread-safe."""

    def __init__(self, model_size: str = "small", device: str = "cpu", compute_type: str = "int8") -> None:
        self.model_size = model_size or getattr(settings, "whisper_model_size", "small")
        self.device = device or getattr(settings, "whisper_device", "cpu")
        self.compute_type = compute_type or getattr(settings, "whisper_compute_type", "int8")
        self._model = None
        self._lock = threading.Lock()
        self.enabled = getattr(settings, "use_local_fallback", True)

    @property
    def _configured(self) -> bool:
        return self.enabled

    def _load_model(self):
        if self._model is None:
            from faster_whisper import WhisperModel
            logger.info(
                "Loading faster-whisper model '%s' on %s/%s (first load downloads weights)",
                self.model_size,
                self.device,
                self.compute_type,
            )
            self._model = WhisperModel(
                self.model_size,
                device=self.device,
                compute_type=self.compute_type,
            )
            logger.info("faster-whisper model ready")
        return self._model

    async def transcribe_chunk(
        self,
        pcm_b64: str,
        language: str = "hi",
        duration_ms: int | None = None,
    ) -> dict:
        if not self._configured:
            return {"text": "", "speaker": "unknown", "confidence": 0.0}

        try:
            pcm = base64.b64decode(pcm_b64)
        except Exception as e:
            logger.error("LocalWhisper: bad audio chunk: %s", e)
            return {"text": "", "speaker": "unknown", "confidence": 0.0}

        # faster-whisper expects a file path or file-like. Write to a temp wav.
        import io
        import wave

        wav_buf = io.BytesIO()
        with wave.open(wav_buf, "wb") as wav:
            wav.setnchannels(1)
            wav.setsampwidth(2)
            wav.setframerate(16000)
            wav.writeframes(pcm)
        wav_buf.seek(0)

        whisper_lang = LANG_MAP.get(language, "hi")

        def _run():
            with self._lock:
                model = self._load_model()
                segments, info = model.transcribe(
                    wav_buf,
                    language=whisper_lang,
                    beam_size=1,
                    vad_filter=True,
                    condition_on_previous_text=True,
                )
                text = " ".join(seg.text.strip() for seg in segments).strip()
                return text, info

        try:
            import asyncio
            text, info = await asyncio.to_thread(_run)
            if not text:
                return {"text": "", "speaker": "unknown", "confidence": 0.0}
            return {
                "text": text,
                "speaker": "unknown",
                "confidence": getattr(info, "avg_logprob", 0.0),
                "language": (getattr(info, "language", "") or ""),
            }
        except Exception as e:
            logger.error("LocalWhisper transcription failed: %s", e)
            return {"text": "", "speaker": "unknown", "confidence": 0.0}
