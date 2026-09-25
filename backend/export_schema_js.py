"""Export backend/form_schema.py to web/src/formSchema.js (mirror).

Run from backend/:  venv\\Scripts\\python.exe export_schema_js.py
The web app fetches /api/schema at boot; this bundled copy is the fallback.
"""

from __future__ import annotations

import json
from pathlib import Path

from form_schema import FORM_SCHEMA

OUT = Path(__file__).resolve().parent.parent / "web" / "src" / "formSchema.js"

HEADER = """// AUTO-GENERATED from backend/form_schema.py — do not edit by hand.
// Regenerate: cd backend && venv\\Scripts\\python.exe export_schema_js.py
// Bundled mirror used if /api/schema is unreachable; backend is the source of truth.
export const FORM_SCHEMA = """

FOOTER = """

export const ALL_FIELDS = FORM_SCHEMA.sections.flatMap((s) =>
  s.fields.map((f) => ({ ...f, section: s }))
);
"""


def main() -> None:
    payload = json.dumps(FORM_SCHEMA, ensure_ascii=False, indent=2)
    OUT.write_text(HEADER + payload + FOOTER, encoding="utf-8")
    sections = len(FORM_SCHEMA["sections"])
    fields = sum(len(s["fields"]) for s in FORM_SCHEMA["sections"])
    print(f"Wrote {OUT} — {sections} sections, {fields} field entries")


if __name__ == "__main__":
    main()
