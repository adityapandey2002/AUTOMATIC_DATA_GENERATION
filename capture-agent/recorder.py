"""Audio recorder — captures 16kHz mono/stereo WAV from USB mic array."""

from __future__ import annotations

import queue
import threading
from typing import Optional

import numpy as np
import sounddevice as sd

SAMPLE_RATE = 16000
CHANNELS = 2  # stereo for diarization via mic separation
BLOCK_SIZE = 1024


class Recorder:
    def __init__(
        self,
        device: Optional[int] = None,
        sample_rate: int = SAMPLE_RATE,
        channels: int = CHANNELS,
    ) -> None:
        self.device = device
        self.sample_rate = sample_rate
        self.channels = channels
        self.audio_queue: queue.Queue[np.ndarray] = queue.Queue(maxsize=128)
        self._stream: Optional[sd.InputStream] = None
        self._running = False

    def _callback(self, indata: np.ndarray, frames: int, time_info, status) -> None:
        if status:
            pass  # drop status for now — could log overflow
        self.audio_queue.put(indata.copy())

    def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._stream = sd.InputStream(
            device=self.device,
            samplerate=self.sample_rate,
            channels=self.channels,
            blocksize=BLOCK_SIZE,
            dtype="float32",
            callback=self._callback,
        )
        self._stream.start()

    def stop(self) -> None:
        self._running = False
        if self._stream is not None:
            self._stream.stop()
            self._stream.close()
            self._stream = None

    def read(self, timeout: float = 0.1) -> Optional[np.ndarray]:
        try:
            return self.audio_queue.get(timeout=timeout)
        except queue.Empty:
            return None

    def list_devices(self) -> list[dict]:
        devices = sd.query_devices()
        inputs = []
        for i, d in enumerate(devices):
            if d["max_input_channels"] > 0:
                inputs.append({"index": i, "name": d["name"], "channels": d["max_input_channels"]})
        return inputs
