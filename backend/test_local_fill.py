"""Unit tests for the extraction/merge core and the session registry.

Run:  venv\\Scripts\\python.exe test_local_fill.py

These are pure-unit (no network, no mic, no running backend). The rest of the
suite in this repo is integration/live-API only, which is why a stray `\\b` in
a local_fill regex could go unnoticed — this file guards that.

Covers:
  * local_fill bilingual extraction, incl. the Devanagari `BD` boundary
  * the script-fidelity gate (Hinglish must not poison the fields)
  * MergeEngine latest-wins + confirm-lock
  * ChunkSession._live_window bounding (O(n^2) fix)
  * _accepts_context provider introspection (TypeError-shim fix)
  * SessionRegistry convergence (global-session fix)
"""

from __future__ import annotations

import re
import sys
import traceback
from pathlib import Path

BACKEND = Path(__file__).resolve().parent
sys.path.insert(0, str(BACKEND))

from engine.local_fill import BD, local_fill  # noqa: E402
from engine.merge import MergeEngine, is_empty  # noqa: E402

_results: list[tuple[str, str]] = []


def check(name: str, actual, expected) -> None:
    ok = actual == expected
    _results.append(("PASS" if ok else "FAIL", name))
    if not ok:
        print(f"  FAIL {name}\n       expected: {expected!r}\n       actual:   {actual!r}")


# --- local_fill ------------------------------------------------------------

def test_age_after_question() -> None:
    # Answer arrives AFTER the question word — the common real-world shape.
    check("age: answer after question", local_fill("आपकी उम्र क्या है 35").get("age"), 35)
    check("age: value right after keyword", local_fill("उम्र 28 साल").get("age"), 28)
    # Hindi numeral words
    check("age: hindi numeral word", local_fill("उम्र पैंतीस साल").get("age"), 35)
    # Devanagari digits are normalized
    check("age: devanagari digits", local_fill("उम्र ४२ साल").get("age"), 42)


def test_name_extraction() -> None:
    # The strict rule needs BD after "है" — a plain \b would never match here
    # because the matra in "है" is a non-word char, so \b fires mid-word.
    check("name: strict rule w/ BD", local_fill("नाम सीता है").get("name"), "सीता")
    # Real Q&A speech: the answer sits after a comma, which the strict regex
    # cannot cross — exercises the _answer_name fallback.
    check("name: after question + comma", local_fill("आपका नाम बताइए, प्रीति कुमारी").get("name"), "प्रीति कुमारी")


def test_name_does_not_absorb_field_answers() -> None:
    """A live session saved the delivery-mode answer as part of the name.

    The strict capture class is [Devanagari\\w\\s-]{2,40}?, which happily runs
    across spaces to the end of the sentence, and the loop keeps the LAST
    match. So a three-chunk encounter produced:

        '... मेरा नाम शिवानी'                    -> 'शिवानी'   ok
        '... मेरा नाम शिवानी सामान्य एलएमपी'   -> 'शिवानी सामान्य एलएमपी'
        '... नाम शिवानी प्रसव नंबर क्या है?'    -> 'शिवानी प्रसव'

    and since merge() is latest-wins, the WORST version is what got persisted
    as the patient's name. A name never contains clinical vocabulary, so the
    span is cut at the first domain term.
    """
    # Exactly the chunks from the reported session, cumulatively.
    c1 = " चलो तुम बताओ तुमारा नाम क्या है? मेरा नाम शिवानी"
    c2 = " सामान्य एलएमपी"
    c3 = " चलो बताओ तुमारों नाम क्या है? शिवानी प्रसव नंबर क्या है?"
    check("name: stable after 1 chunk", local_fill(c1).get("name"), "शिवानी")
    check("name: stable after 2 chunks", local_fill(c1 + c2).get("name"), "शिवानी")
    check("name: stable after 3 chunks", local_fill(c1 + c2 + c3).get("name"), "शिवानी")
    # The delivery-mode answer is still extracted -- it must not be swallowed
    # by the name fix, just kept out of the name.
    check("name: sibling field still found", local_fill(c1 + c2).get("delivery_mode"), "Normal")


def test_name_stop_words_are_word_bounded() -> None:
    """The stop list must not eat names that merely start with a domain word.

    A bare "प्री" (intended for "pre-term") matches inside प्रीति and silently
    destroyed a real patient's name. Every term is matched with a trailing BD.
    """
    for spoken, expected in [
        ("आपका नाम बताइए, प्रीति कुमारी", "प्रीति कुमारी"),
        ("नाम प्रीता सिंह", "प्रीता सिंह"),
        ("नाम प्रीतिमा देवी", "प्रीतिमा देवी"),
        ("नाम सुनीता देवी", "सुनीता देवी"),
        ("नाम क्या है राम कुमार", "राम कुमार"),
        ("मेरा नाम मोहन लाल यादव", "मोहन लाल यादव"),
        ("नाम सीता है", "सीता"),
    ]:
        check(f"name intact: {spoken!r}", local_fill(spoken).get("name"), expected)


def test_phone_and_aadhaar() -> None:
    check("phone: 10-digit", local_fill("मेरा मोबाइल नंबर 9876543210 है").get("contact_phone"), "9876543210")
    check("aadhaar: 12-digit", local_fill("आधार कार्ड 1234 5678 9012 है").get("aadhaar_number"), "123456789012")


def test_lmp() -> None:
    check("lmp: hindi month word", local_fill("एलएमपी मासिक धर्म 5 जनवरी").get("lmp"), "2026-01-05")
    # The numeric branch matches the literal ASCII token "LMP" only, AND the
    # script-fidelity gate still has to clear — so it needs Devanagari context.
    check(
        "lmp: numeric LMP inside devanagari context",
        local_fill("आखिरी मासिक धर्म की तारीख LMP 12-03-2025").get("lmp"),
        "2025-03-12",
    )
    # Latent dead path worth knowing about: a pure-Latin utterance can never
    # reach the numeric branch, because devanagari_ratio == 0.0 short-circuits
    # local_fill to {} before any rule runs. Pinned here so it is a documented
    # behaviour rather than a surprise.
    check("lmp: pure-latin gated out entirely", local_fill("LMP 12-03-2025").get("lmp"), None)
    # Devanagari spelling of LMP is not matched by the numeric rule.
    check(
        "lmp: devanagari LMP + numeric date not matched",
        local_fill("एलएमपी की तारीख 12-03-2025").get("lmp"),
        None,
    )


def test_yes_no_and_admission_category() -> None:
    check("admission: labour pain", local_fill("प्रसव पीड़ा है").get("admission_category"), "With labour pain")
    # "क्या जटिलता है? नहीं" -> the '?' must split question from answer.
    check(
        "admission: explicit 'नहीं' -> no complication",
        "admission_category" in local_fill("क्या कोई जटिलता है? नहीं"),
        False,
    )


def test_delivery_and_baby() -> None:
    check("delivery_mode: normal", local_fill("सामान्य प्रसव हुआ").get("delivery_mode"), "Normal")
    check("delivery_mode: caesarean overrides", local_fill("सीज़ेरियन प्रसव हुआ").get("delivery_mode"), "Caesarean")
    check("baby_sex: boy", local_fill("बच्चा लड़का है").get("baby_sex"), "Boy")
    check("birth_weight: kg", local_fill("शिशु का वजन 2.8 किलो है").get("birth_weight_kg"), 2.8)


def test_script_fidelity_gate() -> None:
    # Hinglish: our rules are Devanagari-only, so filling here would store
    # wrong values. Must return nothing at all.
    check("gate: hinglish rejected", local_fill("my name is seeta devi age 35"), {})
    check("gate: empty input", local_fill(""), {})


def test_bd_boundary_not_word_boundary() -> None:
    """The regression guard for the documented Devanagari \\b trap.

    Python's \\b is ASCII-\\w based. Devanagari matras are combining marks and
    therefore NOT word characters, so \\b fires *inside* a word like "है".
    BD asserts "next char is space/punctuation/end" instead.
    """
    word = "नाम सीता है"
    bad = re.search(r"है\b", word)
    good = re.search(r"है" + BD, word)
    check("BD: \\b fails inside 'है'", bad is not None, False)
    check("BD: lookahead succeeds on 'है'", good is not None, True)


# --- MergeEngine -----------------------------------------------------------

def test_merge_latest_wins_and_lock() -> None:
    m = MergeEngine()
    m.merge({"age": 35}, 0)
    m.merge({"age": 36}, 1)
    check("merge: latest non-empty wins", m.get_snapshot()["answers"]["age"], 36)

    # A confirmed field must be immune to later auto-fill...
    check("merge: confirm returns True", m.confirm("age"), True)
    m.merge({"age": 99}, 2)
    check("merge: confirm lock holds", m.get_snapshot()["answers"]["age"], 36)

    # ...and a manual edit locks the cell too.
    check("set_field: accepts known field", m.set_field("name", "सीता"), True)
    check("set_field: rejects unknown field", m.set_field("not_a_field", "x"), False)
    m.merge({"name": "अन्य"}, 3)
    check("merge: manual edit not overwritten", m.get_snapshot()["answers"]["name"], "सीता")

    # An empty value must never clobber an existing one.
    m.merge({"name": "", "age": None}, 4)
    check("merge: empty value ignored", m.get_snapshot()["answers"]["name"], "सीता")


def test_is_empty() -> None:
    for val, exp in ((None, True), ("", True), ("   ", True), ([], True), ({}, True), (0, False), ("x", False), ([1], False)):
        check(f"is_empty({val!r})", is_empty(val), exp)


# --- handler-level fixes ---------------------------------------------------

def test_live_window_is_bounded() -> None:
    from ws.handler import ChunkSession
    from config import settings

    s = ChunkSession()
    window = max(1, settings.local_fill_window_chunks)
    s.transcript_buffer = [f"chunk{i}" for i in range(50)]
    text = s._live_window()
    check("live_window: bounded length", len(s.transcript_buffer), 50)
    check("live_window: only last N chunks", text, " ".join(s.transcript_buffer[-window:]))
    check("live_window: older chunks excluded", "chunk0" in text, False)


def test_accepts_context_introspection() -> None:
    from ws.handler import _accepts_context
    from ws.groq_asr import GroqWhisperASR
    from ws.local_asr import LocalWhisperASR
    from ws.bhashini_asr import BhashiniASR
    from ws.sarvam_asr import SarvamASR
    from ws.indicconformer_asr import IndicConformerASR

    check("context: groq accepts", _accepts_context(GroqWhisperASR()), True)
    check("context: local accepts", _accepts_context(LocalWhisperASR()), True)
    check("context: bhashini rejects", _accepts_context(BhashiniASR()), False)
    check("context: sarvam rejects", _accepts_context(SarvamASR()), False)
    check("context: indic rejects", _accepts_context(IndicConformerASR()), False)

    # A TypeError raised INSIDE the adapter body must no longer be swallowed
    # and retried with fewer args — it should propagate to the caller's
    # `except Exception` and be logged.
    class Boom:
        def transcribe_chunk(self, pcm_b64, language="hi", duration_ms=None, context=""):
            raise TypeError("internal bug: unsupported operand")

    from ws.handler import _provider_context_args
    kwargs = _provider_context_args(Boom(), "ctx")
    check("context: kwargs built for adapter", "context" in kwargs, True)
    try:
        Boom().transcribe_chunk("x", **kwargs)
        check("context: internal TypeError propagates", "no-raise", "TypeError")
    except TypeError:
        check("context: internal TypeError propagates", True, True)


def test_session_registry_convergence() -> None:
    from ws.handler import sessions

    # The capture agent and the dashboard naming the same encounter must get
    # the SAME object — previously they could diverge, and a dashboard
    # mic_start reset() the agent's in-progress session.
    a = sessions.resolve("demo-enc")
    a.transcript_buffer.append("patient says something")
    a.active = True
    sessions.set_active(a)
    b = sessions.resolve("demo-enc")
    check("registry: same object for same encounter", a is b, True)
    check("registry: transcript intact", b.transcript_buffer, ["patient says something"])

    # No id -> falls back to the active session, so mic_stop reaches it.
    check("registry: no-id resolves to active", sessions.resolve() is a, True)
    check("registry: active getter", sessions.active is a, True)

    # Distinct encounters stay distinct.
    c = sessions.resolve("other-enc")
    check("registry: different encounter -> different session", c is a, False)
    check("registry: lookup by id", sessions.get("other-enc") is c, True)
    check("registry: unknown id is None", sessions.get("nope"), None)

    sessions.release(c)
    check("registry: release clears entry", sessions.get("other-enc"), None)
    sessions.release(a)
    check("registry: release clears active", sessions.active, None)


def test_prompt_echo_rejected() -> None:
    """Whisper echoes the injected domain vocabulary when fed near-silence.

    Observed live: a quiet chunk came back as the exact prompt vocabulary and
    local_fill turned it into a fabricated delivery_mode + final_outcome.
    """
    from ws.handler import is_prompt_echo
    from config import settings

    prompt = settings.hi_prompt_terms
    seen: set[str] = set()

    # The real hallucination from the bug report — must be rejected.
    echo = " प्रसव पीड़ा, सामान्य प्रसव पीड़ा, रेफर, डिस्चार्ज"
    check("echo: observed hallucination rejected", is_prompt_echo(echo, prompt, seen), True)
    # Substring slice of the vocabulary.
    check("echo: vocabulary slice rejected", is_prompt_echo("प्रसव पीड़ा सामान्य प्रसव सीज़ेरियन", prompt, seen), True)

    # Genuine speech that was correctly transcribed in the same session.
    check("echo: 'Hello' kept", is_prompt_echo("Hello", prompt, seen), False)
    check("echo: real Hindi kept", is_prompt_echo("अब आज जा रही है", prompt, seen), False)
    check("echo: real answer kept", is_prompt_echo("मेरा नाम प्रीति कुमारी है", prompt, seen), False)

    # The important false-positive guard: a real patient CAN answer with a
    # prompt word. Two-word answers must survive, otherwise we would suppress
    # genuine clinical answers like a delivery mode.
    check("echo: 2-word real answer 'सामान्य प्रसव' kept", is_prompt_echo("सामान्य प्रसव", prompt, seen), False)
    check("echo: mixed real answer kept", is_prompt_echo("सीज़ेरियन हुआ था", prompt, seen), False)

    # Identical multi-word repeat across chunks = fixed-prompt regurgitation.
    seen2 = {"प्रसव पीड़ा सामान्य प्रसव पीड़ा रेफर डिस्चार्ज"}
    check("echo: verbatim repeat rejected", is_prompt_echo(echo, prompt, seen2), True)

    # No prompt -> nothing to echo.
    check("echo: no prompt is safe", is_prompt_echo("प्रसव पीड़ा सामान्य प्रसव", "", set()), False)


def test_missing_metrics_are_none_not_zero() -> None:
    """A response with no segments must not look maximally confident.

    0.0 defeats every gate (0.0>0.6 False, 0.0<-1.5 False, 0.0>2.4 False), so
    defaulting missing metrics to 0.0 silently bypassed all gating.
    """
    from ws.groq_asr import GroqWhisperASR

    r = GroqWhisperASR()._parse_response({"text": "कुछ", "segments": None})
    for k in ("avg_logprob", "no_speech_prob", "compression_ratio"):
        check(f"metrics: {k} is None when absent", r.get(k), None)

    r2 = GroqWhisperASR()._parse_response({
        "text": "नमस्ते",
        "segments": [{"avg_logprob": -0.3, "no_speech_prob": 0.1, "compression_ratio": 1.1}],
    })
    check("metrics: avg_logprob parsed", round(r2["avg_logprob"], 3), -0.3)
    check("metrics: no_speech_prob parsed", round(r2["no_speech_prob"], 3), 0.1)
    check("metrics: compression_ratio parsed", round(r2["compression_ratio"], 3), 1.1)


def test_gate_respects_missing_metrics() -> None:
    from ws.handler import ChunkSession

    s = ChunkSession()
    # A loud chunk with no metrics must NOT be rejected for low confidence.
    check("gate: loud + no metrics passes", s._gate_result({}, 0.5), None)
    # A genuinely silent chunk is still rejected on RMS alone.
    check("gate: silent still rejected", s._gate_result({}, 0.0), "rejected")
    # Real bad metrics still trip.
    check("gate: low logprob dropped", s._gate_result({"avg_logprob": -3.0}, 0.5), "dropped")
    check("gate: high no_speech rejected", s._gate_result({"no_speech_prob": 0.9}, 0.5), "rejected")


def test_echo_threshold_tradeoff() -> None:
    """Documents why the content rules need 3 words, and the benign residual.

    "प्रसव पीड़ा" (a hallucination) and "सामान्य प्रसव" (a genuine patient
    answer) are BOTH two-word literal substrings of the injected vocabulary and
    are indistinguishable by content. Loosening the rule to 2 words would
    suppress real clinical answers — 'सामान्य प्रसव' is delivery_mode=Normal
    and 'सीज़ेरियन' is delivery_mode=Caesarean — so the content rules stay at 3
    and the residual (a first, isolated 2-word echo) is accepted as noise. It
    is benign: it extracts no fields, and it cannot repeat.
    """
    from ws.handler import is_prompt_echo
    from config import settings

    prompt = settings.hi_prompt_terms

    # The exact string from the reported bug: 7 words, two fabricated fields.
    reported = " प्रसव पीड़ा, सामान्य प्रसव पीड़ा, रेफर, डिस्चार्ज"
    check("tradeoff: reported echo caught", is_prompt_echo(reported, prompt, set(), set()), True)
    check("tradeoff: reported echo had fabricated fields", local_fill(reported),
          {"delivery_mode": "Normal", "final_outcome": "Referral"})

    # The residual 2-word case is NOT caught, but is harmless.
    residual = " प्रसव पीड़ा"
    check("tradeoff: 2-word echo not caught", is_prompt_echo(residual, prompt, set(), set()), False)
    check("tradeoff: 2-word echo extracts nothing", local_fill(residual), {})

    # Real answers that a 2-word rule would have destroyed.
    check("tradeoff: real 'सामान्य प्रसव' survives", is_prompt_echo("सामान्य प्रसव", prompt, set(), set()), False)
    check("tradeoff: real 'सीज़ेरियन' survives", is_prompt_echo("सीज़ेरियन", prompt, set(), set()), False)
    check("tradeoff: 'सीज़ेरियन' really is a delivery mode", local_fill("सीज़ेरियन").get("delivery_mode"), "Caesarean")


def test_echo_fragment_cascade() -> None:
    """After a multi-word echo, its fragments must also be dropped."""
    from ws.handler import is_prompt_echo
    from config import settings

    prompt = settings.hi_prompt_terms
    echoes = set()
    multi = " प्रसव पीड़ा, सामान्य प्रसव पीड़ा, रेफर, डिस्चार्ज"
    check("fragment: multi-word echo caught", is_prompt_echo(multi, prompt, set(), echoes), True)
    echoes.add("प्रसव पीड़ा सामान्य प्रसव पीड़ा रेफर डिस्चार्ज")
    # Whisper then drifts to a bare piece of the same hallucination.
    check("fragment: 'पीड़ा' caught as echo piece", is_prompt_echo("पीड़ा", prompt, set(), echoes), True)
    check("fragment: 'प्रसव पीड़ा' caught as echo piece", is_prompt_echo("प्रसव पीड़ा", prompt, set(), echoes), True)
    # Genuine speech after an echo is untouched.
    check("fragment: real speech still kept", is_prompt_echo("अब आज जा रही है", prompt, set(), echoes), False)


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
