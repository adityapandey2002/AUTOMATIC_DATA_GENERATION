"""Unit tests for the encounter repository (backend/db/repository.py).

Run:  venv\\Scripts\\python.exe test_repository.py

Pure-unit against a throwaway SQLite file (no Postgres, no mic, no running
backend). The seam under test is the injected session factory: the same
repository class binds to a SQLite factory here and to the real
SessionLocal in production.

Covers:
  * save -> read back: encounter, utterances, vitals snapshot, patient, alerts
  * answers -> Patient column mapping (verbatim semantics)
  * idempotent replace: a repeat save leaves no duplicate rows / orphans
  * deletion-audit policy: None writes no row; [] or [ids] writes exactly one
  * empty encounter_id is minted server-side and adopted by the caller
"""
from __future__ import annotations

import os
import sqlite3
import sys
import tempfile
from pathlib import Path

BACKEND = Path(__file__).resolve().parent
sys.path.insert(0, str(BACKEND))

_tmpdb = Path(tempfile.gettempdir()) / "opencode_repo_test.db"
if _tmpdb.exists():
    _tmpdb.unlink()
os.environ["DATABASE_URL"] = f"sqlite:///{_tmpdb.as_posix()}"
os.environ["LLM_FINAL_EXTRACT"] = "false"

from db.connection import init_db  # noqa: E402
init_db()

from db.connection import SessionLocal  # noqa: E402
from db.models import (  # noqa: E402
    Alert, AudioDeletionLog, Encounter, Patient, Utterance, VitalsSnapshot,
)
from db.repository import EncounterRepository, SavedEncounter  # noqa: E402
from engine.validate import ValidationAlert  # noqa: E402

_results: list[tuple[str, str]] = []


def check(name: str, actual, expected) -> None:
    ok = actual == expected
    _results.append(("PASS" if ok else "FAIL", name))
    if not ok:
        print(f"  FAIL {name}\n       expected: {expected!r}\n       actual:   {actual!r}")


def _session():
    return SessionLocal()


def _count(model, encounter_id=None):
    db = _session()
    try:
        q = db.query(model)
        if encounter_id is not None:
            q = q.filter(model.encounter_id == encounter_id)
        return q.count()
    finally:
        db.close()


def _repo():
    return EncounterRepository(SessionLocal)


def main() -> int:
    import traceback

    # --- 1. basic round trip ---------------------------------------------
    repo = _repo()
    snapshot = {
        "answers": {"name": "शिवानी", "age": "22", "delivery_mode": "Normal",
                    "contact_phone": "9999999999", "tags": ["a", "b"]},
        "_confirmed": {"name": True},
    }
    alerts = [ValidationAlert(field="age", message="ok", severity="warning")]
    transcript = ["chunk one", "chunk two"]

    outcome = repo.save(
        encounter_id="enc-1",
        transcript=transcript,
        snapshot=snapshot,
        alerts=alerts,
    )
    check("save: returns SavedEncounter", isinstance(outcome, SavedEncounter), True)
    check("save: encounter_id adopted", outcome.encounter_id, "enc-1")
    check("save: patient_id present", outcome.patient_id is not None, True)

    db = _session()
    try:
        enc = db.query(Encounter).filter(Encounter.id == "enc-1").one()
        check("roundtrip: encounter row", enc.id, "enc-1")
        check("roundtrip: utterances count", db.query(Utterance).filter(Utterance.encounter_id == "enc-1").count(), 2)
        u0 = db.query(Utterance).filter(Utterance.encounter_id == "enc-1", Utterance.chunk_id == 0).one()
        check("roundtrip: utterance 0 text", u0.transcript, "chunk one")
        check("roundtrip: utterance 1 text", db.query(Utterance).filter(Utterance.encounter_id == "enc-1", Utterance.chunk_id == 1).one().transcript, "chunk two")
        vs = db.query(VitalsSnapshot).filter(VitalsSnapshot.encounter_id == "enc-1").one()
        check("roundtrip: vitals answers", vs.data["answers"]["name"], "शिवानी")
        check("roundtrip: vitals confirmed", vs.data["confirmed"], {"name": True})
        pat = db.query(Patient).filter(Patient.encounter_id == "enc-1").one()
        check("roundtrip: patient name", pat.name, "शिवानी")
        check("roundtrip: patient age", pat.age, 22)
        check("roundtrip: patient answers keeps list", pat.answers["tags"], ["a", "b"])
        check("roundtrip: patient answers has name", "name" in pat.answers, True)
        check("roundtrip: alert row", db.query(Alert).filter(Alert.encounter_id == "enc-1").count(), 1)
        al = db.query(Alert).filter(Alert.encounter_id == "enc-1").one()
        check("roundtrip: alert field", al.field, "age")
        check("roundtrip: alert severity", al.severity, "warning")
    finally:
        db.close()

    # --- 2. answers -> Patient mapping semantics ---------------------------
    repo2 = _repo()
    snap2 = {
        "answers": {"name": None, "age": "not-a-number", "contact_phone": "",
                    "tags": ["x", "y", "z"], "spouse_parent_of": None},
        "_confirmed": {},
    }
    repo2.save(encounter_id="enc-2", transcript=[], snapshot=snap2, alerts=[])
    db = _session()
    try:
        pat = db.query(Patient).filter(Patient.encounter_id == "enc-2").one()
        check("mapping: name None stays None", pat.name, None)
        check("mapping: unparseable age -> None", pat.age, None)
        check("mapping: blank contact -> None (str of '')? ", pat.contact_phone, "")
        check("mapping: list kept in answers", pat.answers["tags"], ["x", "y", "z"])
        # all-None keys dropped from stored answers
        check("mapping: None keys dropped", "name" in pat.answers, False)
        check("mapping: spouse None dropped", "spouse_parent_of" in pat.answers, False)
    finally:
        db.close()

    # age: float-string -> int
    repo3 = _repo()
    repo3.save(encounter_id="enc-3", transcript=[], snapshot={"answers": {"age": "22.9"}, "_confirmed": {}}, alerts=[])
    db = _session()
    try:
        check("mapping: float-string age -> int", db.query(Patient).filter(Patient.encounter_id == "enc-3").one().age, 22)
    finally:
        db.close()

    # --- 3. idempotent replace -------------------------------------------
    before_u = _count(Utterance, "enc-1")
    before_a = _count(Alert, "enc-1")
    before_v = _count(VitalsSnapshot, "enc-1")
    before_p = _count(Patient, "enc-1")
    repo.save(encounter_id="enc-1", transcript=["only one now"], snapshot=snapshot, alerts=[])
    check("idempotent: utterances not duplicated", _count(Utterance, "enc-1"), 1)
    check("idempotent: alerts replaced (not appended)", _count(Alert, "enc-1"), 0)
    check("idempotent: vitals one row", _count(VitalsSnapshot, "enc-1"), 1)
    check("idempotent: patient one row", _count(Patient, "enc-1"), 1)
    check("idempotent: utterance text updated", _session().query(Utterance).filter(Utterance.encounter_id == "enc-1").one().transcript, "only one now")

    # --- 4. deletion-audit policy ----------------------------------------
    # None -> no row
    repo.save(encounter_id="enc-4", transcript=["t"], snapshot={"answers": {}, "_confirmed": {}}, alerts=[], deleted_chunk_ids=None)
    check("audit: None -> no row", _count(AudioDeletionLog, "enc-4"), 0)
    # [] -> exactly one row (a deletion happened, even of nothing)
    repo.save(encounter_id="enc-5", transcript=["t"], snapshot={"answers": {}, "_confirmed": {}}, alerts=[], deleted_chunk_ids=[])
    check("audit: [] -> one row", _count(AudioDeletionLog, "enc-5"), 1)
    # [ids] -> one row carrying the ids
    repo.save(encounter_id="enc-6", transcript=["t"], snapshot={"answers": {}, "_confirmed": {}}, alerts=[], deleted_chunk_ids=[1, 2, 3])
    db = _session()
    try:
        log = db.query(AudioDeletionLog).filter(AudioDeletionLog.encounter_id == "enc-6").one()
        check("audit: ids persisted", list(log.chunk_ids), [1, 2, 3])
        check("audit: reason", log.deletion_reason, "transcribe_complete")
    finally:
        db.close()
    # repeat save does NOT add a second audit row when deleted_chunk_ids=None
    repo.save(encounter_id="enc-6", transcript=["t2"], snapshot={"answers": {}, "_confirmed": {}}, alerts=[], deleted_chunk_ids=None)
    check("audit: repeat (None) keeps prior row only", _count(AudioDeletionLog, "enc-6"), 1)

    # --- 5. minted id adopted by caller -----------------------------------
    outcome2 = repo.save(encounter_id="", transcript=["hi"], snapshot={"answers": {}, "_confirmed": {}}, alerts=[])
    check("minted: non-empty id returned", bool(outcome2.encounter_id), True)
    check("minted: encounter persisted under minted id", _count(Encounter) > 0, True)
    db = _session()
    try:
        check("minted: row exists", db.query(Encounter).filter(Encounter.id == outcome2.encounter_id).count(), 1)
    finally:
        db.close()

    passed = sum(1 for s, _ in _results if s == "PASS")
    failed = [n for s, n in _results if s != "PASS"]
    print(f"\n{'-' * 58}")
    print(f"{passed} passed, {len(failed)} failed  ({len(_results)} checks)")
    for n in failed:
        print(f"  {n}")
    return 1 if failed else 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception:
        import traceback
        traceback.print_exc()
        raise SystemExit(1)

