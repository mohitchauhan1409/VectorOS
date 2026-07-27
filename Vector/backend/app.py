"""Vector backend — FastAPI application entry point.

    uvicorn backend.app:app --reload --port 8787

On startup it creates the schema and seeds the demo workspace (idempotent).
"""

from __future__ import annotations

import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.db import SessionLocal, init_db
from backend.routers import analytics, auth, campaigns, companies, meetings, people, pipeline
from backend.seed import seed_demo

app = FastAPI(title="Vector API", version="1.0.0")

_origins = os.getenv(
    "VECTOR_CORS_ORIGINS",
    "http://localhost:5273,http://localhost:5173,http://127.0.0.1:5273",
).split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in _origins],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(companies.router)
app.include_router(people.router)
app.include_router(campaigns.router)
app.include_router(meetings.router)
app.include_router(analytics.router)
app.include_router(pipeline.router)


@app.on_event("startup")
def _startup() -> None:
    init_db()
    db = SessionLocal()
    try:
        seed_demo(db)
    finally:
        db.close()


@app.get("/api/health")
def health() -> dict:
    return {"status": "ok", "service": "vector-api"}
