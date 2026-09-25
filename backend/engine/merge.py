"""Incremental Q&A field merge — never overwrite confirmed fields.

The case sheet is a flat set of fields. Each extraction round contributes
values; the LATER value wins for a field unless it has been confirmed by the
health worker (latest statement wins on self-correction, confirmed locks).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from form_schema import FIELD_BY_KEY


@dataclass
class FieldState:
    value: Any = None
    source_chunk_id: int = -1
    confirmed: bool = False


@dataclass
class CaseSheetFields:
    states: dict[str, FieldState] = field(
        default_factory=lambda: {key: FieldState() for key in FIELD_BY_KEY}
    )

    def to_snapshot(self) -> dict:
        answers = {}
        confirmed = {}
        for key, st in self.states.items():
            if not self._empty(st.value):
                answers[key] = st.value
            else:
                answers[key] = None
            if st.value is not None and st.confirmed:
                confirmed[key] = True
        return {
            "answers": answers,
            "_confirmed": confirmed,
        }

    @staticmethod
    def _empty(value: Any) -> bool:
        if value is None:
            return True
        if isinstance(value, str):
            return value.strip() == ""
        if isinstance(value, (list, tuple, dict)):
            return len(value) == 0
        return False


class MergeEngine:
    def __init__(self) -> None:
        self.fields = CaseSheetFields()

    def reset(self) -> None:
        self.fields = CaseSheetFields()

    def merge(self, extracted: dict, chunk_id: int) -> None:
        """Merge an extracted answer map into the sheet."""
        for key, spec in FIELD_BY_KEY.items():
            value = extracted.get(key)
            if value is None:
                continue
            if self._empty(value):
                continue
            state = self.fields.states[key]
            if state.confirmed:
                # Manual edits (set_field) lock the cell; a later auto-fill
                # may still replace a value the health worker never touched,
                # but never one they typed by hand.
                continue
            # Latest statement wins (self-correction handled by Gemini ordering),
            # but a fresh mention always replaces the draft.
            state.value = value
            state.source_chunk_id = chunk_id

    def confirm(self, field_name: str) -> bool:
        state = self.fields.states.get(field_name)
        if state is not None and state.value is not None:
            state.confirmed = True
            return True
        return False

    def set_field(self, field_name: str, value: Any) -> bool:
        """Manual edit from the UI: overwrite value and lock against ASR."""
        if field_name not in FIELD_BY_KEY:
            return False
        state = self.fields.states[field_name]
        state.value = value
        state.confirmed = True
        state.source_chunk_id = -1
        return True

    def get_snapshot(self) -> dict:
        return self.fields.to_snapshot()

    @staticmethod
    def _empty(value: Any) -> bool:
        if value is None:
            return True
        if isinstance(value, str):
            return value.strip() == ""
        if isinstance(value, (list, tuple, dict)):
            return len(value) == 0
        return False