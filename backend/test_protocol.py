"""Unit + conformance tests for the protocol module (ws/protocol.py).

Run:  venv\\Scripts\\python.exe test_protocol.py

Pure: constructors and parsers move plain dicts, no sockets, no asyncio, no
config, no database. Two families of checks:

  * wire shapes — every declared event constructor produces exactly the dict
    the handlers used to hand-write (content AND key order), serialises with
    json, and hands back its own dict; every command parses with the exact
    normalisation the old inline expressions applied;
  * conformance — the client files (the web app, the browser microphone hook,
    the capture agent, and the e2e page objects) are swept with a plain
    fixed-string search: every event name they consume and every command they
    send must be a member of the module's canonical sets, the canonical sets
    must declare nothing the clients (plus the two deliberate wire-compat
    members) do not use, and ws/handler.py itself must hold no quoted wire
    names at all — drift cannot re-enter the branch code.

Deliberately fixed-string (`name` between two quote chars): no regex, so the
sweep cannot flake on formatting.
"""

from __future__ import annotations

import json
import sys
import traceback
from dataclasses import dataclass
from pathlib import Path

BACKEND = Path(__file__).resolve().parent
REPO = BACKEND.parent
sys.path.insert(0, str(BACKEND))

from ws import protocol  # noqa: E402

_results: list[tuple[str, str]] = []


def check(name: str, actual, expected) -> None:
    ok = actual == expected
    _results.append(("PASS" if ok else "FAIL", name))
    if not ok:
        print(f"  FAIL {name}\n       expected: {expected!r}\n       actual:   {actual!r}")


def _read(relative: str) -> str:
    """Read a repo file as UTF-8 (devanagari lives in some of them)."""
    return (REPO / relative).read_text(encoding="utf-8")


def _present(name: str, text: str) -> bool:
    """Plain fixed-string search: is `name` quoted on this line anywhere?
    Both quote kinds, because the web clients are JS/TS. Adding no clever
    matchers is the point — a sweep that never flakes."""
    return (f'"{name}"' in text) or (f"'{name}'" in text)


# --- purity -----------------------------------------------------------------

def test_protocol_module_is_pure() -> None:
    """The module imports raw dataclasses/typing only. No transport, no config,
    no engine — importing it must not drag the app in."""
    banned = ("config", "db", "engine", "llm", "fastapi", "asyncio", "socket",
              "ws.asr", "ws.handler")
    check("purity: no transport/config import chain",
          [m for m in banned if m in sys.modules], [])


# --- wire status vocabulary ---------------------------------------------------

def test_status_vocabulary() -> None:
    """The closed set of chunk_result statuses. The phantom fourth value the UI
    used to guard against (`empty`) is not in it."""
    check("statuses: the canonical three", list(protocol.STATUSES),
          ["rejected", "tentative", "finalized"])


def test_chunk_result_rejects_unknown_status() -> None:
    """A status that never existed on the wire cannot be built — so drift dies
    at the constructor instead of in a `lastMessage.status` check."""
    try:
        protocol.chunk_result(
            chunk_id=0, encounter_id="e", transcript="", status="empty",
            speaker="unknown", language="", answers={}, confirmed={}, alerts=[],
        )
        ok = False
    except ValueError:
        ok = True
    check("statuses: phantom fourth value fails fast", ok, True)


# --- event constructors: byte-identical wire shapes ---------------------------

def test_chunk_result_rejected_shape() -> None:
    """The silence/hallucination stub: no confidence, no provider, no voice
    metrics — exactly the dict the old literal produced, key order included."""
    out = protocol.chunk_result(
        chunk_id=7, encounter_id="demo", transcript="",
        status=protocol.STATUS_REJECTED, speaker="unknown", language="",
        answers={"age": 30}, confirmed={"age": True}, alerts=[],
    )
    check("chunk_result stub: content", out, {
        "type": "chunk_result", "chunk_id": 7, "encounter_id": "demo",
        "transcript": "", "status": "rejected", "speaker": "unknown",
        "language": "", "answers": {"age": 30}, "confirmed": {"age": True},
        "alerts": [],
    })
    check("chunk_result stub: key order", list(out.keys()), [
        "type", "chunk_id", "encounter_id", "transcript", "status",
        "speaker", "language", "answers", "confirmed", "alerts",
    ])


def test_chunk_result_filled_shape() -> None:
    """The transcript-bearing shape: confidence/provider sit right behind
    status, and a null confidence stays PRESENT (a provider without metrics
    must read as absent, not as a missing key)."""
    out = protocol.chunk_result(
        chunk_id=3, encounter_id="demo", transcript="मेरा नाम शिवानी",
        status=protocol.STATUS_TENTATIVE, confidence=None, provider="groq",
        speaker="patient", language="hi", answers={}, confirmed={}, alerts=[],
    )
    check("chunk_result filled: content", out, {
        "type": "chunk_result", "chunk_id": 3, "encounter_id": "demo",
        "transcript": "मेरा नाम शिवानी", "status": "tentative",
        "confidence": None, "provider": "groq", "speaker": "patient",
        "language": "hi", "answers": {}, "confirmed": {}, "alerts": [],
    })
    check("chunk_result filled: key order", list(out.keys()), [
        "type", "chunk_id", "encounter_id", "transcript", "status",
        "confidence", "provider", "speaker", "language",
        "answers", "confirmed", "alerts",
    ])


def test_chunk_result_allowed_keys_are_declared() -> None:
    full = protocol.chunk_result(
        chunk_id=1, encounter_id="e", transcript="t",
        status=protocol.STATUS_FINALIZED, confidence=None, provider="groq",
        speaker="s", language="l",
        answers={}, confirmed={}, alerts=[],
    )
    wired = protocol.attach_voice(full, voice_level=0.5, vad=1.0)
    check("chunk_result: payload keys == declared tuple",
          set(wired) - {"type"}, set(protocol.EVENTS[protocol.CHUNK_RESULT]))


def test_attach_voice() -> None:
    base = protocol.chunk_result(
        chunk_id=1, encounter_id="e", transcript="t",
        status=protocol.STATUS_REJECTED, speaker="unknown", language="",
        answers={}, confirmed={}, alerts=[],
    )
    out = protocol.attach_voice(base, voice_level=0.4321, vad=1.0)
    check("attach_voice: metrics appended last", list(out.keys()), [
        "type", "chunk_id", "encounter_id", "transcript", "status",
        "speaker", "language", "answers", "confirmed", "alerts",
        "voice_level", "vad",
    ])
    check("attach_voice: quiet chunk flags zero",
          (protocol.attach_voice(base, voice_level=0.0, vad=0.0)["vad"], ), (0.0, ))
    check("attach_voice: base dict not mutated", "voice_level" in base, False)


def test_finalize_result_shape() -> None:
    out = protocol.finalize_result(
        encounter_id="demo", transcript="one two",
        answers={"age": None}, confirmed={},
        alerts=[{"field": "age", "message": "missing age", "severity": "warn"}],
    )
    check("finalize_result: content", out, {
        "type": "finalize_result", "encounter_id": "demo",
        "transcript": "one two", "answers": {"age": None}, "confirmed": {},
        "alerts": [{"field": "age", "message": "missing age", "severity": "warn"}],
    })
    check("finalize_result: key order", list(out.keys()), [
        "type", "encounter_id", "transcript", "answers", "confirmed", "alerts",
    ])


def test_session_state_shapes() -> None:
    on = protocol.session_state(active=True, encounter_id="demo")
    check("session_state on: content", on,
          {"type": "session_state", "active": True, "encounter_id": "demo"})
    off = protocol.session_state(active=False)
    check("session_state off: no encounter key", off,
          {"type": "session_state", "active": False})


def test_snapshot_shape() -> None:
    out = protocol.snapshot(answers={"age": 30}, confirmed={}, transcript="tail")
    check("snapshot: content", out,
          {"type": "snapshot", "answers": {"age": 30}, "confirmed": {},
           "transcript": "tail"})
    check("snapshot: key order", list(out.keys()),
          ["type", "answers", "confirmed", "transcript"])


def test_voice_activity_shape() -> None:
    out = protocol.voice_activity(level=0.1234, encounter_id="demo")
    check("voice_activity: content", out,
          {"type": "voice_activity", "level": 0.1234, "encounter_id": "demo"})


def test_capture_status_shape() -> None:
    check("capture_status: content",
          protocol.capture_status(connected=True),
          {"type": "capture_status", "connected": True})


def test_field_updated_shape() -> None:
    out = protocol.field_updated(field="age", value=30, answers={"age": 30})
    check("field_updated: content", out,
          {"type": "field_updated", "field": "age", "value": 30,
           "answers": {"age": 30}})


def test_field_confirmed_shape() -> None:
    out = protocol.field_confirmed(field="age")
    check("field_confirmed: content", out,
          {"type": "field_confirmed", "field": "age"})


def test_save_result_shape() -> None:
    out = protocol.save_result(ok=True, encounter_id="demo", patient_id=None,
                               answers={})
    check("save_result: null patient_id stays present", out,
          {"type": "save_result", "ok": True, "encounter_id": "demo",
           "patient_id": None, "answers": {}})
    out2 = protocol.save_result(ok=True, encounter_id="demo", patient_id=42,
                                answers={"age": 30})
    check("save_result: content", out2,
          {"type": "save_result", "ok": True, "encounter_id": "demo",
           "patient_id": 42, "answers": {"age": 30}})


def test_every_event_round_trips_through_json() -> None:
    """Every declared event: built full, serialises bare, and comes back
    equal — the payload carries only JSON types."""
    events = [
        protocol.attach_voice(protocol.chunk_result(
            chunk_id=1, encounter_id="e", transcript="t",
            status=protocol.STATUS_TENTATIVE, confidence=None, provider="p",
            speaker="patient", language="hi", answers={"age": 30},
            confirmed={"age": True}, alerts=[],
        ), voice_level=0.5, vad=1.0),
        protocol.finalize_result(encounter_id="e", transcript="t",
                                 answers={"age": 30}, confirmed={},
                                 alerts=[{"field": "age", "message": "m", "severity": "warn"}]),
        protocol.session_state(active=True, encounter_id="e"),
        protocol.session_state(active=False),
        protocol.snapshot(answers={"age": 30}, confirmed={}, transcript="t"),
        protocol.voice_activity(level=0.1, encounter_id="e"),
        protocol.capture_status(connected=True),
        protocol.field_updated(field="age", value=30, answers={"age": 30}),
        protocol.field_confirmed(field="age"),
        protocol.save_result(ok=True, encounter_id="e", patient_id=1, answers={}),
    ]
    for wire in events:
        name = wire.get("type", "<no type>")
        check(f"json round-trip: {name}", json.loads(json.dumps(wire)), wire)
        check(f"declared payload keys cover {name}",
              set(wire) - {"type"} <= set(protocol.EVENTS[name]), True)


# --- command parsing ----------------------------------------------------------

def test_parse_command_round_trip() -> None:
    """Every declared command parses, fields normalise exactly as the old
    inline expressions did, and the unknowns stay ignored (None)."""
    check("mic_start: id stripped",
          protocol.parse_command({"type": "mic_start", "encounter_id": "  e1 "}),
          protocol.MicStart(encounter_id="e1"))
    check("mic_start: missing id",
          protocol.parse_command({"type": "mic_start"}),
          protocol.MicStart(encounter_id=""))
    check("mic_start: null id",
          protocol.parse_command({"type": "mic_start", "encounter_id": None}),
          protocol.MicStart(encounter_id=""))
    check("mic_stop: no fields",
          protocol.parse_command({"type": "mic_stop"}), protocol.MicStop())
    check("set_field: values pass through untouched",
          protocol.parse_command({"type": "set_field", "field": "age", "value": 30}),
          protocol.SetField(field="age", value=30))
    check("set_field: missing keys keep old defaults",
          protocol.parse_command({"type": "set_field"}),
          protocol.SetField(field="", value=None))
    check("save: carries nothing",
          protocol.parse_command({"type": "save", "junk": 1}), protocol.Save())
    check("confirm_field: field only",
          protocol.parse_command({"type": "confirm_field", "field": "age"}),
          protocol.ConfirmField(field="age"))
    check("unknown command: ignored (old elif fall-through)",
          protocol.parse_command({"type": "party"}), None)
    check("typeless junk: ignored", protocol.parse_command({}), None)


def test_parse_chunks_message_round_trip() -> None:
    """finalize / session_start are commands; everything else — including a
    mis-delivered dashboard command — flows through as the audio payload,
    exactly as the old fall-through did."""
    check("finalize: id stripped",
          protocol.parse_chunks_message({"type": "finalize", "encounter_id": " e1 "}),
          protocol.Finalize(encounter_id="e1"))
    check("finalize: bare",
          protocol.parse_chunks_message({"type": "finalize"}),
          protocol.Finalize(encounter_id=""))
    check("session_start: parsed",
          protocol.parse_chunks_message({"type": "session_start", "encounter_id": "e2"}),
          protocol.SessionStart(encounter_id="e2"))

    browser_payload = {
        "chunk_id": 1, "pcm_b64": "AAAA", "sample_rate": 16000, "channels": 1,
        "mic_channel": 0, "start_sample": 0, "end_sample": 96000,
        "duration_ms": 6000, "rms": 0.1, "raw_rms": 0.2, "analyser_rms": 0.3,
        "anySignal": True, "actualRate": 48000, "label": "Mock Microphone",
        "deviceId": "mock", "devRate": 48000, "language": "hi",
    }
    parsed = protocol.parse_chunks_message(browser_payload)
    check("browser chunk: parsed as data", isinstance(parsed, protocol.ChunkData), True)
    check("browser chunk: keys within the declared set",
          set(parsed.payload.keys()) <= set(protocol.CHUNK_KEYS), True)
    check("browser chunk: all diagnostic keys known",
          set(protocol.CHUNK_KEYS) >= set(browser_payload), True)
    check("browser chunk: payload untouched", parsed.payload, browser_payload)

    agent_payload = {
        "chunk_id": 0, "pcm_b64": "AAAA", "sample_rate": 16000, "channels": 1,
        "mic_channel": 0, "start_sample": 0, "end_sample": 1600,
        "duration_ms": 100, "language": "hi",
    }
    parsed = protocol.parse_chunks_message(agent_payload)
    check("capture-agent chunk: minimal set parses",
          (isinstance(parsed, protocol.ChunkData), parsed.encounter_id), (True, ""))

    e2e_payload = dict(agent_payload, encounter_id=" e2e-chunk-test ")
    parsed = protocol.parse_chunks_message(e2e_payload)
    check("e2e chunk: inline encounter honoured",
          (isinstance(parsed, protocol.ChunkData), parsed.encounter_id),
          (True, "e2e-chunk-test"))

    parsed = protocol.parse_chunks_message({"type": "mic_start", "encounter_id": "x"})
    check("dashboard command to /ws/chunks: still data (old fall-through)",
          isinstance(parsed, protocol.ChunkData), True)

    parsed = protocol.parse_chunks_message({})
    check("empty message: data with empty encounter",
          (isinstance(parsed, protocol.ChunkData), parsed.encounter_id), (True, ""))


def test_finalize_is_checked_before_session_start() -> None:
    """A property of the old branch order preserved: a finalize never falls
    through to the audio path."""
    both = {"type": "finalize"}
    check("finalize wins over data", isinstance(
        protocol.parse_chunks_message(both), protocol.Finalize), True)


# --- conditional-field homes (the drift review's item) ------------------------

def test_conditional_fields_declared_on_exactly_one_event() -> None:
    """Every contested payload key has exactly ONE declared home. The review
    suspected `vad` of being attached to the wrong event: it belongs to
    chunk_result (with `voice_level`), while `level` is the voice_activity
    field. No event may carry one of these keys but that."""
    for key, owner in (("vad", protocol.CHUNK_RESULT),
                       ("voice_level", protocol.CHUNK_RESULT),
                       ("level", protocol.VOICE_ACTIVITY)):
        homes = [n for n, keys in protocol.EVENTS.items() if key in keys]
        check(f"field home: {key} on {owner} only", homes, [owner])


# --- conformance: the three clients (plus the e2e page objects) ---------------

@dataclass(frozen=True)
class ConformanceClient:
    """One external client file and the wire names it is known to use.

    `consumes` — event names read off the wire; `sends` — command names put
    on it; `statuses` — chunk_result status literals compared in JS;
    `banned` — literals that must NOT appear (regression pins, e.g. the
    phantom status).
    """

    label: str
    path: str
    consumes: tuple[str, ...] = ()
    sends: tuple[str, ...] = ()
    statuses: tuple[str, ...] = ()
    banned: tuple[str, ...] = ()


# The two members with no client touching them today are deliberate:
# field_confirmed is the echo of a command no client sends (open product
# decision), confirm_field is that command itself.
UNCONSUMED_EVENTS = frozenset({protocol.FIELD_CONFIRMED})
UNSENT_COMMANDS = frozenset({protocol.CONFIRM_FIELD})

CLIENTS = (
    ConformanceClient(
        label="web/src/App.jsx",
        path="web/src/App.jsx",
        consumes=(
            protocol.VOICE_ACTIVITY, protocol.CAPTURE_STATUS,
            protocol.SESSION_STATE, protocol.SNAPSHOT, protocol.CHUNK_RESULT,
            protocol.FIELD_UPDATED, protocol.FINALIZE_RESULT,
            protocol.SAVE_RESULT,
        ),
        sends=(protocol.SET_FIELD, protocol.SAVE),
        statuses=(protocol.STATUS_REJECTED, protocol.STATUS_TENTATIVE),
        banned=("empty",),
    ),
    ConformanceClient(
        label="web/src/hooks/useBrowserMic.js",
        path="web/src/hooks/useBrowserMic.js",
        sends=(protocol.SESSION_START, protocol.FINALIZE),
    ),
    ConformanceClient(
        label="capture-agent/streamer.py",
        path="capture-agent/streamer.py",
        sends=(protocol.FINALIZE,),
    ),
    ConformanceClient(
        label="web/tests/e2e/scribe.spec.ts",
        path="web/tests/e2e/scribe.spec.ts",
        consumes=(
            protocol.SESSION_STATE, protocol.FINALIZE_RESULT,
            protocol.FIELD_UPDATED,
        ),
        sends=(protocol.MIC_START, protocol.MIC_STOP, protocol.SET_FIELD),
    ),
    ConformanceClient(
        label="web/tests/e2e/pages/ScribePage.ts",
        path="web/tests/e2e/pages/ScribePage.ts",
        consumes=(protocol.CHUNK_RESULT,),
        sends=(protocol.SESSION_START,),
    ),
)


def test_client_conformance() -> None:
    """Two-sided name lock. Client side: every name each client uses must be a
    canonical member and must actually appear in the file (quoted) — a client
    that loses a usage, or starts consuming a phantom, fails here. Module
    side: the canonical sets may declare nothing the clients do not use,
    except the two deliberate wire-compat members."""
    consumed: set[str] = set()
    sent: set[str] = set()
    for client in CLIENTS:
        text = _read(client.path)
        for name in client.consumes:
            check(f"{client.label}: {name} is a declared event",
                  name in protocol.EVENTS, True)
            check(f"{client.label}: {name} literal present", _present(name, text), True)
            consumed.add(name)
        for name in client.sends:
            check(f"{client.label}: {name} is a declared command",
                  name in protocol.COMMANDS, True)
            check(f"{client.label}: {name} literal present", _present(name, text), True)
            sent.add(name)
        for status in client.statuses:
            check(f"{client.label}: status {status} is canonical",
                  status in protocol.STATUSES, True)
            check(f"{client.label}: status {status} literal present",
                  _present(status, text), True)
        for banned in client.banned:
            check(f"{client.label}: phantom {banned!r} absent",
                  _present(banned, text), False)

    check("events: canonical set == consumers + declared-unconsumed",
          set(protocol.EVENTS), consumed | UNCONSUMED_EVENTS)
    check("commands: canonical set == senders + declared-unsent",
          set(protocol.COMMANDS), sent | UNSENT_COMMANDS)


def test_handler_holds_no_wire_names() -> None:
    """ws/handler.py routes every emission through the constructors and every
    command through the parsers, so the quoted wire names cannot linger there
    — reintroducing a literal means bypassing the seam, and now it fails."""
    text = _read("backend/ws/handler.py")
    for name in [*protocol.EVENTS, *protocol.COMMANDS]:
        check(f"handler: no quoted literal for {name}",
              f'"{name}"' in text, False)


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
