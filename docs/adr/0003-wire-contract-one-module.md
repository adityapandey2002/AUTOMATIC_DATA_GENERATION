# 0003. The wire contract is one module; clients are conformance-tested, not code-generated

- **Status:** Accepted
- **Date:** 2026-10-22
- **Related:** ADR-0001, ADR-0002 (same seam/one-home pattern)

## Context

Every WebSocket message shape used to be known only by its producer and each of
four consumers independently: `handler.py` carried ~15 string-literal event and
status names, `web/src/App.jsx` consumed ~8, `useBrowserMic.js` sent 2,
`capture-agent/streamer.py` sent 1, and the integration/e2e scripts re-typed the
rest. Drift had already shipped: a frontend guard against a status the backend
never emitted (`"empty"`), and a key declared on the wrong event.

## Decision

`backend/ws/protocol.py` is the one module that owns the wire:

- Events are built by constructors; commands are parsed through one parser; the
  typeless chunk-audio payload has a declared key union.
- `handler.py` emits **only** through the module; a purity test asserts the
  module stays free of socket/asyncio/config/db, and a guard asserts the
  handler holds no quoted wire names at all — drift cannot re-enter the branch
  code.
- The three external clients are pinned by a **conformance sweep**: a
  fixed-string scan in `backend/test_protocol.py` over `web/src/App.jsx`,
  `web/src/hooks/useBrowserMic.js`, `capture-agent/streamer.py`, and the e2e
  page objects, asserting that every name they send or consume is a canonical
  member, and that the canonical set is exactly clients-usage plus the two
  documented wire-compat members (`field_confirmed`, `confirm_field`).

## Consequences

- A protocol change is one edit plus one red/green test run — the sweep turns
  drift into a failing test instead of silent client degradation.
- The canonical tables also document the live/dashboard asymmetry (which
  client sends `mic_start`/`mic_stop` today, which commands have no sender yet)
  instead of leaving it tribal knowledge.
- No codegen toolchain is added; any CI with the repo checkout can run the
  sweep.

## Alternatives considered

- **Generate a TypeScript/JSON-Schema mirror from `protocol.py`.** Rejected at
  the current size (9 events / 7 commands): a generated mirror is a second
  contract that can itself drift, and it adds a build step to every consumer
  (including the Python capture agent) to lock something a ~30-check sweep
  locks already. Revisit if the protocol grows to dozens of shapes or multiple
  independent clients.
- **Leave shapes implicit (status quo).** Rejected: it is the transported bug
  — "one place for every shape" is precisely what drift-kill needed.
