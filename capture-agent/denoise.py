"""Denoiser — DeepFilterNet primary, RNNoise fallback for low-spec machines."""

from __future__ import annotations

import subprocess
import tempfile
from abc import ABC, abstractmethod
from typing import Optional

import numpy as np


class Denoiser(ABC):
    @abstractmethod
    def process(self, audio: np.ndarray, sample_rate: int) -> np.ndarray:
        ...


class DeepFilterDenoiser(Denoiser):
    def __init__(self) -> None:
        try:
            from df.enhance import init_df, load_audio, save_audio  # noqa: F401
            self._available = True
        except ImportError:
            self._available = False

        if self._available:
            from df.enhance import init_df
            self._model, self._df_state, _ = init_df()

    def process(self, audio: np.ndarray, sample_rate: int) -> np.ndarray:
        if not self._available:
            return audio
        from df.enhance import enhance
        import torch

        wav = torch.from_numpy(audio).float()
        if wav.dim() == 1:
            wav = wav.unsqueeze(0)
        enhanced = enhance(self._model, self._df_state, wav)
        return enhanced.squeeze(0).numpy()


class RNNoiseDenoiser(Denoiser):
    def __init__(self) -> None:
        self._available = self._check_rnnoise()

    @staticmethod
    def _check_rnnoise() -> bool:
        try:
            result = subprocess.run(
                ["rnnoise_demo", "--help"],
                capture_output=True, timeout=5,
            )
            return result.returncode == 0
        except (FileNotFoundError, subprocess.TimeoutExpired):
            return False

    def process(self, audio: np.ndarray, sample_rate: int) -> np.ndarray:
        if not self._available:
            return audio
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=True) as tmp_in, \
             tempfile.NamedTemporaryFile(suffix=".wav", delete=True) as tmp_out:
            import scipy.io.wavfile as wavfile
            pcm = (audio * 32767).astype(np.int16)
            wavfile.write(tmp_in.name, sample_rate, pcm)
            subprocess.run(
                ["rnnoise_demo", tmp_in.name, tmp_out.name],
                capture_output=True, timeout=30,
            )
            _, denoised = wavfile.read(tmp_out.name)
            return denoised.astype(np.float32) / 32767.0


def create_denoiser(backend: str = "auto") -> Denoiser:
    if backend == "rnnoise":
        return RNNoiseDenoiser()
    if backend == "deepfilter":
        return DeepFilterDenoiser()
    # auto: try DeepFilter first, fall back to RNNoise
    try:
        d = DeepFilterDenoiser()
        if d._available:
            return d
    except Exception:
        pass
    return RNNoiseDenoiser()
