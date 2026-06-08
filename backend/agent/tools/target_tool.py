"""TargetAgentTool — sends prompts to the target agent and captures responses."""
from __future__ import annotations

import structlog
from typing import Any

import httpx

from agent.tools.base import BaseSentinelTool

log = structlog.get_logger()


class TargetAgentTool(BaseSentinelTool):
    name = "target_agent_prober"
    description = "Send adversarial probes to the target agent endpoint"

    def __init__(self, endpoint_url: str):
        self.endpoint_url = endpoint_url

    def _run(self, prompt: str = "", **kwargs: Any) -> dict:
        try:
            with httpx.Client(timeout=30) as client:
                resp = client.post(
                    self.endpoint_url,
                    json={"message": prompt, "role": "user"},
                    headers={"Content-Type": "application/json"},
                )
                resp.raise_for_status()
                data = resp.json()
                response_text = (
                    data.get("response")
                    or data.get("message")
                    or data.get("content")
                    or str(data)
                )
                log.debug("target_tool.probe_sent", prompt_len=len(prompt), response_len=len(response_text))
                return {"prompt": prompt, "response": response_text, "status": "ok"}
        except httpx.HTTPStatusError as exc:
            log.error("target_tool.http_error", status=exc.response.status_code, url=self.endpoint_url)
            return {"prompt": prompt, "response": "", "status": "error", "error": str(exc)}
        except httpx.TimeoutException:
            log.error("target_tool.timeout", url=self.endpoint_url)
            return {"prompt": prompt, "response": "", "status": "timeout"}
        except Exception as exc:
            log.error("target_tool.unexpected_error", error=str(exc))
            return {"prompt": prompt, "response": "", "status": "error", "error": str(exc)}

    def probe(self, prompt: str) -> dict:
        return self._run(prompt=prompt)
