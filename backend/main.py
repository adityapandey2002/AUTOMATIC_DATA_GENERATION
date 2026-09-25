"""FastAPI application — ambient scribe backend."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket
from fastapi.middleware.cors import CORSMiddleware

from config import settings
from db.connection import init_db
from ws.handler import ws_chunks_handler, ws_dashboard_handler
from form_schema import FORM_SCHEMA

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Initializing database...")
    init_db()
    logger.info("Database ready")
    yield
    logger.info("Shutting down")


app = FastAPI(
    title="Ambient Clinical AI Scribe",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/api/schema")
async def schema():
    return FORM_SCHEMA


@app.get("/api/patients")
async def list_patients():
    from db.connection import SessionLocal
    from db.models import Patient

    db = SessionLocal()
    try:
        rows = (
            db.query(Patient)
            .order_by(Patient.saved_at.desc())
            .limit(200)
            .all()
        )
        return [
            {
                "id": p.id,
                "encounter_id": p.encounter_id,
                "name": p.name,
                "age": p.age,
                "language": p.language,
                "spouse_parent_of": p.spouse_parent_of,
                "contact_phone": p.contact_phone,
                "address": p.address,
                "district": p.district,
                "block": p.block,
                "health_centre": p.health_centre,
                "answers": p.answers or {},
                "saved_at": p.saved_at.isoformat() if p.saved_at else None,
            }
            for p in rows
        ]
    finally:
        db.close()


@app.websocket("/ws/chunks")
async def chunk_endpoint(websocket: WebSocket):
    await ws_chunks_handler(websocket)


@app.websocket("/ws/dashboard")
async def dashboard_endpoint(websocket: WebSocket):
    await ws_dashboard_handler(websocket)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host=settings.ws_host,
        port=settings.ws_port,
        reload=True,
    )
