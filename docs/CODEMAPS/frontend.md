# Frontend Codemap (web/)

**Last Updated:** 2026-09-23

React 19 + Vite 6 + Tailwind 3.4 dashboard for the health worker. Bilingual (English/Hindi)
maternity case-sheet UI. Dev binds localhost:3000, proxies `/api` and `/ws` to 127.0.0.1:8765
(`web/vite.config.js`).

## Source Tree

| File | Purpose |
|------|---------|
| `src/main.jsx` | React entry (StrictMode, `#root`) |
| `src/App.jsx` | Main dashboard: WS dashboard socket, mic Start/Stop w/ elapsed timer, message handlers, alerts, layout |
| `src/formSchema.js` | Bundled mirror of `backend/form_schema.py` (fetched `/api/schema` at boot; fallback) |
| `src/hooks/useWebSocket.js` | Reconnecting dashboard WS to `ws://host:8765/ws/dashboard` (VITE_WS_URL override) |
| `src/hooks/useBrowserMic.js` | Browser microphone capture → resample 16k → WS `/ws/chunks`, chunk VAD, finalize on stop |
| `src/components/CaseSheetForm.jsx` | Bilingual tile grid of all fields; Confirm button per filled field |
| `src/components/TranscriptPanel.jsx` | Live transcript with per-speaker labels + tentative italics |
| `src/components/AlertBanner.jsx` | Critical/warning alert banners |
| `src/components/VitalsForm.jsx` | Legacy vitals form (not wired into current App flow) |
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

`web/src/formSchema.js` must stay in sync with `backend/form_schema.py`. New fields added for
ANC — `anc_checkup_done` (yesno, "ANC checkup done"/"एएनसी जांच हुई") and `anc_visits` (number,
"Number of ANC visits"/"एएनसी जांचों की संख्या") — mirror the backend exactly. Backend remains
the single source of truth (`GET /api/schema`).

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