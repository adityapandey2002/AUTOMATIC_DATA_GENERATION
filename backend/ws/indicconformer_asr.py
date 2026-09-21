"""AI4Bharat IndicConformer — free local ASR with a dedicated Maithili model.

MIT licensed, runs fully offline. Model (NeMo hybrid CTC-RNNT conformer):
  https://huggingface.co/ai4bharat/indicconformer_stt_mai_hybrid_ctc_rnnt_large

Requires NeMo ASR toolkit:
  pip install nemo_toolkit[asr]   (heavy, pulls torch)

Lazy-loaded and thread-safe. If NeMo is not installed, this adapter reports
not-configured and the handler falls through to the next ASR provider.
"""

from __future__ import annotations

import base64
import io
import logging
import tempfile
import threading
import wave
from typing import Optional

from config import settings

logger = logging.getLogger(__name__)

# AI4Bharat IndicConformer Maithili model (NeMo format on HuggingFace)
DEFAULT_MAITHILI_MODEL = "ai4bharat/indicconformer_stt_mai_hybrid_ctc_rnnt_large"

# Map our internal language tags -> IndicConformer model ids
MODEL_MAP = {
    "mai": settings.indic_maithili_model if getattr(settings, "indic_maithili_model", "") else DEFAULT_MAITHILI_MODEL,
    "mag": settings.indic_maithili_model if getattr(settings, "indic_maithili_model", "") else DEFAULT_MAITHILI_MODEL,
    "bho": settings.indic_maithili_model if getattr(settings, "indic_maithili_model", "") else DEFAULT_MAITHILI_MODEL,
    "vajjika": settings.indic_maithili_model if getattr(settings, "indic_maithili_model", "") else DEFAULT_MAITHILI_MODEL,
}

# Languages this adapter can help with (IndicConformer has dedicated models
# for the Bihari/Maithili family we care about).
SUPPORTED_LANGS = {"mai", "mag", "bho", "vajjika"}


class IndicConformerASR:
    def __init__(self) -> None:
        self.enabled = getattr(settings, "use_indic_conformer", True)
        self.min_chunk_ms = getattr(settings, "min_chunk_ms_for_local_indic", 1000)
        self._models: dict[str, object] = {}
        self._lock = threading.Lock()

    @property
    def _configured(self) -> bool:
        return self.enabled and self._nemo_available()

    @staticmethod
    def _nemo_available() -> bool:
        try:
            import nemo.collections.asr as nemo_asr  # noqa: F401
            return True
        except ImportError:
            return False

    def supports(self, language: str) -> bool:
        return (language or "").strip().lower() in SUPPORTED_LANGS

    def _load_model(self, model_id: str):
        import nemo.collections.asr as nemo_asr
        from nemo.collections.asr.parts.utils.transcribe_utils import cleanup
        import torch

        if model_id in self._models:
            return self._models[model_id]

        logger.info("Loading IndicConformer Maithili ASR model: %s", model_id)
        model = nemo_asr.models.ASRModel.from_pretrained(model_id)
        model.eval()
        if torch.cuda.is_available():
            model = model.cuda()
        model.freeze()
        self._models[model_id] = model
        logger.info("IndicConformer model ready")
        return model

    async def transcribe_chunk(
        self,
        pcm_b64: str,
        language: str = "mai",
        duration_ms: int | None = None,
    ) -> dict:
        if not self.enabled:
            return {"text": "", "speaker": "unknown", "confidence": 0.0}

        lang_key = (language or "").strip().lower()
        if lang_key not in MODEL_MAP:
            return {"text": "", "speaker": "unknown", "confidence": 0.0}

        if duration_ms is not None and duration_ms < self.min_chunk_ms:
            return {"text": "", "speaker": "unknown", "confidence": 0.0}

        if not self._nemo_available():
            logger.warning(
                "NeMo toolkit not installed — IndicConformer Maithili ASR unavailable. "
                "Run: pip install nemo_toolkit[asr]"
            )
            return {"text": "", "speaker": "unknown", "confidence": 0.0}

        try:
            pcm = base64.b64decode(pcm_b64)
            wav_buf = io.BytesIO()
            with wave.open(wav_buf, "wb") as wav:
                wav.setnchannels(1)
                wav.setsampwidth(2)
                wav.setframerate(16000)
                wav.writeframes(pcm)

            model_id = MODEL_MAP[lang_key]

            def _run():
                with self._lock:
                    model = self._load_model(model_id)
                    with tempfile.NamedTemporaryFile(suffix=".wav", delete=True) as tmp:
                        wav_buf.seek(0)
                        tmp.write(wav_buf.getvalue())
                        tmp.flush()
                        transcripts = model.transcribe([tmp.name], batch_size=1, verbose=False)
                    text = " ".join(t.strip() for t in transcripts if t).strip()
                    return text

            import asyncio
            text = await asyncio.to_thread(_run)
            if not text:
                return {"text": "", "speaker": "unknown", "confidence": 0.0}
            return {
                "text": text,
                "speaker": "unknown",
                "confidence": 0.5,
                "language": "maithili",
            }
        except Exception as e:
            logger.error("IndicConformer transcription failed: %s", e)
            return {"text": "", "speaker": "unknown", "confidence": 0.0}