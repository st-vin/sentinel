"""Proxy dispatcher — forwards sanitised payloads to the real upstream LLM.

Component 3 of the interception pipeline (after evaluate → ledger → dispatch).
Uses httpx for both streaming and non-streaming responses so the proxy is
transparent to the caller regardless of how the target agent reads the reply.
"""
from __future__ import annotations

import os
import structlog
from typing import AsyncIterator

import httpx

log = structlog.get_logger()

# Hop-by-hop headers that must not be forwarded
_HOP_BY_HOP = frozenset(
    [
        "connection",
        "keep-alive",
        "proxy-authenticate",
        "proxy-authorization",
        "te",
        "trailers",
        "transfer-encoding",
        "upgrade",
        "content-encoding",  # httpx re-encodes automatically
        "content-length",    # httpx recalculates
    ]
)


def _filter_headers(headers: httpx.Headers) -> dict[str, str]:
    """Strip hop-by-hop headers before forwarding upstream."""
    return {k: v for k, v in headers.items() if k.lower() not in _HOP_BY_HOP}


class LLMDispatcher:
    """
    Forwards a (possibly redacted) payload to the upstream LLM and returns
    its response as an httpx.Response.

    The dispatcher is instantiated once per proxy server startup and shared
    across all requests via FastAPI app state.

    Parameters
    ----------
    upstream_url : str
        Base URL of the real LLM provider, e.g. "https://api.openai.com/v1".
        The path suffix from the incoming request ("/chat/completions") is
        appended automatically.
    api_key : str | None
        Bearer token for the upstream LLM.  Falls back to the
        OPENAI_API_KEY environment variable if not provided.
    timeout : float
        Request timeout in seconds (default 120 — allows long completions).
    """

    def __init__(
        self,
        upstream_url: str,
        api_key: str | None = None,
        timeout: float = 120.0,
    ) -> None:
        self._upstream_url = upstream_url.rstrip("/")
        self._api_key = api_key or os.getenv("OPENAI_API_KEY", "")
        self._timeout = timeout
        self._client = httpx.AsyncClient(timeout=self._timeout)

    async def forward(
        self,
        payload: dict,
        path_suffix: str = "/chat/completions",
        extra_headers: dict[str, str] | None = None,
    ) -> httpx.Response:
        """
        POST payload to upstream LLM and return the full response.

        Parameters
        ----------
        payload      : dict — the (potentially redacted) request body
        path_suffix  : str  — path appended to upstream base URL
        extra_headers: dict — any additional headers to forward

        Returns
        -------
        httpx.Response — ready to relay back to the target agent
        """
        target_url = f"{self._upstream_url}{path_suffix}"
        headers: dict[str, str] = {"Authorization": f"Bearer {self._api_key}"}
        if extra_headers:
            headers.update(_filter_headers(httpx.Headers(extra_headers)))

        log.debug(
            "dispatcher.forward",
            url=target_url,
            model=payload.get("model", "unknown"),
            stream=payload.get("stream", False),
        )

        try:
            response = await self._client.post(
                target_url,
                json=payload,
                headers=headers,
            )
            log.info(
                "dispatcher.response",
                status=response.status_code,
                model=payload.get("model"),
            )
            return response
        except httpx.TimeoutException as exc:
            log.error("dispatcher.timeout", url=target_url, error=str(exc))
            raise
        except httpx.RequestError as exc:
            log.error("dispatcher.request_error", url=target_url, error=str(exc))
            raise

    async def aclose(self) -> None:
        """Close the underlying httpx client — called on proxy shutdown."""
        await self._client.aclose()
