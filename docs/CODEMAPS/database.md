# Database Codemap

**Last Updated:** 2026-09-23

SQLAlchemy 2.x models (`backend/db/models.py`) on SQLite (`scribe.db` in repo root per config
default; `.env` sets `sqlite:///./scribe.db` which resolves relative to the backend run dir).
Connection: `backend/db/connection.py` — `engine`, `SessionLocal`, `init_db()` (create_all), `get_db()`.

## Tables / Models

| Table | Model | Key columns | Notes |
|-------|-------|-------------|-------|
| `encounters` | `Encounter` | `id` (UUID str, PK), `created_at`, `clinic_id`, `language_detected`, `status` (active/finalized/confirmed), `consent_given` | parent row; matched by `id` on repeat finalize |
| `patients` | `Patient` | `id`, `encounter_id` (FK), `name`, `age`, `language` | child |
| `utterances` | `Utterance` | `id`, `encounter_id` (FK), `chunk_id`, `speaker`, `transcript`, `language`, `confidence`, `timestamp` | one per transcript chunk |
| `vitals_snapshots` | `VitalsSnapshot` | `id`, `encounter_id` (FK), `timestamp`, `data` (JSON: `{answers, _confirmed}`), `confirmed` | the case sheet snapshot at finalize |
| `alerts` | `Alert` | `id`, `encounter_id` (FK), `timestamp`, `field`, `message`, `severity` (warning/critical), `acknowledged` | validation alerts |
| `audio_deletion_log` | `AudioDeletionLog` | `id`, `encounter_id` (FK), `chunk_ids` (JSON), `deleted_at`, `deletion_reason` | DPDP compliance audit, written by `storage/audio.py::log_deletion()` |

Relationships: `Encounter 1—1 Patient`, `Encounter 1—N Utterance/VitalsSnapshot/Alert`.

## Persistence — `ChunkSession._persist()` in `backend/ws/handler.py`

```
finalize() → local_fill (free) → optional ONE Gemini call → merge → validate
  → _persist(db, snapshot, alerts)
      if encounter_id:
          delete existing rows (children then parent, per model):
            Utterance     where encounter_id == encounter_id
            VitalsSnapshot where encounter_id == encounter_id
            Alert         where encounter_id == encounter_id
            Patient       where encounter_id == encounter_id
            Encounter     where id == encounter_id     (sa_delete)
      insert:
          Encounter(id=encounter_id or None)
          Utterance rows from transcript_buffer
          VitalsSnapshot(data={"answers":..., "confirmed":...}, confirmed=False)
          Alert rows  [field, message, severity]
      db.commit()
  → if audio_delete_after_transcribe: log_deletion(db, encounter_id, chunk_ids)
```

- **Idempotency:** a repeat finalize with the same `encounter_id` deletes old rows first
  (children by `encounter_id`, `Encounter` by `id`) then re-inserts. Fixes
  `sqlite3.IntegrityError: UNIQUE constraint failed: encounters.id`.
- `Encounter` import + delete order: `Utterance`, `VitalsSnapshot`, `Alert`, `Patient`,
  then `Encounter`.
- SQLAlchemy bulk delete used: `from sqlalchemy import delete as sa_delete`.

## Data Flow

```
ASR transcript chunks ──> MergeEngine (in-memory CaseSheetFields, confirmed locks)
       │  live: every chunk → {answers, _confirmed} broadcast to dashboard
finalize() ──> final snapshot persisted to DB (idempotent) ──> audio deletion audit log
```

## Data Rules (extraction → DB)

- Flat schema-key map: keys come from `backend/form_schema.py::FIELD_BY_KEY` (40 fields,
  5 sections), mirrored in `web/src/formSchema.js`.
- `MergeEngine`: latest non-empty value wins unless the field is **confirmed** by the health
  worker (locked).
- `VitalsSnapshot.data` stores the flat `answers` + `_confirmed` maps as-is.

## Related Areas

- [backend.md](backend.md) — extraction pipeline that feeds this DB.
- [frontend.md](frontend.md) — dashboard reads live snapshot, not DB directly.