# Backend Codemap

**Last Updated:** 2026-09-23

FastAPI + WebSockets service. Bilingual Hindi/English ambient scribe backend.
Runs from `backend/` dir with `backend/venv` (Python 3.14.7).

## Entry Points

| File | Purpose |
|------|---------|
| `backend/main.py` | FastAPI app (`title="Ambient Clinical AI Scribe"`, v0.1.0), CORS `*`, lifespan `init_db()` |
| `backend/ws/handler.py` | The core: `ChunkSession`, `/ws/chunks`, `/ws/dashboard`, broadcasts, persistence |
| `backend/engine/local_fill.py` | Free deterministic bilingual field filler (runs every chunk) |
| `backend/form_schema.py` | Bilingual case-sheet schema, single source of truth (40 fields, 5 sections) |

## HTTP / WS Routes

| Route | Method | Handler | Purpose |
|-------|--------|---------|---------|
| `/health` | GET | `health()` | `{"status": "ok"}` |
| `/api/schema` | GET | `schema()` | Servers `FORM_SCHEMA` (the web fetches this at boot) |
| `/ws/chunks` | WS | `ws_chunks_handler()` | Capture agent/audio streaming, live extraction + broadcast |
| `/ws/dashboard` | WS | `ws_dashboard_handler()` | Health-worker dashboard: control + live updates |

## WS Protocol (message shapes)

### Chunks socket → backend (`/ws/chunks`)

| type | payload | effect |
|------|---------|--------|
| `session_start` | `{encounter_id}` | reset + activate session |
| (implicit) | `{chunk_id, pcm_b64, duration_ms, language, ...}` | first chunk auto-starts session |
| `finalize` | `{encounter_id}` | run local_fill + Gemini once, persist, respond + broadcast |

Messages are JSON. A `chunk_id` / `pcm_b64` payload (capture agent sends these) is a chunk.

### Backend → chunks socket (and → dashboard)

Every `chunk_result` / `finalize_result` **is now sent back to the requesting chunks socket**
(added so test scripts / capture agent get results) **and** broadcast to dashboard clients.

| type | keys | notes |
|------|------|-------|
| `chunk_result` | `chunk_id, encounter_id, transcript, status, confidence, provider, speaker, language, answers, confirmed, alerts` | also `voice_level`, `vad` appended in handler |
| `finalize_result` | `encounter_id, transcript, answers, confirmed, alerts` | result of finalize (persisted) |
| `session_state` | `active, encounter_id` | session state broadcasts |
| `snapshot` | `answers, confirmed, transcript` | sent to new dashboard conn |
| `field_confirmed` | `field` | broadcast after confirm_field |
| `voice_activity` | `level, encounter_id` | seen by dashboard |
| `capture_status` | `connected` | whether capture client connected |

### Dashboard socket → backend (`/ws/dashboard`)

| type | payload | effect |
|------|---------|--------|
| `mic_start` | `{encounter_id}` | activate `ChunkSession` |
| `mic_stop` | — | `finalize()` this session, broadcast results |
| `confirm_field` | `{field}` | lock field (MergeEngine.confirm) |

`broadcast_to_dashboard()` is wired to ALL broadcasts (was defined-but-dead; now used).

## ASR Provider Chain (`ws/`)

Provider order in `ChunkSession._provider_order()`:
- if language is IndicConformer-supported (`mai`/`mag`/`bho`/`vajjika`):
  `IndicConformer → Groq → Sarvam → Bhashini → local whisper`
- otherwise: `Groq → Sarvam → Bhashini → IndicConformer → local whisper`

| Provider | File | Config | Notes |
|----------|------|--------|-------|
| Groq | `ws/groq_asr.py` | `groq_api_key`, `groq_model` (=whisper-large-v3 in `.env`) | main working ASR for Hindi (free tier); maps mai/mag/bho→hi |
| Sarvam | `ws/sarvam_asr.py` | `sarvam_api_key` (empty in `.env`) | saaras:v3, LANG_MAP to IN codes |
| Bhashini | `ws/bhashini_asr.py` | `bhashini_api_key` (empty) | gov API, conformer service IDs |
| IndicConformer | `ws/indicconformer_asr.py` | `use_indic_conformer`, `indic_maithili_model` | NeMo toolkit NOT installed → degrades gracefully (falls through) |
| Local whisper | `ws/local_asr.py` | `use_local_fallback`, `whisper_model_size` | faster-whisper small/int8/cpu |

Audio gating in `_gate_result()`: silence rejection via `no_speech_prob` or server-side PCM RMS
(`min_pcm_level_for_speech`); hallucination via `avg_logprob`/`compression_ratio`. Prompt carry:
`_prompt_context()` prepends transcript tail (600 chars) + Hindi domain terms, capped at 800 chars
(under Groq's 896 limit) for `hi`.

## Extraction Pipeline

```
process_chunk()  → ASR (provider chain) → gate → dedupe boundary → local_fill(full_transcript)
                   → MergeEngine.merge(filled) → snapshot → validate_case_sheet → chunk_result
finalize()       → local_fill(full_transcript)  (free, always first)
                   → if settings.llm_final_extract: GeminiExtractor.extract() ONCE (try/except, 429 → local fill kept)
                   → merge → validate → _persist() (idempotent) → finalize_result
```

### `engine/local_fill.py` — free bilingual field filler

Regex/keyword extraction, Devanagari + English. Returns `{field_key: value}`, skips `None`/`""`/`[]`.

Key quirks (documented in module docstring):
- **Devanagari matras are non-word chars** → `\b` FAILS after `है` etc. Uses boundary lookahead
  `BD = r"(?=\s|[.?,।;]|$)"`.
- **Answers usually come AFTER questions** → last-match-wins (`_last`, `_answer_number`, `_answer_name`).
- **Polarity-aware Yes/No**: tracks last Y/N event; `ना + verb` (e.g. "नहीं हुई") → No.
- Extracts fields: `name` (skips पति/पती contexts), `spouse_parent_of`, `age` (Hindi words +
  Devanagari digits via `_to_int`), `block`, `district`, `village`→`address`, `contact_phone`
  (10-digit leading 6–9), `aadhaar_number` (12-digit), `asha_name`, `health_centre`, `lmp`
  (day + Hindi month name → `2026-MM-DD` or LMP `dd/mm/yyyy`), `anc_checkup_done` (Yes/No),
  `anc_visits` (last "N बार"), `pregnancy_complication` (only جटिलत/परेशानी wording, NOT from "जांच"),
  `delivery_mode` ("सामान्य प्रसव"→Normal, caesarean variants), `delivery_outcome`
  (जीवित→Live birth / स्टिल बर्थ→Stillbirth), `baby_sex`, `birth_weight_kg`, `preterm`,
  `babies_count` (जुड़वा→Twin), `immunization` list, `marital_status`, `referred_from`.
- Script-fidelity gate: mostly-Latin transcript (Devanagari ratio < 0.35) → no fill (avoids
  poisoning with Latin/Hinglish mismatches).

### `engine/merge.py` — MergeEngine / CaseSheetFields
Flat `{key: FieldState(value, source_chunk_id, confirmed)}`. Latest non-empty value wins unless
confirmed (locked). `get_snapshot()` → `{"answers": {...}, "_confirmed": {...}}`.

### `engine/validate.py` — validation alerts
`validate_case_sheet(snapshot)` → `[ValidationAlert(field, message, severity)]`.
Ranges: `age` 10–65, `birth_weight_kg` 0.4–8.0 (and <2.5 → low-birth-weight). Critical keywords
list (bilingual). Flags complication/preterm/referred-from/diagnosis keywords/death/referral outcomes.

### `llm/extract.py` — GeminiExtractor (one call per patient)
- Prompt via `build_schema_prompt_text()`; JSON output; temp 0; timeouts; AFC disabled.
- Model = `settings.llm_model` (`gemini-3.5-flash` REQUIRED — 1.5-flash retired/404).
- Retry/backoff logic; daily-quota (429 PerDay) → mark model blocked, fail over to
  `gemini-3.6-flash`, `gemini-3.7-flash`, `gemini-3.5-flash-lite`. 403/404 → permanently unavailable.
- Exceptions in `finalize()` are caught → **local fill kept**.

## Settings (`backend/config.py`, loaded from repo-root `.env`)

| Setting | Default | Notes |
|---------|---------|-------|
| `groq_model` | `whisper-large-v3` | in `.env` |
| `llm_model` | `gemini-3.5-flash` | REQUIRED, in `.env` |
| `llm_final_extract` | `True` | **NEW** — Gemini finalize toggle; False = fully offline/local-fill-only |
| `database_url` | `sqlite:///.../scribe.db` | `.env` sets `sqlite:///./scribe.db` |
| `ws_host` / `ws_port` | `0.0.0.0` / `8765` | — |
| `audio_delete_after_transcribe` | `True` | logs AudioDeletionLog after finalize |
| `use_indic_conformer` | `True` | IndicConformer adapter on (NeMo absent → graceful fallback) |
| `indic_maithili_model` | ai4bharat/..._hybrid_ctc_rnnt_large | — |
| `min_chunk_ms_for_local_indic` | `1000` | — |
| `use_local_fallback` | `True` | faster-whisper fallback |
| `gemini_api_key` / `groq_api_key` | — | real keys in `.env` (rotate GEMINI key if leaked) |

## Dependencies (`backend/requirements.txt`)
`fastapi`, `uvicorn[standard]`, `websockets`, `sqlalchemy`, `asyncpg`, `psycopg2-binary`,
`pydantic`, `pydantic-settings`, `google-genai` (>=1.0, switched from google-generativeai),
`httpx`, `python-dotenv`, `faster-whisper`. Optional `requirements-nemo.txt` for NeMo/IndicConformer
(NOT installed; NeMo doesn't yet support Python 3.14).

## Tests (in `backend/`)

- `integration_test.py` — one-shot REST `/health` + `/api/schema` + dashboard mic round-trip +
  chunks round-trip; run `venv\Scripts\python.exe integration_test.py` (3/3 PASS).
- `test_qa_live.py` — sends ~45s two-voice Hindi Q&A audio (`qa_gnm.mp3` + `qa_patient.mp3` from
  `%TEMP%\opencode`) through `/ws/chunks`; prints transcript + live answers + finalize + alerts.
- `test_e2e_live.py` — older; expects `answers`/`confirmed` keys on `chunk_result`.
- `test_groq_live.py` — direct `GroqWhisperASR` probe.
- `test_bhashini.py` — requires BHASHINI keys.

## Related Areas

- [database.md](database.md)
- [frontend.md](frontend.md)
- [capture-agent.md](capture-agent.md)
- [docs/GUIDES/local-run.md](../GUIDES/local-run.md)