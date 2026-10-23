"""ASR failover module — one interface over five transcription adapters.

The caller hands this module an audio chunk plus the spoken language, and gets
back one normalised `Transcript` (or `None` when nothing could transcribe it).
Everything that used to be spread across the caller now lives here:

  * which provider to try, in which order (specialists before generalists, and
    the local fallback last);
  * passing the Whisper prompt `context` — every adapter accepts it now, so the
    old per-provider signature introspection is gone;
  * whether an adapter is configured and usable *right now*;
  * the minimum-chunk-length policy;
  * retrying transient provider failures, and giving up on permanent ones;
  * collapsing the five different return dicts into one shape.

The five adapters (Groq, Sarvam, Bhashini, IndicConformer, local Whisper) are
implementations behind this module's seam. They are injected, not constructed,
so the whole failover path — ordering, fall-through, retry, normalisation — is
driven in tests by fakes with no network, no API keys, no model download, and
no microphone.

Adapter contract (the seam)
---------------------------
    name: str            stable id used in the transcript and the logs
    priority: int        lower runs first within a tier
    min_chunk_ms: int    shortest audio this adapter will accept (0 = any)
    available            configured and usable right now (read per call, so an
                         adapter that disables itself mid-session is visible)
    supports(language)   True when this adapter is the *preferred* engine for
                         that language (a specialist); such adapters are tried
                         before the general ones
    transcribe_chunk(pcm_b64, language, duration_ms, context) -> dict | None
                         returns the parsed result (empty text means "nothing
                         usable here"), or raises `AsrError` on failure. This
                         module reads only `.text`, `.language`, `.speaker` and
                         the three confidence metrics; any other keys are the
                         adapter's own business.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from typing import Callable, Optional, Protocol, Sequence

from config import settings

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class Transcript:
    """One normalised transcription result — the module's output shape.

    The confidence metrics are the *raw* values and may be `None` when the
    provider does not report them. They are never defaulted to 0.0: 0.0 is the
    best possible value for every downstream gate, so a missing metric must read
    as absent, not as confident. There is deliberately no single `confidence`
    field — the five providers each mean something different by it (a negative
    log-prob, a 0..1 score, or a constant), so the caller gates on the raw
    metrics instead.
    """

    text: str
    provider: str
    language: str = ""
    speaker: str = "unknown"
    avg_logprob: Optional[float] = None
    no_speech_prob: Optional[float] = None
    compression_ratio: Optional[float] = None


class AsrError(Exception):
    """An adapter failure surfaced at the seam.

    `retryable` tells the failover whether another attempt could plausibly
    succeed: transient failures (timeout, 429, 5xx) are retryable; a credential
    or request error that will fail identically every time is not.
    """

    def __init__(self, message: str, *, retryable: bool = False) -> None:
        super().__init__(message)
        self.retryable = retryable


class AsrAdapter(Protocol):
    """The seam the five adapters satisfy. See the module docstring."""

    name: str
    priority: int
    min_chunk_ms: int

    @property
    def available(self) -> bool: ...

    def supports(self, language: str) -> bool: ...

    async def transcribe_chunk(
        self,
        pcm_b64: str,
        language: str = "hi",
        duration_ms: Optional[int] = None,
        context: str = "",
    ) -> Optional[dict]: ...


class AsrFailover:
    """Orders the adapters, calls them, and returns one normalised transcript."""

    def __init__(
        self,
        adapters: Sequence[AsrAdapter],
        *,
        max_attempts: int = 3,
        backoff_s: float = 0.6,
        sleep: Callable = asyncio.sleep,
    ) -> None:
        self._adapters = list(adapters)
        self._max_attempts = max(1, int(max_attempts))
        self._backoff_s = float(backoff_s)
        # `sleep` is injectable so tests exercise the retry schedule without
        # actually waiting on it.
        self._sleep = sleep

    @classmethod
    def from_settings(cls, adapters: Sequence[AsrAdapter], *, sleep: Callable = asyncio.sleep) -> "AsrFailover":
        return cls(
            adapters,
            max_attempts=getattr(settings, "asr_max_attempts", 3),
            backoff_s=getattr(settings, "asr_retry_backoff_s", 0.6),
            sleep=sleep,
        )

    def order(self, language: str) -> list[AsrAdapter]:
        """Specialists for the language first, then by declared priority.

        The local fallback carries the highest priority number, so it runs last
        without any special-casing. This reproduces the old per-language
        hand-written provider lists exactly.
        """
        lang = (language or "").strip().lower()
        return sorted(
            self._adapters,
            key=lambda a: (0 if a.supports(lang) else 1, a.priority),
        )

    async def transcribe(
        self,
        pcm_b64: str,
        language: str = "hi",
        duration_ms: Optional[int] = None,
        context: str = "",
    ) -> Optional[Transcript]:
        """Return the first usable transcript, or None if no adapter could serve it."""
        for adapter in self.order(language):
            if not adapter.available:
                continue
            if duration_ms is not None and adapter.min_chunk_ms and duration_ms < adapter.min_chunk_ms:
                continue

            raw = await self._attempt(adapter, pcm_b64, language, duration_ms, context)
            if raw is None:
                continue
            return self._normalise(raw, adapter)
        return None

    async def _attempt(
        self,
        adapter: AsrAdapter,
        pcm_b64: str,
        language: str,
        duration_ms: Optional[int],
        context: str,
    ) -> Optional[dict]:
        """Call one adapter, retrying only a transient failure.

        Returns the raw result dict, or None to fall through to the next
        adapter. An empty result is *not* retried: the adapter answered, it just
        had nothing for this chunk.
        """
        attempts = self._max_attempts
        for attempt in range(1, attempts + 1):
            try:
                raw = await adapter.transcribe_chunk(
                    pcm_b64,
                    language=language,
                    duration_ms=duration_ms,
                    context=context,
                )
            except AsrError as e:
                logger.warning(
                    "%s failed (attempt %d/%d, retryable=%s): %s: %s",
                    adapter.name,
                    attempt,
                    attempts,
                    e.retryable,
                    type(e).__name__,
                    e,
                )
                if not e.retryable or attempt >= attempts:
                    return None
            except Exception as e:  # unexpected bug in the adapter: don't retry
                logger.warning(
                    "%s raised %s: %s", adapter.name, type(e).__name__, e
                )
                return None
            else:
                if raw and raw.get("text"):
                    if attempt > 1:
                        logger.info(
                            "%s recovered on attempt %d/%d", adapter.name, attempt, attempts
                        )
                    return raw
                return None

            await self._sleep(self._backoff_s * (2 ** (attempt - 1)))
        return None

    @staticmethod
    def _normalise(raw: dict, adapter: AsrAdapter) -> Transcript:
        return Transcript(
            text=raw.get("text") or "",
            provider=adapter.name,
            language=raw.get("language") or "",
            speaker=raw.get("speaker") or "unknown",
            avg_logprob=raw.get("avg_logprob"),
            no_speech_prob=raw.get("no_speech_prob"),
            compression_ratio=raw.get("compression_ratio"),
        )
