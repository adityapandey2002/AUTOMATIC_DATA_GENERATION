# 0002. Offline extraction is an injected adapter, not a settings branch

- **Status:** Accepted
- **Date:** 2026-10-22
- **Related:** ADR-0001 (same seam/injection pattern for ASR adapters)

## Context

`finalize` used to skip the LLM call via a settings flag checked in the middle of
the handler (`llm_final_extract`), next to a strip-guard and a try/except block.
The whole transcript→case-sheet sequence — local fill, merge order,
optional-extract, validate — was hand-typed twice (`process_chunk` live vs
`finalize` final). Only the pure engines were unit-tested; the composition, where
the shipped clinical bugs actually lived (windowed vs full transcript,
local-before-LLM, merge-before-validate), had no home and no test.

## Decision

`backend/engine/enrichment.py` is the module that owns the sequence:

- **Interface:** `Enrichment.enrich(transcripts, mode) -> EnrichResult`, mode
  `"live"` | `"final"`.
- **Extraction seam:** a `FieldExtractor` protocol (`name` +
  `async extract(transcript) -> dict`) with two injected implementations:
  `GeminiExtractor` (real) and `OfflineExtractor` (merges nothing).
- **The module reads no config** and cannot tell the two adapters apart; the
  only config-derived value (window size) is injected at composition time by
  `ChunkSession`.

## Consequences

- Both enrichment modes are testable through the module's interface with fake
  extractors — no network, no Postgres, no mic (`backend/test_enrichment.py`).
- Offline mode costs no special-casing inside the module: the offline adapter
  merges nothing, which is indistinguishable from "the extract added nothing".
  Log wording is preserved via the adapter `name`.
- A third extraction source (another LLM, a dictionary pass) is one class
  satisfying the seam, plus one line where `ChunkSession` composes.

## Alternatives considered

- **Keep the settings branch inside the module**
  (`if not settings.llm_final_extract: skip the LLM`) — rejected: the module
  would read config to special-case one behavior, and tests of offline mode
  would monkeypatch settings instead of injecting an adapter. That is the same
  mistake ADR-0001 removed for the five ASR providers.
- **Pass a pre-windowed transcript string to the module** — rejected: the
  window decision would have stayed in the handler, which is the duplication
  this candidate exists to delete; the module receives the accumulated chunk
  list (by reference, never mutated) and owns join/window itself.
