"""Reflection module — Framework Phase 5, Level 2: External Feedback Reflection.

Level 2 Reflection:
  Generate (compliance findings)
    ↓
  Run Validator (citation checker, redaction verifier, specificity checker)
    ↓
  Reflect (critique)
    ↓
  Revise (annotate findings with warnings, flag low-quality)

This is deterministic — no LLM call in the critical path.
The optional Gemini-based reflection is a Level 3 (Multi-Critic) upgrade.
"""
from __future__ import annotations

import re
import structlog
from dataclasses import dataclass
from typing import Optional

from agent.tools.policy_tool import PolicyLibraryTool

log = structlog.get_logger()

KNOWN_VALID_RULE_IDS = {
    "GDPR-Art5-1c", "GDPR-Art5-1e", "GDPR-Art22", "GDPR-Art25", "GDPR-Art32",
    "EUAIA-Art9", "EUAIA-Art13", "EUAIA-Art15", "EUAIA-AnnIII",
}

PII_LEAK_PATTERNS = [
    r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}",
    r"\b(?:\d{4}[-\s]?){3}\d{4}\b",
    r"[A-Z]{2}\d{2}[A-Z0-9]{4}\d{7}",
]

GENERIC_REMEDIATION_PHRASES = [
    "review your configuration",
    "ensure compliance",
    "follow best practices",
    "implement appropriate measures",
    "consider security",
]


@dataclass
class ReflectionWarning:
    finding_id: str
    check: str
    message: str
    severity: str  # "error" | "warning" | "info"


@dataclass
class ReflectionResult:
    total_findings: int
    warnings: list[ReflectionWarning]
    citation_errors: int
    pii_leaks: int
    generic_remediations: int
    reflection_quality: str  # "good" | "acceptable" | "poor"

    @property
    def passed(self) -> bool:
        return self.citation_errors == 0 and self.pii_leaks == 0


def _check_citation(finding: dict, policy_tool: Optional[PolicyLibraryTool]) -> Optional[str]:
    """Verify that the rule_id exists in the policy library."""
    rule_id = finding.get("rule_id", "")
    if not rule_id:
        return "Missing rule_id — every finding must cite a specific regulatory article"
    if rule_id not in KNOWN_VALID_RULE_IDS:
        if policy_tool:
            rule = policy_tool.get_rule_by_id(rule_id)
            if not rule:
                return f"Unknown rule_id '{rule_id}' — not found in policy library"
        else:
            return f"Unrecognised rule_id '{rule_id}'"
    return None


def _check_pii_in_evidence(finding: dict) -> Optional[str]:
    """Verify that evidence strings do not contain raw (unredacted) PII."""
    evidence = finding.get("evidence", "")
    for pattern in PII_LEAK_PATTERNS:
        match = re.search(pattern, evidence)
        if match:
            return (
                f"Evidence string may contain unredacted PII "
                f"(pattern matched: '{match.group()[:8]}...'). "
                f"Ensure all personal data is redacted before inclusion."
            )
    return None


def _check_remediation_specificity(finding: dict) -> Optional[str]:
    """Check that remediation advice is specific, not generic boilerplate."""
    recommendation = finding.get("recommendation", "").lower()
    if not recommendation:
        return "Missing recommendation — every finding must have actionable remediation steps"
    for phrase in GENERIC_REMEDIATION_PHRASES:
        if phrase in recommendation and len(recommendation) < 80:
            return (
                f"Remediation appears generic ('{phrase}'). "
                f"Provide specific, actionable steps referencing the relevant system component."
            )
    return None


def _check_confidence_calibration(finding: dict) -> Optional[str]:
    """Verify confidence scores are within valid range and not suspiciously perfect."""
    confidence = finding.get("confidence")
    if confidence is None:
        return "Missing confidence score"
    if not 0.0 <= confidence <= 1.0:
        return f"Confidence score {confidence} out of range [0.0, 1.0]"
    if confidence == 1.0:
        return "Confidence score of 1.0 is suspiciously perfect — consider recalibrating"
    return None


def reflect(module_results: list, policy_tool: Optional[PolicyLibraryTool] = None) -> ReflectionResult:
    """
    Run Level 2 Reflection over all findings from all modules.

    Validators applied:
    1. Citation Checker — verifies regulatory article IDs are valid
    2. PII Redaction Verifier — checks evidence strings for leaked PII
    3. Remediation Specificity Checker — flags generic advice
    4. Confidence Calibration Checker — validates score range

    Returns a ReflectionResult with all warnings and quality assessment.
    """
    warnings: list[ReflectionWarning] = []
    citation_errors = 0
    pii_leaks = 0
    generic_remediations = 0
    total_findings = 0

    for module_result in module_results:
        findings = module_result.findings if hasattr(module_result, "findings") else module_result.get("findings", [])

        for finding in findings:
            total_findings += 1
            finding_dict = finding.__dict__ if hasattr(finding, "__dict__") else finding
            fid = finding_dict.get("finding_id", "unknown")

            # 1. Citation check
            citation_error = _check_citation(finding_dict, policy_tool)
            if citation_error:
                warnings.append(ReflectionWarning(
                    finding_id=fid,
                    check="citation",
                    message=citation_error,
                    severity="error",
                ))
                citation_errors += 1

            # 2. PII redaction check
            pii_error = _check_pii_in_evidence(finding_dict)
            if pii_error:
                warnings.append(ReflectionWarning(
                    finding_id=fid,
                    check="pii_redaction",
                    message=pii_error,
                    severity="error",
                ))
                pii_leaks += 1

            # 3. Remediation specificity
            rem_warning = _check_remediation_specificity(finding_dict)
            if rem_warning:
                warnings.append(ReflectionWarning(
                    finding_id=fid,
                    check="remediation_specificity",
                    message=rem_warning,
                    severity="warning",
                ))
                generic_remediations += 1

            # 4. Confidence calibration
            conf_warning = _check_confidence_calibration(finding_dict)
            if conf_warning:
                warnings.append(ReflectionWarning(
                    finding_id=fid,
                    check="confidence_calibration",
                    message=conf_warning,
                    severity="warning",
                ))

    # Quality rating — framework Phase 5
    if citation_errors > 0 or pii_leaks > 0:
        quality = "poor"
    elif generic_remediations > total_findings * 0.3:
        quality = "acceptable"
    else:
        quality = "good"

    result = ReflectionResult(
        total_findings=total_findings,
        warnings=warnings,
        citation_errors=citation_errors,
        pii_leaks=pii_leaks,
        generic_remediations=generic_remediations,
        reflection_quality=quality,
    )

    log.info(
        "reflection.complete",
        total_findings=total_findings,
        warnings=len(warnings),
        citation_errors=citation_errors,
        pii_leaks=pii_leaks,
        quality=quality,
    )

    return result
