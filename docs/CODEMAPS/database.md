# Database Codemap

**Last Updated:** 2026-09-26

SQLAlchemy 2.x models (`backend/db/models.py`) on PostgreSQL 16 (Docker) / SQLite (local dev).
Connection: `backend/db/connection.py` — `engine`, `SessionLocal`, `init_db()` (create_all), `get_db()`.
**Note:** Uses synchronous SQLAlchemy (`create_engine`, `datetime.utcnow`) despite `asyncpg` in requirements.

## Tables / Models (6 tables)

| Table | Model | Key columns | Notes |
|-------|-------|-------------|-------|
| `encounters` | `Encounter` | `id` (UUID str, PK), `created_at`, `clinic_id` (default '', **never written**), `language_detected`, `status` (active/finalized/confirmed — plain string, no CHECK constraint), `consent_given` (default false, **never set to true**) | parent row; matched by `id` on repeat finalize |
| `patients` | `Patient` | `id`, `encounter_id` (FK), `name`, `age`, `language`, `spouse_parent_of`, `contact_phone`, `address`, `district`, `block`, `health_centre`, `answers` (JSON, default {} — the full 181-field case sheet), `saved_at` | 1:1 with Encounter (`uselist=False`) |
| `utterances` | `Utterance` | `id`, `encounter_id` (FK), `chunk_id`, `speaker` (patient/gnm/unknown), `transcript`, `language`, `confidence`, `timestamp` | one per transcript chunk; `chunk_id` has **no uniqueness constraint** |
| `vitals_snapshots` | `VitalsSnapshot` | `id`, `encounter_id` (FK), `timestamp`, `data` (JSON: `{answers, _confirmed}`), `confirmed` (default false) | the case sheet snapshot at finalize; time-series JSON blobs |
| `alerts` | `Alert` | `id`, `encounter_id` (FK), `timestamp`, `field`, `message`, `severity` (warning/critical), `acknowledged` (default false, **never set to true**) | clinical validation alerts |
| `audio_deletion_log` | `AudioDeletionLog` | `id`, `encounter_id` (FK), `chunk_ids` (JSON), `deleted_at`, `deletion_reason` (default 'transcribe_complete') | DPDP compliance audit, written by `db/repository.py::EncounterRepository.save()` |

Relationships: `Encounter 1—1 Patient`, `Encounter 1—N Utterance/VitalsSnapshot/Alert/AudioDeletionLog`.

**Key constraints:**
- `clinic_id` declared but never populated or filtered — multi-tenancy scaffolded only
- `Encounter.consent_given` defaults false, nothing ever sets it true
- `Alert.acknowledged` exists but no code path ever sets it true
- `Utterance.chunk_id` has no uniqueness constraint — re-sent chunks can duplicate rows
- No Alembic — hand-rolled `_migrate_schema()` in `connection.py` does additive `ALTER TABLE ... ADD COLUMN IF NOT EXISTS` only

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

- Flat schema-key map: keys come from `backend/form_schema.py::FIELD_BY_KEY` (181 unique fields / 30 sections / 205 declarations), mirrored in `web/src/formSchema.js`.
- `MergeEngine`: latest non-empty value wins unless the field is **confirmed** by the health
  worker (locked).
- `VitalsSnapshot.data` stores the flat `answers` + `_confirmed` maps as-is.

## Related Areas

- [backend.md](backend.md) — extraction pipeline that feeds this DB.
- [frontend.md](frontend.md) — dashboard reads live snapshot, not DB directly.