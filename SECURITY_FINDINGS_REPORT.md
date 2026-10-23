# Security Vulnerability Assessment Report
## Ambient Clinical AI Scribe — `AUTOMATIC_DATA_GENERATION/`

**Date:** 2026-10-05  
**Reviewer:** security-reviewer agent  
**Scope:** Full codebase review (backend, frontend, capture-agent, deployment)  
**Risk Classification:** **CRITICAL** — Multiple critical vulnerabilities requiring immediate remediation before any production deployment

---

## Executive Summary

| Severity | Count | Description |
|----------|-------|-------------|
| **CRITICAL** | 6 | Immediate exploit risk: no authentication, hardcoded secrets, wide-open CORS, unauthenticated WebSockets |
| **HIGH** | 6 | Significant data exposure risk: PII/Aadhaar handling, no rate limits, sync-in-async DB, no input validation |
| **MEDIUM** | 6 | Compliance and operational risks: hardcoded gender, deprecated APIs, schema drift, missing audit |
| **LOW** | 3 | Configuration and maintenance issues |

**Overall Risk Level: CRITICAL** — This application **must not be deployed to production** in its current state. It handles highly sensitive maternal health data (including Aadhaar numbers, phone numbers, addresses, clinical records) with **zero access controls**.

---

## CRITICAL Findings (Fix Immediately)

### C1. No Authentication / Authorization System Exists
**Location:** Entire codebase  
**Evidence:** `PROJECT_CONTEXT.md` §2.1 F20: "Auth / login / roles — TBD / Not found in codebase"  
**Impact:** Any unauthenticated actor can:
- Stream audio to `/ws/chunks` and receive transcriptions
- Connect to `/ws/dashboard` and receive live patient data (transcripts, form fields, alerts)
- Call `GET /api/patients` and retrieve **all patient records** (names, ages, Aadhaar, addresses, phone numbers, clinical answers)
- Trigger `finalize` / `save` operations on any encounter

**Remediation:** Implement authentication before any production use:
- Add JWT/OIDC authentication (FastAPI `Depends` on REST + WebSocket)
- Require valid token on WebSocket upgrade (`Authorization` header or query param)
- Implement role-based access (ANM, Doctor, Supervisor)
- Enforce clinic-level multi-tenancy (`clinic_id` column exists but is never populated)

---

### C2. CORS Misconfiguration — `allow_origins=["*"]` with `allow_credentials=True`
**File:** `backend/main.py:38-44`
```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,   # DANGEROUS with wildcard origins
    allow_methods=["*"],
    allow_headers=["*"],
)
```
**Impact:** 
- Any malicious website can make authenticated requests to the API on behalf of a logged-in user (once auth exists)
- With `allow_credentials=True`, browsers will send cookies/auth headers to any origin
- Combined with no auth, this is an open door for CSRF and data exfiltration

**Remediation:**
```python
# Production config — explicit origins only
allow_origins=["https://clinic-hospital.example.com", "https://dashboard.example.com"],
allow_credentials=True,
```
Never use `["*"]` with `allow_credentials=True`.

---

### C3. WebSocket Endpoints Have Zero Authentication
**Files:** `backend/main.py:92-99`, `backend/ws/handler.py:681-869`  
**Endpoints:** `/ws/chunks`, `/ws/dashboard`

**Impact:** 
- `/ws/chunks`: Anyone can stream audio, consume ASR quota (Groq free tier = 8 hrs/day), inject malicious audio, trigger LLM calls
- `/ws/dashboard`: Anyone can receive live patient data broadcasts, send `mic_start`/`mic_stop`/`set_field`/`save` commands, control active sessions
- No origin validation on WebSocket upgrade — cross-site WebSocket hijacking possible

**Remediation:**
```python
# In ws_chunks_handler / ws_dashboard_handler
async def ws_chunks_handler(websocket: WebSocket):
    # Validate token BEFORE accept()
    token = websocket.query_params.get("token") or websocket.headers.get("authorization", "").replace("Bearer ", "")
    if not verify_token(token):
        await websocket.close(code=4001, reason="Unauthorized")
        return
    await websocket.accept()
    # ... rest of handler
```

---

### C4. Hardcoded API Keys in `.env` File (COMMITTED TO REPO)
**File:** `AUTOMATIC_DATA_GENERATION/.env` (lines 10, 18)

```
GROQ_API_KEY=gsk_3Cbm...REDACTED...hDFA
GEMINI_API_KEY=AQ.Ab8R...REDACTED...gzdg
```

**Impact:**
- **These are LIVE PRODUCTION KEYS** committed to the repository
- Groq key exposes 8 hrs/day free transcription quota to anyone
- Gemini key exposes ~20 requests/day free tier + potential billing if upgraded
- Keys must be **revoked and rotated immediately**

**Remediation:**
1. **REVOKE BOTH KEYS NOW** in Groq Console and Google AI Studio
2. Generate new keys
3. Add `.env` to `.gitignore` (verify it's already there)
4. Use environment variables / secrets manager in production
5. Never commit `.env` files

---

### C5. Hardcoded Database Password Fallback in `docker-compose.yml`
**File:** `deploy/docker-compose.yml:7, 27`
```yaml
environment:
  POSTGRES_PASSWORD: ${POSTGRES_PASSWORD:-scribe_dev_2024}
```
```yaml
environment:
  DATABASE_URL: postgresql://scribe:${POSTGRES_PASSWORD:-scribe_dev_2024}@postgres:5432/ambient_scribe
```

**Impact:**
- Default password `scribe_dev_2024` used if `POSTGRES_PASSWORD` not set
- Anyone with access to the compose file or container can connect to PostgreSQL
- In production, this exposes all patient data

**Remediation:**
```yaml
# Remove fallback — require explicit env var
environment:
  POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}  # No default!
```
Generate strong password: `openssl rand -base64 32`

---

### C6. Medical PII / Aadhaar Data Stored Without Encryption or Access Controls
**Files:** 
- `backend/form_schema.py:49` — `aadhaar_number` field
- `backend/db/models.py:48-58` — `Patient` model with `answers` JSON column
- `backend/engine/local_fill.py:252-255` — Aadhaar extraction regex

**Data at Risk:**
| Field | Sensitivity | Regulation |
|-------|-------------|------------|
| `aadhaar_number` | **EXTREME** — India Aadhaar Act, DPDP Act 2023 | Unique biometric ID |
| `contact_phone` / `contact_phone_hc` | HIGH — PII | DPDP Act |
| `address`, `district`, `block` | HIGH — PII | DPDP Act |
| `name`, `husband_name`, `spouse_parent_of` | HIGH — PII | DPDP Act |
| Clinical `answers` JSON (181 fields) | HIGH — Health data | DPDP Act, HIPAA-equivalent |

**Current State:**
- All stored in plaintext JSON in `patients.answers` column
- No column-level encryption
- No field-level access control
- `GET /api/patients` returns **everything** including Aadhaar
- No audit logging of data access

**Remediation:**
- Encrypt Aadhaar at rest (application-level encryption with KMS)
- Implement field-level access control (mask Aadhaar in API responses unless authorized)
- Add audit logging for all PII access
- Implement data retention/deletion policies per DPDP Act
- Consider tokenization for Aadhaar (store only last 4 digits + hash)

---

## HIGH Findings

### H1. No Rate Limiting on Any Endpoint
**Impact:**
- `/ws/chunks`: Unlimited audio streaming → ASR quota exhaustion (Groq 8 hrs/day), DoS via resource exhaustion
- `/ws/dashboard`: Unlimited connections → broadcast fan-out DoS
- `GET /api/patients`: No pagination limits (hardcoded `.limit(200)` but no user control) → data scraping
- `GET /api/schema`: Unlimited schema fetching

**Remediation:**
```python
# Add to FastAPI
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

@app.get("/api/patients")
@limiter.limit("30/minute")
async def list_patients(request: Request): ...

# WebSocket: limit connections per IP
# Use middleware or connection manager with per-IP tracking
```

---

### H2. No Request Size Limits (WebSocket + REST)
**Impact:**
- WebSocket messages: No max message size → memory exhaustion via large base64 audio payloads
- Audio chunks: No validation of `pcm_b64` size or `duration_ms` → DoS via oversized chunks
- REST: No body size limit on future POST endpoints

**Evidence:** `handler.py:291` — `payload.get("pcm_b64", "")` accepted without size check  
**Remediation:**
```python
# WebSocket: configure max message size
@app.websocket("/ws/chunks")
async def chunk_endpoint(websocket: WebSocket):
    # uvicorn: --ws-max-size 1048576  (1MB)
    # Or in handler:
    raw = await websocket.receive_text()
    if len(raw) > 1_000_000:  # 1MB limit
        await websocket.close(code=1009, reason="Message too large")
        return
```

---

### H3. Synchronous SQLAlchemy in Async WebSocket Handlers
**Files:** 
- `backend/db/connection.py:12` — `create_engine()` (sync)
- `backend/db/models.py` — `datetime.utcnow` (deprecated)
- `backend/ws/handler.py:471, 527, 839` — `SessionLocal()` used in `async` functions

**Impact:**
- Blocks event loop during DB I/O → degrades WebSocket throughput, increases latency
- Under load, blocks other WebSocket connections
- `datetime.utcnow()` deprecated in Python 3.12+ (naive UTC without tzinfo)
- `asyncpg` in requirements but **never used** — code uses `psycopg2` sync driver

**Remediation:**
```python
# connection.py — migrate to async
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker

engine = create_async_engine(
    settings.database_url.replace("postgresql://", "postgresql+asyncpg://"),
    pool_pre_ping=True,
)
AsyncSessionLocal = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)

# handler.py — use async session
async def _persist(self, db: AsyncSession, snapshot: dict, alerts) -> None:
    # ... use await db.execute(), await db.commit()
    # datetime.utcnow() → datetime.now(timezone.utc)
```

---

### H4. No Input Validation on WebSocket Messages
**File:** `backend/ws/handler.py:692-693`
```python
raw = await websocket.receive_text()
data = json.loads(raw)  # No validation, no schema
```

**Vectors:**
- `chunk_id`: Integer overflow, negative values, extremely large values
- `pcm_b64`: Invalid base64, oversized, non-audio data
- `language`: Arbitrary string passed to ASR providers
- `encounter_id`: UUID confusion, session hijacking via ID prediction
- `set_field`: Arbitrary field names, oversized values, type confusion

**Remediation:** Use Pydantic models for every message type:
```python
from pydantic import BaseModel, Field, field_validator
from typing import Literal

class ChunkMessage(BaseModel):
    type: Literal["chunk"]
    pcm_b64: str = Field(min_length=1, max_length=2_000_000)  # ~1MB base64
    chunk_id: int = Field(ge=0, le=1_000_000)
    duration_ms: int = Field(ge=0, le=30_000)
    language: str = Field(pattern=r"^(hi|en|mai|mag|bho|vajjika)$")
    encounter_id: str | None = Field(default=None, pattern=r"^[0-9a-f-]{36}$")

# In handler:
try:
    msg = ChunkMessage(**data)
except ValidationError as e:
    await websocket.send_json({"type": "error", "message": "Invalid payload"})
    continue
```

---

### H5. WebSocket Origin Not Validated
**File:** `backend/ws/handler.py:681-684`
```python
async def ws_chunks_handler(websocket: WebSocket) -> None:
    await websocket.accept()  # No origin check!
```

**Impact:** Cross-Site WebSocket Hijacking (CSWSH) — malicious site can open WebSocket to backend using victim's browser cookies (once auth exists).

**Remediation:**
```python
async def ws_chunks_handler(websocket: WebSocket) -> None:
    origin = websocket.headers.get("origin")
    allowed = settings.allowed_ws_origins  # Configure in settings
    if origin not in allowed:
        await websocket.close(code=4003, reason="Origin not allowed")
        return
    await websocket.accept()
```

---

### H6. No Secure Headers / HTTPS Enforcement
**Missing:**
- `Strict-Transport-Security` (HSTS)
- `Content-Security-Policy` (CSP)
- `X-Frame-Options: DENY`
- `X-Content-Type-Options: nosniff`
- `Referrer-Policy: strict-origin-when-cross-origin`
- `Permissions-Policy: microphone=(), camera=()` (for non-scribe pages)

**Remediation:** Add `fastapi.middleware.trustedhost.TrustedHostMiddleware` and security headers middleware.

---

## MEDIUM Findings

### M1. FHIR Mapper Hardcodes Gender = "female"
**File:** `backend/fhir/mapper.py:13`
```python
"gender": "female",  # Hardcoded!
```
**Impact:** Incorrect FHIR resources for non-female patients; compliance issue for government reporting.  
**Remediation:** Extract gender from patient data / form schema.

---

### M2. Deprecated `datetime.utcnow()` Throughout Models
**File:** `backend/db/models.py:31, 58, 73, 84, 96, 110`
```python
default=datetime.utcnow  # Deprecated since Python 3.12
```
**Impact:** Naive datetime objects (no timezone) cause subtle bugs in time comparisons, audit logs, and cross-timezone deployments.  
**Remediation:** Use `datetime.now(timezone.utc)` or SQLAlchemy `func.now()`.

---

### M3. `/api/patients` Returns All Patients Without Pagination Controls
**File:** `backend/main.py:57-89`
```python
.limit(200)  # Hardcoded, no offset, no query params
```
**Impact:** Data scraping, memory pressure, no way to paginate for large datasets.  
**Remediation:** Add `skip`, `limit` query params with max limit enforcement.

---

### M4. Frontend Schema Mirror Can Drift from Backend
**Files:** `web/src/formSchema.js` (auto-generated), `backend/export_schema_js.py`  
**Issue:** Regeneration is manual — no CI, no Dockerfile step, no build hook.  
**Impact:** Silent schema mismatch → form rendering errors, validation gaps.  
**Remediation:** Add schema export to frontend build process or CI pipeline.

---

### M5. Audio Deletion Audit Trail Exists But No Actual File Storage
**Files:** `backend/storage/audio.py`, `backend/db/models.py:104-111`  
**Issue:** `AudioDeletionLog` table exists but no code writes audio files to disk — only logs "deletion" of chunks that were never saved as files.  
**Impact:** False compliance evidence; audit log shows deletions that never happened.  
**Remediation:** Either implement actual audio file storage + deletion, or remove the audit log (document that audio is streamed, not stored).

---

### M6. `nginx.conf` Does Not Proxy `/api/*` Endpoints
**File:** `web/nginx.conf:6-17` — Only `/` and `/ws` proxied  
**Impact:** In Docker deployment, `GET /api/schema` and `GET /api/patients` return 404. Patients tab breaks.  
**Remediation:** Add `location /api { proxy_pass http://backend:8765; }`

---

## LOW Findings

### L1. No Security Headers in Frontend Build
**File:** `web/nginx.conf` — No `add_header` directives for CSP, HSTS, etc.

### L2. `uvicorn` Runs with `reload=True` in Main
**File:** `backend/main.py:104-109`
```python
uvicorn.run("main:app", host=settings.ws_host, port=settings.ws_port, reload=True)
```
**Impact:** Reload mode uses more memory, watches files — not for production.  
**Remediation:** Separate dev/prod entrypoints; use `reload=False` in Docker.

### L3. `requirements.txt` Pins No Versions for Critical Deps
**File:** `backend/requirements.txt` — All `>=` lower bounds, no upper bounds  
**Impact:** Supply chain risk; `pip install` could pull breaking changes.  
**Remediation:** Pin exact versions or use `pip-tools` / `uv` with lockfile.

---

## Security Checklist for Production Readiness

| Control | Status | Priority |
|---------|--------|----------|
| Authentication (JWT/OIDC) | ❌ Missing | CRITICAL |
| Authorization (RBAC) | ❌ Missing | CRITICAL |
| CORS restricted origins | ❌ `["*"]` | CRITICAL |
| WebSocket auth + origin check | ❌ Missing | CRITICAL |
| API keys rotated (not in repo) | ❌ **LIVE KEYS IN .env** | CRITICAL |
| DB password not defaulted | ❌ `scribe_dev_2024` fallback | CRITICAL |
| Rate limiting | ❌ Missing | HIGH |
| Request size limits | ❌ Missing | HIGH |
| Input validation (Pydantic) | ❌ Missing | HIGH |
| Async DB driver | ❌ Sync in async | HIGH |
| PII encryption at rest | ❌ Plaintext JSON | HIGH |
| Aadhaar masking in API | ❌ Full exposure | HIGH |
| Audit logging (data access) | ❌ Missing | HIGH |
| HTTPS enforcement (HSTS) | ❌ Missing | MEDIUM |
| Security headers (CSP, etc.) | ❌ Missing | MEDIUM |
| `datetime.utcnow()` → aware | ❌ Deprecated | MEDIUM |
| FHIR gender hardcoded | ⚠️ Stub only | MEDIUM |
| API pagination | ⚠️ Hardcoded limit | MEDIUM |
| Schema sync automation | ❌ Manual | LOW |
| Dependency pinning | ❌ Loose versions | LOW |
| Production uvicorn config | ⚠️ `reload=True` | LOW |

---

## Recommended Remediation Order

1. **IMMEDIATE (Day 0):** Revoke exposed API keys (Groq, Gemini), rotate DB password
2. **Day 1-2:** Add authentication middleware (JWT), protect all WebSocket + REST endpoints
3. **Day 2-3:** Fix CORS, add origin validation, implement rate limiting
4. **Day 3-5:** Migrate to async SQLAlchemy + asyncpg, add Pydantic validation on all WS messages
5. **Day 5-7:** Implement PII encryption (Aadhaar), field-level access control, audit logging
6. **Day 7+:** Security headers, HTTPS enforcement, FHIR fixes, schema sync automation, dependency locking

---

## Compliance Notes (India DPDP Act 2023)

This application processes **Special Category Personal Data** (health data + biometric identifier Aadhaar):
- **Consent:** `consent_given` column exists but never enforced/checked
- **Data Minimization:** Collects 181 fields — review necessity
- **Storage Limitation:** No automated retention/deletion policy
- **Security Safeguards:** Encryption at rest/transit missing
- **Data Principal Rights:** No API for access, correction, erasure
- **Breach Notification:** No logging/monitoring to detect breaches

**Legal Recommendation:** Engage a DPDP compliance auditor before any production deployment handling real patient data.

---

## Appendix: Files Reviewed

| File | Purpose |
|------|---------|
| `backend/main.py` | FastAPI app, CORS, REST, WS mounts |
| `backend/config.py` | Settings, env vars, secrets |
| `backend/ws/handler.py` | WebSocket handlers (869 lines) |
| `backend/db/models.py` | SQLAlchemy models (6 tables) |
| `backend/db/connection.py` | Sync engine, session, migration |
| `backend/form_schema.py` | 30 sections, 181 fields |
| `backend/engine/local_fill.py` | Regex extraction (incl. Aadhaar) |
| `backend/engine/merge.py` | MergeEngine, confirmation logic |
| `backend/engine/validate.py` | Clinical validation alerts |
| `backend/llm/extract.py` | GeminiExtractor, fallback ladder |
| `backend/fhir/mapper.py` | FHIR stub (hardcoded gender) |
| `backend/storage/audio.py` | Deletion audit log |
| `backend/ws/groq_asr.py` | Groq Whisper adapter |
| `backend/ws/local_asr.py` | faster-whisper fallback |
| `deploy/docker-compose.yml` | 3-service stack (db, backend, web) |
| `web/nginx.conf` | Reverse proxy (missing /api) |
| `web/src/App.jsx` | React SPA, WS connection, mic |
| `web/src/hooks/useWebSocket.js` | Reconnecting WS client |
| `web/src/hooks/useBrowserMic.js` | Audio capture, VAD, chunking |
| `AUTOMATIC_DATA_GENERATION/.env` | **LIVE SECRETS — MUST ROTATE** |

---

**End of Report**  
*This report should be treated as confidential. Remediate CRITICAL findings before any external exposure.*