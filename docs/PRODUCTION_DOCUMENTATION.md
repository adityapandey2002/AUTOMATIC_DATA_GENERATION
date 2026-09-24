# Ambient Clinical AI Scribe — Production Documentation Report

**Repository:** `C:\Users\ADITYA\Downloads\AUTOMATIC_REPORT`
**Generated:** 2026-09-24 · Dual-agent analysis (code-reviewer + architect), read-only
**Git:** `main`, 4 commits (`f97ebf6 first commit` → `6a79243 correcting mic problem`); 13 modified files + untracked `docs/` at analysis time

---

## Table of Contents

1. [Project Overview and Scope](#1-project-overview-and-scope)
2. [System Architecture and Data Flow](#2-system-architecture-and-data-flow)
3. [Technology Stack](#3-technology-stack)
4. [Quality Assurance and Automation](#4-quality-assurance-and-automation)
5. [Deployment and DevOps](#5-deployment-and-devops)
6. [Operations and Maintenance](#6-operations-and-maintenance)

---

## 1. Project Overview and Scope

**Product:** Bilingual (Hindi/English) ambient clinical AI scribe for L1 PHC maternity case sheets ("Maternity Services Case Sheet", State Health Society, Bihar). A health worker (GNM/ANM) records a Q&A conversation with a pregnant woman; the system transcribes in real time, auto-fills official case-sheet fields, raises clinical risk alerts, and lets the worker confirm each field before it locks (`README.md:1-11`).

**Components:**

| Area | Path | Role |
|------|------|------|
| Backend | `backend/` | FastAPI + WebSockets on `:8765`; ASR chain, free local filler, 1 Gemini call/patient, SQLAlchemy persistence |
| Web dashboard | `web/` | React 19 + Vite 6 + Tailwind bilingual dashboard on `:3000`, browser-mic mode |
| Capture agent | `capture-agent/` | Standalone mic client: record → denoise → Silero VAD → stream PCM |
| Deploy | `deploy/` | docker-compose (postgres + backend + nginx web) + Windows laptop installer |
| Docs | `docs/` | `ARCHITECTURE.md` + `CODEMAPS/*` + `GUIDES/local-run.md` (untracked in git) |

**Main features / entities:**

- **Live ambient transcription** — two capture paths (standalone agent / browser mic) → `/ws/chunks` → ASR provider chain → gated transcript
- **Auto-filled case sheet** — 40 fields / 5 sections (registration 5, personal 10, admission 13, delivery 7, outcome 5); source of truth `backend/form_schema.py`
- **Free-first extraction** — deterministic bilingual regex (`engine/local_fill.py`) on every chunk; Gemini once per patient at finalize (free tier = 20 req/day)
- **Human-in-the-loop confirm locks** — worker confirms fields; confirmed fields immutable (`merge.py:71-72`)
- **Clinical risk validation** — `engine/validate.py` bilingual alerts (age/weight ranges, critical keywords, complication/preterm/death flags)
- **Persistence + DPDP audit** — SQLite/Postgres encounter records; `AudioDeletionLog` rows
- **FHIR R4** — explicit stub for Phase 2 (`backend/fhir/mapper.py:1`), not wired
- **Speaker diarization** — not implemented (`speaker="mixed"`, `handler.py:312`)

**Design invariants** (`README.md:79-91`): free-first; silence/hallucination gating; worker is source of truth; idempotent persistence.

**Out of scope / stubbed:** FHIR reporting, diarization, multi-encounter concurrency, authentication.

---

## 2. System Architecture and Data Flow

### 2.1 High-level architecture

```
┌─ Capture layer ──────────┐   PCM JSON over WS   ┌─ Backend (FastAPI :8765) ───────────────┐
│ capture-agent/main.py    │ ───────────────────▶ │ main.py routes                          │
│  recorder→denoise→VAD→   │   /ws/chunks         │  ws/handler.py ChunkSession             │
│  streamer                │                      │   ASR chain → gates → local_fill →      │
│ web/src useBrowserMic.js │                      │   MergeEngine → validate → (finalize:   │
│  (browser as 2nd mic)    │                      │   1× Gemini) → _persist                 │
└──────────────────────────┘                      └───────────────┬──────────────────────────┘
┌─ Web dashboard (:3000) ──┐   /ws/dashboard      ┌───────────────▼──────────────────────────┐
│ App.jsx + CaseSheetForm  │ ◀──────────────────▶ │ SQLite scribe.db (6 tables)             │
│  confirm_field/mic_start │   broadcasts         │  or PostgreSQL via docker-compose       │
└──────────────────────────┘                      └──────────────────────────────────────────┘
```

Two capture paths converge on `/ws/chunks`; the dashboard holds `/ws/dashboard` for control + broadcasts. Every `chunk_result`/`finalize_result` goes to the requesting chunks socket AND broadcasts to dashboards (`handler.py:430-431, 391-392`).

### 2.2 Backend routes — `backend/main.py`

| Route | Method | Definition | Purpose |
|-------|--------|-----------|---------|
| `/health` | GET | `main.py:47-49` | `{"status": "ok"}` |
| `/api/schema` | GET | `main.py:52-54` | serves `FORM_SCHEMA` (web fetches at boot, `App.jsx:47-52`) |
| `/ws/chunks` | WS | `main.py:57-59` → `handler.py:374` | audio chunks + extraction results |
| `/ws/dashboard` | WS | `main.py:62-64` → `handler.py:445` | worker commands + live broadcasts |

- App: `title="Ambient Clinical AI Scribe"`, `version="0.1.0"`, lifespan `init_db()` (`main.py:23-36`)
- CORS: `allow_origins=["*"]` WITH `allow_credentials=True` (`main.py:38-44`) — High risk
- Uvicorn: `uvicorn.run(..., reload=True)` (`main.py:67-74`)

**WS protocol:**

- Client → `/ws/chunks`: `session_start {encounter_id}`, audio chunk `{chunk_id, pcm_b64, duration_ms, language, ...}`, `finalize {encounter_id}` (`handler.py:388-415`)
- Client → `/ws/dashboard`: `mic_start`, `mic_stop`, `confirm_field {field}` (`handler.py:474-499`)
- Server → both: `chunk_result`, `finalize_result`, `session_state`, `snapshot`, `field_confirmed`, `voice_activity`, `capture_status`

### 2.3 Database ERD — `backend/db/models.py` (6 tables)

```
encounters (id UUID-str PK, created_at, clinic_id, language_detected,
            status active|finalized|confirmed, consent_given)
   │ 1
   ├── 0..1 patients (id PK, encounter_id FK NOT NULL, name, age, language)
   ├── 0..N utterances (id PK, encounter_id FK, chunk_id,
   │                    speaker patient|gnm|unknown, transcript,
   │                    language, confidence, timestamp)
   ├── 0..N vitals_snapshots (id PK, encounter_id FK, timestamp,
   │                    data JSON {answers, _confirmed}, confirmed)
   ├── 0..N alerts (id PK, encounter_id FK, timestamp, field,
   │                message, severity warning|critical, acknowledged)
   └── 0..N audio_deletion_log (id PK, encounter_id FK,
                        chunk_ids JSON, deleted_at,
                        deletion_reason default "transcribe_complete")
```

- Connection: `create_engine(settings.database_url, pool_pre_ping=True)`; `init_db()` → `Base.metadata.create_all()` — **no Alembic migrations** (`db/connection.py:12-17`)
- Default DB: `sqlite:///<project_root>/scribe.db` (`config.py:28`); compose overrides to Postgres
- **Idempotent persist** (`handler.py:299-334`): delete children by `encounter_id` + `Encounter` by `id` → insert fresh → single commit

### 2.4 Data-flow pipeline

**Per-chunk (live, zero LLM cost)** — `process_chunk()` (`handler.py:122-258`):

```
PCM chunk → pre-ASR RMS gate (<0.004 → reject, no cloud call)
  → provider order by language (mai/mag/bho/vajjika → Indic first;
     else Groq first) → first non-empty text wins
  → post-ASR gate: no_speech_prob>0.6 ✗ | rms<0.004 ✗ |
     compression_ratio>2.4 ✗ | avg_logprob<-1.5 ✗
  → boundary dedupe (Whisper overlap word)
  → transcript_buffer += chunk
  → local_fill(full)          ← FREE bilingual regex
  → MergeEngine.merge         ← latest-wins, confirmed locked
  → validate_case_sheet       ← clinical alerts
  → chunk_result → chunks socket + broadcast → dashboard
```

**Finalize (one LLM call per patient)** — `finalize()` (`handler.py:260-294`):

```
local_fill(full) FIRST (free, catches cross-chunk answers)
  → if llm_final_extract && non-empty:
      GeminiExtractor.extract(full)   ← ONE call, temp=0, JSON mime
        self-heal: 429-PerDay → block model/day → next fallback
        (3.6-flash → 3.7-flash → 3.5-flash-lite); 403/404 → permanent
        any exception → local fill survives
  → merge (confirmed still protected) → validate
  → _persist (idempotent delete-then-insert)
  → optional log_deletion (DPDP audit)
  → finalize_result → chunks socket + broadcast
```

**Module responsibilities:**

| Module | Lines | Responsibility |
|--------|-------|----------------|
| `engine/local_fill.py` | 421 | Bilingual regex; `BD = r"(?=\s|[.?,।;]|$)"` Devanagari boundary (L18; `\b` fails after matras); Hindi digits/words/months; last-match-wins; polarity Yes/No (`yesno_after:323-338`); script-fidelity gate (Devanagari ratio <0.35 → `{}`, L175-200) |
| `engine/merge.py` | 96 | `FieldState(value, source_chunk_id, confirmed)`; latest non-empty wins; confirmed skipped (L62-76); `confirm()` locks (78-83) |
| `engine/validate.py` | 116 | `NUMERIC_RANGES` age 10-65, wt 0.4-8.0 (L15-18); bilingual `CRITICAL_KEYWORDS` (L21-26); low-birth-weight <2.5kg, complication/preterm/referral/death flags |
| `llm/extract.py` | 313 | 9-rule prompt + schema + transcript (L26-48); temp=0, JSON mime, 2048 tokens, 30s timeout (L156-168); failover (L59-63); 429 in-memory block (L66,126-131); 403/404 permanent (L68-69,218-219) |

### 2.5 Third-party API integrations (initialized in code)

| Integration | Module + init | Status |
|---|---|---|
| **Groq ASR** (Whisper large-v3) | `ws/groq_asr.py:52-55`; POST `api.groq.com/openai/v1/audio/transcriptions` via httpx 45s (L25,86,106) | ✅ Working — free, ~2000 req/day |
| **Google Gemini LLM** | `llm/extract.py`: `google.genai.Client(api_key=...)` (L142); `client.aio.models.generate_content` (L195) | ✅ Working, throttled — 20 req/day; `LLM_MODEL=gemini-3.5-flash` required (1.5-flash retired) |
| **Sarvam AI (Saaras v3)** | `ws/sarvam_asr.py:47`; POST `api.sarvam.ai/speech-to-text` (L19) | ⚠️ Placeholder — key empty → instant skip |
| **Bhashini Dhruva** | `ws/bhashini_asr.py:60-63`; POST `dhruva-api.bhashini.gov.in/.../pipeline` (L30) | ⚠️ Placeholder — key + User-ID empty |
| **AI4Bharat IndicConformer (NeMo)** | `ws/indicconformer_asr.py:74` behind `_nemo_available()` (L54-60); model `ai4bharat/indicconformer_stt_mai_hybrid_ctc_rnnt_large` (L28) | ❌ Inert — NeMo lacks Python 3.14 support (venv 3.14.7); chain falls through |
| **faster-whisper local** | `ws/local_asr.py:40-55` lazy `WhisperModel` (small/cpu/int8), thread-locked | ✅ Enabled — offline fallback |
| **Silero VAD** | `capture-agent/vad.py:46-51` `torch.hub.load("snakers4/silero-vad")` | ✅ Installed — 6.2.2; 512-sample frames |
| **DeepFilterNet denoiser** | `capture-agent/denoise.py:19-29` try-import `df.enhance` | ⚠️ Not in requirements — degrades to no-op |
| **edge-tts / soundfile** | Test-audio tooling only | In venv; undeclared in requirements.txt |
| **FHIR R4** | `backend/fhir/mapper.py` pure dict mappers | 🚧 Stub Phase 2, not wired |

**Effective runtime ASR chain today:** Groq(`whisper-large-v3`) → LocalWhisper(`small/int8`). Legacy `google_generativeai-0.8.6` still installed alongside `google_genai-2.24.0` (FutureWarning in `uvicorn.err.log`).

---

## 3. Technology Stack

### 3.1 Declared dependencies

**`backend/requirements.txt`** (ranges, no pins): `fastapi>=0.115,<1.0` · `uvicorn[standard]>=0.30` · `websockets>=13.0` · `sqlalchemy>=2.0` · `asyncpg>=0.30` · `psycopg2-binary>=2.9` · `pydantic>=2.0` · `pydantic-settings>=2.0` · `google-genai>=1.0` · `httpx>=0.27` · `python-dotenv>=1.0` · `faster-whisper>=1.0`

**`backend/requirements-nemo.txt`:** `nemo_toolkit[asr]>=1.23` (optional, ~3+ GB, "may not support Python 3.14") — not installed

**`capture-agent/requirements.txt`:** `sounddevice==0.5.1` (only exact pin in repo) · `numpy>=1.24` · `silero-vad>=5.1` · `torch>=2.0` · `torchaudio>=2.0` · `websocket-client>=1.8` · `pydantic>=2.0` · `psutil>=5.9`

**`web/package.json`:** deps `react ^19.0.0`, `react-dom ^19.0.0`; devDeps `@vitejs/plugin-react ^4.3`, `autoprefixer ^10.4`, `postcss ^8.4`, `tailwindcss ^3.4`, `vite ^6.0`; scripts `dev`/`build`/`preview` only — **no test script**

No `Pipfile`, `pyproject.toml`, or `go.mod` anywhere (glob-verified).

### 3.2 Resolved frontend versions (`web/package-lock.json`)

| Package | Version |
|---|---|
| react / react-dom | **19.2.8** |
| vite | **6.4.3** |
| @vitejs/plugin-react | 4.7.0 |
| tailwindcss | **3.4.19** |
| postcss / autoprefixer | 8.5.28 / 10.5.4 |
| esbuild / rollup | 0.25.12 / 4.63.1 |

State management: none beyond React hooks + raw WebSocket/`fetch` (no Redux/Zustand/TanStack). Styling: Tailwind 3, custom `brand` teal palette, no CSS-in-JS.

### 3.3 Resolved backend versions (`backend/venv`, Python **3.14.7**)

| Package | Version | Package | Version |
|---|---|---|---|
| fastapi | 0.141.1 | google_genai | 2.24.0 |
| starlette | 1.6.0 | google_generativeai (legacy) | 0.8.6 |
| uvicorn | 0.52.4 | httpx | 0.28.1 |
| websockets | 16.1.1 | faster_whisper | 1.2.1 |
| sqlalchemy | 2.0.52 | numpy | 2.5.2 |
| pydantic | 2.13.5 | torch / torchaudio | 2.9.1 / 2.9.1 |
| pydantic_settings | 2.15.0 | silero_vad | 6.2.2 |
| asyncpg / psycopg2_binary | 0.31.0 / 2.9.12 | sounddevice / soundfile | 0.5.1 / 0.14.0 |
| python_dotenv | 1.2.3 | edge_tts / psutil | 7.2.8 / 7.2.2 |

**Not installed:** `nemo_toolkit`, `deepfilternet`/`df`, `scipy`.

### 3.4 Database & ORM

- ORM: SQLAlchemy 2.0 (declarative, `relationship(back_populates=...)`)
- Database: SQLite (dev default `scribe.db`) / PostgreSQL 16-alpine (compose)
- Migrations: **none** — `Base.metadata.create_all()` at startup (no Alembic)

### 3.5 Runtime/container targets

| Target | Base image |
|---|---|
| Backend Docker | `python:3.12-slim` (**differs from dev Python 3.14.7**) |
| Web build/runtime | `node:22-alpine` → `nginx:alpine` |
| Compose DB | `postgres:16-alpine` |
| Ports | backend **8765**, web dev **3000** |

---

## 4. Quality Assurance and Automation

### 4.1 Test inventory

All test scripts live in `backend/` (no `tests/` dir anywhere):

| Script | Type | Assertions | Notes |
|---|---|---|---|
| `backend/integration_test.py` | Offline suite | **7 asserts** | 3 scenarios: local fill field coverage, merge latest-wins + confirm lock, validate alerts. Prints `PASS`/`FAIL`. Timeout = soft PASS if Gemini skipped. |
| `backend/test_qa_live.py` | Live e2e | **0 asserts** (prints) | Two-voice Hindi Q&A audio ? Groq ? local fill ? checks 8 answers + finalize_result identity + empty alerts |
| `backend/test_e2e_live.py` | Live e2e | 0 asserts | Encodes/streams mock audio over WS |
| `backend/test_groq_live.py` | Live smoke | 0 asserts | Direct Groq transcription check |
| `backend/test_bhashini.py` | Live smoke | 0 asserts | Bhashini API (skips if no key) |

### 4.2 Coverage gaps

- **No unit tests** for `local_fill`, `merge`, `validate` beyond the integration smoke
- **No frontend tests** � `web/package.json` has no `test` script; no vitest/jest/playwright
- **No CI/CD** � no `.github/workflows`, no azure-pipelines, no Jenkinsfile (glob-verified)
- **No linters/formatters/type-checkers** � no ruff, black, flake8, mypy, eslint, prettier configs
- **No pre-commit**, no coverage tooling
- No tests for: WS handler branches, DB idempotent persist, Gemini 429 failover, capture agent VAD, browser mic path

### 4.3 How tests are run (current, manual)

```powershell
# from backend/
venv\Scripts\python.exe integration_test.py        # offline, 7 asserts
venv\Scripts\python.exe test_qa_live.py            # needs GROQ_API_KEY + non-empty transcript
```

No single aggregate runner (`pytest` not installed).

---

## 5. Deployment and DevOps

### 5.1 Deployment assets

| Asset | Path | What it does |
|---|---|---|
| Compose stack | `deploy/docker-compose.yml` | `postgres:16-alpine` + backend (uvicorn, 8765) + web (nginx static build, 80) |
| Backend image | `deploy/backend.Dockerfile` (inferred) | `python:3.12-slim`, pip install requirements, uvicorn |
| Web image | web build ? `nginx:alpine` | Vite build output served as static |
| Windows installer | `deploy/scripts/install-laptop.bat` | Laptop deployment helper |
| Env template | `.env.example` | `GROQ_API_KEY`, `GEMINI_API_KEY`, `LLM_MODEL`, `LLM_FINAL_EXTRACT`, `DATABASE_URL`, `GROQ_MODEL=whisper-large-v3` |
| Local run guide | `docs/GUIDES/local-run.md` | Full startup order + troubleshooting |

### 5.2 Environment & config

- `.env` loaded via `pydantic-settings` (`config.py`); secrets never committed (real keys in working `.env` only)
- Critical settings: `llm_model` (must be `gemini-3.5-flash`), `llm_final_extract` (False = fully offline), `groq_model=whisper-large-v3` (NOT `-turbo`), `database_url`
- **No secrets management** (no Vault, no AWS/GCP secret manager references)

### 5.3 CI/CD pipeline

**None.** No pipeline definition exists in the repository. Every build, test, and deploy step is manual:

1. Backend: `venv\Scripts\python.exe -m uvicorn main:app --port 8765 --host 127.0.0.1` (cwd `backend/`)
2. Web: `npm run dev` (cwd `web/`) ? http://localhost:3000
3. Compose: `docker compose -f deploy/docker-compose.yml up --build`
4. Capture agent (manual, repo root): `backend\venv\Scripts\python.exe capture-agent\main.py --language hi --encounter-id demo`

### 5.4 Version control state

- Branch: `main`, linear history, 4 commits, no remote confirmed
- Working tree at analysis: 13 modified files + untracked `docs/` (including `ARCHITECTURE.md`, `CODEMAPS/*`, this file)
- No `.gitignore` hygiene audit for venv/node_modules committed

---

## 6. Operations and Maintenance

### 6.1 Known operational constraints

| Constraint | Impact | Mitigation |
|---|---|---|
| Gemini free tier **20 req/day** | 1 finalize call/patient; per-chunk Gemini would exhaust quota | `local_fill` on every chunk; Gemini only at finalize; `llm_final_extract=False` kill-switch |
| IndicConformer inert (no NeMo on Py 3.14) | `mai/mag/bho/vajjika` lose dedicated ASR path | Falls back to Groq ? local Whisper |
| Sarvam/Bhashini keys empty | Those providers always skip | Documented placeholder status |
| Groq free tier (~2000 req/day) | High-volume clinics may throttle | Local faster-whisper fallback in chain |
| No Alembic | Schema changes require `drop_all`/manual DDL | `create_all` on boot only adds tables |
| CORS `*` + credentials, **no auth** | Any origin can open `/ws/dashboard` and confirm fields | High risk � restrict origins, add token before multi-user |
| No structured logging/APM | Incidents hard to diagnose | stderr only; no Sentry/Datadog |
| No health-based orchestration | Manual start order matters (backend ? web ? agent) | `/health` exists but unused by probes |

### 6.2 Monitoring & observability

- **Health:** `GET /health` ? `{"status":"ok"}` (`main.py:47-49`) � not wired into docker healthcheck
- **Logging:** default uvicorn/logging to stderr; detached-launch pattern redirects to log files (backend.log, etc.)
- **Alerts (clinical, not ops):** `Alert` table + `alerts` broadcast; DPDP `AudioDeletionLog` audit rows
- **No** metrics endpoint, no Prometheus, no distributed tracing, no log aggregation

### 6.3 Backup & data retention

- Dev: single file `backend/scribe.db` � must be volume-mounted in compose (Postgres has named volume)
- Audio: transients not persisted after finalize; optional `log_deletion` writes DPDP audit
- No scheduled backups, no snapshot scripts, no DR runbook

### 6.4 Security posture (summary of review findings)

| Severity | Finding | Location |
|---|---|---|
| High | No authentication on any WS/HTTP route | `main.py`, `handler.py` |
| High | CORS `allow_origins=["*"]` with `allow_credentials=True` | `main.py:38-44` |
| Medium | API keys read from `.env`; no rotation story | `config.py` |
| Medium | PII (name, phone, aadhaar, LMP) in SQLite in cleartext | `db/models.py` |
| Low | DPDP deletion logging is best-effort (exceptions swallowed) | `handler.py` finalize path |
| Info | Free-tier Gemini sees full transcript (PHI leaves device) when `LLM_FINAL_EXTRACT=True` | `llm/extract.py` |

### 6.5 Maintenance playbook (runbook essentials)

```powershell
# Status
Invoke-WebRequest http://127.0.0.1:8765/health

# Stop backend (PowerStop pattern used in session)
Get-CimInstance Win32_Process -Filter "Name='python.exe'" |
  Where-Object { $_.CommandLine -match 'uvicorn' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force }

# Stop dashboard (node vite)
Get-CimInstance Win32_Process -Filter "Name='node.exe'" |
  Where-Object { $_.CommandLine -match 'vite' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force }

# Known-good startup order (from session cheat-sheet)
# 1) backend  (cwd backend/)  : venv\Scripts\python.exe -m uvicorn main:app --port 8765 --host 127.0.0.1
# 2) web      (cwd web/)      : npm run dev  ? http://localhost:3000   (IPv6 localhost, not 127.0.0.1)
# 3) agent    (cwd repo root) : backend\venv\Scripts\python.exe capture-agent\main.py --language hi --encounter-id demo
```

**Turning Gemini off (quota safety):** set `LLM_FINAL_EXTRACT=False` in `.env` ? finalize uses local fill only.

**Schema change procedure (until Alembic):** edit `form_schema.py` + `formSchema.js` mirrors ? stop backend ? drop tables or `sqlite3 backend/scribe.db DROP ...` ? restart (`create_all`).

---

## Appendix A � Gap checklist (recommended before production)

- [ ] Add authentication (session token) + tighten CORS to dashboard origin only
- [ ] Pin backend requirements (currently unpinned ranges) and align Docker Python (3.12) with dev (3.14)
- [ ] Install/enable Alembic migrations
- [ ] Add pytest unit tests for `local_fill` (incl. Devanagari `\b` regression cases), `merge`, `validate`; convert live scripts to assert-based
- [ ] Add CI (GitHub Actions): lint (ruff/eslint) + pytest + `npm run build`
- [ ] Wire `/health` to compose healthcheck; add structured JSON logging
- [ ] PII at-rest encryption or SQLCipher; key rotation for Groq/Gemini
- [ ] Decide diarization strategy (speaker labels currently `mixed`)
- [ ] Wire FHIR mapper for Phase 2 reporting
- [ ] Production-grade audio deletion job + backup cron for Postgres

## Appendix B � Key file index

```
backend/
  main.py                 FastAPI app, routes, CORS, lifespan
  config.py               settings (llm_model, llm_final_extract, groq_model)
  form_schema.py          40-field bilingual schema (source of truth)
  ws/handler.py           ChunkSession, gates, local_fill/Gemini, _persist, broadcast
  ws/groq_asr.py          Groq Whisper ASR
  ws/sarvam_asr.py        Sarvam Saaras (placeholder)
  ws/bhashini_asr.py      Bhashini Dhruva (placeholder)
  ws/indicconformer_asr.py NeMo Indic (inert)
  ws/local_asr.py         faster-whisper fallback
  engine/local_fill.py    free bilingual regex filler
  engine/merge.py         latest-wins + confirm locks
  engine/validate.py      clinical alert rules
  llm/extract.py          Gemini extractor + 429/403/404 failover
  db/models.py            6 tables
  db/connection.py        engine + create_all
  integration_test.py     7 asserts
  test_qa_live.py         live Q&A e2e (prints)
web/
  src/App.jsx             boot, /api/schema, WS wiring
  src/formSchema.js       mirrored 40-field schema
  src/components/CaseSheetForm.jsx  live case sheet + confirm UX
  src/hooks/useBrowserMic.js        browser mic capture
capture-agent/
  main.py  vad.py  streamer.py  denoise.py
deploy/
  docker-compose.yml  scripts/install-laptop.bat
docs/
  ARCHITECTURE.md  PRODUCTION_DOCUMENTATION.md  CODEMAPS/*  GUIDES/local-run.md
```

---

*End of report. Sections marked analysis-only; run commands verified in-session 2026-09-24. Deploy topology inferred from `deploy/` assets and env templates � confirm exact Dockerfile paths if they differ.*
