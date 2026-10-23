# AGENTS.md

Project-level guidance for coding agents working in this repository.

## Agent skills

### Issue tracker

Issues are tracked in GitHub Issues on `adityapandey2002/AUTOMATIC_DATA_GENERATION`, via the `gh` CLI. See `docs/agents/issue-tracker.md`.

### Domain docs

Single-context: one `GLOSSARY.md` at the repo root, and decisions recorded as ADRs in `docs/adr/`. See `docs/agents/domain.md`.

## Working conventions

### Running Python

- The only working interpreter is `backend/venv/Scripts/python.exe` (3.14). Run it from `backend/` so `import db`, `import ws`, `import engine` resolve.
- Tests are standalone scripts, not pytest: `python test_X.py` prints a PASS/FAIL table and exits 0/1. Keep that pattern for new tests.
- Dev consoles are cp1252 and the tests print Devanagari, so `PYTHONIOENCODING=utf-8` must be set or Python raises `UnicodeEncodeError` mid-run. Prefer the wrapper: `powershell -File backend/run_tests.ps1` (runs the whole offline suite).
- Tests never touch Postgres. Set `DATABASE_URL=sqlite:///...` **before** importing `config`/`db` (see `backend/test_name_saved.py`).

### Design

- One module owns one job behind a small interface; callers **inject** dependencies instead of constructing them, so tests drive the whole path with fakes. `docs/adr/0001-asr-failover-module.md` and `backend/ws/asr.py` are the established shape: injected adapters at a seam, declarative ordering, one normalised output type.
- A module's tests cross exactly its interface. If a test needs to reach past the interface, the module is the wrong shape.
- Never encode a missing/confidential metric as `0.0` — there it reads as the *best* possible value for every gate. `None` means absent (see `ws/asr.py`).
- Do not send a fabricated value where a real one is unknown (`confidence` in one provider's dict is a negative log-prob, in another a 0..1 score, in two more a constant — gate on raw metrics instead).

### Docs

- When work names a new domain concept, add it to `GLOSSARY.md`. Record load-bearing decisions in `docs/adr/` (next number in sequence).
- Keep `docs/CODEMAPS/` and `docs/ARCHITECTURE.md` in sync when a file's role changes or a documented helper disappears.
