"""ElasticSearchTool — searches Elastic indices for PII patterns via MCP."""
from __future__ import annotations

import os
import structlog
from typing import Any

import httpx

from agent.tools.base import BaseSentinelTool

log = structlog.get_logger()

MOCK_PII_HITS = [
    {
        "index": "agent-logs-2026",
        "doc_id": "doc_001",
        "field": "message",
        "match": "email",
        "snippet": "User email: j***.d***@example.com was logged",
        "source": "elastic_mock",
    }
]


class ElasticSearchTool(BaseSentinelTool):
    name = "elastic_pii_scanner"
    description = "Search Elastic logs for PII patterns"

    def __init__(self, api_key: str = "", cloud_id: str = ""):
        self.api_key = api_key or os.getenv("ELASTIC_API_KEY", "")
        self.cloud_id = cloud_id or os.getenv("ELASTIC_CLOUD_ID", "")

    def _run(self, index: str = "*", patterns: list[str] | None = None, **kwargs: Any) -> dict:
        if not self.api_key or not self.cloud_id:
            log.warning("elastic_tool.no_credentials_using_mock")
            return {"hits": MOCK_PII_HITS, "source": "mock"}

        try:
            query = {
                "query": {
                    "bool": {
                        "should": [
                            {"regexp": {"message": p}} for p in (patterns or [])
                        ]
                    }
                },
                "size": 100,
            }
            headers = {
                "Authorization": f"ApiKey {self.api_key}",
                "Content-Type": "application/json",
            }
            base_url = self._resolve_base_url()
            with httpx.Client(timeout=30) as client:
                resp = client.post(
                    f"{base_url}/{index}/_search",
                    headers=headers,
                    json=query,
                )
                resp.raise_for_status()
                data = resp.json()
                hits = [
                    {
                        "index": h.get("_index"),
                        "doc_id": h.get("_id"),
                        "snippet": h.get("_source", {}).get("message", ""),
                        "source": "elastic",
                    }
                    for h in data.get("hits", {}).get("hits", [])
                ]
                log.info("elastic_tool.searched", hits=len(hits))
                return {"hits": hits, "source": "elastic"}
        except Exception as exc:
            log.error("elastic_tool.error", error=str(exc))
            return {"hits": MOCK_PII_HITS, "source": "mock_fallback", "error": str(exc)}

    def _resolve_base_url(self) -> str:
        if self.cloud_id and ":" in self.cloud_id:
            import base64
            decoded = base64.b64decode(self.cloud_id.split(":")[1]).decode()
            parts = decoded.split("$")
            host = parts[0]
            es_id = parts[1] if len(parts) > 1 else "elasticsearch"
            return f"https://{es_id}.{host}"
        return "https://localhost:9200"

    def search_pii(self, index: str = "*", patterns: list[str] | None = None) -> list[dict]:
        result = self._run(index=index, patterns=patterns)
        return result.get("hits", [])
