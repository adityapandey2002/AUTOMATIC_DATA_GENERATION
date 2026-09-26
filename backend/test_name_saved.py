"""End-to-end proof that a finalize/save writes the patient's NAME.

The complaint was "case sheet should be saved with names". Extraction is only
half of it: the row in `patients` also has to come out right, since
`Handler._build_patient` maps answers -> columns.

Runs against a throwaway SQLite file so a live encounter is never touched, and
with Gemini disabled so it spends no quota. The transcripts are the exact
chunks from the reported session.
"""

from __future__ import annotations

import asyncio
import os
import sqlite3
import sys
import tempfile
from pathlib import Path

BACKEND = Path(__file__).resolve().parent
sys.path.insert(0, str(BACKEND))

# Must be set before anything imports config/db.
_tmpdb = Path(tempfile.gettempdir()) / "opencode_name_save_test.db"
if _tmpdb.exists():
    _tmpdb.unlink()
os.environ["DATABASE_URL"] = f"sqlite:///{_tmpdb.as_posix()}"
os.environ["LLM_FINAL_EXTRACT"] = "false"  # no Gemini quota for this check

from db.connection import init_db  # noqa: E402
from ws.handler import ChunkSession  # noqa: E402

# Verbatim from the reported live session.
CHUNKS = [
    " चलो तुम बताओ तुमारा नाम क्या है? मेरा नाम शिवानी",
    " सामान्य एलएमपी",
    " चलो बताओ तुमारों नाम क्या है? शिवानी प्रसव नंबर क्या है?",
]


def main() -> int:
    init_db()
    session = ChunkSession()
    session.reset("name-save-check")
    session.active = True
    # Bypass ASR: these are the transcripts Groq already returned.
    session.transcript_buffer = list(CHUNKS)
    session.chunk_ids = list(range(len(CHUNKS)))

    result = asyncio.run(session.finalize())

    print("=== finalize() answers ===")
    for k, v in result["answers"].items():
        print(f"  {k:20} {v!r}")

    conn = sqlite3.connect(_tmpdb)
    conn.row_factory = sqlite3.Row
    rows = list(conn.execute("SELECT * FROM patients"))
    print(f"\n=== patients rows: {len(rows)} ===")
    ok = True
    for r in rows:
        print(f"  name              {r['name']!r}")
        print(f"  age               {r['age']!r}")
        print(f"  answers           {r['answers']!r}")
        if r["name"] != "शिवानी":
            ok = False
        if "सामान्य" in (r["name"] or ""):
            ok = False
        if "प्रसव" in (r["name"] or ""):
            ok = False
    if not rows:
        print("  FAIL  no patient row written at all")
        return 1

    print()
    if ok:
        print("  PASS  patients.name is exactly the spoken name, unpolluted")
        return 0
    print("  FAIL  saved name is wrong or polluted")
    return 1


if __name__ == "__main__":
    code = main()
    try:
        _tmpdb.unlink()
    except OSError:
        pass
    raise SystemExit(code)
