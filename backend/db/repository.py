"""Encounter persistence — one repository module behind an injected session factory.

The write path used to live in `ChunkSession._persist`, a private session
method spanning five ORM models, reachable only through a live WebSocket
session. It now lives here and is owned exactly once:

  * the **idempotent replace** — a repeat save for the same encounter deletes
    the previous rows (the four children by `encounter_id`, the encounter row
    by its own `id`) and writes fresh ones. Save twice and there are no
    duplicate rows and no orphaned utterances/vitals. Deletion-audit rows are
    deliberately NOT replaced: each audit records one deletion event.
  * the **answers → Patient mapping** (moved verbatim from
    `ChunkSession._patient_from_answers`) — field-key → column semantics are
    clinical data, not plumbing.
  * the **deletion audit** (absorbed from `backend/storage/audio.py`) — the
    module owns the DPDP audit ROW; the caller owns the POLICY of whether this
    save deleted audio (`deleted_chunk_ids`, see `save`).

Seam
----
The session factory is INJECTED, never constructed here: a `SessionLocal`-
shaped callable returning an ORM session. Two implementations already exist
in nature and satisfy this one seam — the Postgres/SQLite `SessionLocal` in
`backend/db/connection.py` (real, what `ChunkSession` composes by default)
and the per-test SQLite factory (what `backend/test_repository.py` and
`test_name_saved.py` set up). No ORM-vs-noORM adapter is needed; the module
never imports `db.connection`, so an instance is not bound to how the app
read its config — the composition site is.

The module reads no config: the `audio_delete_after_transcribe` gate stays in
`ChunkSession.finalize`, exactly like the extraction adapter is chosen at
composition time (ADR-0002) rather than inside the enrichment module.

One normalised output: `save(...) -> SavedEncounter` —
`encounter_id` is the effective id (re-generated when the caller passed an
empty one, which the `finalize` path must then adopt), `patient_id` is what
the dashboard `save_result` needs without a second database read.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Callable, Mapping, Optional, Sequence

from sqlalchemy import delete as sa_delete
from sqlalchemy.orm import Session

from db.models import Alert, AudioDeletionLog, Encounter, Patient, Utterance, VitalsSnapshot
from engine.validate import ValidationAlert

logger = logging.getLogger(__name__)

# The four child models keyed by the encounter; the encounter row itself is
# keyed by its own id. (This is the old `hasattr(model, "encounter_id")`
# branch, made explicit: Encounter is the one model the branch existed for.)
_CHILD_MODELS = (Utterance, VitalsSnapshot, Alert, Patient)


@dataclass(frozen=True)
class SavedEncounter:
    """The repository's one normalised output: the ids a save produced."""

    encounter_id: str
    patient_id: Optional[str]


def _patient_from_answers(answers: Mapping[str, Any], encounter_id: str) -> Patient:
    """Map case-sheet field keys onto the Patient columns.

    Moved VERBATIM from `ChunkSession._patient_from_answers`: a list-valued
    answer is joined with ", ", the age is parsed leniently (float string →
    int, unparseable/blank → None), and all-None keys are dropped from the
    stored `answers` JSON. Field-key → column semantics are clinical data;
    do not invent.
    """
    def s(key):
        v = answers.get(key)
        if v is None:
            return None
        if isinstance(v, list):
            return ", ".join(str(x) for x in v)
        return str(v)

    age_raw = answers.get("age")
    age_val = None
    if age_raw not in (None, ""):
        try:
            age_val = int(float(str(age_raw).strip()))
        except (TypeError, ValueError):
            age_val = None

    return Patient(
        encounter_id=encounter_id,
        name=s("name"),
        age=age_val,
        language=None,
        spouse_parent_of=s("spouse_parent_of"),
        contact_phone=s("contact_phone"),
        address=s("address"),
        district=s("district"),
        block=s("block"),
        health_centre=s("health_centre"),
        answers={k: v for k, v in answers.items() if v is not None},
        saved_at=datetime.utcnow(),
    )


class EncounterRepository:
    """Writes one encounter (sheet + transcript + alerts + audit) at a time."""

    def __init__(self, session_factory: Callable[[], Session]) -> None:
        """Bind the repository to an injected session factory.

        The factory is the seam: any `SessionLocal`-shaped callable that
        returns an ORM session. The module never constructs one itself.
        """
        self._session_factory = session_factory

    def _audit_audio_deletion(
        self,
        db: Session,
        encounter_id: str,
        chunk_ids: Sequence[int],
    ) -> None:
        """Write the DPDP audit row (absorbed verbatim from
        `backend/storage/audio.py::log_deletion`, which this replaces — the
        shared session and the separate commit are both preserved)."""
        ids = list(chunk_ids)
        entry = AudioDeletionLog(
            encounter_id=encounter_id,
            chunk_ids=ids,
            deleted_at=datetime.utcnow(),
            deletion_reason="transcribe_complete",
        )
        db.add(entry)
        db.commit()
        logger.info(
            "Deletion logged: encounter=%s chunks=%d reason=%s",
            encounter_id,
            len(ids),
            "transcribe_complete",
        )

    def save(
        self,
        encounter_id: str,
        transcript: Sequence[str],
        snapshot: Mapping[str, Any],
        alerts: Sequence[ValidationAlert],
        deleted_chunk_ids: Optional[Sequence[int]] = None,
    ) -> SavedEncounter:
        """Replace the stored encounter with exactly this shape; return ids.

        `encounter_id` — the encounter to (re)write. Empty means "generate
        one": the effective id comes back on the result, so the caller can
        adopt it (the `finalize` path always does).

        `transcript` — the accumulated per-chunk transcripts, oldest first
        (`ChunkSession.transcript_buffer` by reference, never mutated). One
        `utterances` row per entry with `chunk_id` = its index.

        `snapshot` — the MergeEngine snapshot: `answers` (→ the
        `vitals_snapshots` data and the `patients` mapping) + `_confirmed`
        (→ the same data payload).

        `alerts` — `ValidationAlert`s from the sheet's own validation run;
        each becomes one `alerts` row (field, message, severity).

        `deleted_chunk_ids` — the chunk ids whose audio THIS save deleted
        (the finalize-after-transcribe path, when its config policy says so);
        passing them writes one DPDP audit row even when the list is empty,
        because the save *was* a deletion. Leave None when no audio was
        deleted at this save (the dashboard save) — then no row is written.
        The row-keeping is the module's; the deletion policy is the caller's.
        """
        db = self._session_factory()
        try:
            if encounter_id:
                for model in _CHILD_MODELS:
                    db.execute(sa_delete(model).where(model.encounter_id == encounter_id))
                db.execute(sa_delete(Encounter).where(Encounter.id == encounter_id))

            encounter = Encounter(id=encounter_id or None)
            db.add(encounter)
            db.flush()
            effective_id = encounter.id

            for i, text in enumerate(transcript):
                db.add(Utterance(
                    encounter_id=effective_id,
                    chunk_id=i,
                    speaker="mixed",
                    transcript=text,
                ))

            db.add(VitalsSnapshot(
                encounter_id=effective_id,
                data={
                    "answers": snapshot["answers"],
                    "confirmed": snapshot["_confirmed"],
                },
                confirmed=False,
            ))

            patient = _patient_from_answers(snapshot["answers"], effective_id)
            db.add(patient)

            for alert in alerts:
                db.add(Alert(
                    encounter_id=effective_id,
                    field=alert.field,
                    message=alert.message,
                    severity=alert.severity,
                ))

            db.commit()
            logger.info(
                "Persisted encounter %s (patient %s) with %d utterances",
                effective_id,
                patient.id,
                len(transcript),
            )

            if deleted_chunk_ids is not None:
                self._audit_audio_deletion(db, effective_id, deleted_chunk_ids)

            return SavedEncounter(encounter_id=effective_id, patient_id=patient.id)
        finally:
            db.close()
