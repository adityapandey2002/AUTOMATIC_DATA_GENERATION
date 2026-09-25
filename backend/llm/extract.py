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
import re
from datetime import date
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

MAX_ATTEMPTS = 3
BASE_RETRY_MS = 1000
MAX_RETRY_MS = 30000
MAX_SERVER_WAIT_S = 15.0
_RETRYABLE_STATUS = {429, 500, 502, 503, 504}

# Free-tier Gemini quotas are PER PROJECT + PER MODEL + per day/minute. Once
# gemini-3.5-flash's 20 req/day pool is spent, a different model still has its
# own untouched pool; fail over instead of dead-ending till midnight.
FALLBACK_MODELS = (
    "gemini-3.6-flash",
    "gemini-3.7-flash",
    "gemini-3.5-flash-lite",
)

# model id -> ISO date when its per-day quota was observed exhausted.
_daily_quota_blocked: dict[str, str] = {}

# Models the API reports as retired/forbidden (404/403) - skip forever.
_permanently_unavailable: set[str] = set()


def _http_code(exc: Exception) -> Optional[int]:
    """Numeric HTTP status code, if the exception carries one.

    google-genai APIError.status is the STRING reason ('RESOURCE_EXHAUSTED');
    APIError.code is the int status (429, 500, ...). The previous retry check
    read .status, so even permanent 4xx errors were retried 4 times.
    """
    code = getattr(exc, "code", None)
    if isinstance(code, int):
        return code
    code = getattr(exc, "status_code", None)
    return code if isinstance(code, int) else None


def _quota_period(exc: Exception) -> Optional[str]:
    """'day' | 'minute' | 'hour' | None from a 429 body naming the metric."""
    if _http_code(exc) != 429:
        return None
    blob = f"{exc} {getattr(exc, 'details', '')}"
    if "PerDay" in blob:
        return "day"
    if "PerMinute" in blob:
        return "minute"
    if "PerHour" in blob:
        return "hour"
    return None


def _server_retry_delay_s(exc: Exception) -> Optional[float]:
    """Seconds from the API-provided 'retryDelay' ('3.9s'/'24s'), if any."""
    found: list[float] = []

    def walk(node) -> None:
        if isinstance(node, dict):
            for key, val in node.items():
                if key == "retryDelay" and isinstance(val, str):
                    m = re.search(r"(\d+(?:\.\d+)?)", val)
                    if m:
                        found.append(float(m.group(1)))
                else:
                    walk(val)
        elif isinstance(node, list):
            for item in node:
                walk(item)

    walk(getattr(exc, "details", None))
    return max(found) if found else None


def _quota_metric(exc: Exception) -> str:
    m = re.search(r"metric:\s*([^\s,]+)", f"{exc}")
    return m.group(1) if m else "unknown"


def _mark_daily_quota_blocked(model: str) -> None:
    _daily_quota_blocked[model] = date.today().isoformat()


def _is_daily_quota_blocked(model: str) -> bool:
    return _daily_quota_blocked.get(model) == date.today().isoformat()



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
            # SDK default request timeout is ~300s; a hung model call would
            # stall finalize() for minutes. Bound each request explicitly.
            http_options=types.HttpOptions(timeout=30000),
            # Plain text->JSON call with no tools: keep SDK 2.x from enabling
            # AFC (which logs 'AFC is enabled' + a warning on every attempt).
            automatic_function_calling=types.AutomaticFunctionCallingConfig(
                disable=True
            ),
        )

        for model in dict.fromkeys([settings.llm_model, *FALLBACK_MODELS]):
            if model in _permanently_unavailable:
                continue
            if _is_daily_quota_blocked(model):
                logger.info(
                    "Gemini skipping %s: daily quota exhausted earlier today",
                    model,
                )
                continue
            result = await self._extract_with_model(client, model, prompt, config)
            if result is not None:
                return result
            # None => that model's PER-DAY pool is spent. A different model has
            # its own pool, so fail over immediately instead of retrying into a
            # quota that will not recover for hours.
        logger.error("Gemini extraction unavailable: no model has quota today")
        return self._empty_result()

    async def _extract_with_model(
        self, client, model: str, prompt: str, config
    ) -> Optional[dict]:
        """Bounded attempts on ONE model. None => fail over to the next one."""
        delay_ms = BASE_RETRY_MS
        for attempt in range(1, MAX_ATTEMPTS + 1):
            try:
                response = await client.aio.models.generate_content(
                    model=model,
                    contents=prompt,
                    config=config,
                )
            except Exception as e:
                code = _http_code(e)
                if code is None:
                    # Transport-level failure (request timeout / connection
                    # error): the endpoint itself is unhealthy. Move on.
                    logger.warning(
                        "Gemini %s request failed without HTTP status (%s); "
                        "failing over",
                        model,
                        type(e).__name__,
                    )
                    return None
                if code not in _RETRYABLE_STATUS:
                    logger.error(
                        "Gemini extraction failed (HTTP %s, not retryable): %s",
                        code,
                        e,
                    )
                    if code in (403, 404):
                        _permanently_unavailable.add(model)
                    return self._empty_result()

                period = _quota_period(e)
                if code == 429 and period == "day":
                    # Per-day quota: retrying is pointless. Every attempt just
                    # burns another request against a pool that only resets at
                    # midnight and adds seconds of latency to finalize().
                    logger.error(
                        "Gemini %s daily quota exhausted (%s) - not retrying; failing over",
                        model,
                        _quota_metric(e),
                    )
                    _mark_daily_quota_blocked(model)
                    return None

                if attempt == MAX_ATTEMPTS:
                    logger.error(
                        "Gemini extraction failed on %s after %d attempts: %s",
                        model,
                        MAX_ATTEMPTS,
                        e,
                    )
                    return None  # next model has a different quota pool

                server_wait = _server_retry_delay_s(e)
                if server_wait is not None:
                    # Honour the API's own retryDelay (per-minute limits ask
                    # for 12-24s; a 1-2s backoff just re-429s immediately).
                    sleep_s = min(server_wait, MAX_SERVER_WAIT_S)
                else:
                    jitter = random.uniform(0.5, 1.5)
                    sleep_s = min(delay_ms * jitter, MAX_RETRY_MS) / 1000
                    delay_ms = min(delay_ms * 2, MAX_RETRY_MS)
                logger.warning(
                    "Gemini extraction attempt %d/%d on %s failed (%s); retrying in %.1fs",
                    attempt,
                    MAX_ATTEMPTS,
                    model,
                    code or type(e).__name__,
                    sleep_s,
                )
                await asyncio.sleep(sleep_s)

        return None

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
            elif spec["type"] == "table":
                # Post-delivery vitals grid: {"row|column": value}
                if isinstance(value, dict):
                    result[key] = {
                        str(k): str(v) for k, v in value.items()
                        if v not in (None, "")
                    } or None
                else:
                    result[key] = None
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