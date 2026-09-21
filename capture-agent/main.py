"""Capture Agent — orchestrates record → denoise → VAD → stream pipeline."""

from __future__ import annotations

import argparse
import logging
import os
import signal
import sys
import time

import numpy as np

from probe import MachineProfile
from recorder import Recorder
from denoise import create_denoiser
from vad import VADChunker
from streamer import ChunkStreamer

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("capture-agent")

SAMPLE_RATE = 16000
CHANNELS = 2


def to_mono(stereo: np.ndarray) -> np.ndarray:
    if stereo.ndim == 1:
        return stereo
    return stereo.mean(axis=1).astype(np.float32)


def main() -> None:
    parser = argparse.ArgumentParser(description="Ambient Scribe Capture Agent")
    parser.add_argument("--backend-url", default=os.getenv("BACKEND_WS_URL", "ws://localhost:8765/ws/chunks"))
    parser.add_argument("--mic-device", type=int, default=int(os.getenv("MIC_DEVICE", "0")))
    parser.add_argument("--denoiser", choices=["auto", "deepfilter", "rnnoise"], default="auto")
    parser.add_argument("--encounter-id", default="")
    parser.add_argument(
        "--language",
        default=os.getenv("STT_LANGUAGE", "hi"),
        help="Spoken language: hi (Hindi) or mai (Maithili/Magahi)",
    )
    args = parser.parse_args()

    profile = MachineProfile()
    logger.info("Machine: %s", profile.summary())

    denoiser_backend = args.denoiser
    if denoiser_backend == "auto":
        denoiser_backend = profile.evaluate()
    logger.info("Denoiser: %s", denoiser_backend)

    recorder = Recorder(device=args.mic_device, sample_rate=SAMPLE_RATE, channels=CHANNELS)
    denoiser = create_denoiser(denoiser_backend)
    vad = VADChunker(sample_rate=SAMPLE_RATE)
    streamer = ChunkStreamer(ws_url=args.backend_url, language=args.language)

    if not streamer.connect():
        logger.error("Could not connect to backend — will retry on first chunk")
    else:
        logger.info("Connected to backend")

    running = True

    def shutdown(signum, frame):
        nonlocal running
        logger.info("Shutting down...")
        running = False

    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)

    recorder.start()
    logger.info("Recording started — Ctrl+C to stop")

    try:
        while running:
            frame = recorder.read(timeout=0.1)
            if frame is None:
                continue

            mono = to_mono(frame)
            denoised = denoiser.process(mono, SAMPLE_RATE)
            chunks = vad.feed(denoised)

            for chunk in chunks:
                if chunk.duration_ms >= 300:
                    streamer.send_chunk(chunk)
                    logger.debug("Sent chunk %.0fms", chunk.duration_ms)

        for chunk in vad.flush():
            if chunk.duration_ms >= 300:
                streamer.send_chunk(chunk)

        if args.encounter_id:
            streamer.send_finalize(args.encounter_id)

    finally:
        recorder.stop()
        streamer.disconnect()
        logger.info("Capture agent stopped")


if __name__ == "__main__":
    main()
