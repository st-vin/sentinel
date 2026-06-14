"""Proxy layer interfaces — strict component contracts for the interception pipeline.

Every component that plugs into the Sentinel proxy MUST satisfy these interfaces.
This keeps the proxy server, compliance modules, and dispatcher independently testable.
"""
from __future__ import annotations

import hashlib
import json
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class VerdictType(str, Enum):
    """The three possible outcomes of a compliance evaluation."""
    ALLOW = "allow"      # Payload passes — forward as-is
    REDACT = "redact"    # Payload contains PII — scrub and forward
    BLOCK = "block"      # Payload contains injection / critical violation — reject


@dataclass
class InterceptionVerdict:
    """
    Returned by IComplianceEvaluator.evaluate_payload().

    Fields
    ------
    verdict         : VerdictType — the enforcement action to take
    reason          : str — human-readable explanation (appears in 403 body / ledger)
    findings        : list[dict] — serialisable snapshots of every detected issue
    redacted_payload: dict | None — populated iff verdict == REDACT; the sanitised
                      copy of the original payload ready to forward to the LLM
    pii_types_found : list[str] — deduplicated PII type names seen (for ledger stats)
    """
    verdict: VerdictType
    reason: str
    findings: list[dict] = field(default_factory=list)
    redacted_payload: Optional[dict] = None
    pii_types_found: list[str] = field(default_factory=list)


class IComplianceEvaluator(ABC):
    """
    Abstract evaluator interface.

    Implementations MUST be synchronous — the proxy server calls this from an
    asyncio thread pool via run_in_executor() to avoid blocking the event loop.

    The payload is the full parsed JSON body of the intercepted LLM request
    (OpenAI chat/completions format or any JSON-over-HTTP format).
    """

    @abstractmethod
    def evaluate_payload(self, payload: dict) -> InterceptionVerdict:
        """
        Evaluate the intercepted request payload.

        Parameters
        ----------
        payload : dict
            The parsed JSON body of the incoming LLM request.

        Returns
        -------
        InterceptionVerdict
            The enforcement verdict with full finding detail.
        """

    # ── Utility helpers available to all implementations ─────────────────────

    @staticmethod
    def extract_message_texts(payload: dict) -> list[str]:
        """
        Extract all human-readable text from an OpenAI-compatible messages array.
        Handles both string content and the content-parts list format.
        """
        texts: list[str] = []
        messages = payload.get("messages", [])
        for msg in messages:
            content = msg.get("content", "")
            if isinstance(content, str):
                texts.append(content)
            elif isinstance(content, list):
                # Content-parts format: [{"type": "text", "text": "..."}]
                for part in content:
                    if isinstance(part, dict) and part.get("type") == "text":
                        texts.append(part.get("text", ""))
        # Also capture any tool call arguments
        for msg in messages:
            for tc in msg.get("tool_calls", []):
                try:
                    args = tc.get("function", {}).get("arguments", "")
                    if isinstance(args, str):
                        texts.append(args)
                except Exception:
                    pass
        return texts

    @staticmethod
    def digest_payload(payload: dict) -> str:
        """Return the SHA-256 hex digest of the canonical JSON payload (for ledger)."""
        canonical = json.dumps(payload, sort_keys=True, ensure_ascii=False)
        return hashlib.sha256(canonical.encode()).hexdigest()
