# Ambient Clinical AI Scribe for Maternal Health

**Bilingual (Hindi/English) ambient scribe** for L1 Primary Health Centre maternity case sheets
(Maternity Services Case Sheet, State Health Society, Bihar). A health worker (GNM/ANM) records a
Q&A conversation with a pregnant woman; the system transcribes it in real time, auto-fills the
official case-sheet fields, flags clinical risk alerts, and lets the worker confirm each field.

```
capture-agent ──PCM chunks──▶ backend (/ws/chunks) ──live updates──▶ web dashboard (/ws/dashboard)
   (mic, VAD)                    ASR → local_fill → merge → validate      (bilingual case sheet)
```

## What's inside

| Area | Path | What it is |
|------|------|------------|
| Backend | `backend/` | FastAPI + WebSockets service (Python 3.14 venv under `backend/venv`), ASR provider chain, free local bilingual field filler, one Gemini call per patient at finalize, SQLAlchemy persistence |
| Web dashboard | `web/` | React 19 + Vite 6 + Tailwind (teal "modern clinical" palette) bilingual case-sheet dashboard, browser-mic mode, WS dashboard |
| Capture agent | `capture-agent/` | Optional client mic capture: record → denoise → Silero VAD → chunk to backend (`main.py`) |
| Deploy | `deploy/` | docker-compose (postgres + backend + nginx web) + Windows laptop installer script |

## Quick start (Windows dev)

Only working Python on this machine is the repo venv: `backend\venv\Scripts\python.exe` (Python 3.14.7).

```powershell
# 1. Backend — run dir MUST be backend/
cd backend
venv\Scripts\python.exe -m uvicorn main:app --port 8765 --host 127.0.0.1

# 2. Web dashboard (second terminal)
cd web
npm run dev            # binds localhost:3000; proxies /api and /ws → 127.0.0.1:8765
```

Open `http://localhost:3000`, press **Start Recording** and ask the patient the registration
questions. See [docs/GUIDES/local-run.md](docs/GUIDES/local-run.md) for the full run guide and
Windows cheat-sheet.

## Capture agent (optional separate mic machine)

```powershell
# From repo ROOT:
backend\venv\Scripts\python.exe capture-agent\main.py --language hi --encounter-id demo
```

## Tests

```powershell
# From backend/ (backend must be running on 127.0.0.1:8765):
venv\Scripts\python.exe integration_test.py   # 3/3 PASS (REST + WS round-trips)
venv\Scripts\python.exe test_qa_live.py       # 45s two-voice Hindi Q&A demo, prints transcript + answers + finalize
```

## Environment (.env)

`.env` is gitignored. Copy `.env.example` and fill in keys:

| Variable | Status | Notes |
|----------|--------|-------|
| `GROQ_API_KEY` / `GROQ_MODEL` | working | `whisper-large-v3` — free tier, main ASR path for Hindi |
| `GEMINI_API_KEY` / `LLM_MODEL` | working, throttled | `LLM_MODEL=gemini-3.5-flash` is **required** (gemini-1.5-flash is retired/404 on this account). Free tier = 20 req/day — hence the "Gemini once per patient" strategy |
| `SARVAM_API_KEY`, `BHASHINI_*` | empty | optional ASR providers, not currently configured |
| `DATABASE_URL` | set | `sqlite:///./scribe.db` for local dev |

> **Security:** `.env` holds live keys (`GROQ_API_KEY`, `GEMINI_API_KEY`). Rotate `GEMINI_API_KEY`
> if it ever appears in logs/tool output — it surfaced once in this session on the free tier
> (20 req/day). Never commit `.env` (it is already gitignored).

## Architecture / codemaps

- [docs/CODEMAPS/INDEX.md](docs/CODEMAPS/INDEX.md) — overview, architecture diagram, entry points
- [docs/CODEMAPS/backend.md](docs/CODEMAPS/backend.md) — backend modules, ASR chain, WS protocol, extraction pipeline
- [docs/CODEMAPS/database.md](docs/CODEMAPS/database.md) — SQLAlchemy schema, persistence/idempotency flow
- [docs/CODEMAPS/frontend.md](docs/CODEMAPS/frontend.md) — web dashboard structure and WS message handling
- [docs/CODEMAPS/capture-agent.md](docs/CODEMAPS/capture-agent.md) — mic capture pipeline and dependencies
- [docs/GUIDES/local-run.md](docs/GUIDES/local-run.md) — full run/usage/how-to-verify guide + Windows cheat-sheet

## Key design decisions

- **Free first, paid only on leftover ambiguity**: every chunk is filled by
  [`backend/engine/local_fill.py`](backend/engine/local_fill.py) — free, deterministic, bilingual
  regex/keyword extraction. Gemini (`backend/llm/extract.py`) is called **once per patient** at
  finalize for ambiguous leftovers, so the 20 req/day free-tier quota lasts all day. Set
  `llm_final_extract=false` in `.env` to go fully offline (local fill only).
- **Silence/hallucination gating**: PCM RMS + `no_speech_prob`/`avg_logprob`/`compression_ratio`
  gates keep junk off the case sheet.
- **Health worker is the source of truth**: every auto-filled field can be confirmed via the
  dashboard (`confirm_field`); confirmed fields are never overwritten.
- **Idempotent persistence**: a repeated `finalize` for the same `encounter_id` replaces old rows
  instead of crashing on the `encounters.id` UNIQUE constraint.