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

# Consecutive load/transcribe failures before the fallback switches itself off.
# A missing or truncated model snapshot fails identically every single time, so
# retrying it per chunk only adds latency to chunks the cloud provider could
# have served.
_MAX_LOAD_FAILURES = 3

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
        self._consecutive_failures = 0
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
        context: str = "",
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
                kwargs = dict(
                    language=whisper_lang,
                    beam_size=1,
                    vad_filter=True,
                    condition_on_previous_text=True,
                    no_speech_threshold=settings.no_speech_prob_threshold,
                    log_prob_threshold=settings.avg_logprob_floor,
                    compression_ratio_threshold=settings.compression_ratio_threshold,
                )
                if context and context.strip():
                    kwargs["initial_prompt"] = context.strip()
                segments, info = model.transcribe(wav_buf, **kwargs)
                text = " ".join(seg.text.strip() for seg in segments).strip()
                return text, info

        try:
            import asyncio
            text, info = await asyncio.to_thread(_run)
            self._consecutive_failures = 0
            if not text:
                return {"text": "", "speaker": "unknown", "confidence": 0.0}
            # Same rule as groq_asr._parse_response: a missing metric must be
            # None, never 0.0. avg_logprob is a log-probability, so 0.0 is the
            # *best possible* value -- a response with no metrics at all would
            # sail past both the tentative and the floor gate as if Whisper were
            # certain. None makes the gates skip.
            avg_logprob = getattr(info, "avg_logprob", None)
            if avg_logprob is not None:
                avg_logprob = float(avg_logprob)
            no_speech_prob = getattr(info, "no_speech_prob", None)
            if no_speech_prob is not None:
                no_speech_prob = float(no_speech_prob)
            compression_ratio = getattr(info, "compression_ratio", None)
            if compression_ratio is not None:
                compression_ratio = float(compression_ratio)
            return {
                "text": text,
                "speaker": "unknown",
                "confidence": avg_logprob,
                "avg_logprob": avg_logprob,
                "no_speech_prob": no_speech_prob,
                "compression_ratio": compression_ratio,
                "language": (getattr(info, "language", "") or ""),
            }
        except Exception as e:
            # Log the TYPE too: several exception classes stringify to an empty
            # string, which is what produced the undiagnosable
            # "LocalWhisper transcription failed:" line with nothing after it.
            self._consecutive_failures += 1
            if self._consecutive_failures >= _MAX_LOAD_FAILURES and self._model is None:
                # The weights almost certainly never downloaded. Retrying the
                # load on every chunk would re-pay the multi-second hub timeout
                # per chunk for the rest of the encounter, stalling the live
                # pipeline while Groq was perfectly capable of serving it.
                self.enabled = False
                logger.error(
                    "LocalWhisper disabled after %d failed attempts (%s: %s); "
                    "cloud ASR is now the only path",
                    self._consecutive_failures,
                    type(e).__name__,
                    e,
                )
            else:
                logger.error(
                    "LocalWhisper transcription failed: %s: %s", type(e).__name__, e
                )
            return {"text": "", "speaker": "unknown", "confidence": 0.0}
