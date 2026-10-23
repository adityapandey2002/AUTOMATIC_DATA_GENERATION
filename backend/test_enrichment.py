"""Unit tests for the enrichment module (engine/enrichment.py).

Run:  venv\\Scripts\\python.exe test_enrichment.py

Pure-unit: the extraction adapter is a fake, so the whole transcript -> case
sheet sequence — bounded live window vs full transcript, local-fill-first
merge order, the LLM seam, the extraction-failure policy, and validation — is
exercised through the module's interface only, with no network, no Gemini
key, no Postgres, and no microphone:

  * mode "live": fills from the bounded window, NEVER calls the extractor
  * mode "final": fills from the FULL transcript, calls the extractor exactly
    once, and merges its result AFTER the local fill
  * the offline adapter satisfies the seam by contributing nothing
  * an extractor failure keeps the local fill and still validates
  * validation alerts ride the one EnrichResult the call sites consume
"""

from __future__ import annotations

import asyncio
import inspect
import sys
import traceback
from pathlib import Path

BACKEND = Path(__file__).resolve().parent
sys.path.insert(0, str(BACKEND))

from engine.enrichment import (  # noqa: E402
    EnrichResult,
    Enrichment,
    OfflineExtractor,
)
from engine.merge import MergeEngine  # noqa: E402

_results: list[tuple[str, str]] = []


def check(name: str, actual, expected) -> None:
    ok = actual == expected
    _results.append(("PASS" if ok else "FAIL", name))
    if not ok:
        print(f"  FAIL {name}\n       expected: {expected!r}\n       actual:   {actual!r}")


class FakeExtractor:
    """A scripted adapter satisfying the seam.

    `result` is merged in after the local fill; `error`, when set, is raised
    instead. Every transcript handed to `extract` is recorded in `calls`.
    """

    def __init__(self, result: dict | None = None, error: Exception | None = None) -> None:
        self.name = "fake"
        self.calls: list[str] = []
        self._result = result if result is not None else {}
        self._error = error

    async def extract(self, transcript: str) -> dict:
        self.calls.append(transcript)
        if self._error is not None:
            raise self._error
        return self._result


def _run(enricher: Enrichment, chunks, mode: str, chunk_id: int = 0) -> EnrichResult:
    return asyncio.run(enricher.enrich(chunks, mode, chunk_id=chunk_id))


# --- mode "live" -------------------------------------------------------------

def test_live_never_calls_extractor() -> None:
    fake = FakeExtractor()
    enricher = Enrichment(MergeEngine(), fake, window_chunks=3)
    r = _run(enricher, ["प्रसव पीड़ा है"], "live", chunk_id=7)
    check("live: extractor not called", fake.calls, [])
    check("live: labour pain filled", r.snapshot["answers"]["admission_category"], "With labour pain")
    check("live: clean sheet, no alerts", r.alerts, [])
    check("live: one normalised result type", type(r).__name__, "EnrichResult")


# --- mode "final" ------------------------------------------------------------

def test_final_calls_extractor_once_on_the_full_transcript() -> None:
    fake = FakeExtractor(result={"contact_phone": "9876543210"})
    enricher = Enrichment(MergeEngine(), fake, window_chunks=3)
    r = _run(enricher, ["उम्र ३० साल", "नाम सीता है"], "final")
    check("final: extractor called exactly once", len(fake.calls), 1)
    check("final: extractor saw the FULL transcript", fake.calls[0], "उम्र ३० साल नाम सीता है")
    check("final: local fill kept (age)", r.snapshot["answers"]["age"], 30)
    check("final: local fill kept (name)", r.snapshot["answers"]["name"], "सीता")
    check("final: extractor value merged in", r.snapshot["answers"]["contact_phone"], "9876543210")


def test_final_merges_extractor_after_local_fill() -> None:
    """Merge ordering: local fill first, extractor second (merge is latest-
    non-empty-wins). Had the module merged the extractor first, local_fill's
    own age of 30 would have overwritten it."""
    fake = FakeExtractor(result={"age": 99})
    enricher = Enrichment(MergeEngine(), fake, window_chunks=3)
    r = _run(enricher, ["उम्र ३० साल"], "final")
    check("final: extractor merged AFTER the local fill", r.snapshot["answers"]["age"], 99)


def test_final_blank_transcript_skips_extractor() -> None:
    fake = FakeExtractor()
    enricher = Enrichment(MergeEngine(), fake, window_chunks=3)
    r = _run(enricher, [], "final")
    check("final: empty buffer, extractor skipped", fake.calls, [])
    check("final: fresh sheet answers", set(r.snapshot["answers"].values()), {None})
    check("final: fresh sheet is unconfirmed", r.snapshot["_confirmed"], {})
    check("final: fresh sheet validates clean", r.alerts, [])


def test_final_whitespace_transcript_skips_extractor() -> None:
    fake = FakeExtractor()
    enricher = Enrichment(MergeEngine(), fake, window_chunks=3)
    r = _run(enricher, ["   "], "final")
    check("final: whitespace-only transcript, extractor skipped", fake.calls, [])
    check("final: whitespace fills nothing", set(r.snapshot["answers"].values()), {None})


def test_extractor_failure_keeps_local_fill() -> None:
    fake = FakeExtractor(result={"never": "merged"}, error=RuntimeError("429 / quota"))
    enricher = Enrichment(MergeEngine(), fake, window_chunks=3)
    r = _run(enricher, ["उम्र ३० साल"], "final")
    check("failing: extractor was attempted", len(fake.calls), 1)
    check("failing: local fill survives the failure", r.snapshot["answers"]["age"], 30)
    check("failing: validation still ran", r.alerts, [])


# --- the bounded live window --------------------------------------------------

def test_live_window_bounds_extraction() -> None:
    """Live mode scans only the last `window_chunks` chunks — the module owns
    the window, and it never truncates (or otherwise mutates) the caller's
    list."""
    enricher = Enrichment(MergeEngine(), FakeExtractor(), window_chunks=2)
    chunks = ["उम्र ४२ साल", "मरीज़ ठीक है", "प्रसव पीड़ा है"]
    r = _run(enricher, chunks, "live", chunk_id=0)
    check("window: older chunk excluded from the live fill", r.snapshot["answers"]["age"], None)
    check("window: in-window chunk still filled", r.snapshot["answers"]["admission_category"], "With labour pain")
    check("window: caller's list untouched", chunks, ["उम्र ४२ साल", "मरीज़ ठीक है", "प्रसव पीड़ा है"])


def test_final_scans_the_full_transcript() -> None:
    """Finalize deliberately re-scans everything regardless of the window; the
    extractor still runs (its empty result just merges nothing)."""
    fake = FakeExtractor()
    enricher = Enrichment(MergeEngine(), fake, window_chunks=2)
    chunks = ["उम्र ४२ साल", "मरीज़ ठीक है", "प्रसव पीड़ा है"]
    r = _run(enricher, chunks, "final")
    check("final: cross-chunk pairing on the full transcript", r.snapshot["answers"]["age"], 42)
    check("final: extractor ran on the full transcript", fake.calls, ["उम्र ४२ साल मरीज़ ठीक है प्रसव पीड़ा है"])
    check("final: empty extractor result merged nothing extra", r.snapshot["_confirmed"], {})


def test_window_never_discards_earlier_fills() -> None:
    """MergeEngine already retains what older chunks found; the narrow live
    window only limits how far back a *correction* can be picked up."""
    fake = FakeExtractor()
    enricher = Enrichment(MergeEngine(), fake, window_chunks=2)
    _run(enricher, ["उम्र ४२ साल"], "live", chunk_id=0)
    r = _run(enricher, ["मरीज़ ठीक है", "नाम सीता है"], "live", chunk_id=1)
    check("window: earlier fill retained across chunks", r.snapshot["answers"]["age"], 42)
    check("window: new chunk fills earlier gap", r.snapshot["answers"]["name"], "सीता")


# --- validation ---------------------------------------------------------------

def test_validation_alerts_ride_the_result() -> None:
    enricher = Enrichment(MergeEngine(), FakeExtractor(), window_chunks=3)
    r = _run(enricher, ["उम्र ९२ साल"], "live", chunk_id=0)
    check("alerts: field", [a.field for a in r.alerts], ["age"])
    check("alerts: severity", r.alerts[0].severity, "warning")
    check("alerts: out-of-range VALUE is still merged", r.snapshot["answers"]["age"], 92)
    check("alerts: alert objects carry the payload fields", r.alerts[0].message, "Age 92 years outside expected range (10–65)")


# --- the seam ------------------------------------------------------------------

def test_offline_adapter_contributes_nothing() -> None:
    """The offline adapter mirrors `llm_final_extract=false`: no call recorded
    beyond the seam, no values merged, and the sheet behaves identically."""
    enricher = Enrichment(MergeEngine(), OfflineExtractor(), window_chunks=3)
    r = _run(enricher, ["उम्र ३० साल"], "final")
    check("offline: local fill still runs", r.snapshot["answers"]["age"], 30)
    check("offline: nothing else merged", r.snapshot["_confirmed"], {})
    off = OfflineExtractor()
    check("offline: seam name", off.name, "offline")
    check("offline: extract contributes nothing", asyncio.run(off.extract("anything at all")), {})


def test_both_adapters_satisfy_one_seam() -> None:
    """Both adapters satisfy ONE seam — `name` + `async extract(transcript)` —
    so the module never special-cases either (mirrors the ASR adapter check)."""
    from llm.extract import GeminiExtractor

    for adapter_cls, expected_name in ((GeminiExtractor, "Gemini"), (OfflineExtractor, "offline")):
        adapter = adapter_cls()
        params = inspect.signature(adapter.extract).parameters
        check(f"seam: {expected_name} takes a transcript", list(params), ["transcript"])
        check(f"seam: {expected_name} has a stable name", adapter.name, expected_name)
        check(f"seam: {expected_name} extract is awaitable", inspect.iscoroutinefunction(adapter.extract), True)


def test_unknown_mode_is_rejected() -> None:
    enricher = Enrichment(MergeEngine(), FakeExtractor(), window_chunks=3)
    try:
        asyncio.run(enricher.enrich(["प्रसव पीड़ा है"], "party", chunk_id=0))
        ok = False
    except ValueError:
        ok = True
    check("mode: unknown mode fails fast", ok, True)


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
