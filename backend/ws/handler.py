"""WebSocket handlers — audio chunks, dashboard control, live broadcasting.

- /ws/chunks    : capture agent streams PCM chunks; the backend runs
                  ASR -> Q&A form extraction -> merge -> broadcast.
- /ws/dashboard : health-worker UI. Receives live transcript + form updates.
                  Sends mic_start / mic_stop / confirm_field commands.

The health worker has the final say: they start/stop recording and confirm
each auto-filled field before it locks.
"""

from __future__ import annotations

import array
import base64
import json
import logging
import math
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

    def reset(self, encounter_id: str = "") -> None:
        self.encounter_id = encounter_id
        self.chunk_ids = []
        self.transcript_buffer = []
        self.merge.reset()

    def _provider_order(self, language: str) -> list:
        """Order ASR providers by best-fit for the spoken language."""
        lang_key = (language or "").strip().lower()
        if self.indic.supports(lang_key):
            return [self.indic, self.groq, self.sarvam, self.bhashini, self.local_asr]
        return [self.groq, self.sarvam, self.bhashini, self.indic, self.local_asr]

    async def process_chunk(self, payload: dict) -> Optional[dict]:
        if not self.active:
            return None

        pcm_b64 = payload.get("pcm_b64", "")
        chunk_id = payload.get("chunk_id", 0)
        duration_ms = payload.get("duration_ms") or 0
        language = payload.get("language", "hi")
        self.chunk_ids.append(chunk_id)

        transcript = ""
        asr_result: dict = {"speaker": "unknown", "language": ""}

        for provider in self._provider_order(language):
            try:
                result = await provider.transcribe_chunk(
                    pcm_b64, language=language, duration_ms=duration_ms
                )
            except TypeError:
                result = await provider.transcribe_chunk(pcm_b64, language=language)
            except Exception as e:
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
                break

        if not transcript:
            return {
                "type": "chunk_result",
                "chunk_id": chunk_id,
                "encounter_id": self.encounter_id,
                "transcript": "",
                "speaker": "unknown",
                "language": "",
                "answers": self.merge.get_snapshot()["answers"],
                "confirmed": self.merge.get_snapshot()["_confirmed"],
                "alerts": [],
            }

        self.transcript_buffer.append(transcript)
        full_transcript = " ".join(self.transcript_buffer)

        # Per-chunk: free local bilingual field filler (instant, no API quota)
        filled = local_fill(full_transcript)
        self.merge.merge(filled, chunk_id)
        snapshot = self.merge.get_snapshot()
        validation_alerts = validate_case_sheet(snapshot)

        return {
            "type": "chunk_result",
            "chunk_id": chunk_id,
            "encounter_id": self.encounter_id,
            "transcript": transcript,
            "speaker": asr_result.get("speaker", "unknown"),
            "language": asr_result.get("language", ""),
            "answers": snapshot["answers"],
            "confirmed": snapshot["_confirmed"],
            "alerts": [{"field": a.field, "message": a.message, "severity": a.severity} for a in validation_alerts],
        }

    async def finalize(self) -> dict:
        full_transcript = " ".join(self.transcript_buffer)

        # Free local fill always runs first — fields already set locally stay.
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

    def _persist(self, db, snapshot: dict, alerts) -> None:
        # Idempotent: a repeat finalize (same encounter_id) replaces old rows.
        if self.encounter_id:
            for model in (Utterance, VitalsSnapshot, Alert, Patient, Encounter):
                db.execute(sa_delete(model).where(model.encounter_id == self.encounter_id) if hasattr(model, "encounter_id") else sa_delete(model).where(model.id == self.encounter_id))
        encounter = Encounter(id=self.encounter_id or None)
        db.add(encounter)
        db.flush()

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

        for alert in alerts:
            db.add(Alert(
                encounter_id=encounter.id,
                field=alert.field,
                message=alert.message,
                severity=alert.severity,
            ))

        db.commit()
        logger.info("Persisted encounter %s with %d utterances", encounter.id, len(self.transcript_buffer))


# --- Connection registries -------------------------------------------------

dashboard_clients: set[WebSocket] = set()
capture_clients: set[WebSocket] = set()
current_session: Optional[ChunkSession] = None


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
    global current_session
    await websocket.accept()
    capture_clients.add(websocket)
    await broadcast_capture_status()
    session = ChunkSession()
    current_session = session

    try:
        while True:
            raw = await websocket.receive_text()
            data = json.loads(raw)

            if data.get("type") == "finalize":
                session.encounter_id = data.get("encounter_id", session.encounter_id)
                result = await session.finalize()
                await websocket.send_text(json.dumps(result))
                await broadcast_to_dashboard(result)
                session.active = False
                break

            if data.get("type") == "session_start":
                session.active = True
                session.encounter_id = data.get("encounter_id", "")
                session.reset(session.encounter_id)
                await broadcast_to_dashboard({"type": "session_state", "active": True, "encounter_id": session.encounter_id})
                continue

            if "encounter_id" in data:
                session.encounter_id = data["encounter_id"]

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

            voice_level = _pcm_level(data.get("pcm_b64", ""))
            await broadcast_to_dashboard({
                "type": "voice_activity",
                "level": voice_level,
                "encounter_id": session.encounter_id,
            })

            result = await session.process_chunk(data)
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
        if current_session is session:
            current_session = None
        session.active = False


async def ws_dashboard_handler(websocket: WebSocket) -> None:
    """Dashboard endpoint — commands from the health worker + live updates."""
    global current_session
    await websocket.accept()
    dashboard_clients.add(websocket)

    try:
        # Send current state on connect (snapshot of the running session)
        if current_session is not None:
            snapshot = current_session.merge.get_snapshot()
            if current_session.active:
                await websocket.send_text(json.dumps({
                    "type": "session_state",
                    "active": True,
                    "encounter_id": current_session.encounter_id,
                }))
            await websocket.send_text(json.dumps({
                "type": "snapshot",
                "answers": snapshot["answers"],
                "confirmed": snapshot["_confirmed"],
                "transcript": " ".join(current_session.transcript_buffer[-8:]),
            }))
        await broadcast_capture_status()

        while True:
            raw = await websocket.receive_text()
            data = json.loads(raw)
            msg_type = data.get("type")

            if msg_type == "mic_start":
                session = current_session or ChunkSession()
                current_session = session
                session.active = True
                session.reset(data.get("encounter_id", ""))
                logger.info("Recording started (encounter %s)", session.encounter_id)
                await broadcast_to_dashboard({
                    "type": "session_state",
                    "active": True,
                    "encounter_id": session.encounter_id,
                })

            elif msg_type == "mic_stop":
                if current_session and current_session.active:
                    result = await current_session.finalize()
                    await broadcast_to_dashboard(result)
                else:
                    await broadcast_to_dashboard({"type": "session_state", "active": False})

            elif msg_type == "confirm_field":
                field = data.get("field", "")
                if current_session and current_session.confirm(field):
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