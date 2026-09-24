# Codemap Index

**Last Updated:** 2026-09-23

Architecture maps for **Ambient Clinical AI Scribe for Maternal Health** — bilingual
(Hindi/English) ambient scribe for L1 PHC maternity case sheets (State Health Society, Bihar).

## Entry Points

| Entry | File | Purpose |
|-------|------|---------|
| Backend app | `backend/main.py` | FastAPI app, REST + WebSocket endpoints |
| Backend WS handlers | `backend/ws/handler.py` | `/ws/chunks` + `/ws/dashboard` session logic |
| Web dashboard | `web/src/App.jsx` | Health-worker dashboard UI, browser mic mode |
| Capture agent | `capture-agent/main.py` | Standalone mic → VAD → chunk streaming client |
| Schema (source of truth) | `backend/form_schema.py` | Bilingual case-sheet schema (mirrored in `web/src/formSchema.js`) |
| Tests | `backend/integration_test.py`, `test_qa_live.py`, `test_e2e_live.py`, `test_groq_live.py`, `test_bhashini.py` | One-shot verification / live demos |

## Architecture

```
┌─────────────────────┐    PCM chunks (16k mono int16)     ┌────────────────────────────────────────┐
│  capture-agent/     │ ─────────────────────────────────▶ │  backend/  FastAPI :8765                │
│  main.py            │   /ws/chunks (session_start,       │  ─ ws/handler.py ChunkSession           │
│  recorder→denoise→  │    audio chunks, finalize)         │    ASR chain: Groq → Sarvam → Bhashini  │
│  VAD→streamer       │                                    │    → IndicConformer → local whisper     │
└─────────────────────┘                                    │    └─ per chunk: local_fill() (free)    │
                                                           │    └─ finalize: GeminiExtractor (once)  │
┌─────────────────────┐                                    │    └─ MergeEngine → validate → persist   │
│  web/  React :3000  │ ◀─────── live broadcasts ──────── │  ─ /ws/dashboard (mic_start/mic_stop/   │
│  App.jsx            │  session_state/snapshot/chunk_    │    confirm_field; session_state/snapshot/│
│  CaseSheetForm      │  result/field_confirmed/finalize_ │    chunk_result/field_confirmed/... )    │
│  useBrowserMic      │  result/voice_activity/capture_   │                                          │
│                     │  status                           │   ─ db/connection.py → SQLite scribe.db │
└─────────────────────┘                                    └────────────────────────────────────────┘

backend/form_schema.py (40 fields, 5 sections) = single source of truth
   ↳ build_schema_prompt_text() → GeminiExtractor prompt
   ↳ web/src/formSchema.js (offline mirror, fetched /api/schema at boot)
```

## Codemap Areas

| File | Covers |
|------|--------|
| [backend.md](backend.md) | backend package modules, ASR provider chain, WS protocol message shapes, local_fill + Gemini extraction pipeline, settings |
| [database.md](database.md) | SQLAlchemy models, tables, persistence + idempotent finalize flow |
| [frontend.md](frontend.md) | web source tree, message handlers, schema mirror, brand palette |
| [capture-agent.md](capture-agent.md) | mic capture pipeline, VAD, denoiser, streaming, dependencies, usage |

## Key Facts

- **Only working Python:** `backend\venv\Scripts\python.exe` (Python 3.14.7, venv under `backend/`).
- **Ports:** backend 8765 (127.0.0.1), web dashboard 3000.
- **Model gating for cost:** every chunk → `local_fill()` (free); ONE Gemini call per patient at
  finalize (`settings.llm_final_extract`) for ambiguous leftovers.
- **Installed keys:** `GROQ_API_KEY` (working), `GEMINI_API_KEY` (real, free tier 20 req/day — rotate
  if it leaked). Sarvam/Bhashini empty. NeMo not installed → IndicConformer degrades gracefully.
- **Git history style:** terse lowercase messages ("correcting mic problem", "adding more fields").

## Related Docs

- [docs/GUIDES/local-run.md](../GUIDES/local-run.md) — run/usage how-to + Windows cheat-sheet.
- [README.md](../../README.md) — project overview + quick start.