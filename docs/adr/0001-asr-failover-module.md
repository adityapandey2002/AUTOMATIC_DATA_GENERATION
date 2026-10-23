# 0001. ASR failover is one module with injected provider adapters

- **Status:** Accepted
- **Date:** 2026-10-14
- **Supersedes:** the hand-written provider loop + `ChunkSession._provider_order`

## Context

Five ASR engines — Groq, Sarvam, Bhashini, IndicConformer, and local
faster-whisper — were called by a loop handwritten inside
`ChunkSession.process_chunk`, ordered by `ChunkSession._provider_order`.

Each provider differed in ways the caller had to know about:

- **Signature.** Only Groq and local Whisper accepted the Whisper prompt
  `context`; the other three did not. The caller introspected signatures
  (`_accepts_context`, with a `_CONTEXT_SUPPORT` cache) to decide whether to
  pass it. Catching the resulting `TypeError` was rejected because it also
  swallowed genuine `TypeError`s raised *inside* a provider body.
- **Return shape.** Five different dicts (4, 5, 7, and 9 keys), with
  `confidence` meaning a negative log-prob in one, a 0..1 score in another, and
  a hardcoded constant (`0.8`, `0.5`) in two more.
- **Failure behaviour.** Only Groq retried; the rest swallowed every error and
  returned an empty result.
- **Availability.** Signalled five different ways (`_configured` false, a
  self-disabling circuit breaker, a missing NeMo import, a minimum-duration
  gate, or empty text).

Ordering, availability, context, and retry knowledge were therefore spread
across the caller and the five adapters.

## Decision

`backend/ws/asr.py` is the module that owns audio → transcript.

- **Interface:** `AsrFailover.transcribe(pcm_b64, language, duration_ms,
  context) -> Transcript | None`.
- **Owned here:** provider ordering, `context` passing, availability, the
  minimum-chunk-length policy, retry of transient failures, and normalisation.
- **Adapters:** the five providers are injected (not constructed) and satisfy
  one seam — `name`, `priority`, `min_chunk_ms`, `available`,
  `supports(language)`, and `transcribe_chunk(pcm_b64, language, duration_ms,
  context)` returning a dict or raising `AsrError`. The module never
  special-cases a provider by name.
- **Ordering is declarative:** `sorted by (specialist-first, priority)`. A
  provider that claims the language via `supports()` is tried first; the local
  fallback carries the highest priority number, so it runs last without being
  special-cased. This reproduces the old per-language lists exactly.
- **Retry is uniform and bounded** by `asr_max_attempts`; the adapter classifies
  each failure `retryable` (timeout, 429, 5xx) or not (bad credential, bad
  request, a model that will never load).
- **`Transcript` carries raw metrics only.** The single `confidence` field is
  dropped: the providers disagree on what it means, so the caller gates on
  `avg_logprob` / `no_speech_prob` / `compression_ratio` instead. Absent metrics
  stay `None`, never `0.0` (0.0 is the *best* value for every gate).
- **Post-ASR gating stays in the caller** (silence, low confidence, prompt
  echo). The module normalises; it does not judge.

## Consequences

- The whole failover path is testable with fakes — no network, keys, model
  download, or microphone (`backend/test_asr_failover.py`).
- Non-Groq providers now retry transient failures too, and the per-attempt
  HTTP timeout is unified to `asr_timeout_s` (was a hardcoded 30s in
  Sarvam/Bhashini, 45s in Groq).
- Adding a provider is one class satisfying the seam, plus one line in
  `ChunkSession.__init__`.
- `_accepts_context`, `_CONTEXT_SUPPORT`, `_provider_context_args`, and
  `_provider_order` are deleted.

## Alternatives considered

- **Keep retry inside each adapter (status quo: Groq only).** Rejected: the
  "single dropped request loses the chunk" failure applies to every provider.
  Only Groq had retry because it was the only provider working when the bug was
  found, not because it was uniquely fragile.
- **Have each adapter return `Transcript` directly.** Rejected for now: the
  adapters parse five vendor response formats, and the module normalises once.
  Pushing the type into all five is churn until a second consumer needs it.
- **Keep a single `confidence` field.** Rejected: it is not comparable across
  providers and actively misled the gates (a fabricated `0.8` reads as
  high-confidence).
