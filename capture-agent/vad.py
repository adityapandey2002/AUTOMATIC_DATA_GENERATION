"""Voice Activity Detection — Silero VAD, chunks audio into speech segments."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import numpy as np
import torch


@dataclass
class SpeechChunk:
    audio: np.ndarray  # float32 mono
    sample_rate: int
    start_sample: int
    end_sample: int

    @property
    def duration_ms(self) -> float:
        return len(self.audio) / self.sample_rate * 1000

    @property
    def pcm_bytes(self) -> bytes:
        pcm = (self.audio * 32767).astype(np.int16)
        return pcm.tobytes()


class VADChunker:
    def __init__(
        self,
        sample_rate: int = 16000,
        threshold: float = 0.5,
        min_speech_ms: float = 300,
        max_speech_ms: float = 10000,
        min_silence_ms: float = 400,
        context_ms: float = 300,
    ) -> None:
        self.sample_rate = sample_rate
        self.threshold = threshold
        self.min_speech_samples = int(min_speech_ms * sample_rate / 1000)
        self.max_speech_samples = int(max_speech_ms * sample_rate / 1000)
        self.min_silence_samples = int(min_silence_ms * sample_rate / 1000)
        self.context_samples = int(context_ms * sample_rate / 1000)

        self._model, _ = torch.hub.load(
            repo_or_dir="snakers4/silero-vad",
            model="silero_vad",
            force_reload=False,
            onnx=False,
        )
        self._buffer: list[np.ndarray] = []
        self._speech_start: Optional[int] = None
        self._silence_count = 0
        self._global_offset = 0

    def reset(self) -> None:
        self._buffer.clear()
        self._speech_start = None
        self._silence_count = 0
        self._global_offset = 0

    def feed(self, audio_chunk: np.ndarray) -> list[SpeechChunk]:
        """Feed raw float32 mono audio, get back complete speech chunks."""
        self._buffer.append(audio_chunk)
        total_samples = sum(len(c) for c in self._buffer)

        if total_samples < 512:
            return []

        audio = np.concatenate(self._buffer)
        self._buffer.clear()

        prob = self._get_speech_prob(audio)
        is_speech = prob >= self.threshold

        chunks: list[SpeechChunk] = []

        if is_speech:
            self._silence_count = 0
            if self._speech_start is None:
                self._speech_start = max(0, len(audio) - self.min_speech_samples)
        else:
            self._silence_count += len(audio)
            if self._speech_start is not None and self._silence_count >= self.min_silence_samples:
                speech_audio = audio[self._speech_start:]
                if len(speech_audio) >= self.min_speech_samples:
                    truncated = speech_audio[: self.max_speech_samples]
                    context_start = max(0, self._speech_start - self.context_samples)
                    chunk_with_context = audio[context_start:]
                    chunks.append(SpeechChunk(
                        audio=chunk_with_context,
                        sample_rate=self.sample_rate,
                        start_sample=self._global_offset + context_start,
                        end_sample=self._global_offset + self._speech_start + len(speech_audio),
                    ))
                self._speech_start = None
                self._silence_count = 0

        self._global_offset += len(audio)
        return chunks

    def flush(self) -> list[SpeechChunk]:
        """Flush any remaining buffered speech."""
        if self._speech_start is None or not self._buffer:
            return []
        audio = np.concatenate(self._buffer)
        self._buffer.clear()
        speech_audio = audio[self._speech_start:]
        context_start = max(0, self._speech_start - self.context_samples)
        chunk = SpeechChunk(
            audio=audio[context_start:],
            sample_rate=self.sample_rate,
            start_sample=self._global_offset + context_start,
            end_sample=self._global_offset + len(audio),
        )
        self._speech_start = None
        self._silence_count = 0
        return [chunk] if len(speech_audio) >= self.min_speech_samples else []

    def _get_speech_prob(self, audio: np.ndarray) -> float:
        self._model.reset_states()
        window = 512 if self.sample_rate == 16000 else 256
        tensor = torch.from_numpy(audio).float()
        if tensor.dim() == 1:
            tensor = tensor.unsqueeze(0)

        probs: list[float] = []
        with torch.no_grad():
            for start in range(0, tensor.shape[1], window):
                frame = tensor[:, start : start + window]
                if frame.shape[1] < window:
                    frame = torch.nn.functional.pad(frame, (0, window - frame.shape[1]))
                probs.append(self._model(frame, self.sample_rate).item())
        return max(probs) if probs else 0.0
