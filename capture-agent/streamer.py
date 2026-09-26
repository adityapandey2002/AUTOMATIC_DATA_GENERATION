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

# Socket timeout in seconds. Serves two purposes: upper bound on how long a
# send can block, and the reader thread's poll interval (it catches
# WebSocketTimeoutException and loops). Must comfortably exceed the time to
# push one chunk's base64 payload.
_SOCKET_TIMEOUT_S = 30.0


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
        self._reader: Optional[threading.Thread] = None
        self._stop = threading.Event()

    def connect(self) -> bool:
        for attempt in range(1, self.max_retries + 1):
            try:
                # Socket timeout doubles as the reader's poll interval: recv()
                # raises WebSocketTimeoutException on each expiry, which the
                # reader loop swallows. It must stay well above the time to send
                # one chunk, or a slow send spuriously looks like a dead socket.
                ws = websocket.create_connection(self.ws_url, timeout=_SOCKET_TIMEOUT_S)
                self._ws = ws
                self._connected = True
                self._stop.clear()
                self._start_reader(ws)
                self._flush_spool()
                logger.info("Connected to backend at %s", self.ws_url)
                return True
            except (ConnectionRefusedError, OSError) as e:
                logger.warning("Connect attempt %d/%d failed: %s", attempt, self.max_retries, e)
                time.sleep(self.retry_delay * min(attempt, 5))
        self._connected = False
        return False

    def _start_reader(self, ws: websocket.WebSocket) -> None:
        """Drain the socket from a daemon thread.

        This is not optional housekeeping. websocket-client only processes
        control frames -- ping, pong, close -- inside recv(). The backend sends
        a JSON reply for every accepted chunk, and uvicorn/websockets sends
        periodic pings and closes the connection if they go unanswered. A client
        that only ever calls send() therefore never drains the replies, never
        auto-pongs, and gets disconnected by ping timeout. That is what made
        'Chunks client disconnected' appear every few seconds while the
        microphone kept recording: the agent reconnected, resent nothing, and
        the session appeared to stall.
        """
        self._reader = threading.Thread(
            target=self._read_loop, args=(ws,), name="ws-reader", daemon=True
        )
        self._reader.start()

    def _read_loop(self, ws: websocket.WebSocket) -> None:
        while not self._stop.is_set():
            try:
                ws.recv()
            except websocket.WebSocketTimeoutException:
                continue  # idle socket, still healthy
            except (websocket.WebSocketException, OSError) as e:
                # Only retire the connection if it is still the current one; a
                # reconnect may already have installed a fresh socket.
                if self._ws is ws:
                    logger.warning("Backend connection lost: %s", e)
                    self._connected = False
                return

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

        if not self._connected or self._ws is None:
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
        ws = self._ws
        if ws is None:
            return
        while self._spool:
            payload = self._spool[0]
            try:
                with self._lock:
                    ws.send(json.dumps(payload))
                self._spool.popleft()
            except (websocket.WebSocketException, OSError):
                break

    def send_finalize(self, encounter_id: str) -> None:
        msg = {"type": "finalize", "encounter_id": encounter_id}
        ws = self._ws
        if not self._connected or ws is None:
            return
        try:
            with self._lock:
                ws.send(json.dumps(msg))
        except (websocket.WebSocketException, OSError) as e:
            logger.warning("Finalize send failed: %s", e)
            self._connected = False

    def disconnect(self) -> None:
        self._stop.set()
        self._connected = False
        ws, self._ws = self._ws, None
        if ws is not None:
            try:
                ws.close()
            except Exception:
                pass
        reader, self._reader = self._reader, None
        if reader is not None and reader.is_alive():
            reader.join(timeout=2.0)
