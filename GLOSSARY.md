# Glossary

Domain and architecture vocabulary for the Ambient Clinical AI Scribe. Terms
here are code-verified; where the code and a doc disagree, the code wins.

## Domain

**Encounter** — one clinical visit. Identified by `encounter_id` (a UUID). The
unit everything else keys on: sessions, chunks, the case sheet, and the
`encounters`/`patients` rows. Both the capture agent and the dashboard converge
on one encounter by name (`SessionRegistry`).

**Chunk** — one bounded slice of audio streamed to `/ws/chunks`. Carries
`chunk_id`, `duration_ms`, `language`, and base64 PCM (`pcm_b64`). Produced by
two capture paths that both converge on the same endpoint: the capture agent
(Silero VAD) and the browser microphone (RMS VAD).

**Transcript** — the normalised text result of transcribing a chunk. In code it
is the `Transcript` dataclass in `backend/ws/asr.py`: text, provider, language,
speaker, and the three raw confidence metrics. Distinct from the raw per-vendor
response dict an adapter parses internally.

**Case sheet** — the structured clinical record extracted from the transcript:
the map of field-key → value (`answers`), plus the set of manually confirmed
fields. Persisted as a `VitalsSnapshot` and a `Patient` row.

**Confirmed lock** — a per-field flag the backend owns (the `confirmed` map in
WS broadcasts; `_confirmed` in the `MergeEngine` snapshot). Once set, later
auto-fill never overwrites that cell; the UI renders it differently and never
re-sends the value until cleared by a session reset.

**Pending value** — a value auto-filled from speech that no human has vouched
for yet. The UI's meaning for blue rendering: "the scribe wrote this, check it."

**Field tile** — the card the case-sheet form renders per schema field: slate
(empty), blue (pending), or brand-teal with an OK mark (confirmed lock set).

**Live window** — the bounded tail (last `local_fill_window_chunks` chunks) that
a per-chunk enrichment round re-scans. Narrowing it only limits how far back a
live correction can be picked up: the sheet never forgets an earlier fill, and
finalize always re-scans the full transcript.

**Local fill** — the offline, regex-based bilingual extractor
(`backend/engine/local_fill.py`). Runs on every chunk and on finalize; costs no
API quota. Sets most fields without any model call.

**Prompt echo** — a hallucination where Whisper, handed near-silence, regurgitates
the domain vocabulary (`hi_prompt_terms`) it was given as a decoding prompt
instead of returning nothing. Confidently wrong (clears every confidence gate),
so it is caught by comparing the output against the prompt
(`is_prompt_echo`), not by gating.

## Architecture

**ASR failover module** — `backend/ws/asr.py`. The one interface the rest of the
app uses to turn audio into a `Transcript`: `AsrFailover.transcribe(...)`. Owns
provider ordering, passing the prompt `context`, availability, the
minimum-chunk-length policy, transient retry, and normalisation to a single
`Transcript`. Callers never see a provider's own response shape.

**Provider** (a.k.a. **transcript adapter**) — one concrete ASR engine behind the
ASR failover module's seam. There are five: Groq (`groq`), Sarvam (`sarvam`),
Bhashini (`bhashini`), IndicConformer (`indicconformer`), and local
faster-whisper (`local`). Each satisfies the seam: `name`, `priority`,
`min_chunk_ms`, `available`, `supports(language)`, and
`transcribe_chunk(pcm_b64, language, duration_ms, context)` returning the parsed
dict or raising `AsrError`.

**Specialist** — a provider that claims a language via `supports(language)`, so
the failover tries it *before* the general providers. IndicConformer is the
specialist for the Bihari/Maithili family (`mai`, `mag`, `bho`, `vajjika`); the
rest are generalists.

**Seam** — the adapter interface above. The five providers are implementations
behind it; they are injected into the module (not constructed by it) so tests
drive the whole failover path with fakes.

**MergeEngine** — `backend/engine/merge.py`. Combines extraction results into the
case sheet with latest-wins semantics; a manually set field is locked against
ASR overwrite.

**Enrichment module** — `backend/engine/enrichment.py`. The one interface turning
accumulated per-chunk transcripts into the case sheet:
`Enrichment.enrich(transcripts, mode) -> EnrichResult`. Owns the
live-window-vs-full-transcript decision, merge ordering (local fill before the
extract), the extraction seam, and validation. `live` scans the live window and
merges with the passed `chunk_id`; `final` scans the full join, merges once with
`-1`, calls the extractor at most once on a non-blank join, and validates.

**Extraction adapter** — one concrete implementation behind the enrichment
module's seam (`FieldExtractor`): a `name` plus
`async extract(transcript) -> dict` of field keys to values. Two exist:
`GeminiExtractor` (real, runs at finalize) and `OfflineExtractor`. Injected by
`ChunkSession`, never constructed by the module.

**Encounter repository** — `backend/db/repository.py`. The one module owning the persistence write path: the idempotent replace (delete-then-insert across the five ORM models), the answers→`Patient` column mapping, and the DPDP deletion-audit row. Callers (`finalize`, the dashboard `save` branch) pass a snapshot and receive a `SavedEncounter`; the repository never constructs its own session.

**Session factory (seam)** — the injected `Callable[[], Session]` the repository binds to. Two implementations satisfy it without an adapter: the configured `SessionLocal` (Postgres/SQLite, real) and the per-test SQLite factory. The repository never imports `db.connection`, so an instance is not bound to how the app read its config.

**Idempotent replace** — a repeat save for the same encounter deletes the previous child rows (by `encounter_id`) and the encounter row (by `id`), then writes fresh ones. Save twice and there are no duplicate rows and no orphaned utterances/vitals. Deletion-audit rows are deliberately NOT replaced — each audit records one deletion event.

**Deletion audit** — the `audio_deletion_logs` row written by the repository when a save actually deleted audio (`deleted_chunk_ids is not None`, including an empty list). The row-keeping is the module's; the deletion *policy* (whether this save deleted audio, and which chunks) stays with the caller (`ChunkSession.finalize`).

**SavedEncounter** — the repository's single normalised output: `encounter_id` (the effective id, minted server-side when the caller passed an empty one) and `patient_id` (what the dashboard `save_result` needs without a second read).

**Protocol module** — `backend/ws/protocol.py`. Owns every message shape on the
WebSocket wire: backend→client events built by constructors, client→backend
commands parsed through one parser, and the typeless chunk-audio payload with
its declared key union. `handler.py` may hold no quoted wire names at all; the
module is the only home of a shape.

**Event / Command** — a backend→client message (event) or client→backend message
(command) declared in the protocol module's canonical tables. Every shape a
client uses is a canonical member, and no canonical member goes unused without a
recorded reason.

**Chunk data message** — the typeless audio payload on `/ws/chunks`: the union of
keys the two capture paths send (agent plus browser diagnostics) plus
`encounter_id`. Parsed through `parse_chunks_message`, which passes the payload
through untouched.

**Voice metrics** — `voice_level` and `vad` live on `chunk_result` (and nowhere
else); `level` is the only key on `voice_activity`. The one-home invariant is
test-enforced.

**Conformance sweep** — the fixed-string scan in `backend/test_protocol.py` that
pins every wire name the external clients (App.jsx, useBrowserMic.js,
capture-agent/streamer.py, plus the e2e page objects) send or consume to the
protocol module's canonical set. It is the stand-in for code generation: the
contract stays in one place, and drift shows up as a red test, not a runtime
silent-degradation.
