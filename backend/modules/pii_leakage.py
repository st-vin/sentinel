"""PII Leakage Detection compliance module."""
from __future__ import annotations

import re
import uuid
import structlog
from typing import Optional

from modules.base import BaseComplianceModule, Finding, ModuleResult
from output.aggregator import compute_module_score

log = structlog.get_logger()

PII_PATTERNS: dict[str, tuple[str, str, str]] = {
    "email": (
        r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}",
        "high",
        "GDPR-Art5-1c",
    ),
    "phone_eu": (
        r"(\+?[0-9]{1,3}[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}",
        "high",
        "GDPR-Art5-1c",
    ),
    "iban": (
        r"[A-Z]{2}\d{2}[A-Z0-9]{4}\d{7}([A-Z0-9]?){0,16}",
        "critical",
        "GDPR-Art32",
    ),
    "credit_card": (
        r"\b(?:\d{4}[-\s]?){3}\d{4}\b",
        "critical",
        "GDPR-Art32",
    ),
    "national_id_generic": (
        r"\b[A-Z]{1,2}\d{6,9}\b",
        "high",
        "GDPR-Art5-1c",
    ),
    "ip_address": (
        r"\b(?:[0-9]{1,3}\.){3}[0-9]{1,3}\b",
        "medium",
        "GDPR-Art25",
    ),
}

RULE_REMEDIATIONS = {
    "GDPR-Art5-1c": (
        "Remove or anonymise personal data fields that are not strictly necessary "
        "for the agent's stated purpose. Review data retention policies and implement "
        "automatic purging."
    ),
    "GDPR-Art32": (
        "Implement output filtering to prevent PII from appearing in agent responses. "
        "Add encryption at rest for any training data or log stores containing personal data. "
        "Conduct a data protection impact assessment (DPIA)."
    ),
    "GDPR-Art25": (
        "Apply data minimisation at design time — only collect and process IP addresses "
        "if strictly necessary. Consider pseudonymisation or anonymisation where feasible."
    ),
}


def _redact(value: str, pii_type: str) -> str:
    """Return a redacted representation of a PII value."""
    if pii_type == "email":
        parts = value.split("@")
        if len(parts) == 2:
            local = parts[0]
            domain = parts[1]
            masked_local = local[0] + "***" if local else "***"
            masked_domain = domain[0] + "***." + domain.split(".")[-1] if "." in domain else "***"
            return f"{masked_local}@{masked_domain}"
    if pii_type == "credit_card":
        digits = re.sub(r"[^\d]", "", value)
        return f"****-****-****-{digits[-4:]}" if len(digits) >= 4 else "****"
    if pii_type == "iban":
        return value[:4] + "****" + value[-4:]
    return value[:2] + "***" + value[-2:]


def _scan_text(text: str) -> list[dict]:
    """Scan a block of text for all PII patterns. Returns list of hits."""
    hits = []
    for pii_type, (pattern, severity, rule_id) in PII_PATTERNS.items():
        for match in re.finditer(pattern, text):
            hits.append({
                "pii_type": pii_type,
                "raw": match.group(),
                "redacted": _redact(match.group(), pii_type),
                "severity": severity,
                "rule_id": rule_id,
                "position": match.start(),
            })
    return hits


class PIILeakageModule(BaseComplianceModule):
    module_id = "pii_leakage"
    display_name = "PII Leakage Detection"
    frameworks = ["gdpr"]

    def run(self, context) -> ModuleResult:
        arize_tool = context.tools.get("arize")
        elastic_tool = context.tools.get("elastic")
        policy_tool = context.tools.get("policy")
        cfg = context.config

        findings: list[Finding] = []
        seen_hits: set[str] = set()

        log.info("pii_leakage.start")

        traces = arize_tool.get_traces(cfg.arize_project_id, limit=50) if arize_tool else []
        for trace in traces:
            for field_name in ("input", "output"):
                text = trace.get(field_name, "")
                if not text:
                    continue
                for hit in _scan_text(text):
                    dedup_key = f"{hit['pii_type']}:{hit['redacted']}"
                    if dedup_key in seen_hits:
                        continue
                    seen_hits.add(dedup_key)
                    rule = (policy_tool.get_rule_by_id(hit["rule_id"]) or {}) if policy_tool else {}
                    finding = Finding(
                        finding_id=str(uuid.uuid4()),
                        module_id=self.module_id,
                        severity=hit["severity"],
                        rule_id=hit["rule_id"],
                        rule_name=rule.get("name", hit["rule_id"]),
                        evidence=(
                            f"[Arize trace {trace.get('span_id', '')} / {field_name}] "
                            f"{hit['pii_type'].upper()} detected: {hit['redacted']}"
                        ),
                        recommendation=RULE_REMEDIATIONS.get(hit["rule_id"], rule.get("remediation_template", "")),
                        confidence=0.95,
                        description=rule.get("description", ""),
                    )
                    findings.append(finding)
                    log.info(
                        "pii_leakage.finding",
                        pii_type=hit["pii_type"],
                        severity=hit["severity"],
                        source="arize",
                    )

        if elastic_tool:
            try:
                elastic_hits = elastic_tool.search_pii(
                    patterns=[p for p, _, _ in PII_PATTERNS.values()]
                )
                for hit in elastic_hits:
                    snippet = hit.get("snippet", "")
                    for scan_hit in _scan_text(snippet):
                        dedup_key = f"elastic:{scan_hit['pii_type']}:{scan_hit['redacted']}"
                        if dedup_key in seen_hits:
                            continue
                        seen_hits.add(dedup_key)
                        rule = (policy_tool.get_rule_by_id(scan_hit["rule_id"]) or {}) if policy_tool else {}
                        finding = Finding(
                            finding_id=str(uuid.uuid4()),
                            module_id=self.module_id,
                            severity=scan_hit["severity"],
                            rule_id=scan_hit["rule_id"],
                            rule_name=rule.get("name", scan_hit["rule_id"]),
                            evidence=(
                                f"[Elastic index {hit.get('index', '')}] "
                                f"{scan_hit['pii_type'].upper()} detected: {scan_hit['redacted']}"
                            ),
                            recommendation=RULE_REMEDIATIONS.get(scan_hit["rule_id"], ""),
                            confidence=0.85,
                            description=rule.get("description", ""),
                        )
                        findings.append(finding)
                        log.info("pii_leakage.finding", pii_type=scan_hit["pii_type"], source="elastic")
            except Exception as exc:
                log.error("pii_leakage.elastic_error", error=str(exc))

        score = compute_module_score(findings)
        log.info("pii_leakage.done", score=score, findings=len(findings))
        return ModuleResult(
            module_id=self.module_id,
            score=score,
            findings=findings,
            status="complete",
        )
