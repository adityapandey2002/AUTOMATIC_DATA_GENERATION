"""Unit tests for the ASR failover module (ws/asr.py).

Run:  venv\\Scripts\\python.exe test_asr_failover.py

Pure-unit: the adapters are fakes, so the whole failover path is exercised with
no network, no API keys, no model download, and no microphone:

  * one normalised Transcript out, whatever shape the adapters speak
  * specialist-first ordering, reproducing the old per-language lists
  * unavailable adapters are skipped
  * the min-chunk policy is the module's, applied uniformly
  * transient failures are retried, permanent ones are not
  * an empty result falls through without retrying
  * `context` reaches every adapter
"""

from __future__ import annotations

import asyncio
import sys
import traceback
from pathlib import Path

BACKEND = Path(__file__).resolve().parent
sys.path.insert(0, str(BACKEND))

from ws.asr import AsrError, AsrFailover, Transcript  # noqa: E402

_results: list[tuple[str, str]] = []


def check(name: str, actual, expected) -> None:
    ok = actual == expected
    _results.append(("PASS" if ok else "FAIL", name))
    if not ok:
        print(f"  FAIL {name}\n       expected: {expected!r}\n       actual:   {actual!r}")


async def _noop_sleep(_seconds: float) -> None:
    return None


def run(failover: AsrFailover, **kw) -> object:
    return asyncio.run(failover.transcribe("AAAA", **kw))


class FakeAdapter:
    """A scripted adapter satisfying the seam.

    `script` is a list of outcomes consumed one per call: a dict is returned, an
    Exception is raised. The last entry repeats.
    """

    def __init__(
        self,
        name: str,
        priority: int,
        script: list | None = None,
        *,
        available: bool = True,
        supports_langs=(),
        min_chunk_ms: int = 0,
    ) -> None:
        self.name = name
        self.priority = priority
        self.min_chunk_ms = min_chunk_ms
        self._available = available
        self._supports = set(supports_langs)
        self._script = list(script) if script else [{"text": ""}]
        self.calls: list[dict] = []

    @property
    def available(self) -> bool:
        return self._available

    def supports(self, language: str) -> bool:
        return language in self._supports

    async def transcribe_chunk(self, pcm_b64, language="hi", duration_ms=None, context=""):
        self.calls.append({"language": language, "duration_ms": duration_ms, "context": context})
        item = self._script[min(len(self.calls) - 1, len(self._script) - 1)]
        if isinstance(item, BaseException):
            raise item
        return item


def _failover(*adapters: FakeAdapter, max_attempts: int = 3) -> AsrFailover:
    return AsrFailover(list(adapters), max_attempts=max_attempts, backoff_s=0.0, sleep=_noop_sleep)


# --- output shape ----------------------------------------------------------

def test_returns_normalised_transcript() -> None:
    a = FakeAdapter("groq", 10, [{
        "text": "नमस्ते",
        "language": "hi",
        "speaker": "patient",
        "avg_logprob": -0.3,
        "no_speech_prob": 0.1,
        "compression_ratio": 1.1,
        "words": [1, 2, 3],  # adapter-specific keys are ignored
    }])
    out = run(_failover(a))
    check("shape: is a Transcript", isinstance(out, Transcript), True)
    check("shape: text", out.text, "नमस्ते")
    check("shape: provider is the adapter name", out.provider, "groq")
    check("shape: language", out.language, "hi")
    check("shape: speaker", out.speaker, "patient")
    check("shape: avg_logprob", round(out.avg_logprob, 3), -0.3)
    check("shape: no_speech_prob", round(out.no_speech_prob, 3), 0.1)
    check("shape: compression_ratio", round(out.compression_ratio, 3), 1.1)
    # There is deliberately no single `confidence` -- the providers disagree on
    # what it means.
    check("shape: no misleading confidence field", hasattr(out, "confidence"), False)


def test_missing_metrics_stay_none() -> None:
    a = FakeAdapter("sarvam", 20, [{"text": "ok", "confidence": 0.9}])
    out = run(_failover(a))
    check("metrics: avg_logprob absent -> None", out.avg_logprob, None)
    check("metrics: no_speech_prob absent -> None", out.no_speech_prob, None)
    check("metrics: adapter 'confidence' is not promoted", hasattr(out, "confidence"), False)


def test_none_when_nothing_succeeds() -> None:
    a = FakeAdapter("groq", 10, [{"text": ""}])
    check("empty everywhere -> None", run(_failover(a)), None)


# --- ordering --------------------------------------------------------------

def test_order_puts_specialist_first() -> None:
    general = FakeAdapter("groq", 10)
    specialist = FakeAdapter("indicconformer", 40, supports_langs=("mai",))
    fo = _failover(general, specialist)
    check("order(mai): specialist first", [a.name for a in fo.order("mai")], ["indicconformer", "groq"])
    check("order(hi): specialist demoted to priority", [a.name for a in fo.order("hi")], ["groq", "indicconformer"])


def test_order_matches_legacy_provider_lists() -> None:
    """The declarative order must reproduce the old hand-written lists exactly."""
    from ws.groq_asr import GroqWhisperASR
    from ws.sarvam_asr import SarvamASR
    from ws.bhashini_asr import BhashiniASR
    from ws.indicconformer_asr import IndicConformerASR
    from ws.local_asr import LocalWhisperASR

    fo = AsrFailover([
        GroqWhisperASR(),
        SarvamASR(),
        BhashiniASR(),
        IndicConformerASR(),
        LocalWhisperASR(),
    ])
    check(
        "order(hi): [groq, sarvam, bhashini, indic, local]",
        [a.name for a in fo.order("hi")],
        ["groq", "sarvam", "bhashini", "indicconformer", "local"],
    )
    check(
        "order(mai): [indic, groq, sarvam, bhashini, local]",
        [a.name for a in fo.order("mai")],
        ["indicconformer", "groq", "sarvam", "bhashini", "local"],
    )


# --- availability and the min-chunk policy ---------------------------------

def test_unavailable_skipped() -> None:
    down = FakeAdapter("groq", 10, available=False)
    up = FakeAdapter("sarvam", 20, [{"text": "from sarvam"}])
    out = run(_failover(down, up))
    check("unavailable: not called", down.calls, [])
    check("unavailable: fell through", out.text, "from sarvam")
    check("unavailable: provider", out.provider, "sarvam")


def test_short_chunk_skips_min_chunk_adapters() -> None:
    needs_1500 = FakeAdapter("groq", 10, [{"text": "x"}], min_chunk_ms=1500)
    any_length = FakeAdapter("sarvam", 20, [{"text": "from sarvam"}])
    out = run(_failover(needs_1500, any_length), duration_ms=1000)
    check("min-chunk: too-short adapter not called", needs_1500.calls, [])
    check("min-chunk: fell through to the next", out.text, "from sarvam")


# --- retry -----------------------------------------------------------------

def test_transient_failure_retried_and_recovers() -> None:
    a = FakeAdapter("groq", 10, [AsrError("boom", retryable=True), {"text": "recovered"}])
    out = run(_failover(a))
    check("retry: recovered", out.text, "recovered")
    check("retry: two attempts", len(a.calls), 2)


def test_retry_is_bounded_then_falls_through() -> None:
    a = FakeAdapter("groq", 10, [AsrError("boom", retryable=True)])
    b = FakeAdapter("sarvam", 20, [{"text": "from sarvam"}])
    out = run(_failover(a, b, max_attempts=3))
    check("retry: bounded at max_attempts", len(a.calls), 3)
    check("retry: fell through after exhaustion", out.provider, "sarvam")


def test_retry_exhausted_with_no_alternative_returns_none() -> None:
    a = FakeAdapter("groq", 10, [AsrError("boom", retryable=True)])
    check("retry: None when nothing left", run(_failover(a, max_attempts=2)), None)
    check("retry: attempted twice", len(a.calls), 2)


def test_permanent_failure_not_retried() -> None:
    a = FakeAdapter("groq", 10, [AsrError("bad key", retryable=False)])
    b = FakeAdapter("sarvam", 20, [{"text": "from sarvam"}])
    out = run(_failover(a, b))
    check("permanent: one attempt only", len(a.calls), 1)
    check("permanent: fell through", out.provider, "sarvam")


def test_unexpected_exception_not_retried() -> None:
    a = FakeAdapter("groq", 10, [TypeError("internal bug")])
    b = FakeAdapter("sarvam", 20, [{"text": "from sarvam"}])
    out = run(_failover(a, b))
    check("unexpected: one attempt only", len(a.calls), 1)
    check("unexpected: fell through", out.provider, "sarvam")


def test_empty_result_falls_through_without_retry() -> None:
    empty = FakeAdapter("groq", 10, [{"text": ""}])
    next_one = FakeAdapter("sarvam", 20, [{"text": "from sarvam"}])
    out = run(_failover(empty, next_one))
    check("empty: one call, no retry", len(empty.calls), 1)
    check("empty: fell through", out.provider, "sarvam")


# --- context ---------------------------------------------------------------

def test_context_reaches_every_adapter() -> None:
    a = FakeAdapter("groq", 10, [{"text": "", }])
    b = FakeAdapter("sarvam", 20, [{"text": "from sarvam"}])
    run(_failover(a, b), context="प्रसव पीड़ा")
    check("context: passed to first adapter", a.calls[0]["context"], "प्रसव पीड़ा")
    check("context: passed to the fall-through adapter", b.calls[0]["context"], "प्रसव पीड़ा")


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
