"""Backend settings — loaded from .env / environment variables."""

from __future__ import annotations

from pathlib import Path

from pydantic_settings import BaseSettings

BACKEND_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = BACKEND_DIR.parent
ENV_FILE = PROJECT_ROOT / ".env"


class Settings(BaseSettings):
    sarvam_api_key: str = ""
    bhashini_api_key: str = ""
    bhashini_user_id: str = ""
    bhashini_pipeline_id: str = ""
    gemini_api_key: str = ""
    groq_api_key: str = ""
    groq_model: str = "whisper-large-v3"
    llm_model: str = "gemini-3.5-flash"
    # Gemini is called once per case at finalize for ambiguous fields.
    # The free bilingual local filler handles every chunk. Set false to go
    # fully offline / zero-cost (local fill only).
    llm_final_extract: bool = True

    database_url: str = "sqlite:///" + str((PROJECT_ROOT / "scribe.db").as_posix())
    ws_host: str = "0.0.0.0"
    ws_port: int = 8765
    audio_delete_after_transcribe: bool = True

    sample_rate: int = 16000
    max_chunk_duration_ms: int = 15000

    # Local faster-whisper fallback
    use_local_fallback: bool = True
    whisper_model_size: str = "small"
    whisper_device: str = "cpu"
    whisper_compute_type: str = "int8"
    whisper_low_quality_threshold: float = -1.0
    min_chunk_ms_for_whisper: int = 1000
    min_chunk_ms_for_cloud: int = 800

    # Whisper confidence gating (providers that return metrics, e.g. local
    # faster-whisper). A chunk is REJECTED as silence when no_speech_prob
    # exceeds this; dropped below avg_logprob_floor.
    no_speech_prob_threshold: float = 0.6
    avg_logprob_tentative: float = -1.0
    avg_logprob_floor: float = -1.5
    compression_ratio_threshold: float = 2.4

    # Server-side speech gate (works for all providers, incl. Groq which does
    # not expose no_speech_prob): a chunk whose RMS voice level is below this
    # but which still produced "text" is almost certainly a hallucination on
    # digital silence. Kept low so quiet-but-real speech is never dropped.
    min_pcm_level_for_speech: float = 0.004

    # Per-chunk prompt carry: prepend tail of previous accepted transcript and
    # append the Hindi maternity domain vocabulary last (Whisper bias).
    prompt_tail_characters: int = 600
    # Groq rejects prompts longer than 896 characters; cap well below that.
    prompt_max_characters: int = 800
    hi_prompt_terms: str = (
        "इस केस शीट में ये शब्द आते हैं: नाम, पति, पता, ब्लॉक, जिला, "
        "आधार कार्ड, मोबाइल नंबर, गर्भावस्था, एमसीटीएस नंबर, आरसीएच नंबर, "
        "एलएमपी, एएनसी जांच, प्रसव पीड़ा, सामान्य प्रसव, सीज़ेरियन, "
        "जुड़वा बच्चा, गर्भपात, प्री-टर्म, शिशु का वजन, बीसीजी, टीकाकरण, "
        "रेफर, डिस्चार्ज"
    )

    # AI4Bharat IndicConformer (local Maithili ASR, MIT licensed)
    use_indic_conformer: bool = True
    indic_maithili_model: str = "ai4bharat/indicconformer_stt_mai_hybrid_ctc_rnnt_large"
    min_chunk_ms_for_local_indic: int = 1000

    model_config = {
        "env_file": str(ENV_FILE) if ENV_FILE.exists() else None,
        "extra": "ignore",
    }


settings = Settings()
