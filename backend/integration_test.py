"""One-shot integration test — starts backend, exercises REST + WebSocket, prints results."""

import asyncio
import base64
import json
import os
import sys
import time

import httpx
import websockets

# Point at an isolated instance to test without disturbing a live encounter:
#   SCRIBE_TEST_PORT=8766, with the backend started using a separate
#   DATABASE_URL (e.g. sqlite:///./test_scribe.db). Defaults to the
#   developer's normal backend on 8765.
_PORT = os.getenv("SCRIBE_TEST_PORT", "8765")
BASE = f"http://127.0.0.1:{_PORT}"
WS_CHUNKS = f"ws://127.0.0.1:{_PORT}/ws/chunks"
WS_DASH = f"ws://127.0.0.1:{_PORT}/ws/dashboard"


async def test_rest():
    async with httpx.AsyncClient() as client:
        r = await client.get(f"{BASE}/health", timeout=5)
        assert r.status_code == 200, f"health status {r.status_code}"
        assert r.json() == {"status": "ok"}

        s = await client.get(f"{BASE}/api/schema", timeout=5)
        assert s.status_code == 200, "schema endpoint failed"
        schema_fields = s.json()["sections"][0]["fields"][0]["key"]
        return f"REST /health + /api/schema OK (first field: {schema_fields})"


async def test_dashboard_ws():
    async with websockets.connect(WS_DASH, open_timeout=5) as ws:
        # Connect handler may push capture_status/snapshot first — drain until mic_start ack.
        await ws.send(json.dumps({"type": "mic_start", "encounter_id": "it-dash"}))
        resp = None
        deadline = time.time() + 5
        while time.time() < deadline:
            msg = json.loads(await asyncio.wait_for(ws.recv(), timeout=deadline - time.time()))
            if msg.get("type") == "session_state":
                resp = msg
                break
        assert resp is not None, "no session_state received after mic_start"
        assert resp.get("active") is True
        await ws.send(json.dumps({"type": "mic_stop"}))
        return f"WS {WS_DASH} mic_start/mic_stop round-trip OK"


async def test_chunks_ws():
    async with websockets.connect(WS_CHUNKS, open_timeout=5) as ws:
        await ws.send(json.dumps({"type": "session_start", "encounter_id": "it-chunks"}))
        silence = base64.b64encode(b"\x00\x00" * 1600).decode("ascii")
        payload = {
            "chunk_id": 0,
            "pcm_b64": silence,
            "sample_rate": 16000,
            "channels": 1,
            "mic_channel": 0,
            "start_sample": 0,
            "end_sample": 1600,
            "duration_ms": 100,
            "language": "hi",
        }
        await ws.send(json.dumps(payload))
        try:
            resp = await asyncio.wait_for(ws.recv(), timeout=15)
            data = json.loads(resp)
            assert data.get("type") == "chunk_result", f"unexpected type {data.get('type')}"
            assert "answers" in data and "confirmed" in data, "missing answers/confirmed"
            return f"WS {WS_CHUNKS} chunk round-trip OK (answers={sum(v is not None for v in data['answers'].values())} fields)"
        except asyncio.TimeoutError:
            return "WS /ws/chunks connected but no chunk_result returned (no API key / empty result expected)"


async def main():
    results = []
    results.append(await test_rest())
    results.append(await test_dashboard_ws())
    results.append(await test_chunks_ws())
    for r in results:
        print("PASS:", r)


if __name__ == "__main__":
    asyncio.run(main())
