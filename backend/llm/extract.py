"""Gemini Flash — fill the bilingual MCH case sheet from a Q&A conversation.

The health worker (GNM/ANM) asks structured questions; the patient replies in
Hindi / Maithili / Bhojpuri. This module extracts the answer for every schema
field, letting the patient's latest answer win when she corrects herself.
"""

from __future__ import annotations

import asyncio
import json
import logging
import random
from typing import Any, Optional

from google import genai
from google.genai import types

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

MAX_ATTEMPTS = 4
BASE_RETRY_MS = 1000
MAX_RETRY_MS = 30000
_RETRYABLE_STATUS = {429, 500, 502, 503, 504}


class GeminiExtractor:
    def __init__(self) -> None:
        self._client = None
        self._model_id = None

    def _get_client(self):
        if self._client is None:
            self._client = genai.Client(api_key=settings.gemini_api_key)
            self._model_id = settings.llm_model
        return self._client

    async def extract(self, transcript: str) -> dict:
        """Extract a flat {field_key: value} answer map from the transcript."""
        if not settings.gemini_api_key or not transcript.strip():
            return self._empty_result()

        client = self._get_client()
        prompt = EXTRACTION_PROMPT.format(
            schema=build_schema_prompt_text(),
            transcript=transcript,
        )
        config = types.GenerateContentConfig(
            response_mime_type="application/json",
            temperature=0.0,
            max_output_tokens=2048,
        )

        delay_ms = BASE_RETRY_MS
        for attempt in range(1, MAX_ATTEMPTS + 1):
            try:
                response = await client.aio.models.generate_content(
                    model=self._model_id,
                    contents=prompt,
                    config=config,
                )
                return self._handle_response(response)
            except Exception as e:
                status = getattr(e, "status", None) or getattr(
                    e, "status_code", None
                )
                if isinstance(status, int) and status not in _RETRYABLE_STATUS:
                    logger.error("Gemini extraction failed: %s", e)
                    return self._empty_result()
                if attempt == MAX_ATTEMPTS:
                    logger.error(
                        "Gemini extraction failed after %d attempts: %s",
                        MAX_ATTEMPTS,
                        e,
                    )
                    return self._empty_result()
                jitter = random.uniform(0.5, 1.5)
                sleep_ms = min(delay_ms * jitter, MAX_RETRY_MS)
                logger.warning(
                    "Gemini extraction attempt %d/%d failed (%s); retrying in %.1fs",
                    attempt,
                    MAX_ATTEMPTS,
                    type(e).__name__,
                    sleep_ms / 1000,
                )
                await asyncio.sleep(sleep_ms / 1000)
                delay_ms = min(delay_ms * 2, MAX_RETRY_MS)

        return self._empty_result()

    def _handle_response(self, response) -> dict:
        raw = (response.text or "").strip()
        if raw.startswith("```"):
            raw = raw.strip("`")
            if raw.startswith("json"):
                raw = raw[4:].strip()
        try:
            data = json.loads(raw)
        except json.JSONDecodeError as e:
            logger.error("Gemini returned invalid JSON: %s", e)
            return self._empty_result()
        return self._coerce(data)

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