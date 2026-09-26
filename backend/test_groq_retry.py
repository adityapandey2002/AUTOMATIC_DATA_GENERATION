"""Unit tests for the Groq ASR retry/observability contract.

Run:  venv\\Scripts\\python.exe test_groq_retry.py

Pure-unit: httpx.AsyncClient is faked, so nothing here touches the network or
spends Groq quota.

Why this file exists. A live session logged

    16:21:35 Chunk 3 received
    16:21:54 [ERROR] ws.groq_asr: Groq transcription failed:

and then went silent for the rest of the encounter. Two defects were tangled
together:

  1. No retry. Every other provider was inert (IndicConformer needs NeMo,
     Sarvam/Bhashini need keys, local faster-whisper needed a 461MB download),
     so Groq was the only working engine and a single dropped request lost that
     chunk for good. Recording continued, transcription did not.
  2. Undiagnosable logging. `logger.error("...: %s", e)` prints str(e), and
     several httpx/asyncio exceptions stringify to the empty string -- hence the
     bare colon above. The exception TYPE is now always included.

Covers:
  * transient failures (timeout, 429, 5xx) are retried and recover
  * non-transient 4xx is NOT retried (it is a credential/config problem)
  * retries are bounded and then return the empty result, never a fake one
  * an empty-message exception is still labelled with its type
  * the pre-flight short-circuits still make zero network calls
"""

from __future__ import annotations

import asyncio
import base64
import json
import logging
import sys
import traceback
from pathlib import Path
from unittest import mock

BACKEND = Path(__file__).resolve().parent
sys.path.insert(0, str(BACKEND))

from config import settings  # noqa: E402
from ws import groq_asr  # noqa: E402
from ws.groq_asr import GroqWhisperASR  # noqa: E402

_results: list[tuple[str, str]] = []


def check(name: str, actual, expected) -> None:
    ok = actual == expected
    _results.append(("PASS" if ok else "FAIL", name))
    if not ok:
        print(f"  FAIL {name}\n       expected: {expected!r}\n       actual:   {actual!r}")


# --- fakes -----------------------------------------------------------------

_OK_BODY = {
    "text": " मेरा नाम शिवानी",
    "segments": [
        {
            "start": 0.0,
            "end": 2.0,
            "text": " मेरा नाम शिवानी",
            "avg_logprob": -0.21,
            "no_speech_prob": 0.04,
            "compression_ratio": 1.1,
        }
    ],
}


class _FakeResponse:
    def __init__(self, status_code: int, payload: dict | None = None, text: str = "") -> None:
        self.status_code = status_code
        self._payload = payload if payload is not None else {}
        self.text = text or json.dumps(self._payload, ensure_ascii=False)

    def json(self) -> dict:
        return self._payload


class _FakeClient:
    """Stands in for httpx.AsyncClient; replays a scripted list of outcomes.

    An Exception in the script is raised instead of returned, which is how the
    timeout/reset paths are exercised. The last entry repeats, so a script of
    length 1 means "always this".
    """

    def __init__(self, script: list, calls: list[int], timeouts: list) -> None:
        self._script = script
        self._calls = calls
        self._timeouts = timeouts

    async def __aenter__(self) -> "_FakeClient":
        return self

    async def __aexit__(self, *exc) -> bool:
        return False

    async def post(self, *args, **kwargs):
        self._calls.append(1)
        item = self._script[min(len(self._calls) - 1, len(self._script) - 1)]
        if isinstance(item, BaseException):
            raise item
        return item


def _drive(script: list, duration_ms: int = 6000, api_key: str = "gsk_unit_test_key") -> tuple[dict, int, list]:
    """Run transcribe_chunk against a scripted API and return (result, calls, timeouts)."""
    calls: list[int] = []
    timeouts: list = []

    def factory(timeout=None, **kw):
        timeouts.append(timeout)
        return _FakeClient(script, calls, timeouts)

    pcm = b"\x00\x00" * 16000  # 1s of 16k mono s16
    # Silence the provider logger: on the final attempt groq_asr logs with
    # exc_info=True, which dumps a full traceback per scripted failure. The
    # assertions below read the log records, not the console.
    logger = groq_asr.logger
    prev_level, prev_prop = logger.level, logger.propagate
    logger.setLevel(logging.CRITICAL)
    logger.propagate = False
    try:
        # __init__ snapshots settings.groq_api_key, so both patches must be in
        # place before the object is built.
        with mock.patch.object(groq_asr.httpx, "AsyncClient", factory), mock.patch.object(
            settings, "groq_api_key", api_key
        ), mock.patch.object(settings, "asr_retry_backoff_s", 0.0):
            asr = GroqWhisperASR()
            result = asyncio.run(
                asr.transcribe_chunk(
                    base64.b64encode(pcm).decode("ascii"), language="hi", duration_ms=duration_ms
                )
            )
    finally:
        logger.setLevel(prev_level)
        logger.propagate = prev_prop
    return result, len(calls), timeouts


# --- tests -----------------------------------------------------------------

def test_success_first_attempt() -> None:
    result, calls, _ = _drive([_FakeResponse(200, _OK_BODY)])
    check("happy path: text returned", result["text"], " मेरा नाम शिवानी")
    check("happy path: one call, no retry", calls, 1)


def test_timeout_recovers() -> None:
    """The reported failure: a slow/dropped request must not lose the chunk."""
    script = [httpx_read_timeout(), httpx_read_timeout(), _FakeResponse(200, _OK_BODY)]
    result, calls, _ = _drive(script)
    check("timeout: chunk recovered", result["text"], " मेरा नाम शिवानी")
    check("timeout: took 3 attempts", calls, 3)


def test_rate_limit_retried() -> None:
    script = [
        _FakeResponse(429, text="rate_limit_exceeded"),
        _FakeResponse(429, text="rate_limit_exceeded"),
        _FakeResponse(200, _OK_BODY),
    ]
    result, calls, _ = _drive(script)
    check("429: retried then recovered", result["text"], " मेरा नाम शिवानी")
    check("429: took 3 attempts", calls, 3)


def test_server_error_retried() -> None:
    script = [_FakeResponse(503, text="overloaded"), _FakeResponse(200, _OK_BODY)]
    result, calls, _ = _drive(script)
    check("5xx: retried then recovered", result["text"], " मेरा नाम शिवानी")
    check("5xx: took 2 attempts", calls, 2)


def test_client_error_not_retried() -> None:
    """401 will fail identically every time; retrying only wastes the session."""
    result, calls, _ = _drive([_FakeResponse(401, text="invalid api key")])
    check("401: returns empty result", result["text"], "")
    check("401: NOT retried", calls, 1)


def test_retries_are_bounded() -> None:
    result, calls, _ = _drive([httpx_read_timeout()])
    check("exhausted: empty result, never fabricated text", result["text"], "")
    check("exhausted: bounded at asr_max_attempts", calls, settings.asr_max_attempts)
    check("exhausted: confidence is not a fake number", result["confidence"], 0.0)


def test_empty_exception_is_labelled() -> None:
    """The bare "Groq transcription failed:" line: str(e) was empty.

    The retry must still name the type, otherwise the log is worthless again.
    """
    boom = httpx_read_timeout()
    with mock.patch.object(groq_asr.logger, "error") as err_log, mock.patch.object(
        groq_asr.logger, "warning"
    ):
        _drive([boom, boom, boom])
    blob = " ".join(str(c) for c in err_log.call_args_list)
    check("empty-message exception: type is logged", "ReadTimeout" in blob, True)
    check("empty-message exception: not a bare colon", blob.strip().endswith(":"), False)


def test_timeout_budget_is_bounded() -> None:
    """A 45s timeout x3 would stall a live encounter for over 2 minutes."""
    _, _, timeouts = _drive([_FakeResponse(200, _OK_BODY)])
    check("per-attempt timeout from settings", timeouts[0], settings.asr_timeout_s)
    check("timeout is not the old 45s", timeouts[0] < 45.0, True)


def test_short_chunk_makes_no_call() -> None:
    result, calls, _ = _drive([_FakeResponse(200, _OK_BODY)], duration_ms=200)
    check("short chunk: empty result", result["text"], "")
    check("short chunk: zero network calls", calls, 0)


def test_unconfigured_makes_no_call() -> None:
    """A placeholder key must short-circuit before any socket is opened."""
    # .env on a dev box holds a real key, so the placeholder has to be forced.
    result, calls, _ = _drive([_FakeResponse(200, _OK_BODY)], api_key="your_groq_api_key")
    check("placeholder key: empty result", result["text"], "")
    check("placeholder key: zero network calls", calls, 0)


def httpx_read_timeout() -> BaseException:
    """A timeout exception that stringifies to '' -- the exact logging trap."""
    import httpx

    return httpx.ReadTimeout("", request=None)


def main() -> int:
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    for fn in tests:
        print(f"{fn.__name__}...")
        try:
            fn()
        except Exception:
            _results.append(("ERROR", fn.__name__))
            traceback.print_exc()

    passed = sum(1 for s, _ in _results if s == "PASS")
    failed = [n for s, n in _results if s != "PASS"]
    print(f"\n{'-' * 58}")
    print(f"{passed} passed, {len(failed)} failed  ({len(_results)} checks)")
    for n in failed:
        print(f"  {n}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
