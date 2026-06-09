"""Ephemeral Proxy Lifecycle Orchestrator.

Manages the full lifecycle of a Sentinel intercept proxy session:

  1. Finds a free TCP port (tries 8787 first, then scans upward)
  2. Builds the proxy app (evaluator + dispatcher + ledger)
  3. Starts uvicorn.Server in a background asyncio task (same event loop,
     no subprocess overhead — clean shutdown on task cancel)
  4. Polls /health until the server is accepting connections (max 5 s)
  5. Yields a SessionHandle to the caller
  6. On context exit — cancels the server task and awaits drain

Additionally provides launch_target_agent() for running a target agent
subprocess with OPENAI_BASE_URL pointing at the proxy.

Usage
-----
    async with ProxySession(
        upstream_llm_url="https://api.openai.com/v1",
        upstream_api_key=os.getenv("OPENAI_API_KEY"),
    ) as handle:
        print(f"Proxy live at {handle.proxy_base_url}")
        proc = await launch_target_agent(
            cmd=["python", "my_agent.py"],
            proxy_base_url=handle.proxy_base_url,
        )
        await proc.wait()
"""
from __future__ import annotations

import asyncio
import os
import socket
import uuid
from contextlib import asynccontextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import AsyncIterator, Optional

import httpx
import structlog
import uvicorn

from modules.adapter import ProxyComplianceAdapter
from proxy.dispatcher import LLMDispatcher
from proxy.server import build_proxy_app
from ledger.transaction_log import TransactionLog

log = structlog.get_logger()

_PROXY_HEALTH_TIMEOUT = 5.0   # seconds to wait for proxy to come up
_PROXY_HEALTH_INTERVAL = 0.1  # seconds between health polls
_DEFAULT_PROXY_PORT = 8787
_PORT_SCAN_MAX = 100          # try up to 100 ports before giving up


# ── Port utilities ────────────────────────────────────────────────────────────

def _is_port_free(port: int, host: str = "127.0.0.1") -> bool:
    """Return True if the given TCP port is not in use."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            s.bind((host, port))
            return True
        except OSError:
            return False


def _find_free_port(preferred: int = _DEFAULT_PROXY_PORT) -> int:
    """Return the preferred port if free, else scan upward for a free one."""
    for candidate in range(preferred, preferred + _PORT_SCAN_MAX):
        if _is_port_free(candidate):
            return candidate
    raise RuntimeError(
        f"No free TCP port found in range {preferred}–{preferred + _PORT_SCAN_MAX}"
    )


# ── Session handle ─────────────────────────────────────────────────────────────

@dataclass
class SessionHandle:
    """
    Returned by ProxySession context manager.

    Carry this around to interact with the running proxy session.
    """
    session_id: str
    proxy_port: int
    proxy_base_url: str    # e.g. "http://127.0.0.1:8787/v1"
    ledger_path: Path
    ledger: TransactionLog


# ── Proxy lifecycle context manager ──────────────────────────────────────────

@asynccontextmanager
async def ProxySession(
    upstream_llm_url: str,
    upstream_api_key: Optional[str] = None,
    preferred_port: int = _DEFAULT_PROXY_PORT,
    block_on_pii: bool = False,
    block_on_injection: bool = True,
    session_id: Optional[str] = None,
    ledger_root: Optional[Path] = None,
) -> AsyncIterator[SessionHandle]:
    """
    Async context manager that spins up an ephemeral Sentinel proxy.

    Parameters
    ----------
    upstream_llm_url : str
        Base URL of the real LLM, e.g. "https://api.openai.com/v1".
        Supplied per-session so different sessions can target different providers.
    upstream_api_key : str | None
        API key for the upstream LLM. Falls back to OPENAI_API_KEY env var.
    preferred_port   : int
        Try this port first; auto-scan upward if taken.
    block_on_pii     : bool
        If True, critical PII causes a BLOCK (default: REDACT).
    block_on_injection : bool
        If True, any injection pattern causes a BLOCK (default: True).
    session_id       : str | None
        Caller-supplied session ID. Auto-generated UUID if not provided.
    ledger_root      : Path | None
        Directory for ledger files. Defaults to ledger/data/.
    """
    sid = session_id or str(uuid.uuid4())
    port = _find_free_port(preferred_port)
    api_key = upstream_api_key or os.getenv("OPENAI_API_KEY", "")

    log.info(
        "proxy_session.starting",
        session_id=sid,
        port=port,
        upstream=upstream_llm_url,
    )

    # Build components
    evaluator = ProxyComplianceAdapter(
        block_on_pii=block_on_pii,
        block_on_injection=block_on_injection,
    )
    dispatcher = LLMDispatcher(upstream_url=upstream_llm_url, api_key=api_key)
    ledger = TransactionLog(session_id=sid, ledger_root=ledger_root)

    proxy_app = build_proxy_app(evaluator, dispatcher, ledger, session_id=sid)

    # Configure uvicorn to run programmatically (no os.fork / subprocess)
    uv_config = uvicorn.Config(
        app=proxy_app,
        host="127.0.0.1",
        port=port,
        log_level="warning",   # Keep proxy logs quiet — sentinel backend owns stdout
        access_log=False,
    )
    server = uvicorn.Server(config=uv_config)

    # Start the server as a background asyncio task
    server_task = asyncio.create_task(server.serve(), name=f"proxy-{sid}")

    # Poll /health until the server is accepting connections
    proxy_base = f"http://127.0.0.1:{port}/v1"
    health_url = f"http://127.0.0.1:{port}/health"

    async with httpx.AsyncClient(timeout=2.0) as probe:
        deadline = asyncio.get_event_loop().time() + _PROXY_HEALTH_TIMEOUT
        while True:
            await asyncio.sleep(_PROXY_HEALTH_INTERVAL)
            try:
                r = await probe.get(health_url)
                if r.status_code == 200:
                    break
            except Exception:
                pass
            if asyncio.get_event_loop().time() > deadline:
                server_task.cancel()
                raise TimeoutError(
                    f"Proxy server on port {port} did not start within "
                    f"{_PROXY_HEALTH_TIMEOUT}s"
                )

    log.info(
        "proxy_session.ready",
        session_id=sid,
        port=port,
        proxy_base_url=proxy_base,
    )

    handle = SessionHandle(
        session_id=sid,
        proxy_port=port,
        proxy_base_url=proxy_base,
        ledger_path=ledger.path,
        ledger=ledger,
    )

    try:
        yield handle
    finally:
        # Signal uvicorn to shut down and wait for it to drain
        server.should_exit = True
        try:
            await asyncio.wait_for(server_task, timeout=5.0)
        except (asyncio.CancelledError, asyncio.TimeoutError):
            server_task.cancel()
        log.info("proxy_session.stopped", session_id=sid, port=port)


# ── Target agent subprocess launcher ─────────────────────────────────────────

async def launch_target_agent(
    cmd: list[str],
    proxy_base_url: str,
    extra_env: Optional[dict[str, str]] = None,
    cwd: Optional[str] = None,
) -> asyncio.subprocess.Process:
    """
    Launch a target agent subprocess with OPENAI_BASE_URL redirected to the
    Sentinel proxy.  The agent's code is untouched — only its environment
    variables are modified.

    Parameters
    ----------
    cmd           : list[str] — command to run, e.g. ["python", "agent.py"]
    proxy_base_url: str       — from SessionHandle.proxy_base_url
    extra_env     : dict      — additional env vars to inject
    cwd           : str       — working directory for the subprocess

    Returns
    -------
    asyncio.subprocess.Process — caller is responsible for awaiting proc.wait()
    """
    env = {**os.environ}
    env["OPENAI_BASE_URL"] = proxy_base_url
    env["HTTP_PROXY"] = proxy_base_url.replace("/v1", "")
    env["HTTPS_PROXY"] = proxy_base_url.replace("/v1", "")
    if extra_env:
        env.update(extra_env)

    log.info(
        "target_agent.launching",
        cmd=cmd,
        openai_base_url=proxy_base_url,
    )

    proc = await asyncio.create_subprocess_exec(
        *cmd,
        env=env,
        cwd=cwd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    log.info("target_agent.launched", pid=proc.pid)
    return proc
