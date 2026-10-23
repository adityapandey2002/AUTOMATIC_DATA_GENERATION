"""WS protocol module — the one owner of every backend <-> client message shape.

Both transports (``/ws/chunks`` and ``/ws/dashboard``) deal in plain JSON dict
messages. Until now every message shape was known only by its producer and each
of its consumers independently: `ws/handler.py` emitted raw dicts and matched
~15 hand-typed string names, while `web/src/App.jsx`, the browser microphone
hook, and the capture agent re-typed the same names in three other codebases.
Drift already landed once (a phantom status, a field attached to the wrong
event, an unused command pair).

This module is the seam between the socket layer and the wire:

  * **Backend -> client events** go out only through the constructor functions
    below, one per event type. Each returns the exact wire dict, in the exact
    key order, that `ws/handler.py` used to hand-write at that emission point.
  * **Client -> backend commands** come in only through `parse_command` (the
    dashboard transport) and `parse_chunks_message` (the chunks transport).
    The parsers normalise fields with the very same expressions the handler
    branches used to inline, so routing through them cannot change behavior.

The module is pure: no socket, no asyncio, no config, no database. Everything
goes in and out of plain dicts, so the whole wire contract is testable with no
running server (`backend/test_protocol.py`), and the three external clients —
`web/src/App.jsx`, `web/src/hooks/useBrowserMic.js`, and
`capture-agent/streamer.py` — are held to it by a fixed-string conformance
check in that same test file, which is deliberately preferred over generating
a JS/TS mirror of these names.

Vocabulary: the events and commands below are the interface; `ws/handler.py`
decides WHICH behavior runs at each branch while this module owns WHAT the
message looks like.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Optional, Union

# --- wire status vocabulary (values of chunk_result's `status` key) ---------

STATUS_REJECTED = "rejected"
STATUS_TENTATIVE = "tentative"
STATUS_FINALIZED = "finalized"
STATUSES = (STATUS_REJECTED, STATUS_TENTATIVE, STATUS_FINALIZED)

# --- backend -> client event names -----------------------------------------

CHUNK_RESULT = "chunk_result"
FINALIZE_RESULT = "finalize_result"
SESSION_STATE = "session_state"
SNAPSHOT = "snapshot"
VOICE_ACTIVITY = "voice_activity"
CAPTURE_STATUS = "capture_status"
FIELD_UPDATED = "field_updated"
FIELD_CONFIRMED = "field_confirmed"
SAVE_RESULT = "save_result"

# --- client -> backend command names ---------------------------------------

SESSION_START = "session_start"
FINALIZE = "finalize"
MIC_START = "mic_start"
MIC_STOP = "mic_stop"
SET_FIELD = "set_field"
SAVE = "save"
CONFIRM_FIELD = "confirm_field"

# --- the canonical sets -----------------------------------------------------
#
# These two tables are the single source of truth for every name on the wire.
# The tuples are every PAYLOAD key the event may carry (the "type"
# discriminator is not listed — every event carries it by definition). The
# constructors document which keys appear on which path.
# `backend/test_protocol.py` pins the tables against the three client files,
# so a name cannot be added, removed, or retyped on one side without failing
# there.

EVENTS: dict[str, tuple[str, ...]] = {
    CHUNK_RESULT: (
        "chunk_id", "encounter_id", "transcript", "status",
        "speaker", "language", "answers", "confirmed", "alerts",
        "confidence", "provider",
        "voice_level", "vad",
    ),
    FINALIZE_RESULT: ("encounter_id", "transcript", "answers", "confirmed", "alerts"),
    SESSION_STATE: ("active", "encounter_id"),
    SNAPSHOT: ("answers", "confirmed", "transcript"),
    VOICE_ACTIVITY: ("level", "encounter_id"),
    CAPTURE_STATUS: ("connected",),
    FIELD_UPDATED: ("field", "value", "answers"),
    FIELD_CONFIRMED: ("field",),
    SAVE_RESULT: ("ok", "encounter_id", "patient_id", "answers"),
}

COMMANDS: dict[str, tuple[str, ...]] = {
    SESSION_START: ("encounter_id",),
    FINALIZE: ("encounter_id",),
    MIC_START: ("encounter_id",),
    MIC_STOP: (),
    SET_FIELD: ("field", "value"),
    SAVE: (),
    CONFIRM_FIELD: ("field",),
}

# Client -> backend audio data (the /ws/chunks payload; it carries no "type").
# Union of the keys the two producers send: the capture agent sends the first
# nine, the browser microphone adds the diagnostic block, and the e2e page
# object also names the encounter inline.
CHUNK_KEYS: tuple[str, ...] = (
    "chunk_id", "pcm_b64", "sample_rate", "channels", "mic_channel",
    "start_sample", "end_sample", "duration_ms", "language",
    "rms", "raw_rms", "analyser_rms", "anySignal", "actualRate",
    "label", "deviceId", "devRate",
    "encounter_id",
)

# Sentinel: "key must not appear on this shape" — distinct from None, which is
# a real wire value (e.g. chunk_result carries a null `confidence` when the
# serving adapter reported no logprob).
_ABSENT = object()


# --- backend -> client constructors ----------------------------------------
#
# Key order matches the emission points byte for byte. Optional keys are
# _ABSENT by default so a shape can omit them outright (the old dict literals
# did), while an explicitly passed None is written to the wire as null.

def chunk_result(
    *,
    chunk_id: int,
    encounter_id: str,
    transcript: str,
    status: str,
    speaker: str,
    language: str,
    answers: Any,
    confirmed: Any,
    alerts: Any,
    confidence: Any = _ABSENT,
    provider: str | None = _ABSENT,
) -> dict:
    """One chunk of audio acknowledged: its transcript line and the sheet.

    Two shapes share this event. The rejected/stub shape (`transcript` empty,
    `status` `rejected`) carries neither `confidence` nor `provider`. The
    filled shape carries `confidence` even when the serving adapter reported
    no metric — the key is present with a null value. `status` must be one of
    the canonical three; a constructor attempt at a fourth value fails here
    rather than drifting onto the wire.
    """
    if status not in STATUSES:
        raise ValueError(f"status must be one of {STATUSES}, got {status!r}")
    out: dict[str, Any] = {
        "type": CHUNK_RESULT,
        "chunk_id": chunk_id,
        "encounter_id": encounter_id,
        "transcript": transcript,
        "status": status,
    }
    if confidence is not _ABSENT:
        out["confidence"] = confidence
    if provider is not _ABSENT:
        out["provider"] = provider
    out["speaker"] = speaker
    out["language"] = language
    out["answers"] = answers
    out["confirmed"] = confirmed
    out["alerts"] = alerts
    return out


def attach_voice(result: dict, *, voice_level: float, vad: float) -> dict:
    """Append the chunk voice metrics to a chunk_result before it is sent.

    The chunks handler computes one RMS pass per accepted payload and reuses
    it for the voice-activity broadcast, the silence gate, and this wire
    field pair — `voice_level` (the raw 0..1 level) and `vad` (its 0/1
    thresholded flag). Returns a NEW dict; never mutates the session's
    payload.
    """
    out = dict(result)
    out["voice_level"] = voice_level
    out["vad"] = vad
    return out


def finalize_result(
    *,
    encounter_id: str,
    transcript: str,
    answers: Any,
    confirmed: Any,
    alerts: Any,
) -> dict:
    """The final, validated case sheet for the whole encounter (plus DB save)."""
    return {
        "type": FINALIZE_RESULT,
        "encounter_id": encounter_id,
        "transcript": transcript,
        "answers": answers,
        "confirmed": confirmed,
        "alerts": alerts,
    }


def session_state(*, active: bool, encounter_id: str = _ABSENT) -> dict:
    """Recording state change. The inactive shape carries no `encounter_id`
    (stop-of-nothing has no encounter to name)."""
    out: dict[str, Any] = {"type": SESSION_STATE, "active": active}
    if encounter_id is not _ABSENT:
        out["encounter_id"] = encounter_id
    return out


def snapshot(*, answers: Any, confirmed: Any, transcript: str) -> dict:
    """Catch-up state pushed to a dashboard client on connect."""
    return {
        "type": SNAPSHOT,
        "answers": answers,
        "confirmed": confirmed,
        "transcript": transcript,
    }


def voice_activity(*, level: float, encounter_id: str) -> dict:
    """Per-chunk voice level broadcast (one RMS pass shared with the gate)."""
    return {
        "type": VOICE_ACTIVITY,
        "level": level,
        "encounter_id": encounter_id,
    }


def capture_status(*, connected: bool) -> dict:
    """Whether any capture transport is connected, broadcast on every change."""
    return {"type": CAPTURE_STATUS, "connected": connected}


def field_updated(*, field: str, value: Any, answers: Any) -> dict:
    """A successful manual edit echo. `set_field` locks the cell, so the UI
    mirrors the confirmation lock from this event until the next full map."""
    return {
        "type": FIELD_UPDATED,
        "field": field,
        "value": value,
        "answers": answers,
    }


def field_confirmed(*, field: str) -> dict:
    """Echo of a confirmed field lock. This event has no client consumer
    today: the confirm command is kept first-class while the clinician-facing
    confirm affordance stays an open product decision."""
    return {"type": FIELD_CONFIRMED, "field": field}


def save_result(
    *,
    ok: bool,
    encounter_id: str,
    patient_id: Optional[int],
    answers: Any,
) -> dict:
    """Outcome of a dashboard save (idempotent per encounter)."""
    return {
        "type": SAVE_RESULT,
        "ok": ok,
        "encounter_id": encounter_id,
        "patient_id": patient_id,
        "answers": answers,
    }


# --- client -> backend command parsing --------------------------------------
#
# One union of parsed command definitions, in the order the handler branches
# runs them. The parsers normalise fields exactly as the old inline
# expressions did, so existing messages parse identically.

@dataclass(frozen=True)
class MicStart:
    encounter_id: str


@dataclass(frozen=True)
class MicStop:
    pass


@dataclass(frozen=True)
class SetField:
    field: str
    value: Any


@dataclass(frozen=True)
class Save:
    pass


@dataclass(frozen=True)
class ConfirmField:
    """First-class command; no client sends it today. Kept for the product
    decision about a clinician-facing confirm affordance — never delete the
    backend branch while that is open."""
    field: str


Command = Union[MicStart, MicStop, SetField, Save, ConfirmField]


@dataclass(frozen=True)
class Finalize:
    encounter_id: str


@dataclass(frozen=True)
class SessionStart:
    encounter_id: str


@dataclass(frozen=True)
class ChunkData:
    """Everything that is not a command on /ws/chunks: the audio payload,
    passed through untouched (the handlers read the keys they always read),
    plus its stripped encounter_id for the session-binding logic."""

    payload: Mapping
    encounter_id: str


ChunkMessage = Union[Finalize, SessionStart, ChunkData]


def _encounter_id(data: Mapping) -> str:
    """The inline expression every handler branch used for encounter ids:
    missing/null/non-string collapse to the empty string, whitespace stripped."""
    return str(data.get("encounter_id") or "").strip()


def parse_command(data: Mapping) -> Optional[Command]:
    """Parse one /ws/dashboard message into its command, or None when the
    type is not a dashboard command (unknown commands are ignored, exactly as
    the old if/elif chain ignored them)."""
    msg_type = data.get("type")
    if msg_type == MIC_START:
        return MicStart(encounter_id=_encounter_id(data))
    if msg_type == MIC_STOP:
        return MicStop()
    if msg_type == SET_FIELD:
        return SetField(field=data.get("field", ""), value=data.get("value"))
    if msg_type == SAVE:
        return Save()
    if msg_type == CONFIRM_FIELD:
        return ConfirmField(field=data.get("field", ""))
    return None


def parse_chunks_message(data: Mapping) -> ChunkMessage:
    """Parse one /ws/chunks message: the two commands, or the audio payload.

    `finalize` is checked first — the old handler did — because a finalize
    must not be mistaken for data, and any other message (including a
    command of the OTHER transport mis-delivered here) flows through as
    ChunkData exactly as it used to.
    """
    msg_type = data.get("type")
    if msg_type == FINALIZE:
        return Finalize(encounter_id=_encounter_id(data))
    if msg_type == SESSION_START:
        return SessionStart(encounter_id=_encounter_id(data))
    return ChunkData(payload=data, encounter_id=_encounter_id(data))
