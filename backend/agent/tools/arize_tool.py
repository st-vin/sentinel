"""ArizeTraceTool — fetches traces, spans, and evaluations from Arize via MCP."""
from __future__ import annotations

import os
import json
import structlog
from typing import Any

import httpx

from agent.tools.base import BaseSentinelTool

log = structlog.get_logger()

MOCK_TRACES = [
    {
        "span_id": f"span_{i:04d}",
        "trace_id": f"trace_{i:04d}",
        "input": f"User input {i}",
        "output": f"Agent response {i}",
        "latency_ms": 250 + i * 10,
        "model": "gemini-1.5-flash",
    }
    for i in range(25)
]


class ArizeTraceTool(BaseSentinelTool):
    name = "arize_trace_fetcher"
    description = "Retrieve LLM trace data from Arize for a given project"

    def __init__(self, api_key: str = "", space_key: str = ""):
        self.api_key = api_key or os.getenv("ARIZE_API_KEY", "")
        self.space_key = space_key or os.getenv("ARIZE_SPACE_KEY", "")
        self.base_url = "https://app.arize.com/api/v1"

    def _run(self, project_id: str = "", limit: int = 50, **kwargs: Any) -> dict:
        if not self.api_key or not project_id:
            log.warning("arize_tool.no_credentials_using_mock")
            return {"traces": MOCK_TRACES[:limit], "source": "mock"}

        try:
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            }
            with httpx.Client(timeout=30) as client:
                resp = client.get(
                    f"{self.base_url}/traces",
                    headers=headers,
                    params={"project_id": project_id, "limit": limit},
                )
                resp.raise_for_status()
                data = resp.json()
                log.info("arize_tool.fetched", count=len(data.get("traces", [])))
                return data
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 401:
                raise ArizeAuthError("Arize authentication failed — check your API key") from exc
            log.error("arize_tool.http_error", status=exc.response.status_code)
            return {"traces": MOCK_TRACES[:limit], "source": "mock_fallback", "error": str(exc)}
        except httpx.TimeoutException as exc:
            raise ToolTimeoutError("Arize MCP timed out after 30s") from exc
        except Exception as exc:
            log.error("arize_tool.unexpected_error", error=str(exc))
            return {"traces": MOCK_TRACES[:limit], "source": "mock_fallback"}

    def get_traces(self, project_id: str, limit: int = 50) -> list[dict]:
        result = self._run(project_id=project_id, limit=limit)
        return result.get("traces", [])

    def get_recent_responses(self, project_id: str, n: int = 20) -> list[str]:
        traces = self.get_traces(project_id, limit=n)
        return [t.get("output", "") for t in traces if t.get("output")]


class MockArizeTraceTool(ArizeTraceTool):
    """Always returns fixture data — use as fallback when Arize is unreachable."""

    def _run(self, project_id: str = "", limit: int = 50, **kwargs: Any) -> dict:
        return {"traces": MOCK_TRACES[:limit], "source": "mock"}


class ArizeAuthError(Exception):
    pass


class ToolTimeoutError(Exception):
    pass
