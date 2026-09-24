# Run & Usage Guide — Windows

**Last Updated:** 2026-09-23

How to run and verify the Ambient Clinical AI Scribe locally on Windows.

## Prerequisites / Only working Python

- The only working Python on this machine is the repo venv:
  `backend\venv\Scripts\python.exe` (Python 3.14.7, venv under `backend/`).
- Install all dependencies into that venv (backend deps + capture-agent deps).
  - capture-agent deps: `numpy>=1.24` (**numpy<2 has no 3.14 wheels**), torch `2.9.1+cpu`,
    torchaudio, `silero-vad` **6.2.2** (VAD needs 512-sample frames @16kHz — fixed),
    psutil, sounddevice, `edge-tts` + soundfile for TTS test audio.
- NeMo is NOT installed → IndicConformer degrades gracefully (Groq routes Maithili-as-Hindi).

## 1. Start the backend

Run dir **MUST be `backend/`** (config/relative DB path depends on it):

```powershell
cd backend
venv\Scripts\python.exe -m uvicorn main:app --port 8765 --host 127.0.0.1
```

Behind the scenes: `lifespan` calls `init_db()` (creates tables in `scribe.db`), CORS `*`.
REST: `GET /health` → `{"status":"ok"}`, `GET /api/schema` → schema.

## 2. Start the web dashboard

```powershell
cd web
npm run dev
```

Binds localhost (IPv6) port **3000**. Vite proxies `/api` and `/ws` to `127.0.0.1:8765`.

Open `http://localhost:3000`. Press **Start Recording** and speak the Q&A; answers auto-fill,
each can be confirmed.

## 3. Capture agent (optional, separate mic machine)

From repo **ROOT**:

```powershell
backend\venv\Scripts\python.exe capture-agent\main.py --language hi --encounter-id demo
```

(Language `hi` = Hindi, `mai` = Maithili/Magahi.)

## Tests / Demos

Backend must be running on `127.0.0.1:8765`. These are one-shot scripts run from `backend/`:

| Command | What it does |
|---------|--------------|
| `venv\Scripts\python.exe integration_test.py` | /health + /api/schema REST, dashboard mic round-trip, chunks round-trip (**3/3 PASS**) |
| `venv\Scripts\python.exe test_qa_live.py` | Sends ~45s two-voice Hindi Q&A audio (`qa_gnm.mp3` + `qa_patient.mp3` from `%TEMP%\opencode`) via `/ws/chunks`; prints transcript, live answers, `finalize_result`, alerts — current demo |
| `venv\Scripts\python.exe test_e2e_live.py` | Older; sends `groq_test_hi.mp3`, expects `answers`/`confirmed` keys |
| `venv\Scripts\python.exe test_groq_live.py` | Direct GroqWhisperASR probe |
| `venv\Scripts\python.exe test_bhashini.py` | Requires BHASHINI_API_KEY + USER_ID in .env |

## Manage commands cheat-sheet

| Task | Command |
|------|---------|
| Stop all python processes | `Get-Process -Name python | Stop-Process -Force` |
| Check ports | `netstat -ano | findstr 8765`, `netstat -ano | findstr 3000` |
| Backend log | `%TEMP%\opencode\backend.log` |
| Vite log | `%TEMP%\opencode\vite.log` (check `web/vite.out.log` / `web/vite.err.log`) |

## Detached background launch (Windows PowerShell)

The shell tool hangs on `-RedirectStandardOutput`; use cmd redirection instead:

```powershell
Start-Process -FilePath "cmd.exe" -ArgumentList "/c", "... > log 2>&1"
```

Example (from repo root):
```powershell
Start-Process -FilePath "cmd.exe" -ArgumentList "/c", "cd /d C:\Users\ADITYA\Downloads\AUTOMATIC_REPORT\backend && venv\Scripts\python.exe -m uvicorn main:app --port 8765 --host 127.0.0.1 > %TEMP%\opencode\backend.log 2>&1"
```

## .env keys / reality notes

- `GROQ_API_KEY` — real, working (free tier). `GROQ_MODEL=whisper-large-v3`.
- `GEMINI_API_KEY` — REAL key. Free tier = **20 req/day** on `gemini-3.5-flash`.
  `LLM_MODEL=gemini-3.5-flash` is REQUIRED — `gemini-1.5-flash` is retired/404 on this account.
  **Appeared once in tool output this session — user advised rotating it.** Do not commit `.env`
  (gitignored).
- `llm_final_extract: bool = True` in `config.py` toggles the Gemini finalize; set False for
  fully offline local-fill-only extraction.
- Sarvam/Bhashini keys are empty in `.env`.
- Swiss-army extraneous: only the venv python works for local runs (no system python 3.14).

## Cost / quota design

- Every chunk → `local_fill(full_transcript)` — free, deterministic, bilingual.
- Gemini runs ONCE per case at `finalize()` for ambiguous leftovers; exceptions (incl. 429
  ResourceExhausted) are caught and logged — local fill is kept.
- If daily quota exhausted, `llm/extract.py` fails over to gemini-3.6-flash / 3.7-flash /
  3.5-flash-lite; 403/404 → permanently unavailable set.

## Related docs

- [docs/CODEMAPS/INDEX.md](../CODEMAPS/INDEX.md)
- [docs/CODEMAPS/backend.md](../CODEMAPS/backend.md)
- [docs/CODEMAPS/database.md](../CODEMAPS/database.md)
- [docs/CODEMAPS/frontend.md](../CODEMAPS/frontend.md)
- [docs/CODEMAPS/capture-agent.md](../CODEMAPS/capture-agent.md)