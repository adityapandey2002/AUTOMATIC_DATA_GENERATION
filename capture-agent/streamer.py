"""WebSocket streamer — sends audio chunks to the backend, handles reconnection."""

from __future__ import annotations

import base64
import json
import logging
import threading
import time
from typing import Optional
from collections import deque

import websocket

from vad import SpeechChunk

logger = logging.getLogger(__name__)


class ChunkStreamer:
    def __init__(
        self,
        ws_url: str,
        max_retries: int = 10,
        retry_delay: float = 2.0,
        language: str = "hi",
    ) -> None:
        self.ws_url = ws_url
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self.language = language
        self._ws: Optional[websocket.WebSocket] = None
        self._lock = threading.Lock()
        self._connected = False
        self._spool: deque[dict] = deque(maxlen=500)
        self._chunk_counter = 0

    def connect(self) -> bool:
        for attempt in range(1, self.max_retries + 1):
            try:
                self._ws = websocket.create_connection(self.ws_url, timeout=10)
                self._connected = True
                self._flush_spool()
                logger.info("Connected to backend at %s", self.ws_url)
                return True
            except (ConnectionRefusedError, OSError) as e:
                logger.warning("Connect attempt %d/%d failed: %s", attempt, self.max_retries, e)
                time.sleep(self.retry_delay * min(attempt, 5))
        self._connected = False
        return False

    def send_chunk(self, chunk: SpeechChunk, mic_channel: int = 0) -> bool:
        payload = {
            "chunk_id": self._chunk_counter,
            "pcm_b64": base64.b64encode(chunk.pcm_bytes).decode("ascii"),
            "sample_rate": chunk.sample_rate,
            "channels": 1,
            "mic_channel": mic_channel,
            "start_sample": chunk.start_sample,
            "end_sample": chunk.end_sample,
            "duration_ms": round(chunk.duration_ms, 1),
            "language": self.language,
        }
        self._chunk_counter += 1

        if not self._connected:
            self._spool.append(payload)
            self.connect()
            return self._connected

        try:
            with self._lock:
                self._ws.send(json.dumps(payload))
            return True
        except (websocket.WebSocketException, OSError) as e:
            logger.warning("Send failed: %s — spooling", e)
            self._connected = False
            self._spool.append(payload)
            self.connect()
            return False

    def _flush_spool(self) -> None:
        while self._spool:
            payload = self._spool[0]
            try:
                with self._lock:
                    self._ws.send(json.dumps(payload))
                self._spool.popleft()
            except (websocket.WebSocketException, OSError):
                break

    def send_finalize(self, encounter_id: str) -> None:
        msg = {"type": "finalize", "encounter_id": encounter_id}
        try:
            with self._lock:
                self._ws.send(json.dumps(msg))
        except (websocket.WebSocketException, OSError):
            pass

    def disconnect(self) -> None:
        self._connected = False
        if self._ws:
            try:
                self._ws.close()
            except Exception:
                pass
            self._ws = None
