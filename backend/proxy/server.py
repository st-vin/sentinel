"""Sentinel Ephemeral Proxy Server — Component 1 of the interception pipeline.

This is a STANDALONE FastAPI application, separate from the main Sentinel API.
It is never imported into main.py.  Instead it is launched programmatically by
orchestrator/process_manager.py via uvicorn.Server.

Architecture
------------
Every incoming POST to /v1/chat/completions is:

  1. Parsed       — extract JSON body
  2. Evaluated    — IComplianceEvaluator.evaluate_payload() (thread pool)
  3. Ledger write — TransactionLog.record() before touching the wire
  4. Dispatched   — forward to upstream LLM (or return 403 if BLOCK)
  5. Relayed      — return the upstream response to the target agent

The evaluator and dispatcher are injected via app.state at startup so that
every component remains independently testable without a running server.
"""
from __future__ import annotations

import asyncio
import os
import structlog
from contextlib import asynccontextmanager
from typing import Any, Optional

import uvicorn
from fastapi import FastAPI, Request, Response
from fastapi.responses import JSONResponse

from proxy.interfaces import IComplianceEvaluator, VerdictType
from proxy.dispatcher import LLMDispatcher
from ledger.transaction_log import TransactionLog, TransactionEntry

log = structlog.get_logger()


# ── Application factory ───────────────────────────────────────────────────────

def build_proxy_app(
    evaluator: IComplianceEvaluator,
    dispatcher: LLMDispatcher,
    ledger: TransactionLog,
    session_id: str,
) -> FastAPI:
    """
    Construct and configure the ephemeral proxy FastAPI app.

    Parameters are injected rather than read from globals so that the app
    is fully testable by passing mock implementations.
    """

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        app.state.evaluator = evaluator
        app.state.dispatcher = dispatcher
        app.state.ledger = ledger
        app.state.session_id = session_id
        log.info("proxy.startup", session_id=session_id)
        yield
        await dispatcher.aclose()
        log.info("proxy.shutdown", session_id=session_id)

    proxy = FastAPI(
        title="Sentinel Intercept Proxy",
        version="1.0.0",
        lifespan=lifespan,
        docs_url=None,   # No docs on the proxy — it's ephemeral infra
        redoc_url=None,
    )

    # ── Health endpoint ───────────────────────────────────────────────────────

    @proxy.get("/health")
    async def health() -> dict:
        return {"status": "ok", "session_id": session_id}

    # ── Main intercept endpoint ───────────────────────────────────────────────

    @proxy.post("/v1/chat/completions")
    async def intercept_chat(request: Request) -> Response:
        """
        Drop-in replacement for POST /v1/chat/completions.

        The target agent must set OPENAI_BASE_URL=http://127.0.0.1:<port>/v1
        and will be completely unaware of the interception.
        """
        ev: IComplianceEvaluator = request.app.state.evaluator
        disp: LLMDispatcher = request.app.state.dispatcher
        lgr: TransactionLog = request.app.state.ledger
        sid: str = request.app.state.session_id

        # ── 1. Parse body ─────────────────────────────────────────────────────
        try:
            body: dict = await request.json()
        except Exception as exc:
            log.warning("proxy.bad_request", error=str(exc))
            return JSONResponse(
                status_code=400,
                content={"error": {"message": "Invalid JSON body", "type": "invalid_request_error"}},
            )

        payload_digest = IComplianceEvaluator.digest_payload(body)

        # ── 2. Evaluate (runs in thread pool — synchronous evaluator) ─────────
        loop = asyncio.get_event_loop()
        verdict = await loop.run_in_executor(None, ev.evaluate_payload, body)

        log.info(
            "proxy.verdict",
            session_id=sid,
            verdict=verdict.verdict,
            findings=len(verdict.findings),
            pii_types=verdict.pii_types_found,
        )

        # ── 3. Write-ahead ledger entry (before touching the wire) ────────────
        entry = TransactionEntry(
            session_id=sid,
            original_payload_digest=payload_digest,
            verdict=verdict.verdict.value,
            reason=verdict.reason,
            findings_count=len(verdict.findings),
            pii_types_found=verdict.pii_types_found,
            was_forwarded=verdict.verdict != VerdictType.BLOCK,
            model=body.get("model", "unknown"),
        )
        await lgr.record(entry)

        # ── 4. Enforce verdict ────────────────────────────────────────────────
        if verdict.verdict == VerdictType.BLOCK:
            return JSONResponse(
                status_code=403,
                content={
                    "error": {
                        "message": f"Request blocked by Sentinel: {verdict.reason}",
                        "type": "sentinel_compliance_block",
                        "findings": verdict.findings,
                        "session_id": sid,
                    }
                },
            )

        # Use redacted payload if available, otherwise forward original
        forward_payload = (
            verdict.redacted_payload
            if verdict.verdict == VerdictType.REDACT and verdict.redacted_payload
            else body
        )

        # ── 5. Dispatch to upstream LLM ───────────────────────────────────────
        try:
            upstream_response = await disp.forward(
                payload=forward_payload,
                path_suffix="/chat/completions",
            )
        except Exception as exc:
            log.error("proxy.dispatch_error", error=str(exc))
            return JSONResponse(
                status_code=502,
                content={"error": {"message": f"Upstream LLM error: {exc}", "type": "upstream_error"}},
            )

        # ── 6. Relay upstream response to target agent ────────────────────────
        relay_headers = {
            k: v for k, v in upstream_response.headers.items()
            if k.lower() not in {"content-encoding", "transfer-encoding", "connection"}
        }
        # Annotate response so the ledger/dashboard can correlate
        relay_headers["x-sentinel-session-id"] = sid
        relay_headers["x-sentinel-verdict"] = verdict.verdict.value

        return Response(
            content=upstream_response.content,
            status_code=upstream_response.status_code,
            headers=relay_headers,
            media_type=upstream_response.headers.get("content-type", "application/json"),
        )

    # ── Wildcard passthrough for any other paths ──────────────────────────────
    # e.g. /v1/models, /v1/embeddings — forward without evaluation
    @proxy.api_route(
        "/v1/{path:path}",
        methods=["GET", "POST", "PUT", "DELETE", "PATCH"],
    )
    async def passthrough(request: Request, path: str) -> Response:
        """Forward non-completions paths directly to upstream without evaluation."""
        disp: LLMDispatcher = request.app.state.dispatcher
        try:
            body_bytes = await request.body()
            body = {}
            if body_bytes:
                import json as _json
                body = _json.loads(body_bytes)
        except Exception:
            body = {}

        try:
            resp = await disp.forward(payload=body, path_suffix=f"/{path}")
        except Exception as exc:
            return JSONResponse(status_code=502, content={"error": str(exc)})

        relay_headers = {
            k: v for k, v in resp.headers.items()
            if k.lower() not in {"content-encoding", "transfer-encoding", "connection"}
        }
        return Response(
            content=resp.content,
            status_code=resp.status_code,
            headers=relay_headers,
            media_type=resp.headers.get("content-type", "application/json"),
        )

    return proxy


# ── Standalone runner (for smoke testing) ────────────────────────────────────

if __name__ == "__main__":
    """
    Smoke-test runner — starts the proxy with a no-op evaluator.
    Usage:
        cd backend
        python -m proxy.server
    Then: curl http://localhost:8787/health
    """
    from proxy.interfaces import InterceptionVerdict

    class _PassthroughEvaluator(IComplianceEvaluator):
        def evaluate_payload(self, payload: dict) -> InterceptionVerdict:
            return InterceptionVerdict(verdict=VerdictType.ALLOW, reason="passthrough mode")

    upstream = os.getenv("SENTINEL_UPSTREAM_LLM_URL", "https://api.openai.com/v1")
    port = int(os.getenv("SENTINEL_PROXY_PORT", "8787"))
    ledger = TransactionLog()

    _evaluator = _PassthroughEvaluator()
    _dispatcher = LLMDispatcher(upstream_url=upstream)
    _app = build_proxy_app(_evaluator, _dispatcher, ledger, session_id="smoke-test")

    uvicorn.run(_app, host="127.0.0.1", port=port, log_level="info")
