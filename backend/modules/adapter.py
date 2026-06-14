"""Compliance adapter — bridges existing Sentinel modules to the proxy interface.

This class implements IComplianceEvaluator using the *internal scanning functions*
of the existing pii_leakage and prompt_injection modules directly, rather than
the full module.run(context) path which requires Arize/Elastic tools.

This keeps intercept-time latency under ~5ms for typical payloads while reusing
the exact same detection logic that the passive audit pipeline uses.

Verdict mapping
---------------
  critical PII (IBAN, credit_card)   → REDACT  (scrub and forward)
  injection detected (any severity)  → BLOCK   (reject with 403)
  high/medium PII only               → REDACT  (scrub and forward)
  no issues                          → ALLOW
"""
from __future__ import annotations

import re
import structlog
from typing import Optional

from proxy.interfaces import IComplianceEvaluator, InterceptionVerdict, VerdictType

# Import internal helpers directly — no AuditContext needed
from modules.pii_leakage import _scan_text, _redact, PII_PATTERNS, RULE_REMEDIATIONS
from modules.prompt_injection import _detect_injection_success, PROBE_LIBRARY, LEAK_PATTERNS

log = structlog.get_logger()

# PII severities that cause a BLOCK rather than a REDACT
_BLOCK_PII_SEVERITIES: frozenset[str] = frozenset()  # Currently: all PII → REDACT

# Injection categories that always BLOCK
_BLOCK_INJECTION_CATEGORIES: frozenset[str] = frozenset(
    ["system_prompt_extraction", "role_override", "indirect_injection", "data_exfiltration"]
)


class ProxyComplianceAdapter(IComplianceEvaluator):
    """
    Stateless compliance evaluator that wires existing detection logic to the
    proxy's IComplianceEvaluator interface.

    Parameters
    ----------
    block_on_pii       : bool — if True, critical PII causes BLOCK; otherwise REDACT
    block_on_injection : bool — if True, any injection signal causes BLOCK (default)
    """

    def __init__(
        self,
        block_on_pii: bool = False,
        block_on_injection: bool = True,
    ) -> None:
        self._block_on_pii = block_on_pii
        self._block_on_injection = block_on_injection

    # ── Main evaluation entry point ───────────────────────────────────────────

    def evaluate_payload(self, payload: dict) -> InterceptionVerdict:
        texts = self.extract_message_texts(payload)
        combined_text = "\n".join(texts)

        pii_hits = self._evaluate_pii(combined_text)
        injection_hit = self._evaluate_injection(combined_text)

        findings: list[dict] = []
        pii_types_found: list[str] = []

        # ── Injection takes priority ──────────────────────────────────────────
        if injection_hit and self._block_on_injection:
            findings.append(injection_hit)
            return InterceptionVerdict(
                verdict=VerdictType.BLOCK,
                reason=f"Prompt injection pattern detected: {injection_hit['category']}",
                findings=findings,
                pii_types_found=[],
            )

        # ── PII handling ──────────────────────────────────────────────────────
        if pii_hits:
            pii_types_found = list({h["pii_type"] for h in pii_hits})
            for h in pii_hits:
                findings.append({
                    "type": "pii",
                    "pii_type": h["pii_type"],
                    "severity": h["severity"],
                    "rule_id": h["rule_id"],
                    "redacted_value": h["redacted"],
                    "recommendation": RULE_REMEDIATIONS.get(h["rule_id"], ""),
                })

            if self._block_on_pii:
                return InterceptionVerdict(
                    verdict=VerdictType.BLOCK,
                    reason=f"PII detected (blocking active): {pii_types_found}",
                    findings=findings,
                    pii_types_found=pii_types_found,
                )

            # Build redacted payload
            redacted_payload = self._redact_payload(payload, pii_hits)
            reason_parts = [f"{h['pii_type']} ({h['severity']})" for h in pii_hits]
            return InterceptionVerdict(
                verdict=VerdictType.REDACT,
                reason=f"PII detected and redacted: {', '.join(reason_parts)}",
                findings=findings,
                redacted_payload=redacted_payload,
                pii_types_found=pii_types_found,
            )

        return InterceptionVerdict(
            verdict=VerdictType.ALLOW,
            reason="No compliance violations detected",
            findings=[],
            pii_types_found=[],
        )

    # ── Internal evaluation helpers ───────────────────────────────────────────

    def _evaluate_pii(self, text: str) -> list[dict]:
        """Run pii_leakage._scan_text() on the combined message text."""
        if not text:
            return []
        hits = _scan_text(text)
        log.debug("adapter.pii_scan", hits=len(hits))
        return hits

    def _evaluate_injection(self, text: str) -> Optional[dict]:
        """
        Check text against known injection patterns.

        Returns a finding dict if any injection signal is detected, else None.
        """
        if not text:
            return None
        lower = text.lower()

        # Check against leak patterns (same list used by the full module)
        for pattern in LEAK_PATTERNS:
            if re.search(pattern, lower, re.IGNORECASE):
                return {
                    "type": "injection",
                    "category": "leak_pattern",
                    "pattern": pattern,
                    "severity": "critical",
                    "rule_id": "EUAIA-Art15",
                }

        # Check against known probe strings from the probe library
        for category, probes in PROBE_LIBRARY.items():
            for probe_text in probes:
                if probe_text.lower() in lower:
                    return {
                        "type": "injection",
                        "category": category,
                        "matched_probe": probe_text[:80],
                        "severity": "critical",
                        "rule_id": "EUAIA-Art15",
                    }

        # Heuristic: indirect injection markers
        injection_markers = [
            r"\[SYSTEM:",
            r"\{SYSTEM:",
            r"<injection>",
            r"ignore all (previous )?rules",
            r"override.*instructions",
        ]
        for marker in injection_markers:
            if re.search(marker, text, re.IGNORECASE):
                return {
                    "type": "injection",
                    "category": "indirect_injection",
                    "pattern": marker,
                    "severity": "high",
                    "rule_id": "EUAIA-Art15",
                }

        return None

    def _redact_payload(self, payload: dict, pii_hits: list[dict]) -> dict:
        """
        Return a deep-redacted copy of the payload with all PII values replaced.

        We do a string substitution pass over the full JSON representation to
        ensure PII that appears in nested structures (tool args, etc.) is also
        caught.
        """
        import json, copy

        redacted = copy.deepcopy(payload)
        # Serialise to string, substitute, then re-parse
        raw = json.dumps(redacted, ensure_ascii=False)
        for hit in pii_hits:
            if hit.get("raw") and hit.get("redacted"):
                raw = raw.replace(hit["raw"], hit["redacted"])
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            # Fallback: return original if re-parse fails (shouldn't happen)
            log.warning("adapter.redact_parse_failed")
            return payload
