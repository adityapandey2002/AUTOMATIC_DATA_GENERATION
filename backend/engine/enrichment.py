"""Transcript → case-sheet enrichment — one module over the extraction sequence.

The caller hands this module the accumulated per-chunk transcripts and gets
back one result: the current case-sheet snapshot plus its validation alerts.
Everything that used to be hand-typed inline at BOTH call sites (per chunk and
at finalize) now lives here and is owned exactly once:

  * which transcript to extract from — the bounded live window on a chunk,
    and deliberately the FULL encounter transcript at finalize (the one pass
    that can pair a question in one chunk with its answer in another; it runs
    once per patient, so the cost is irrelevant);
  * merge ordering — the free local fill is always merged first, then the LLM
    extract (finalize only), so the LLM cleans up the ambiguous leftovers
    while a health-worker-confirmed field still wins over both;
  * when the LLM runs — only on finalize, only once per encounter, and never
    on a blank transcript;
  * the fatal-extractor policy — if the extractor raises, the sheet is not
    lost: the failure is logged, the local fill is kept, and validation still
    runs;
  * validation — both call sites get alerts from the same run over the same
    snapshot, so a chunk_result and a finalize_result can never disagree
    about what is wrong with the sheet.

The merge engine and the extraction adapter are injected, never constructed
here: ChunkSession builds one MergeEngine per session (the dashboard mutates
it directly through set_field, so it must remain the session's), then picks
the adapter — real Gemini when `llm_final_extract` is on, the offline adapter
when it is off — and hands both to this module. The module never special-cases
either adapter: an offline adapter that contributes nothing and a failed API
call are the same no-op merge, and the whole path is testable with a fake
extractor (backend/test_enrichment.py: no network, no keys, no Postgres, no
microphone).

Windowing (the O(n^2) fix): local_fill() re-scans the transcript with ~30
regex passes, so the live path re-scans only the last `window_chunks` chunks.
MergeEngine already retains everything found earlier (latest-non-empty-wins
never clears a field), so narrowing the window only limits how far back a
*correction* can be picked up live; finalize re-scans the full transcript
regardless. The module never mutates the caller's list.

Adapter contract (the seam) — FieldExtractor
--------------------------------------------
    name: str                        stable id used in the logs
    extract(transcript) -> dict      {field_key: value} map merged in after
                                     the local fill; may be empty (or a map
                                     of all-None values — same thing: nothing
                                     to add). Anything it cannot get through
                                     the wire, it raises — the module keeps
                                     the local fill and logs.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Protocol, Sequence

from engine.local_fill import local_fill
from engine.merge import MergeEngine
from engine.validate import ValidationAlert, validate_case_sheet

logger = logging.getLogger(__name__)

# The merge marker finalize has always used: not a real chunk id.
FINAL_CHUNK_ID = -1

MODE_LIVE = "live"
MODE_FINAL = "final"
_MODES = (MODE_LIVE, MODE_FINAL)


class FieldExtractor(Protocol):
    """The seam the extraction adapters satisfy. See the module docstring."""

    name: str

    async def extract(self, transcript: str) -> dict: ...


class OfflineExtractor:
    """The offline adapter: satisfies the seam by contributing nothing.

    Mirrors the offline behaviour of `llm_final_extract=false` — no network,
    no extraction, and no merged values: merge({}) touches no field. It is
    declared here, beside the seam it satisfies, but it is injected like any
    other adapter; this module never constructs it.
    """

    name = "offline"

    async def extract(self, transcript: str) -> dict:
        return {}


@dataclass(frozen=True)
class EnrichResult:
    """The module's one normalised output: the merged sheet plus its alerts."""

    snapshot: dict[str, Any]  # MergeEngine snapshot: "answers" + "_confirmed"
    alerts: list[ValidationAlert]


class Enrichment:
    """Chooses the transcript, merges the extractions in order, validates."""

    def __init__(
        self,
        merge: MergeEngine,
        extractor: FieldExtractor,
        *,
        window_chunks: int,
    ) -> None:
        self._merge = merge
        self._extractor = extractor
        self._window_chunks = max(1, int(window_chunks))

    def _live_window(self, transcripts: Sequence[str]) -> str:
        """Transcript tail used for the per-chunk local fill.

        Bounded to the last N chunks so the ~30 regex passes in local_fill()
        don't re-scan the whole encounter on every chunk. MergeEngine keeps
        anything found in older chunks, so narrowing the window only limits
        how far back a *correction* can be picked up live — finalize() re-scans
        the full transcript regardless.
        """
        return " ".join(transcripts[-self._window_chunks:])

    async def enrich(
        self,
        transcripts: Sequence[str],
        mode: str,
        *,
        chunk_id: int = 0,
    ) -> EnrichResult:
        """Run one enrichment round; return the sheet snapshot + alerts.

        `transcripts` is the accumulated per-chunk transcript text, oldest
        first (ChunkSession.transcript_buffer). Mode "live" fills from the
        bounded window and never calls the extractor; mode "final" fills from
        the full transcript, then merges the extractor's answer map.
        """
        if mode not in _MODES:
            raise ValueError(f"unknown enrichment mode {mode!r}; use 'live' or 'final'")

        text = self._live_window(transcripts) if mode == MODE_LIVE else " ".join(transcripts)

        # Free local bilingual field filler (instant, no API quota) always
        # merges first. finalize merges with the -1 marker — not a chunk id.
        filled = local_fill(text)
        self._merge.merge(filled, chunk_id if mode == MODE_LIVE else FINAL_CHUNK_ID)

        if mode == MODE_FINAL:
            await self._extract_and_merge(text)

        snapshot = self._merge.get_snapshot()
        alerts = validate_case_sheet(snapshot)
        return EnrichResult(snapshot=snapshot, alerts=alerts)

    async def _extract_and_merge(self, text: str) -> None:
        """The LLM cleans up the ambiguous leftovers — ONE call per encounter.

        A blank transcript means nothing to extract. An extractor failure is
        logged and swallowed: the local fill is kept, and validation still
        runs on what the sheet actually holds.
        """
        if not text.strip():
            return
        try:
            extracted = await self._extractor.extract(text)
            self._merge.merge(extracted, FINAL_CHUNK_ID)
        except Exception as e:
            logger.warning(
                "%s final extraction failed (local fill kept): %s",
                self._extractor.name,
                e,
            )
