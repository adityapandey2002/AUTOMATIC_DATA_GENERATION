# Frontend Codemap (web/)

**Last Updated:** 2026-09-26

React 19 + Vite 6 + Tailwind 3.4 dashboard for the health worker. Bilingual (English/Hindi)
maternity case-sheet UI. Dev binds localhost:3000, proxies `/api` and `/ws` to 127.0.0.1:8765
(`web/vite.config.js`).

**No router** — single-page, two-tab application with tab state in `App.jsx`.

## Source Tree

| File | Purpose |
|------|---------|
| `src/main.jsx` | React entry (StrictMode, `#root`) |
| `src/App.jsx` | Main dashboard: tab state (`'scribe' | 'patients'`), WS dashboard socket, mic Start/Stop w/ elapsed timer, message handlers, alerts, layout |
| `src/formSchema.js` | Bundled mirror of `backend/form_schema.py` (fetched `/api/schema` at boot; fallback) — **AUTO-GENERATED**, do not edit by hand. Regenerate: `cd backend && venv\Scripts\python.exe export_schema_js.py` |
| `src/hooks/useWebSocket.js` | Reconnecting dashboard WS to `ws://host:8765/ws/dashboard` (VITE_WS_URL override); resends unacknowledged chunks on reconnect |
| `src/hooks/useBrowserMic.js` | Browser microphone capture → resample 16k → WS `/ws/chunks`, chunk VAD (RMS threshold 0.002), finalize on stop |
| `src/components/CaseSheetForm.jsx` | Bilingual tile grid of all **181 fields / 30 sections**; Confirm button per filled field (locks field via WS `confirm_field`) |
| `src/components/TranscriptPanel.jsx` | Live transcript with per-speaker labels + tentative italics |
| `src/components/AlertBanner.jsx` | Critical/warning alert banners |
| `src/components/PatientsList.jsx` | Patient list / encounter history (fetches `GET /api/patients` on mount) |
| `index.html` | Shell, Inter font, SVG favicon |

## WS Message Handling (App.jsx)

| Message type | Handler effect |
|--------------|----------------|
| `voice_activity` | voice-active pulse indicator |
| `capture_status` | capture-connected indicator |
| `session_state` | sets recording state; resets answers/messages/alerts on start |
| `snapshot` | sets answers/confirmed, transcript |
| `chunk_result` | appends transcript (unless rejected/empty), updates answers/confirmed/alerts |
| `field_confirmed` | marks confirmed |
| `finalize_result` | sets final answers/confirmed/alerts, stops recording, resets timer |

Controls sent:
- `mic_start` (on Start Recording, with new uuid encounter_id)
- `stopMic` flushes then `finalize` via browser-mic hook cleanup
- `confirm_field` on dashboard Confirm button

## Browser Mic Notes (useBrowserMic.js)

- Creates AudioContext at device rate (does NOT force 16k — forcing 16k feeds all-zero buffers
  to ScriptProcessor in current Chrome/Edge).
- Downconverts via `resampleToRate()` to 16k mono `int16` PCM for the wire; payload carries
  `rms`, `raw_rms`, `analyser_rms`, `anySignal`, `devRate`, `label` for the backend log.
- Client-side VAD: `rms > 0.002`, chunk target ~6s, idle flush 0.9s, min chunk 800ms.
- On `stop()`: flushes buffered tail, sends `finalize {encounter_id}`.
- WS to `ws://${hostname}:8765/ws/chunks` with session_start + pending spool during reconnect.

## Schema Mirror

`web/src/formSchema.js` is **AUTO-GENERATED** from `backend/form_schema.py` — do not edit by hand.
Header comment:
```
AUTO-GENERATED from backend/form_schema.py — do not edit by hand.
Regenerate: cd backend && venv\Scripts\python.exe export_schema_js.py
Bundled mirror used if /api/schema is unreachable; backend is the source of truth.
```

**Regeneration is a manual step.** Nothing in CI, `package.json`, or the Dockerfile runs
`export_schema_js.py`, so the two files can silently drift. The app prefers the live
`/api/schema` response and only falls back to this bundle.

Backend schema: **30 sections, 181 unique field keys, 205 declarations** (including 6 generated `doctor_notes_1..6`).

## No Router

This is a **single-page, two-tab application** — there is no router. Tab state (`'scribe' | 'patients'`)
is managed directly in `App.jsx` with a simple `useState`. No `react-router` dependency exists.

## Styling

Tailwind `brand` palette = teal "modern clinical" (`#f0fdfa → #134e4a`).
Card/feature shadows `card`/`lifted`. Layout: header gradient brand, 2-col grid
(transcript | case sheet), slate backgrounds.

## Build / Deploy

- `npm run dev` (Vite dev server :3000), `npm run build`.
- `web/Dockerfile`: node:22-alpine build → nginx:alpine; proxies `/ws` to `http://backend:8765`
  in `web/nginx.conf`.
- docker-compose (deploy/) maps web :3000→80.

## Related Areas

- [INDEX.md](INDEX.md)
- [backend.md](backend.md) — WS protocol it consumes.
- [capture-agent.md](capture-agent.md) — alternative mic source (capture agent instead of browser mic).