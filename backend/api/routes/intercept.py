"""Intercept session REST API routes.

POST   /api/v1/intercept/session           — start a proxy session
GET    /api/v1/intercept/session/{id}/status — health + counters
GET    /api/v1/intercept/session/{id}/ledger — tail the forensic ledger
DELETE /api/v1/intercept/session/{id}      — gracefully stop the session

Sessions are stored in an in-memory registry (same pattern as audit.py).
Each session runs an independent ProxySession asynccontextmanager in a
background asyncio.Task so it does not block the main FastAPI event loop.
"""
from __future__ import annotations

import asyncio
import uuid
from typing import Any

import structlog
from fastapi import APIRouter, BackgroundTasks, HTTPException

from api.schemas import (
    InterceptSessionRequest,
    InterceptSessionResponse,
    InterceptStatusResponse,
)
from orchestrator.process_manager import ProxySession

log = structlog.get_logger()
router = APIRouter(tags=["intercept"])

# ── In-memory session registry ────────────────────────────────────────────────
# keyed by session_id; each entry holds the session task + metadata
_sessions: dict[str, dict[str, Any]] = {}


# ── Background task that owns the proxy lifecycle ─────────────────────────────

async def _run_proxy_session(session_id: str, request: InterceptSessionRequest) -> None:
    """
    Runs inside a background asyncio.Task for the lifetime of the session.

    The ProxySession context manager owns the proxy server; when this task is
    cancelled (on DELETE) the context exits and the proxy shuts down cleanly.
    """
    record = _sessions[session_id]
    try:
        async with ProxySession(
            upstream_llm_url=request.upstream_llm_url,
            upstream_api_key=request.upstream_api_key,
            preferred_port=request.proxy_port,
            block_on_pii=request.block_on_pii,
            block_on_injection=request.block_on_injection,
            session_id=session_id,
        ) as handle:
            record["status"] = "running"
            record["proxy_port"] = handle.proxy_port
            record["proxy_base_url"] = handle.proxy_base_url
            record["ledger_path"] = str(handle.ledger_path)
            record["ledger"] = handle.ledger

            log.info(
                "intercept.session_ready",
                session_id=session_id,
                port=handle.proxy_port,
                upstream=request.upstream_llm_url,
            )

            # Keep the session alive until cancelled (DELETE endpoint)
            await asyncio.Event().wait()

    except asyncio.CancelledError:
        log.info("intercept.session_cancelled", session_id=session_id)
        record["status"] = "stopped"
    except Exception as exc:
        log.error("intercept.session_error", session_id=session_id, error=str(exc))
        record["status"] = "failed"
        record["error"] = str(exc)


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.post(
    "/intercept/session",
    response_model=InterceptSessionResponse,
    status_code=202,
    summary="Start an intercept proxy session",
)
async def create_intercept_session(request: InterceptSessionRequest):
    """
    Start an ephemeral Sentinel proxy session.

    The proxy will listen on the returned `proxy_port` and intercept all
    OpenAI-compatible LLM traffic. Point your target agent at the returned
    `proxy_base_url` by setting `OPENAI_BASE_URL`.
    """
    session_id = str(uuid.uuid4())
    _sessions[session_id] = {
        "session_id": session_id,
        "status": "starting",
        "proxy_port": request.proxy_port,
        "proxy_base_url": None,
        "ledger_path": None,
        "ledger": None,
        "upstream_llm_url": request.upstream_llm_url,
        "task": None,
    }

    task = asyncio.create_task(
        _run_proxy_session(session_id, request),
        name=f"intercept-session-{session_id}",
    )
    _sessions[session_id]["task"] = task

    # Wait briefly for the proxy to come up before returning to the caller
    # so the proxy_port / proxy_base_url fields are populated in the response
    for _ in range(50):   # 50 × 100ms = 5 s max
        await asyncio.sleep(0.1)
        if _sessions[session_id]["status"] in ("running", "failed", "stopped"):
            break

    record = _sessions[session_id]
    if record["status"] == "failed":
        raise HTTPException(
            status_code=500,
            detail=f"Proxy session failed to start: {record.get('error', 'unknown error')}",
        )

    log.info("intercept.session_created", session_id=session_id, port=record["proxy_port"])
    return InterceptSessionResponse(
        session_id=session_id,
        status=record["status"],
        proxy_port=record["proxy_port"],
        proxy_base_url=record.get("proxy_base_url") or f"http://127.0.0.1:{record['proxy_port']}/v1",
        ledger_path=record.get("ledger_path", ""),
        upstream_llm_url=request.upstream_llm_url,
    )


@router.get(
    "/intercept/session/{session_id}/status",
    response_model=InterceptStatusResponse,
    summary="Get intercept session status and traffic counters",
)
async def get_session_status(session_id: str):
    record = _sessions.get(session_id)
    if not record:
        raise HTTPException(status_code=404, detail=f"Session {session_id!r} not found")

    ledger = record.get("ledger")
    stats = await ledger.stats() if ledger else {}

    return InterceptStatusResponse(
        session_id=session_id,
        status=record["status"],
        proxy_port=record.get("proxy_port"),
        proxy_base_url=record.get("proxy_base_url"),
        transactions_processed=stats.get("total_transactions", 0),
        allowed_count=stats.get("allowed", 0),
        redacted_count=stats.get("redacted", 0),
        blocked_count=stats.get("blocked", 0),
        pii_types_encountered=stats.get("pii_types_encountered", []),
        ledger_path=record.get("ledger_path"),
    )


@router.get(
    "/intercept/session/{session_id}/ledger",
    summary="Return the last N ledger entries for a session",
)
async def get_session_ledger(session_id: str, n: int = 100):
    """
    Return the most recent *n* ledger entries (most recent last).

    Note: raw PII values are never stored — only SHA-256 digests and PII type
    names appear in the ledger, in compliance with GDPR Article 5(1)(e).
    """
    record = _sessions.get(session_id)
    if not record:
        raise HTTPException(status_code=404, detail=f"Session {session_id!r} not found")
    ledger = record.get("ledger")
    if not ledger:
        return {"session_id": session_id, "entries": [], "total": 0}
    entries = await ledger.tail(n=n)
    return {"session_id": session_id, "entries": entries, "total": len(entries)}


@router.delete(
    "/intercept/session/{session_id}",
    summary="Stop an active intercept proxy session",
)
async def stop_session(session_id: str):
    record = _sessions.get(session_id)
    if not record:
        raise HTTPException(status_code=404, detail=f"Session {session_id!r} not found")

    task: asyncio.Task | None = record.get("task")
    if task and not task.done():
        task.cancel()
        try:
            await asyncio.wait_for(asyncio.shield(task), timeout=6.0)
        except (asyncio.CancelledError, asyncio.TimeoutError):
            pass

    record["status"] = "stopped"
    log.info("intercept.session_stopped", session_id=session_id)
    return {"session_id": session_id, "status": "stopped"}


@router.get(
    "/intercept/sessions",
    summary="List all intercept sessions",
)
async def list_sessions():
    sessions = []
    for record in _sessions.values():
        sessions.append({
            "session_id": record["session_id"],
            "status": record["status"],
            "proxy_port": record.get("proxy_port"),
            "upstream_llm_url": record.get("upstream_llm_url"),
        })
    return {"sessions": list(reversed(sessions))}
