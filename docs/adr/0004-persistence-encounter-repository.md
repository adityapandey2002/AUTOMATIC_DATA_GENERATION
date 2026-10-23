# 0004. Persistence is an injected encounter repository, not a private session method

- **Status:** Accepted
- **Date:** 2026-10-23
- **Related:** ADR-0001, ADR-0002, ADR-0003 (same seam/injection/one-output pattern)

## Context

The write path used to live in `ChunkSession._persist`, a **private** session
method spanning five ORM models (`Encounter`, `Patient`, `Utterance`,
`VitalsSnapshot`, `Alert`), hand-rolled delete-then-insert for idempotency,
the answer-key → `Patient` column mapping (`_patient_from_answers`), a
`hasattr` branch, and a call into `backend/storage/audio.py::log_deletion`.
It was reachable only through a live WebSocket session, so it could not be
tested directly — `test_name_saved.py` proved this by needing the full
session machinery plus a SQLite `DATABASE_URL` hack just to reach it.

## Decision

`backend/db/repository.py` is the module that owns persistence:

- **Interface:** `EncounterRepository.save(encounter_id, transcript, snapshot,
  alerts, deleted_chunk_ids=None) -> SavedEncounter`.
- **Seam:** the **session factory is injected** — a `Callable[[], Session]`
  returning an ORM session. The module never imports `db.connection`, so an
  instance is never bound to how the app read its config. Two implementations
  already exist in nature and satisfy this one seam: the configured
  `SessionLocal` (real) and the per-test SQLite factory.
- **Owned here:** the idempotent replace, the answers → `Patient` mapping
  (moved verbatim — field-key → column semantics are clinical data), and the
  DPDP deletion-audit row (absorbed from the now-deleted one-function module
  `backend/storage/audio.py`).
- **Not owned here:** the audio-deletion **policy** (whether this save deleted
  audio, and which chunks) stays with the caller (`ChunkSession.finalize`);
  the audit *row* is the module's. Same split as "offline mode is an adapter,
  not a settings branch" (ADR-0002): policy at composition, row-keeping in
  the module.
- **Output:** a single normalised `SavedEncounter(encounter_id, patient_id)` —
  the effective id (minted server-side when the caller passed an empty one) and
  the patient id the dashboard `save_result` needs without a second read.

## Consequences

- Persistence becomes testable without a socket or ASR (`backend/test_repository.py`,
  36 checks, SQLite only).
- `ChunkSession` no longer has a `_persist` or `_patient_from_answers` method;
  `_patient_from_answers` lives once, in the module.
- `backend/storage/audio.py` is deleted; its one function is absorbed into the
  save.
- `ChunkSession` receives the repository via its constructor, defaulting to the
  real `SessionLocal`-bound one, so existing construction sites
  (`SessionRegistry`, the offline tests) keep working with no new wiring.

## Alternatives considered

- **Keep the write path as a private session method.** Rejected: it is the
  reason persistence could only be exercised through a live WebSocket, and the
  reason the name test needed the full session machinery plus a SQLite hack.
- **Introduce a Postgres adapter and a SQLite adapter.** Rejected: both already
  speak SQLAlchemy; the only thing that genuinely varies is the session factory,
  which is a callable, not a type. A second adapter would be a hypothetical
  seam (one implementation in production).
- **Let the module decide whether to delete audio.** Rejected: that policy
  depends on `settings.audio_delete_after_transcribe` and on the streamed
  chunk ids, which are session state; the module reading config to special-case
  one behavior is the same mistake ADR-0002 rejected for offline extraction.
