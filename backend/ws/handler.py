"""WebSocket handlers — audio chunks, dashboard control, live broadcasting.

- /ws/chunks    : capture agent streams PCM chunks; the backend runs
                  ASR -> Q&A form extraction -> merge -> broadcast.
- /ws/dashboard : health-worker UI. Receives live transcript + form updates.
                  Sends mic_start / mic_stop / set_field / save commands.

Auto-filled fields land directly in the sheet (no per-field confirm).
Manual cell edits (set_field) lock the value against ASR overwrite.
"""

from __future__ import annotations

import array
import base64
import inspect
import json
import logging
import math
import re
import uuid
from datetime import datetime
from typing import Optional

from fastapi import WebSocket, WebSocketDisconnect

from config import settings
from ws.sarvam_asr import SarvamASR
from ws.bhashini_asr import BhashiniASR
from ws.local_asr import LocalWhisperASR
from ws.groq_asr import GroqWhisperASR
from ws.indicconformer_asr import IndicConformerASR
from llm.extract import GeminiExtractor
from engine.merge import MergeEngine
from engine.validate import validate_case_sheet
from engine.local_fill import local_fill
from db.connection import SessionLocal
from db.models import Encounter, Utterance, VitalsSnapshot, Alert, Patient
from sqlalchemy import delete as sa_delete
from storage.audio import log_deletion

logger = logging.getLogger(__name__)


def _accepts_context(provider) -> bool:
    """Whether this provider's transcribe_chunk() takes a `context` kwarg.

    Only Groq and local faster-whisper use the prompt-context carry; the
    Sarvam/Bhashini/IndicConformer adapters do not. We introspect the signature
    once per provider class instead of catching TypeError, which used to also
    swallow genuine TypeErrors raised *inside* a provider body and silently
    retry it with fewer arguments — turning a real bug into a no-op.
    """
    try:
        params = inspect.signature(provider.transcribe_chunk).parameters
    except (TypeError, ValueError):  # pragma: no cover - builtins/C-extensions
        return False
    if "context" in params:
        return True
    return any(p.kind is inspect.Parameter.VAR_KEYWORD for p in params.values())


# Cache of provider class -> bool, so the signature is inspected once per class
# rather than once per chunk per provider.
_CONTEXT_SUPPORT: dict[type, bool] = {}


def _provider_context_args(provider, context: str) -> dict:
    cls = type(provider)
    supported = _CONTEXT_SUPPORT.get(cls)
    if supported is None:
        supported = _accepts_context(provider)
        _CONTEXT_SUPPORT[cls] = supported
    return {"context": context} if supported else {}


# --- Prompt-echo (hallucination) detection --------------------------------
#
# Whisper fed near-silence does not return nothing: it regurgitates the prompt
# it was given. We always append `hi_prompt_terms` (a comma-separated domain
# vocabulary) to bias Hindi decoding, so a quiet chunk comes back as e.g.
#   "प्रसव पीड़ा, सामान्य प्रसव पीडा, रेफर, डिस्चार्ज"
# which local_fill() then turns into a FABRICATED delivery_mode and
# final_outcome on the case sheet.
#
# This is not catchable by confidence gating: measured against the live API,
# that hallucination comes back avg_logprob=-0.149, no_speech_prob=0.113,
# compression_ratio=0.82 — i.e. Whisper is *confidently* wrong and clears every
# logprob/no-speech threshold. Only comparing the output against the prompt we
# injected catches it.

_ECHO_MIN_TOKENS = 3      # below this, "सामान्य प्रसव" is a real answer
_ECHO_REPEAT_MIN_TOKENS = 2
_ECHO_FRAGMENT_MIN_CHARS = 3

# Devanagari + Latin word characters; everything else is separator.
_WORD_RE = re.compile(r"[ऀ-ॿa-z0-9]+", re.IGNORECASE)


def _echo_tokens(text: str) -> list[str]:
    return _WORD_RE.findall(text or "")


def _echo_norm(text: str) -> str:
    """Lowercased, punctuation-free, whitespace-collapsed form for comparison."""
    return " ".join(_WORD_RE.findall((text or "").lower()))


def is_echo_fragment(text: str, echoes: Optional[set[str]]) -> bool:
    """True when `text` is a piece of an echo we already rejected.

    Once Whisper starts regurgitating the prompt it drifts *within* the
    hallucinated phrase — the 4-term echo "प्रसव पीड़ा, सामान्य प्रसव पीड़ा,
    रेफर, डिस्चार्ज" is followed by the bare fragment "पीड़ा". A single word
    can't be judged on content (a patient may legitimately answer
    "सीज़ेरियन"), but it can be recognised as a substring of a known echo.
    """
    if not echoes:
        return False
    norm = _echo_norm(text)
    if len(norm) < _ECHO_FRAGMENT_MIN_CHARS:
        return False
    return any(norm in echo for echo in echoes)


def is_prompt_echo(
    text: str,
    prompt: str,
    seen: Optional[set[str]] = None,
    echoes: Optional[set[str]] = None,
) -> bool:
    """True when `text` looks like the model echoing `prompt` rather than speech.

    `seen` is the set of normalised transcripts already accepted this session;
    an identical repeat is treated as a hallucination too, since a fixed prompt
    makes the model emit the same phrase over and over. `echoes` is the set of
    already-rejected echoes, used to catch follow-on fragments.

    Deliberately biased toward precision. "सामान्य प्रसव" and "प्रसव पीड़ा" are
    BOTH two-word literal substrings of the vocabulary and are structurally
    indistinguishable by content, so the content rules require three words and
    only the repeat rule — which needs two — operates at the shorter length.
    Dropping a genuine second mention costs a duplicate line in the
    transcript; keeping a hallucination fabricates the clinical record.
    """
    if is_echo_fragment(text, echoes):
        return True

    norm = _echo_norm(text)
    tokens = _echo_tokens(text)
    if not tokens:
        return False

    # 1. Verbatim repeat of an earlier accepted chunk from the same prompt.
    if seen and len(tokens) >= _ECHO_REPEAT_MIN_TOKENS and norm in seen:
        return True

    if len(tokens) < _ECHO_MIN_TOKENS or not prompt:
        return False

    prompt_tokens = set(_echo_tokens(prompt))
    # 2. Every single word came out of the injected vocabulary.
    if prompt_tokens and all(t in prompt_tokens for t in tokens):
        return True
    # 3. The utterance is a literal slice of the vocabulary string. Real speech
    #    is never a verbatim substring of a comma-separated word list.
    prompt_norm = _echo_norm(prompt)
    if prompt_norm and norm in prompt_norm:
        return True
    return False



class ChunkSession:
    def __init__(self) -> None:
        self.groq = GroqWhisperASR()
        self.indic = IndicConformerASR()
        self.sarvam = SarvamASR()
        self.bhashini = BhashiniASR()
        self.local_asr = LocalWhisperASR()
        self.extractor = GeminiExtractor()
        self.merge = MergeEngine()
        self.encounter_id: str = ""
        self.chunk_ids: list[int] = []
        self.transcript_buffer: list[str] = []
        self.active: bool = False
        # Normalised transcripts already accepted this session, for repeat-
        # hallucination detection. Bounded so a long encounter can't grow it
        # without limit.
        self._seen_transcripts: set[str] = set()
        # Normalised texts already identified as prompt echoes, so follow-on
        # fragments of the same hallucination are caught too.
        self._echo_transcripts: set[str] = set()

    def reset(self, encounter_id: str = "") -> None:
        self.encounter_id = encounter_id
        self.chunk_ids = []
        self.transcript_buffer = []
        self._seen_transcripts = set()
        self._echo_transcripts = set()
        self.merge.reset()

    def _remember(self, transcript: str) -> None:
        if len(self._seen_transcripts) > 400:
            self._seen_transcripts.clear()
        self._seen_transcripts.add(_echo_norm(transcript))

    def _remember_echo(self, transcript: str) -> None:
        if len(self._echo_transcripts) > 50:
            self._echo_transcripts.clear()
        self._echo_transcripts.add(_echo_norm(transcript))

    def _provider_order(self, language: str) -> list:
        """Order ASR providers by best-fit for the spoken language."""
        lang_key = (language or "").strip().lower()
        if self.indic.supports(lang_key):
            return [self.indic, self.groq, self.sarvam, self.bhashini, self.local_asr]
        return [self.groq, self.sarvam, self.bhashini, self.indic, self.local_asr]

    def _prompt_context(self, language: str) -> str:
        """Build Whisper prompt = tail of previous transcript + domain vocab last.

        Capped to stay safely under Groq's 896-character prompt limit so a
        long session can never 400 with an oversized prompt mid-recording.
        """
        tail = ""
        if self.transcript_buffer:
            joined = " ".join(self.transcript_buffer[-2:])
            tail = joined[-settings.prompt_tail_characters:]
        terms = getattr(settings, "hi_prompt_terms", "").strip()
        if "hi" in (language or "").lower() and terms:
            parts = [t for t in (tail, terms) if t]
            prompt = " ".join(parts)
        else:
            prompt = tail
        return prompt[: settings.prompt_max_characters]

    @staticmethod
    def _dedupe_boundary(previous: str, new: str) -> str:
        """Strip a word re-emitted at the head of the new chunk (Whisper overlap)."""
        if not previous or not new:
            return new
        prev_words = previous.split()
        new_words = new.split()
        if not prev_words or not new_words:
            return new
        strip = 0
        if new_words[0] == prev_words[-1]:
            strip = 1
        elif len(prev_words) > 1 and new_words[0] == prev_words[-2]:
            strip = 1
        return " ".join(new_words[strip:]) if strip else new

    def _gate_result(self, asr_result: dict, pcm_level: float) -> Optional[str]:
        """Return None if chunk is usable; else 'rejected' (silence) or 'dropped'
        (hallucination/low-confidence). Confidence metrics only exist for some
        providers (local faster-whisper); the RMS gate works for all (incl.
        Groq, which does not expose no_speech_prob)."""
        no_speech = asr_result.get("no_speech_prob")
        compression = asr_result.get("compression_ratio")
        avg_logprob = asr_result.get("avg_logprob")

        # Silence detected either by the provider metric or by PCM energy.
        if no_speech is not None and no_speech > settings.no_speech_prob_threshold:
            return "rejected"
        if pcm_level < settings.min_pcm_level_for_speech:
            return "rejected"
        if compression is not None and compression > settings.compression_ratio_threshold:
            return "dropped"
        if avg_logprob is not None and avg_logprob < settings.avg_logprob_floor:
            return "dropped"
        return None

    def _live_window(self) -> str:
        """Transcript tail used for the per-chunk local fill.

        Bounded to the last N chunks so the ~30 regex passes in local_fill()
        don't re-scan the whole encounter on every chunk. MergeEngine keeps
        anything found in older chunks, so narrowing the window only limits
        how far back a *correction* can be picked up live — finalize() re-scans
        the full transcript regardless.
        """
        window = max(1, settings.local_fill_window_chunks)
        return " ".join(self.transcript_buffer[-window:])

    async def process_chunk(self, payload: dict, pcm_level: Optional[float] = None) -> Optional[dict]:
        if not self.active:
            return None

        pcm_b64 = payload.get("pcm_b64", "")
        chunk_id = payload.get("chunk_id", 0)
        duration_ms = payload.get("duration_ms") or 0
        language = payload.get("language", "hi")
        self.chunk_ids.append(chunk_id)
        context = self._prompt_context(language)

        # RMS is a full base64 decode + pure-Python sum over every sample, so it
        # is computed once here and reused for both the log line and the gate.
        # The caller may pass a value it already computed for the voice-activity
        # broadcast, in which case we reuse that instead of decoding again.
        if pcm_level is None:
            pcm_level = _pcm_level(pcm_b64)
        logger.info(
            "Chunk %d: len=%s dur=%sms js_rms=%.4f raw_rms=%.4f anlz_rms=%.4f anySignal=%s ctxRate=%s dev=%r@%s level=%.4f",
            chunk_id,
            len(pcm_b64),
            duration_ms,
            float(payload.get("rms") or 0),
            float(payload.get("raw_rms") or 0),
            float(payload.get("analyser_rms") or 0),
            payload.get("anySignal"),
            payload.get("actualRate"),
            payload.get("label") or "?",
            payload.get("devRate") or "?",
            pcm_level,
        )

        empty_payload = {
            "type": "chunk_result",
            "chunk_id": chunk_id,
            "encounter_id": self.encounter_id,
            "transcript": "",
            "status": "rejected",
            "speaker": "unknown",
            "language": "",
            "answers": self.merge.get_snapshot()["answers"],
            "confirmed": self.merge.get_snapshot()["_confirmed"],
            "alerts": [],
        }

        # Cheap pre-ASR silence gate: don't burn a cloud call on quiet/noise.
        if not pcm_b64 or pcm_level < settings.min_pcm_level_for_speech:
            return empty_payload

        transcript = ""
        asr_result: dict = {"speaker": "unknown", "language": ""}
        provider_name = ""

        for provider in self._provider_order(language):
            try:
                result = await provider.transcribe_chunk(
                    pcm_b64,
                    language=language,
                    duration_ms=duration_ms,
                    **_provider_context_args(provider, context),
                )
            except Exception as e:
                # Real errors (including TypeErrors from inside the adapter)
                # now surface here instead of being masked by a retry shim.
                logger.warning(
                    "%s failed for chunk %d: %s",
                    type(provider).__name__,
                    chunk_id,
                    e,
                )
                continue

            if result and result.get("text"):
                transcript = result["text"]
                asr_result = result
                provider_name = type(provider).__name__
                logger.info(
                    "Chunk %d ASR ok via %s (dur=%dms): %r",
                    chunk_id,
                    provider_name,
                    duration_ms,
                    transcript[:100],
                )
                break

        if not transcript:
            return empty_payload

        # Post-ASR gating: silence / hallucination should never reach the sheet.
        gate = self._gate_result(asr_result, pcm_level)
        if gate == "rejected":
            logger.info(
                "Chunk %d rejected as silence (dur=%dms pcm_level=%.4f prov=%s text=%r)",
                chunk_id,
                duration_ms,
                pcm_level,
                provider_name,
                transcript[:60],
            )
            return empty_payload
        if gate == "dropped":
            logprob = asr_result.get("avg_logprob")
            logger.info(
                "Chunk %d dropped (low confidence, %s avg_logprob=%.2f): %r",
                chunk_id,
                provider_name,
                logprob if logprob is not None else float("nan"),
                transcript[-80:],
            )
            return empty_payload

        # Prompt-echo guard. Whisper handed near-silence returns the domain
        # vocabulary we injected rather than silence, and confidence gating
        # cannot catch it (the echo comes back avg_logprob ~ -0.15). Left in
        # place it fabricates delivery_mode / final_outcome on the case sheet,
        # so it must be dropped here, before local_fill ever sees it.
        if is_prompt_echo(transcript, context, self._seen_transcripts, self._echo_transcripts):
            self._remember_echo(transcript)
            logger.info(
                "Chunk %d rejected as prompt echo (dur=%dms pcm_level=%.4f prov=%s): %r",
                chunk_id,
                duration_ms,
                pcm_level,
                provider_name,
                transcript[:80],
            )
            return empty_payload

        # Overlap dedup across chunk seams (Whisper re-emits tail words).
        previous = " ".join(self.transcript_buffer[-1:]) if self.transcript_buffer else ""
        transcript = self._dedupe_boundary(previous, transcript)
        if not transcript:
            return empty_payload

        tentative = bool(
            asr_result.get("avg_logprob") is not None
            and asr_result.get("avg_logprob") < settings.avg_logprob_tentative
        )

        self.transcript_buffer.append(transcript)
        self._remember(transcript)

        # Per-chunk: free local bilingual field filler (instant, no API quota).
        # Scoped to a bounded tail window — see _live_window().
        filled = local_fill(self._live_window())
        self.merge.merge(filled, chunk_id)
        snapshot = self.merge.get_snapshot()
        validation_alerts = validate_case_sheet(snapshot)

        return {
            "type": "chunk_result",
            "chunk_id": chunk_id,
            "encounter_id": self.encounter_id,
            "transcript": transcript,
            "status": "tentative" if tentative else "finalized",
            "confidence": asr_result.get("avg_logprob"),
            "provider": provider_name,
            "speaker": asr_result.get("speaker", "unknown"),
            "language": asr_result.get("language", ""),
            "answers": snapshot["answers"],
            "confirmed": snapshot["_confirmed"],
            "alerts": [{"field": a.field, "message": a.message, "severity": a.severity} for a in validation_alerts],
        }

    async def finalize(self) -> dict:
        full_transcript = " ".join(self.transcript_buffer)

        # Free local fill always runs first — fields already set locally stay.
        # NOTE: deliberately the FULL transcript, not the live window. This is
        # the one pass that can pair a question in one chunk with its answer in
        # another, and it runs once per patient, so the cost is irrelevant.
        filled = local_fill(full_transcript)
        self.merge.merge(filled, -1)

        # Gemini cleans up the ambiguous leftovers — ONE call per patient.
        if settings.llm_final_extract and full_transcript.strip():
            try:
                extracted = await self.extractor.extract(full_transcript)
                self.merge.merge(extracted, -1)
            except Exception as e:
                logger.warning("Gemini final extraction failed (local fill kept): %s", e)

        snapshot = self.merge.get_snapshot()
        validation_alerts = validate_case_sheet(snapshot)

        db = SessionLocal()
        try:
            self._persist(db, snapshot, validation_alerts)
            if settings.audio_delete_after_transcribe:
                log_deletion(db, self.encounter_id, self.chunk_ids)
        finally:
            db.close()

        self.active = False
        return {
            "type": "finalize_result",
            "encounter_id": self.encounter_id,
            "transcript": full_transcript,
            "answers": snapshot["answers"],
            "confirmed": snapshot["_confirmed"],
            "alerts": [{"field": a.field, "message": a.message, "severity": a.severity} for a in validation_alerts],
        }

    def confirm(self, field_name: str) -> bool:
        return self.merge.confirm(field_name)

    def set_field(self, field_name: str, value) -> bool:
        return self.merge.set_field(field_name, value)

    def _patient_from_answers(self, answers: dict, encounter_id: str) -> Patient:
        def s(key):
            v = answers.get(key)
            if v is None:
                return None
            if isinstance(v, list):
                return ", ".join(str(x) for x in v)
            return str(v)

        age_raw = answers.get("age")
        age_val = None
        if age_raw not in (None, ""):
            try:
                age_val = int(float(str(age_raw).strip()))
            except (TypeError, ValueError):
                age_val = None

        return Patient(
            encounter_id=encounter_id,
            name=s("name"),
            age=age_val,
            language=None,
            spouse_parent_of=s("spouse_parent_of"),
            contact_phone=s("contact_phone"),
            address=s("address"),
            district=s("district"),
            block=s("block"),
            health_centre=s("health_centre"),
            answers={k: v for k, v in answers.items() if v is not None},
            saved_at=datetime.utcnow(),
        )

    def _persist(self, db, snapshot: dict, alerts) -> None:
        # Idempotent: a repeat finalize/save (same encounter_id) replaces old rows.
        if self.encounter_id:
            for model in (Utterance, VitalsSnapshot, Alert, Patient, Encounter):
                db.execute(sa_delete(model).where(model.encounter_id == self.encounter_id) if hasattr(model, "encounter_id") else sa_delete(model).where(model.id == self.encounter_id))
        encounter = Encounter(id=self.encounter_id or None)
        db.add(encounter)
        db.flush()
        self.encounter_id = encounter.id

        for i, text in enumerate(self.transcript_buffer):
            db.add(Utterance(
                encounter_id=encounter.id,
                chunk_id=i,
                speaker="mixed",
                transcript=text,
            ))

        db.add(VitalsSnapshot(
            encounter_id=encounter.id,
            data={
                "answers": snapshot["answers"],
                "confirmed": snapshot["_confirmed"],
            },
            confirmed=False,
        ))

        answers = snapshot["answers"]
        patient = self._patient_from_answers(answers, encounter.id)
        db.add(patient)

        for alert in alerts:
            db.add(Alert(
                encounter_id=encounter.id,
                field=alert.field,
                message=alert.message,
                severity=alert.severity,
            ))

        db.commit()
        logger.info(
            "Persisted encounter %s (patient %s) with %d utterances",
            encounter.id,
            patient.id,
            len(self.transcript_buffer),
        )
        return patient


# --- Connection registries -------------------------------------------------

dashboard_clients: set[WebSocket] = set()
capture_clients: set[WebSocket] = set()


class SessionRegistry:
    """Maps encounter_id -> ChunkSession.

    This replaces a single module-level `current_session` global, which let the
    capture agent and the dashboard end up pointing at *different* ChunkSession
    objects for the same encounter — and let a dashboard `mic_start` call
    reset() the very session the capture agent was streaming into, silently
    discarding the transcript collected so far.

    Sessions are keyed by encounter_id so both transports converge on the same
    object. `_active` tracks which one is currently recording, because a
    capture agent that has not yet announced an encounter_id still needs the
    dashboard's mic_start/mic_stop to address it.
    """

    def __init__(self) -> None:
        self._by_id: dict[str, ChunkSession] = {}
        self._active: Optional[ChunkSession] = None

    @staticmethod
    def _key(encounter_id: str) -> str:
        return (encounter_id or "").strip()

    def resolve(self, encounter_id: str = "") -> ChunkSession:
        """Get the session for this encounter, creating it if unseen.

        With no encounter_id we fall back to the currently-active session, so a
        dashboard that doesn't know the id (capture-agent mode) still reaches
        the running recording instead of orphaning it.
        """
        key = self._key(encounter_id)
        if key:
            existing = self._by_id.get(key)
            if existing is not None:
                return existing
            session = ChunkSession()
            session.encounter_id = key
            self._by_id[key] = session
            return session
        if self._active is not None:
            return self._active
        return self.set_active(ChunkSession())

    def set_active(self, session: ChunkSession) -> ChunkSession:
        self._active = session
        key = self._key(session.encounter_id)
        if key:
            self._by_id[key] = session
        return session

    @property
    def active(self) -> Optional[ChunkSession]:
        return self._active

    def get(self, encounter_id: str) -> Optional[ChunkSession]:
        return self._by_id.get(self._key(encounter_id))

    def release(self, session: ChunkSession) -> None:
        """Drop a session once its transport is gone and it isn't recording."""
        if self._active is session:
            self._active = None
        key = self._key(session.encounter_id)
        if key and self._by_id.get(key) is session:
            del self._by_id[key]


sessions = SessionRegistry()


def _pcm_level(pcm_b64: str) -> float:
    """Rough RMS voice level (0..1) for a base64 PCM16 chunk."""
    try:
        samples = array.array("h", base64.b64decode(pcm_b64))
        if not samples:
            return 0.0
        rms = math.sqrt(sum(s * s for s in samples) / len(samples))
        return min(1.0, rms / 5000.0)
    except Exception:
        return 0.0


async def broadcast_capture_status() -> None:
    await broadcast_to_dashboard({
        "type": "capture_status",
        "connected": bool(capture_clients),
    })


async def broadcast_to_dashboard(message: dict) -> None:
    dead: list[WebSocket] = []
    for client in list(dashboard_clients):
        try:
            await client.send_text(json.dumps(message))
        except Exception:
            dead.append(client)
    for d in dead:
        dashboard_clients.discard(d)


async def ws_chunks_handler(websocket: WebSocket) -> None:
    """Capture-agent endpoint. Runs ASR -> extraction and broadcasts live."""
    await websocket.accept()
    capture_clients.add(websocket)
    await broadcast_capture_status()
    # Bound lazily on the first payload that names an encounter, so an agent
    # and a dashboard referring to the same encounter share one ChunkSession.
    session: Optional[ChunkSession] = None

    try:
        while True:
            raw = await websocket.receive_text()
            data = json.loads(raw)

            incoming_id = str(data.get("encounter_id") or "").strip()

            if data.get("type") == "finalize":
                session = session or sessions.resolve(incoming_id)
                if incoming_id:
                    session.encounter_id = incoming_id
                result = await session.finalize()
                await websocket.send_text(json.dumps(result))
                await broadcast_to_dashboard(result)
                session.active = False
                break

            if data.get("type") == "session_start":
                session = sessions.resolve(incoming_id)
                session.active = True
                session.reset(session.encounter_id or incoming_id)
                sessions.set_active(session)
                await broadcast_to_dashboard({"type": "session_state", "active": True, "encounter_id": session.encounter_id})
                continue

            # Re-resolve if this payload names a different encounter than the
            # one we were already filling (e.g. a browser-mic run switching id).
            if session is None or (incoming_id and incoming_id != session.encounter_id):
                session = sessions.resolve(incoming_id)
            if incoming_id:
                session.encounter_id = incoming_id
                sessions.set_active(session)

            # First audio chunk implicitly starts the session (the capture agent
            # does not send session_start), so chunks are never dropped.
            if not session.active:
                session.active = True
                session.reset(session.encounter_id)
                await broadcast_to_dashboard({
                    "type": "session_state",
                    "active": True,
                    "encounter_id": session.encounter_id,
                })

            # One RMS pass, reused for the voice-activity broadcast AND the
            # in-handler silence gate.
            voice_level = _pcm_level(data.get("pcm_b64", ""))
            await broadcast_to_dashboard({
                "type": "voice_activity",
                "level": voice_level,
                "encounter_id": session.encounter_id,
            })

            result = await session.process_chunk(data, pcm_level=voice_level)
            if result is None:
                # Not recording — drain silently so the agent keeps its socket.
                continue
            result["voice_level"] = voice_level
            result["vad"] = 1.0 if voice_level > 0.02 else 0.0
            await websocket.send_text(json.dumps(result))
            await broadcast_to_dashboard(result)

    except WebSocketDisconnect:
        logger.info("Chunks client disconnected")
    except Exception as e:
        logger.error("Chunks WebSocket error: %s", e)
    finally:
        capture_clients.discard(websocket)
        await broadcast_capture_status()
        if session is not None:
            session.active = False
            sessions.release(session)


async def ws_dashboard_handler(websocket: WebSocket) -> None:
    """Dashboard endpoint — commands from the health worker + live updates."""
    await websocket.accept()
    dashboard_clients.add(websocket)

    try:
        # Send current state on connect (snapshot of the running session)
        active = sessions.active
        if active is not None:
            snapshot = active.merge.get_snapshot()
            if active.active:
                await websocket.send_text(json.dumps({
                    "type": "session_state",
                    "active": True,
                    "encounter_id": active.encounter_id,
                }))
            await websocket.send_text(json.dumps({
                "type": "snapshot",
                "answers": snapshot["answers"],
                "confirmed": snapshot["_confirmed"],
                "transcript": " ".join(active.transcript_buffer[-8:]),
            }))
        await broadcast_capture_status()

        while True:
            raw = await websocket.receive_text()
            data = json.loads(raw)
            msg_type = data.get("type")

            if msg_type == "mic_start":
                requested = str(data.get("encounter_id") or "").strip()
                session = sessions.resolve(requested)
                # Only reset a session that isn't already recording. Previously
                # this unconditionally called reset(), so a health worker
                # clicking "Start" while the capture agent was streaming wiped
                # the in-progress transcript.
                if not session.active:
                    session.active = True
                    session.reset(requested or session.encounter_id)
                sessions.set_active(session)
                logger.info("Recording started (encounter %s)", session.encounter_id)
                await broadcast_to_dashboard({
                    "type": "session_state",
                    "active": True,
                    "encounter_id": session.encounter_id,
                })

            elif msg_type == "mic_stop":
                session = sessions.active
                if session and session.active:
                    result = await session.finalize()
                    await broadcast_to_dashboard(result)
                else:
                    await broadcast_to_dashboard({"type": "session_state", "active": False})

            elif msg_type == "set_field":
                field = data.get("field", "")
                value = data.get("value")
                session = sessions.active or sessions.resolve()
                if session.set_field(field, value):
                    snapshot = session.merge.get_snapshot()
                    await broadcast_to_dashboard({
                        "type": "field_updated",
                        "field": field,
                        "value": value,
                        "answers": snapshot["answers"],
                    })

            elif msg_type == "save":
                session = sessions.active or sessions.resolve()
                if not session.encounter_id:
                    session.encounter_id = str(uuid.uuid4())
                    sessions.set_active(session)
                snapshot = session.merge.get_snapshot()
                validation_alerts = validate_case_sheet(snapshot)
                db = SessionLocal()
                try:
                    patient = session._persist(db, snapshot, validation_alerts)
                    patient_id = patient.id if patient else None
                    encounter_id = session.encounter_id
                finally:
                    db.close()
                await broadcast_to_dashboard({
                    "type": "save_result",
                    "ok": True,
                    "encounter_id": encounter_id,
                    "patient_id": patient_id,
                    "answers": snapshot["answers"],
                })

            elif msg_type == "confirm_field":
                # Kept for wire compatibility; UI no longer sends this.
                field = data.get("field", "")
                session = sessions.active
                if session and session.confirm(field):
                    await broadcast_to_dashboard({
                        "type": "field_confirmed",
                        "field": field,
                    })

    except WebSocketDisconnect:
        pass
    except Exception as e:
        logger.error("Dashboard WebSocket error: %s", e)
    finally:
        dashboard_clients.discard(websocket)