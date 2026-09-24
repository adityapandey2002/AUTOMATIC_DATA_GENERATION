# Ambient Clinical AI Scribe — Architecture Document

**Project:** Ambient Clinical AI Scribe for Maternal Health
**Domain:** Bilingual (Hindi/English) ambient scribe for Bihar L1 PHC maternity case sheets
("Maternity Services Case Sheet", State Health Society, Bihar)
**Stack:** `backend/` = FastAPI + WebSockets + SQLAlchemy/SQLite (`:8765`) · `web/` = React + Vite (`:3000`) · `capture-agent/` = standalone mic recorder (Python)
**Schema:** 40 fields / 5 sections — single source of truth = `backend/form_schema.py`

---

## Table of Contents

1. [Big-Picture Layered View](#1-big-picture-layered-view)
2. [Model Inventory](#2-model-inventory)
3. [Transcription & Analysis Pipeline](#3-transcription--analysis-pipeline)
   - [3A. Live per-chunk mode](#3a-live-per-chunk-mode-zero-llm-cost)
   - [3B. Finalize mode](#3b-finalize-mode-one-llm-call-per-patient)
4. [Key Design Trade-Offs](#4-key-design-trade-offs)
5. [Full Encounter Sequence Diagram](#5-full-encounter-sequence-diagram)
6. [Data Model / Schema](#6-data-model--schema)
7. [Case Sheet Schema (40 fields / 5 sections)](#7-case-sheet-schema-40-fields--5-sections)
8. [WS Message Protocol](#8-websocket-message-protocol)
9. [Architectural Risks & Gaps](#9-architectural-risks--gaps)
10. [Run & Management Cheat-Sheet](#10-run--management-cheat-sheet)

---

## 1. Big-Picture Layered View

```
┌────────────────────────────┐      ┌─────────────────────────────────────────────────────┐
│ ① DEVICE / CAPTURE LAYER   │      │ ② TRANSPORT (FastAPI :8765, main.py)                │
│                            │      │  REST: /health · /api/schema (serves FORM_SCHEMA)   │
│ capture-agent/             │ ───▶ │  WS:  /ws/chunks    ← audio framing + results      │
│  recorder(16k stereo f32)  │ PCM  │  WS:  /ws/dashboard ← mic_start/mic_stop/           │
│  → to_mono → denoise       │ JSON │           confirm_field + all live broadcasts       │
│  → Silero VAD → streamer   │      │        (handler.py:374 ws_chunks, :445 dashboard)   │
│                            │      └───────────────────┬─────────────────────────────────┘
│ web/ React :3000           │                          ▼
│  App.jsx (dashboard WS)    │      ┌─────────────────────────────────────────────────────┐
│  useBrowserMic (browser as │ ───▶ │ ③ BACKEND ORCHESTRATION — ws/handler.py             │
│  mic, 2nd path into        │      │  ChunkSession:                                     │
│  /ws/chunks)               │      │   • provider-chain ASR (lang-ordered)              │
│  CaseSheetForm (confirm UI)│      │   • gates (RMS / no_speech / logprob) → dedupe      │
└────────────────────────────┘      │   • LIVE: local_fill(full) EVERY chunk (free)      │
                                    │        → MergeEngine(latest-wins, confirm locks)   │
                                    │        → validate_case_sheet → chunk_result        │
                                    │   • FINALIZE: local_fill → ONE Gemini call →       │
                                    │        merge → validate → _persist (idempotent)    │
                                    └───────────────────┬─────────────────────────────────┘
                                                        ▼
                                    ┌─────────────────────────────────────────────────────┐
                                    │ ④ DATA / DB — SQLite scribe.db (db/models.py)       │
                                    │  Encounter · Patient · Utterance ·                  │
                                    │  VitalsSnapshot(JSON{answers,_confirmed}) ·         │
                                    │  Alert · AudioDeletionLog (DPDP audit)              │
                                    └───────────────────┬─────────────────────────────────┘
                                                        ▼
                                    ┌─────────────────────────────────────────────────────┐
                                    │ ⑤ UI — web/src/App.jsx + CaseSheetForm.jsx          │
                                    │  live transcript · 40-field tile grid · per-field   │
                                    │  Confirm-lock (amber=draft → brand=locked) ·        │
                                    │  AlertBanner · elapsed / VAD indicators             │
                                    └─────────────────────────────────────────────────────┘
```

Two capture paths converge on **`/ws/chunks`**:

- **Capture agent path:** standalone Python recorder → Silero VAD → PCM chunks
- **Browser path:** `useBrowserMic.js` → resample 16 kHz → RMS-VAD → base64 chunks

The dashboard keeps a second socket `/ws/dashboard` purely for control + broadcast reception. Every `chunk_result`/`finalize_result` is sent **both** back to the requesting chunks socket **and** broadcast to all dashboard clients (`handler.py:430-431, 391-392`).

---

## 2. Model Inventory

### Summary table

| # | Model | Role | Free/Paid | Quota (this key) | Status |
|---|-------|------|-----------|------------------|--------|
| 1 | **Groq Whisper large-v3** | Primary ASR (transcription) | Free | ~8 hrs/day, 2000 req/day | ✅ Working |
| 2 | **Gemini 3.5 Flash** | LLM analysis (JSON extraction) | Free | **20 req/day** | ✅ Working |
| 3 | **IndicConformer Maithili** | Local STT for Bihari languages | Free, offline | n/a (local) | ❌ Inert (NeMo/Py3.14) |
| 4 | **Local Whisper** (faster-whisper) | ASR fallback | Free, offline | CPU-bound | ✅ Enabled |
| 5 | **Sarvam Saaras v3** | Bihari cloud ASR fallback | API | — | ⚠️ Key empty, skips |
| 6 | **Bhashini Dhruva** | Govt cloud ASR fallback | Govt API | — | ⚠️ Key empty, skips |
| 7 | **Silero VAD 6.2.2** | Voice-activity detection (capture) | Free, offline | n/a (on-device) | ✅ Installed |

### Detail

**1. Groq Whisper large-v3** — `backend/ws/groq_asr.py`, `GROQ_MODEL=whisper-large-v3` in `.env`

- Primary transcription: PCM → WAV → POST `/openai/v1/audio/transcriptions`, `language=hi`, `verbose_json`, `temperature=0`
- Maps `mai/mag/bho/vajjika → hi` (`groq_asr.py:31-39`) — Whisper has no native Bihari support
- Prompt = transcript tail (140 words / ≤650 chars, under 896-char cap) + Hindi domain vocabulary (`groq_asr.py:96-104`, `config.py:61-70`)
- Free tier (no card), ~8 hrs/day audio, 2,000 req/day
- Returns `verbose_json` segment metrics (`avg_logprob`, `no_speech_prob`, `compression_ratio`) used by post-ASR gate

**2. Gemini 3.5 Flash** — `backend/llm/extract.py`, `LLM_MODEL=gemini-3.5-flash`

- JSON case-sheet extraction, ONE call per patient at finalize
- `temperature=0`, `response_mime_type=application/json`, 2048 max output tokens, 30 s HTTP timeout
- Prompt = `EXTRACTION_PROMPT` (bilingual rules) + `build_schema_prompt_text()` (40 fields w/ bilingual labels + enum options) + transcript
- **Free tier: 20 req/day — this constraint drives the entire architecture**
- Self-heal ladder: 429 PerDay → block model for today → fail over to `gemini-3.6-flash → gemini-3.7-flash → gemini-3.5-flash-lite` (own pools, `extract.py:59-63, 223-233`); 403/404 → permanently skip; all exhausted → all-`None` (local fill survives)
- `llm_final_extract=True` config toggle: flip False → fully offline

**3. AI4Bharat IndicConformer (Maithili)** — `backend/ws/indicconformer_asr.py`

- First-choice for `mai/mag/bho/vajjika` language tags (`handler.py:64-65`)
- Free, MIT, fully offline
- **NOT installed:** requires `nemo_toolkit[asr]`; NeMo has no Python 3.14 support (venv is 3.14.7)
- `_nemo_available()` always False → adapter returns empty → chain gracefully falls through to Groq
- `USE_INDIC_CONFORMER=true` in `.env` but effectively inert

**4. Local Whisper** — `backend/ws/local_asr.py` (faster-whisper)

- `small / int8 / cpu`, lazy-loaded + thread-locked
- Last resort when Groq fails/rate-limits
- Weak on Maithili / code-mixing; CPU-bound → slow in live stream

**5/6. Sarvam / Bhashini** — env-only placeholders

- `SARVAM_API_KEY=EMPTY`, Bhashini key + `USER_ID` empty → `_configured=False` → chain skips instantly

**7. Silero VAD 6.2.2** — `capture-agent/vad.py`

- On-device voice-activity detection in the capture pipeline (NOT on backend)
- **512-sample frame caveat:** Silero requires 512-sample windows @16 kHz; `VADChunker.feed()` buffers until ≥512 (`vad.py:68-69`), slides frames, zero-pads short tail (`vad.py:121-134`)
- Chunk emission: min speech 300 ms, silence-stop 400 ms, max 10 s speech, 300 ms look-back (`vad.py:40-44`); `main.py` drops chunks <300 ms
- Browser-mic path has NO Silero — uses simple RMS threshold (`useBrowserMic.js:6, 331`)

### Effective runtime chain (graph)

```
LANGUAGE ROUTING — handler._provider_order()
─────────────────────────────────────────────

  language ∈ {mai, mag, bho, vajjika}:
  ┌──────────────────┐   empty    ┌──────────────┐   empty    ┌──────────┐
  │ IndicConformer   │ ─────────▶ │   Groq       │ ─────────▶ │ Sarvam   │ ...
  │ (NeMo absent ✗)  │            │ Whisper v3 ✓ │            │ (key ✗)  │
  └──────────────────┘            └──────────────┘            └──────────┘

  language = hi / default:
  ┌──────────────┐   empty    ┌──────────┐   empty    ┌──────────────┐
  │   Groq       │ ─────────▶ │  Sarvam  │ ─────────▶ │  Bhashini    │ ...
  │ Whisper v3 ✓ │            │ (key ✗)  │            │  (key ✗)     │
  └──────────────┘            └──────────┘            └──────────────┘

  ══════════════════════════════════════════════════════════
  EFFECTIVE (today):  Groq(whisper-large-v3) → LocalWhisper(small/int8)
  ══════════════════════════════════════════════════════════
```

### Model cost/latency graph (conceptual)

```
              latency (live streaming)          cost per chunk
                 ┌──────────────┐                 ┌──────────────┐
  Local fill  ▶  │ ██           │ ~0 ms           │ $0 (FREE)    │
                 └──────────────┘                 └──────────────┘
                 ┌──────────────────┐             ┌──────────────┐
  Groq ASR    ▶  │ ████████████     │ ~300-800 ms  │ $0 (FREE)    │
                 └──────────────────┘             └──────────────┘
                 ┌─────────────────────────┐      ┌──────────────┐
  LocalWhisper▶  │ ████████████████████    │ ~2-6 s│ $0 (FREE)    │
                 └─────────────────────────┘       └──────────────┘
                 ┌─────────────────┐               ┌──────────────┐
  Gemini       ▶ │ ███████████     │ ~1-4 s        │ $0 / 20 day  │
  (finalize)     └─────────────────┘               └──────────────┘
```

---

## 3. Transcription & Analysis Pipeline

**Invariant for both modes:** transcription always completes and gates pass **before** any analysis runs, and free local analysis always runs **before** the paid LLM.

### Common pre-steps (both modes)

1. `ws_chunks_handler` accepts socket (`handler.py:374-379`)
2. First audio payload **implicitly** starts session if no `session_start` sent (`handler.py:406-415`)
3. `voice_activity` broadcast fires per chunk (`handler.py:417-422`)

---

### 3A. LIVE per-chunk mode (zero LLM cost)

```
 [capture agent]                         [backend ws/handler.py]                    [Groq cloud]
 ─────────────                           ──────────────────────                     ────────────
 recorder(16k stereo f32)                                                                    │
   → to_mono                                                                                 │
   → denoiser(deepfilter)                                                                    │
   → Silero VAD(512smp) ──► SpeechChunk                                                       │
   → streamer.send_chunk({pcm_b64, ...}) ──►                                                 │
                                             │                                                │
                                             ▼                                                │
                                    ┌─ ① PRE-ASR SILENCE GATE ─┐                             │
                                    │  _pcm_level(RMS)         │                             │
                                    │  rms < 0.004 ?           │                             │
                                    │  YES → return empty ──── │ (no cloud call)             │
                                    └──────────────────────────┘                             │
                                             │ pass                                           │
                                             ▼                                                │
                                    ┌─ ② PROVIDER SELECTION ───┐                             │
                                    │ _provider_order(lang)    │                             │
                                    │ first non-empty wins ────┼──────────────────────────────┤
                                    └──────────────────────────┘   transcribe(WAV, language=hi,│
                                             ▲                     verbose_json, prompt)      │
                                             │ ◄──────────────── text + metrics ──────────────┘
                                             ▼
                                    ┌─ ③ POST-ASR GATE ────────┐
                                    │ _gate_result():          │
                                    │  no_speech_prob > 0.6 ✗  │ → REJECT (silence)
                                    │  pcm_level < 0.004     ✗ │ → REJECT (hallucination)
                                    │  compression_ratio > 2.4 ✗│ → DROP (low confidence)
                                    │  avg_logprob < -1.5    ✗ │ → DROP
                                    └──────────────────────────┘
                                             │ pass
                                             ▼
                                    ┌─ ④ BOUNDARY DEDUPE ──────┐
                                    │ strip word re-emitted at  │
                                    │ chunk head (overlap)      │
                                    └──────────────────────────┘
                                             │
                                             ▼
                                    transcript_buffer += chunk
                                    full = " ".join(buffer)
                                             │
                                             ▼
                                    ┌─ ⑤ LOCAL FILL (FREE) ────┐
                                    │ local_fill(full)         │  ← Devanagari regex,
                                    │  phone / name / age /    │    polarity Yes/No,
                                    │  address / block /       │    last-match-wins,
                                    │  district / LMP / ANC /  │    script-fidelity gate
                                    │  delivery / baby / ...   │    (Devanagari ratio <0.35 → {})
                                    └──────────────────────────┘
                                             │ {field: value}
                                             ▼
                                    ┌─ ⑥ MERGE ────────────────┐
                                    │ MergeEngine.merge()      │
                                    │  latest non-empty wins   │
                                    │  confirmed? → SKIP (lock)│
                                    └──────────────────────────┘
                                             │
                                             ▼
                                    ┌─ ⑦ VALIDATE ─────────────┐
                                    │ validate_case_sheet()    │
                                    │  age 10-65, wt 0.4-8.0,  │
                                    │  <2.5 → low-birth-weight,│
                                    │  critical keywords,      │
                                    │  complication flags      │
                                    └──────────────────────────┘
                                             │
                                             ▼
                                    ┌─ ⑧ EMIT ─────────────────┐
                                    │ chunk_result {           │
                                    │  transcript, answers,    │
                                    │  confirmed, alerts, ...} │
                                    └──────────────────────────┘
                                      │                │
                       to chunks socket            broadcast
                                     ▼                   ▼
                              capture agent        dashboard UI
                                                 (CaseSheetForm
                                                  fills live)

 NO GEMINI CALL IN THIS MODE — sheet fills entirely from regex.
```

---

### 3B. Finalize mode (one LLM call per patient)

```
  Trigger: dashboard mic_stop  OR  chunks socket {type:"finalize"}
─────────────────────────────────────────────────────────────────────────────
                                                                  [Gemini cloud]
 [backend ws/handler.py]                                            │
                                                                   │
  ┌─ ① LOCAL FILL (FREE, FIRST) ──────┐                            │
  │ local_fill(full_transcript)       │                            │
  │  re-derives from whole transcript│                            │
  │  (catches cross-chunk answers)   │                            │
  │  merge(chunk_id=-1)              │                            │
  └───────────────────────────────────┘                            │
  ┌─ ② ONE GEMINI CALL ──────────────┐                            │
  │ if llm_final_extract && non-empty:│                            │
  │   extract(full) =                 │                            │
  │    EXTRACTION_PROMPT +            │                            │
  │    build_schema_prompt_text() +   │ ──── generate_content ────▶│
  │    transcript                     │ ◄── JSON {40 fields} ──────┘
  │   temp=0, json mime, 2048 tokens  │
  │                                   │  429 PerDay?
  │   self-heal ladder:               │   → block model for today
  │    3.5-flash (20/day)             │   → next model (own pool)
  │    → 3.6-flash (20/day)           │  403/404?
  │    → 3.7-flash (20/day)           │   → permanently skip
  │    → 3.5-flash-lite (20/day)      │  all exhausted?
  │    → returns all-None             │   → local fill survives
  │                                   │
  │   ANY exception in finalize()?    │
  │    → catch → local fill kept ✓    │
  └───────────────────────────────────┘
  ┌─ ③ MERGE (GEMINI) ───────────────┐
  │ merge(gemini_dict, chunk_id=-1)  │  confirmed? → still SKIPPED
  └───────────────────────────────────┘
  ┌─ ④ VALIDATE ─────────────────────┐
  │ validate_case_sheet(snapshot)    │
  └───────────────────────────────────┘
  ┌─ ⑤ PERSIST (IDEMPOTENT) ─────────┐
  │ if encounter_id:                 │
  │   DELETE children by             │
  │    encounter_id:                 │
  │    Utterance, VitalsSnapshot,    │
  │    Alert, Patient                │
  │   DELETE Encounter by id         │
  │ INSERT fresh:                    │
  │   Encounter                      │
  │   Utterances (speaker="mixed")   │
  │   VitalsSnapshot(data={          │
  │    answers, confirmed})          │
  │   Alerts (one per validation)    │
  │ single commit ✓                  │
  └───────────────────────────────────┘
  ┌─ ⑥ AUDIO DELETION AUDIT ─────────┐
  │ if audio_delete_after_transcribe:│
  │   AudioDeletionLog row           │
  │   (DPDP compliance)              │
  └───────────────────────────────────┘
  ┌─ ⑦ EMIT ─────────────────────────┐
  │ finalize_result {                │
  │  transcript, answers, confirmed, │
  │  alerts}                         │
  └───────────────────────────────────┘
        │                  │
   to chunks socket   broadcast → dashboard (UI locks recording, sets final state)
```

---

## 4. Key Design Trade-Offs

### Why local-first + Gemini-once-per-patient

The Gemini key is capped at **~20 requests/day**, while a single maternity encounter can generate dozens of audio chunks over several minutes. If every chunk triggered an LLM extraction, **one patient would exhaust the whole day's budget**.

| Strategy | Cost per chunk | Live fill quality | Quota |
|----------|---------------|-------------------|-------|
| Gemini every chunk | 1 request | High | Exhausted by 1st patient |
| **Local fill every chunk + Gemini once at finalize** | **$0 live, 1/finalize** | **High enough (regex covers most)** | **~1 patient/day minimum, ladder → 80** |
| Gemini at finalize only | $0 live | Poor (0 fields until finalize) | 1/finalize |

**`local_fill`** is a deterministic, zero-latency, zero-quota regex filler on **every** chunk (and again first at finalize), enough to fill most of the 40 fields live so the health worker sees the sheet populate in real time.

**Gemini** is reserved for a **single** schema-prompted pass at finalize for exactly the cases regex is bad at — ambiguous phrasing, indirect answers, code-mixed Maithili, cross-sentence question/answer pairing.

The `llm_final_extract` toggle makes the LLM fully optional: flip it off → entirely offline.

**Trade-offs accepted:** finalize latency (seconds when Gemini runs); reduced extraction recall during live streaming (acceptable because the physician reviews and confirms everything before trust).

**Failover ladder expands quota:** exhausting `gemini-3.5-flash`'s 20/day steps sideways to three other models with own pools; per-day-block memory avoids wasting retries on a dead pool.

### Why flat field-map merge with physician confirm locks

The case sheet is a **fixed, flat 40-field form** — not a nested document — so `{key: FieldState(value, source_chunk_id, confirmed)}` is the simplest thing that works.

- **"Latest non-empty wins"** (`merge.py:75`) implements natural self-correction: patient says 35 then corrects to 36 → later utterance overwrites. Matches both regex (last-match-wins helpers `_last`/`_answer_number`) and Gemini (prompt rule 2).
- **`confirmed` flag = human-in-the-loop safety interlock:** once health worker clicks Confirm, `merge()` skips that key entirely (`merge.py:71-72`) — neither later chunk nor finalize-time Gemini can overwrite a clinician-vetted value. Critical in clinical setting: automation is aggressive during streaming while human has final authority.
- Visual: amber draft → brand-locked with "OK" badge (`CaseSheetForm.jsx:37-42`).

**Trade-off:** locks only as good as confirm being taken; confirmed-but-wrong field has no in-app unlock path.

### Why the Devanagari `\b` gotcha mattered (BD-lookahead fix)

Python's `\b` uses ASCII-style `\w` semantics — **Devanagari combining marks (matras) are NOT word characters**.

```
Pattern:  नाम\b
Text:     नाम है  →  \b after म sees... a SPACE (word→nonword = boundary?) 
           BUT: pattern नाम then \b — if followed by " है", the boundary fires.
           The REAL breakage: \b after है in "नाम सीता है"
           → ह is word, ै is NOT word (combining mark)
           → \b fires BETWEEN ह and ै — INSIDE the word!
           → "है\b" can NEVER match (confirmed by test).
```

This meant naive rules matched **almost nothing** on real Hindi transcripts — the entire free filler would have been dead code, silently returning `{}` and defeating the whole quota strategy.

**Fix:** `BD = r"(?=\s|[.?,।;]|$)"` (`local_fill.py:16-18`) — asserts "next char is whitespace, ASCII/Devanagari punctuation, or end-of-string" instead of a word boundary. Script-agnostic, correctly terminates matches before `है`, `।`, `?`, etc.

**Companion design choices:**
- **Last-match-wins:** answers usually come AFTER questions → use last match (`_last`, `_answer_number`, `_answer_name`)
- **Script-fidelity gate:** Devanagari ratio < 0.35 → refuse to fill (`local_fill.py:190-200`)

**Trade-off:** every new regex must remember `BD`, not `\b`; a future contributor adding `\b` reintroduces silent match failures (no unit tests catch this — existing tests are integration/live-API only).

### Why finalize is idempotent

Both dashboard `mic_stop` AND chunks `type:"finalize"` invoke `session.finalize()`, and browser-mic `stop()` can race/repeat. Because `Encounter.id` is caller-supplied `encounter_id`, naively re-inserting raises `sqlite3.IntegrityError: UNIQUE constraint failed`.

`_persist()` does **delete-then-insert** for every child table by `encounter_id` and parent by `id` (`handler.py:299-306`).

**Payoff:** finalize can be retried freely after network blip, double-click, or Gemini timeout — always converges to current in-memory state, never accumulating duplicate rows.

**Trade-off:** repeat finalize *replaces* rather than appends history (older utterance rows destroyed) — fine for "latest snapshot wins" semantics, wrong if per-attempt audit history needed.

### What would change with a PAID Gemini tier

The single-call-at-finalize bottleneck exists purely because of the 20 req/day ceiling. With paid tier:

| Change | Benefit |
|--------|---------|
| Extract per chunk / N chunks | Sheet fills with LLM-quality values DURING encounter (not regex drafts) |
| Cover ~20 uncovered fields | MCTS/RCH, IPD, admission category, EDD, diagnoses, contraceptive history, provider/outcome |
| Cross-field validation passes | EDD↔LMP consistency, outcome↔baby fields |
| Sliding-window incremental extract | Per-chunk merges into same MergeEngine (confirm-locks still protect) |

**Architecture already supports this** — `merge()` is chunk-agnostic, accepts merges from any source at any time; only `process_chunk()` call-site would change. Trade-off shifts from "quota exhaustion" to "per-encounter dollar cost + per-chunk latency." Would likely still keep regex as instant first pass + LLM as background enrichment.

---

## 5. Full Encounter Sequence Diagram

```
 HealthWorker      web/App.jsx      capture-agent      backend handler.py        Groq        Gemini       SQLite
 (dashboard WS)    useBrowserMic      main.py          ChunkSession/chains       (ASR)      (finalize)   scribe.db
     │                  │  ①mic_start │                      │                    │            │           │
     │──Start Rec──────▶│─────────────┼─────────────────────▶│ session.active=True │            │           │
     │                  │ (new uuid encounter_id)            │ reset(merge/buffer) │            │           │
     │                  │             │                      │◀─session_state──────┼────────────┼───────────│──▶ UI
     │                  │             │                      │                    │            │           │
     │◀═════════════════╡  [or browser mic: getUserMedia → AudioContext → resample 16k → RMS-VAD → base64]  │
     │                  │             │                      │                    │            │           │
     │                  │             │ recorder→denoise→    │                    │            │           │
     │                  │             │ SileroVAD(512smp)→   │                    │            │           │
     │                  │             │ send_chunk(pcm_b64)──┤                    │            │           │
     │                  │             │   ②chunks ×N ───────▶│                    │            │           │
     │                  │             │                      │ pre-ASR RMS gate   │            │           │
     │                  │             │                      │ provider order(lang)           │           │
     │                  │             │                      │──transcribe────────▶│            │           │
     │                  │             │                      │◀─text+logprob───────│            │           │
     │                  │             │                      │ gate(reject/drop)   │            │           │
     │                  │             │                      │ dedupe→buffer       │            │           │
     │                  │             │                      │ local_fill(full)←FREE│           │           │
     │                  │             │                      │ MergeEngine.merge   │            │           │
     │                  │             │                      │ validate_case_sheet │            │           │
     │                  │             │◀──chunk_result───────┤                    │            │           │
     │◀──voice_activity─┼◀──chunk_result(broadcast)──────────┤                    │            │           │
     │   + transcript    │   answers/confirmed/alerts update  │                    │            │           │
     │   CaseSheetForm  │   [health worker clicks Confirm → confirm_field → merge.confirm (LOCK)]          │
     │                  │  ③mic_stop   │                      │                    │            │           │
     │──Stop───────────▶│─────────────┼─────────────────────▶│ finalize()         │            │           │
     │                  │  (or browser stop() → flush → finalize msg)              │            │           │
     │                  │             │                      │ local_fill AGAIN (free, first)   │           │
     │                  │             │                      │──ONE Gemini extract (temp=0)────▶│           │
     │                  │             │                      │◀─JSON{40 fields}──(429→next model/local)──│  │
     │                  │             │                      │ merge → validate    │            │           │
     │                  │             │                      │ _persist (DELETE-then-INSERT, idempotent)────────▶
     │                  │             │                      │ log_deletion (DPDP audit) ─────────────────────▶│
     │◀──finalize_result──────────────┼◀──finalize_result(broadcast)──┤           │            │           │
     │   + alerts        │  answers/confirmed locked-in; recording stops          │            │           │
```

---

## 6. Data Model / Schema

### SQLite tables (db/models.py)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                             scribe.db                                       │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  encounters(id PK, created_at, clinic_id, language_detected,               │
│             status, consent_given)                                          │
│       │ 1                                                                   │
│       │── 0..1  patients(encounter_id FK, name, age, language)             │
│       │ 1                                                                   │
│       │── 0..N  utterances(encounter_id FK, chunk_id, speaker,             │
│       │                    transcript, language, confidence, timestamp)     │
│       │ 1                                                                   │
│       │── 0..N  vitals_snapshots(encounter_id FK,                          │
│       │                    data JSON{answers, _confirmed}, confirmed,      │
│       │                    timestamp)                                       │
│       │ 1                                                                   │
│       │── 0..N  alerts(encounter_id FK, field, message,                    │
│       │              severity, acknowledged, timestamp)                     │
│       │ 1                                                                   │
│       └── 0..N  audio_deletion_log(encounter_id FK,                        │
│                      chunk_ids JSON, deleted_at, deletion_reason)           │
│                                                                             │
│  SQLite via db/connection.py (SessionLocal)                                │
└─────────────────────────────────────────────────────────────────────────────┘

  Data flow through tables:
  encounter (created implicit on first chunk / explicit mic_start)
    → utterances (one per transcript_buffer entry, speaker="mixed")
    → vitals_snapshots (ONE per finalize: data = {answers: {...}, _confirmed: {...}})
    → alerts (one per validate_case_sheet warning/critical)
    → audio_deletion_log (one per finalize if audio_delete_after_transcribe)
```

**Idempotent persist flow** (`_persist()`, `handler.py:299-334`):
```
if encounter_id set:
  DELETE FROM utterances WHERE encounter_id = ?
  DELETE FROM vitals_snapshots WHERE encounter_id = ?
  DELETE FROM alerts WHERE encounter_id = ?
  DELETE FROM patients WHERE encounter_id = ?
  DELETE FROM encounters WHERE id = ?
  INSERT encounter, utterances, vitals_snapshot, alerts
  single COMMIT
```

---

## 7. Case Sheet Schema (40 fields / 5 sections)

**Source of truth:** `backend/form_schema.py` (Python dict) → served at `GET /api/schema` → mirrored in `web/src/formSchema.js`

| # | Section (id) | Title (EN) | Title (HI) | Fields |
|---|-------------|-----------|-----------|--------|
| 1 | `registration` | Registration Details | पंजीकरण विवरण | mcts_rch_number, ipd_number, bpl_jsy_registered, aadhaar_number, referred_from (5) |
| 2 | `personal` | Personal & Contact Details | व्यक्तिगत एवं संपर्क विवरण | name, spouse_parent_of, age, address, block, district, health_centre, contact_phone, contact_phone_hc, asha_name (10) |
| 3 | `admission` | Admission & Medical Status | भर्ती एवं चिकित्सीय स्थिति | admission_date, admission_time, admission_category, marital_status, birth_attendant, lmp, edd, **pregnancy_complication, anc_checkup_done, anc_visits** (added this session), provisional_diagnosis, final_diagnosis, contraceptive_history (13) |
| 4 | `delivery` | Delivery & Baby | प्रसव एवं शिशु | delivery_mode, delivery_outcome, babies_count, birth_weight_kg, preterm, baby_sex, immunization (7) |
| 5 | `outcome` | Final Outcome | अंतिम परिणाम | final_outcome, final_date_time, provider_name, provider_designation, provider_phone (5) |

**Field types:** `text`, `yesno`, `number`, `date`, `time`, `select` (w/ bilingual options), `wide` (spans full tile row)

**Key functions:**
- `build_schema_prompt_text()` → generates bilingual Gemini prompt section from FORM_SCHEMA
- `ALL_FIELDS`, `FIELD_BY_KEY` → flat indexes for merge/validate

**New this session:** `anc_checkup_done` (yesno, "एएनसी जांच हुई" / "ANC checkup done"), `anc_visits` (number, "एएनसी जांचों की संख्या" / "Number of ANC visits")

---

## 8. WebSocket Message Protocol

### Two sockets

| Endpoint | Who connects | Purpose |
|----------|-------------|---------|
| `ws://...:8765/ws/chunks` | capture-agent / browser mic | Audio in, results out |
| `ws://...:8765/ws/dashboard` | React App.jsx | Commands in, broadcasts out |

### Client → Server

**`/ws/chunks`:**
```json
{"type": "session_start", "encounter_id": "demo"}
{"chunk_id": 0, "pcm_b64": "...", "sample_rate": 16000, "channels": 1,
 "mic_channel": 0, "start_sample": 0, "end_sample": 8000,
 "duration_ms": 500, "language": "hi"}
{"type": "finalize", "encounter_id": "demo"}
```

**`/ws/dashboard`:**
```json
{"type": "mic_start", "encounter_id": "new-uuid"}
{"type": "mic_stop"}
{"type": "confirm_field", "field": "name"}
```

### Server → Client

**To chunks socket + broadcast to dashboard:**
```json
{"type": "chunk_result", "chunk_id": 0, "encounter_id": "...",
 "transcript": "...", "status": "finalized", "confidence": 0.95,
 "provider": "groq-whisper", "speaker": "mixed", "language": "hi",
 "answers": {"name": "सीता देवी", "age": 24, ...},
 "confirmed": {"name": true},
 "alerts": [{"field": "...", "message": "...", "severity": "warning"}],
 "voice_level": 0.42, "vad": true}

{"type": "finalize_result", "encounter_id": "...",
 "transcript": "...", "answers": {...}, "confirmed": {...},
 "alerts": [...]}

{"type": "session_state", "active": true, "encounter_id": "demo"}

{"type": "snapshot", "answers": {...}, "confirmed": {...}, "transcript": "..."}

{"type": "field_confirmed", "field": "name"}

{"type": "voice_activity", "level": 0.42, "vad": true}
```

---

## 9. Architectural Risks & Gaps

| # | Risk | Severity | Detail |
|---|------|----------|--------|
| 1 | **Single global session** | 🔴 High | `current_session` is one module-level global (`handler.py:341`). Two simultaneous encounters share/overwrite the same session. Only one encounter at a time. No session registry keyed by `encounter_id`. |
| 2 | **No authentication** | 🔴 High | CORS `allow_origins=["*"]` + `allow_credentials=True` (`main.py:38-44`); both WS endpoints accept unauthenticated connections. PHI (Aadhaar, phone, name, diagnosis) exposed. |
| 3 | **Gemini quota hot-spot** | 🟡 Medium | 20 req/day hard ceiling. Failover ladder masks across 4 models (~80/day) but all same free key. `_daily_quota_blocked` is in-process memory — restart forgets blocked models. |
| 4 | **Chain degrades to 2 providers** | 🟡 Medium | IndicConformer (NeMo/Py3.14), Sarvam (key empty), Bhashini (key empty) all inert → effective chain = Groq → local whisper. Groq rate-limit → slow CPU fallback. |
| 5 | **Persist not fully transactional** | 🟡 Medium | `_persist()` commits, then `log_deletion()` opens separate commit. Crash between → encounter persisted but no deletion-audit row. |
| 6 | **Local fill coverage gap** | 🟡 Medium | ~20 of 40 fields have no regex rule (MCTS/RCH, IPD, admission category, EDD, diagnoses, contraceptive history, provider/outcome) — only fill if Gemini succeeds. |
| 7 | **BD-lookahead fragility** | 🟠 Low-Med | Future contributor adding `\b` reintroduces silent failures. No unit tests assert local_fill outputs (only integration/live-API tests). |
| 8 | **No diarization** | 🟠 Low-Med | `speaker="mixed"` persisted. Stereo channel exists "for future" but attribution not implemented — GNM vs patient disambiguated only by regex heuristics. |
| 9 | **Audio retention** | 🟢 Low | `AUDIO_DELETE_AFTER_TRANSCRIBE=true` writes audit row only; chunks never stored server-side (transient in WS payload) — mostly no-op audit entry. |
| 10 | **Schema mirror drift** | 🟢 Low | `web/src/formSchema.js` manually synced with `backend/form_schema.py` (mitigated by `/api/schema` fetch at boot). |

---

## 10. Run & Management Cheat-Sheet

### Start (3 terminals)

```powershell
# Terminal 1 — Backend (from backend/)
cd C:\Users\ADITYA\Downloads\AUTOMATIC_REPORT\backend
venv\Scripts\python.exe -m uvicorn main:app --port 8765 --host 127.0.0.1

# Terminal 2 — Dashboard (from web/)
cd C:\Users\ADITYA\Downloads\AUTOMATIC_REPORT\web
npm run dev
# → open http://localhost:3000 (binds IPv6 localhost)

# Terminal 3 — Capture agent (from repo ROOT)
cd C:\Users\ADITYA\Downloads\AUTOMATIC_REPORT
backend\venv\Scripts\python.exe capture-agent\main.py --language hi --encounter-id demo
```

### Stop all

```powershell
Get-Process -Name python | Stop-Process -Force
Get-Process -Name node | Stop-Process -Force
```

### Check status

```powershell
Get-NetTCPConnection -LocalPort 8765 -State Listen   # backend
Get-NetTCPConnection -LocalPort 3000 -State Listen   # dashboard
```

### Tests

```powershell
cd backend
venv\Scripts\python.exe integration_test.py           # 3/3 REST + WS
venv\Scripts\python.exe test_qa_live.py               # full audio → answers → finalize
venv\Scripts\python.exe test_e2e_live.py hi           # older e2e
```

### Key env vars (.env)

```
GROQ_API_KEY=...           # ✅ working
GEMINI_API_KEY=...         # ✅ working (free-tier, rotate if leaked)
LLM_MODEL=gemini-3.5-flash # REQUIRED (1.5-flash is retired/404)
LLM_FINAL_EXTRACT=true     # false = fully offline
GROQ_MODEL=whisper-large-v3 # NOT -turbo
USE_INDIC_CONFORMER=true   # inert (NeMo/Py3.14)
USE_LOCAL_FALLBACK=true
SARVAM_API_KEY=            # empty
BHASHINI_API_KEY=          # empty
```

---

## Appendix: File Index

| Path | Role |
|------|------|
| `backend/main.py` | FastAPI app, `/health`, `/api/schema`, WS route registration |
| `backend/config.py` | Pydantic settings (models, keys, toggles) |
| `backend/form_schema.py` | 40-field bilingual schema (single source) |
| `backend/ws/handler.py` | ChunkSession, provider chain, gates, merge, validate, persist |
| `backend/ws/groq_asr.py` | Groq Whisper adapter |
| `backend/ws/indicconformer_asr.py` | IndicConformer adapter (inert) |
| `backend/ws/local_asr.py` | faster-whisper fallback |
| `backend/ws/sarvam_asr.py` | Sarvam adapter (key empty) |
| `backend/ws/bhashini_asr.py` | Bhashini adapter (key empty) |
| `backend/llm/extract.py` | Gemini extractor + self-heal ladder |
| `backend/engine/local_fill.py` | Free bilingual regex field-filler |
| `backend/engine/merge.py` | MergeEngine (latest-wins, confirm locks) |
| `backend/engine/validate.py` | Case-sheet validation rules |
| `backend/db/models.py` | SQLAlchemy 6 tables |
| `backend/db/connection.py` | SessionLocal factory |
| `backend/storage/audio.py` | AudioDeletionLog (DPDP) |
| `capture-agent/main.py` | Recorder → denoise → VAD → streamer entry |
| `capture-agent/vad.py` | Silero VAD chunker (512-sample frames) |
| `capture-agent/streamer.py` | WS chunk sender |
| `web/src/App.jsx` | Dashboard root, WS handlers, mic Start/Stop |
| `web/src/formSchema.js` | Mirror of FORM_SCHEMA |
| `web/src/components/CaseSheetForm.jsx` | 40-field tile grid, confirm UI |
| `web/src/components/TranscriptPanel.jsx` | Live transcript bubbles |
| `web/src/components/AlertBanner.jsx` | Validation alerts |
| `web/src/hooks/useBrowserMic.js` | Browser mic → RMS-VAD → WS |
| `web/vite.config.js` | Dev proxy /api + /ws → 127.0.0.1:8765 |
| `docs/CODEMAPS/*.md` | Per-area codemaps (INDEX, backend, database, capture-agent, frontend) |
| `docs/GUIDES/local-run.md` | Full Windows run guide |

---

**Sources:** `docs/CODEMAPS/backend.md`, `INDEX.md`, `capture-agent.md`, `database.md`, `frontend.md`; `backend/ws/handler.py`; `backend/engine/{local_fill,merge,validate}.py`; `backend/llm/extract.py`; `backend/form_schema.py`; `backend/config.py`; `backend/main.py`; `backend/ws/{groq,indicconformer,local,sarvam,bhashini}_asr.py`; `backend/db/models.py`; `backend/storage/audio.py`; `capture-agent/{main,streamer,vad}.py`; `web/src/App.jsx`; `web/src/components/CaseSheetForm.jsx`; `web/src/hooks/useBrowserMic.js`; `.env` (secrets masked).