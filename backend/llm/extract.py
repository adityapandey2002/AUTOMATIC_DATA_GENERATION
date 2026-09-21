"""Gemini Flash — fill the bilingual MCH case sheet from a Q&A conversation.

The health worker (GNM/ANM) asks structured questions; the patient replies in
Hindi / Maithili / Bhojpuri. This module extracts the answer for every schema
field, letting the patient's latest answer win when she corrects herself.
"""

from __future__ import annotations

import json
import logging
from typing import Any, Optional

import google.generativeai as genai

from config import settings
from form_schema import build_schema_prompt_text

logger = logging.getLogger(__name__)

EXTRACTION_PROMPT = """You are filling the official Bihar maternity case sheet from a recorded Q&A conversation at a Primary Health Centre.

CONTEXT
- A health worker (GNM/ANM) asks the pregnant woman questions one by one (name, age, address, husband's name, ANC checkup done or not, previous pregnancies, LMP, complications, etc.).
- The patient answers. Answers may be short ("haan", "tees"), long, or indirect. Speech is Hindi / Maithili / Bhojpuri / code-mixed.

RULES
1. Match each health-worker question to the correct field below, then fill it from the PATIENT's answer.
2. If the patient corrects an earlier answer, the LATEST statement wins.
3. Fill ONLY fields that are clearly mentioned. Leave everything else as null. NEVER guess or infer.
4. Yes/No fields: return exactly "Yes" or "No".
5. Select fields: return exactly one allowed value (from the list).
6. Multiselect: return an array of the allowed values mentioned.
7. Dates as YYYY-MM-DD, times as HH:MM, age as an integer, weight as a number in kg.
8. Numbers and phone numbers: keep digits as spoken (e.g. "9456781234").
9. Return ONLY a JSON object mapping field keys to values (or null). No commentary.

FORM FIELDS
{schema}

TRANSCRIPT
{transcript}
"""


class GeminiExtractor:
    def __init__(self) -> None:
        self._model = None
        if settings.gemini_api_key:
            genai.configure(api_key=settings.gemini_api_key)

    def _get_model(self):
        if self._model is None:
            self._model = genai.GenerativeModel(
                model_name=settings.llm_model,
                generation_config=genai.GenerationConfig(
                    response_mime_type="application/json",
                    temperature=0.0,
                    max_output_tokens=2048,
                ),
            )
        return self._model

    async def extract(self, transcript: str) -> dict:
        """Extract a flat {field_key: value} answer map from the transcript."""
        if not settings.gemini_api_key or not transcript.strip():
            return self._empty_result()

        try:
            model = self._get_model()
            prompt = EXTRACTION_PROMPT.format(
                schema=build_schema_prompt_text(),
                transcript=transcript,
            )
            response = await model.generate_content_async(prompt)
            raw = response.text.strip()
            if raw.startswith("```"):
                raw = raw.strip("`")
                if raw.startswith("json"):
                    raw = raw[4:].strip()
            data = json.loads(raw)
            return self._coerce(data)
        except json.JSONDecodeError as e:
            logger.error("Gemini returned invalid JSON: %s", e)
            return self._empty_result()
        except Exception as e:
            logger.error("Gemini extraction failed: %s", e)
            return self._empty_result()

    def _coerce(self, data: dict) -> dict:
        """Keep only schema keys, lightly coercing numbers."""
        from form_schema import FIELD_BY_KEY

        result: dict[str, Any] = {}
        for key, spec in FIELD_BY_KEY.items():
            if key not in data:
                result[key] = None
                continue
            value = data[key]
            if value is None or value == "":
                result[key] = None
                continue
            if spec["type"] == "number":
                result[key] = self._safe_number(value)
            elif spec["type"] in ("select", "yesno", "time", "date", "text"):
                result[key] = str(value).strip() if str(value).strip().lower() != "null" else None
            elif spec["type"] == "multiselect":
                if isinstance(value, list):
                    result[key] = [str(v) for v in value]
                else:
                    result[key] = [str(value)]
        return result

    @staticmethod
    def _safe_number(value) -> Optional[float]:
        try:
            return float(str(value).replace(",", "").strip())
        except (ValueError, TypeError):
            return None

    @staticmethod
    def _empty_result() -> dict:
        from form_schema import FIELD_BY_KEY

        return {key: None for key in FIELD_BY_KEY}