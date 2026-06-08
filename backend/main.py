"""Sentinel — FastAPI entrypoint."""
from __future__ import annotations

import os
import structlog
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.routes.audit import router as audit_router
from api.routes.reports import router as reports_router

log = structlog.get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI):
    log.info("sentinel.startup", environment=os.getenv("ENVIRONMENT", "development"))
    yield
    log.info("sentinel.shutdown")


app = FastAPI(
    title="Sentinel GRC Auditor API",
    description="Autonomous AI Governance, Risk, and Compliance auditor",
    version="1.0.0",
    lifespan=lifespan,
)

origins = os.getenv("CORS_ORIGINS", "http://localhost:3000").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(audit_router, prefix="/api/v1")
app.include_router(reports_router, prefix="/api/v1")


@app.get("/health")
async def health():
    return {"status": "ok", "service": "sentinel-backend"}
