# Ambient Clinical AI Scribe - E2E Testing Guide

This document describes how to run end-to-end tests for the Ambient Clinical AI Scribe application.

## Test Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                      E2E Test Suite                             │
├─────────────────────────────────────────────────────────────────┤
│  • Playwright + Chromium (headless or headed)                   │
│  • Custom fixtures that start/stop backend & frontend           │
│  • Page Object Model (ScribePage) for UI interactions           │
│  • Direct WebSocket tests for /ws/chunks and /ws/dashboard      │
└─────────────────────────────────────────────────────────────────┘
         │                    │                    │
         ▼                    ▼                    ▼
    ┌──────────┐       ┌──────────────┐    ┌────────────┐
    │ Backend  │       │  Frontend    │    │  Browser   │
    │ FastAPI  │       │  Vite/React  │    │  Playwright│
    │ :8766    │       │  :3001       │    │  Chromium  │
    └──────────┘       └──────────────┘    └────────────┘
```

## Quick Start

### Prerequisites

- Node.js 20+
- Python 3.11+
- Playwright browsers (installed via `npx playwright install`)

### Install Dependencies

```bash
# Backend
cd backend
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
pip install faster-whisper  # For local ASR fallback in CI

# Frontend
cd web
npm ci
npx playwright install --with-deps chromium
```

### Run Tests Locally

```bash
cd web

# Run all E2E tests (headless)
npx playwright test

# Run with visible browser (headed mode)
npx playwright test --headed

# Run specific test file
npx playwright test tests/e2e/scribe.spec.ts

# Debug mode (opens Playwright Inspector)
npx playwright test --debug

# Run with trace viewer
npx playwright test --trace on

# Show HTML report after run
npx playwright show-report
```

## Test Structure

```
web/
├── playwright.config.ts          # Playwright configuration
├── tests/
│   └── e2e/
│       ├── fixtures.ts           # Test fixtures (backend, frontend, page)
│       ├── scribe.spec.ts        # Main E2E test suite
│       └── pages/
│           └── ScribePage.ts     # Page Object Model for Scribe UI
├── test-results/                 # Generated test artifacts
│   ├── junit.xml                # JUnit XML for CI
│   ├── screenshots/             # Failure screenshots
│   └── videos/                  # Failure videos
└── playwright-report/           # HTML report
```

## Test Scenarios Covered

| Test | Description |
|------|-------------|
| Backend health endpoint | Verifies `/health` returns `{status: "ok"}` |
| Schema endpoint | Verifies `/api/schema` returns form schema |
| Frontend loads | Verifies React app loads and connects to backend WS |
| Start Recording | Click Start → session begins, timer shows |
| Dashboard WS round-trip | `mic_start` → `session_state` → `mic_stop` → `finalize_result` |
| Chunks WS round-trip | `session_start` → audio chunk → `chunk_result` → `finalize` |
| Audio chunk updates fields | Silence chunk → local_fill extracts fields → UI updates |
| Stop Recording finalizes | Stop button → finalize_result broadcast |
| Case sheet sections | All major form sections render |
| Field labels bilingual | English + Hindi labels present |
| Save button disabled | Disabled when no fields filled |
| Capture agent status | Connection indicator present |

## CI Configuration

### GitHub Actions (`.github/workflows/e2e.yml`)

The CI pipeline:
1. Sets up Node.js 20 and Python 3.11
2. Installs system dependencies for Chromium
3. Installs backend deps (including `faster-whisper` for local ASR)
4. Installs frontend deps and Playwright Chromium
5. Runs E2E tests with local ASR only (no cloud API keys needed)
6. Uploads HTML report, JUnit XML, and failure artifacts

### Environment Variables for CI

```yaml
env:
  GROQ_API_KEY: ${{ secrets.GROQ_API_KEY }}    # Optional - for cloud ASR
  GEMINI_API_KEY: ${{ secrets.GEMINI_API_KEY }} # Optional - for LLM extraction
  SARVAM_API_KEY: ''                            # Disabled in CI
  BHASHINI_API_KEY: ''                          # Disabled in CI
  USE_LOCAL_FALLBACK: 'true'                    # Use faster-whisper
  USE_INDIC_CONFORMER: 'false'                  # Disable (needs NeMo)
  LLM_FINAL_EXTRACT: 'false'                    # Disable (needs Gemini)
```

### Required Secrets (Optional)

For full cloud ASR testing in CI, add these repository secrets:
- `GROQ_API_KEY` - Groq Whisper API key
- `GEMINI_API_KEY` - Google Gemini API key

Without these, tests run in "local-only" mode using `faster-whisper` (CPU, `int8` model).

## Mocking ASR for CI

The test fixtures automatically configure the backend for CI:
- Uses SQLite test database (`test_scribe.db`)
- Runs on port 8766 (via `SCRIBE_TEST_PORT`)
- Enables `USE_LOCAL_FALLBACK=true` with `faster-whisper`
- Disables cloud providers (Sarvam, Bhashini, IndicConformer)
- Disables Gemini final extraction

This means **no API keys are required for CI** - tests run completely offline using local Whisper.

## Writing New Tests

### Using the Page Object

```typescript
import { test } from './fixtures';
import { ScribePage } from './pages/ScribePage';

test('My new test', async ({ page }) => {
  const scribe = new ScribePage(page);
  await scribe.goto();
  await scribe.startRecording();
  
  // Send audio and verify
  const result = await scribe.sendDummyAudioChunk('my-test');
  expect(result.type).toBe('chunk_result');
  
  await scribe.stopRecording();
});
```

### Direct WebSocket Testing

```typescript
test('Direct WS test', async ({ backendUrl }) => {
  const ws = new WebSocket(backendUrl.replace('http', 'ws') + '/ws/dashboard');
  // ... send/receive messages
});
```

## Troubleshooting

### Backend fails to start
- Check Python version (3.11+ required)
- Verify `faster-whisper` installed: `pip install faster-whisper`
- Check port 8766 not in use

### Frontend fails to start
- Check Node.js version (20+ required)
- Run `npm ci` to reinstall dependencies
- Check port 3001 not in use

### WebSocket connection fails
- Ensure backend is healthy: `curl http://localhost:8766/health`
- Check CORS settings in `backend/main.py` (should allow all origins)
- Verify `VITE_WS_URL` points to correct backend port

### Tests flaky in CI
- Increase timeouts in `playwright.config.ts`
- Add `await page.waitForLoadState('networkidle')` after navigation
- Use `waitForSelector` with `state: 'visible'` instead of `toBeVisible`

### Chromium not found
```bash
npx playwright install --with-deps chromium
```

## Artifacts

After test runs, find artifacts in:
- **HTML Report**: `web/playwright-report/index.html`
- **JUnit XML**: `web/test-results/junit.xml`
- **Screenshots**: `web/test-results/screenshots/`
- **Videos**: `web/test-results/videos/`
- **Traces**: `web/test-results/traces/` (open with `npx playwright show-trace`)

## Extending Tests

### Add new Page Object

Create `tests/e2e/pages/NewPage.ts`:
```typescript
export class NewPage {
  readonly page: Page;
  constructor(page: Page) { this.page = page; }
  // ... locators and methods
}
```

### Add new test file

Create `tests/e2e/new-feature.spec.ts`:
```typescript
import { test } from './fixtures';
import { NewPage } from './pages/NewPage';

test.describe('New Feature', () => {
  // ... tests
});
```

## Performance Notes

- Tests run **sequentially** (`workers: 1`) because each worker starts its own backend/frontend
- Total test suite takes ~60-120 seconds locally
- CI runs on Ubuntu with 2 vCPUs, 7GB RAM
- For faster local iteration, run single test file: `npx playwright test tests/e2e/scribe.spec.ts --headed`

## Local Development Tips

1. **Run backend/frontend manually** for interactive debugging:
   ```bash
   # Terminal 1 - Backend
   cd backend && SCRIBE_TEST_PORT=8766 DATABASE_URL=sqlite:///./test_scribe.db python -m uvicorn main:app --port 8766
   
   # Terminal 2 - Frontend
   cd web && VITE_WS_URL=ws://localhost:8766/ws/dashboard npm run dev -- --port 3001
   
   # Terminal 3 - Tests (connect to running services)
   cd web && npx playwright test --headed
   ```

2. **Use Playwright Codegen** to record new tests:
   ```bash
   npx playwright codegen http://localhost:3001
   ```

3. **Inspect traces** for failed tests:
   ```bash
   npx playwright show-trace test-results/traces/trace.zip
   ```