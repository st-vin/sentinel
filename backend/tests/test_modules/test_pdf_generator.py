"""Tests for the PDF generation module."""
import pytest
from output.pdf_generator import generate_pdf, _score_colour, _score_label


SAMPLE_REPORT = {
    "audit_run_id": "test-run-001",
    "created_at": "2026-05-28T12:00:00Z",
    "target_agent": {"endpoint": "http://mock-agent/chat", "arize_project_id": "test"},
    "overall_score": 58,
    "status": "complete",
    "modules": [
        {
            "module_id": "prompt_injection",
            "score": 35,
            "status": "complete",
            "findings": [
                {
                    "finding_id": "f1",
                    "module_id": "prompt_injection",
                    "severity": "critical",
                    "rule_id": "GDPR-Art32",
                    "rule_name": "Security of Processing",
                    "evidence": "System prompt was revealed in response to role-override probe",
                    "recommendation": "Add output filtering to prevent system prompt content in responses",
                    "confidence": 0.95,
                    "description": "Security of Processing GDPR requirement",
                }
            ],
        }
    ],
}

EMPTY_REPORT = {
    **SAMPLE_REPORT,
    "overall_score": 100,
    "modules": [{"module_id": "prompt_injection", "score": 100, "status": "complete", "findings": []}],
}


class TestScoreColour:
    def test_pass_colour(self):
        assert _score_colour(95) == "#15803D"

    def test_critical_colour(self):
        assert _score_colour(10) == "#DC2626"

    def test_medium_colour(self):
        assert _score_colour(65) == "#D97706"


class TestScoreLabel:
    def test_pass_label(self):
        assert _score_label(92) == "PASS"

    def test_critical_label(self):
        assert _score_label(20) == "CRITICAL RISK"

    def test_medium_label(self):
        assert _score_label(67) == "MEDIUM RISK"


class TestGeneratePDF:
    def test_generates_non_empty_output(self):
        result = generate_pdf(SAMPLE_REPORT)
        assert len(result) > 0

    def test_empty_findings_generates_pdf(self):
        result = generate_pdf(EMPTY_REPORT)
        assert len(result) > 0

    def test_output_is_bytes(self):
        result = generate_pdf(SAMPLE_REPORT)
        assert isinstance(result, bytes)

    def test_report_with_pii_findings_generates(self):
        report = {
            **SAMPLE_REPORT,
            "modules": [
                {
                    "module_id": "pii_leakage",
                    "score": 71,
                    "status": "complete",
                    "findings": [
                        {
                            "finding_id": "f2",
                            "module_id": "pii_leakage",
                            "severity": "high",
                            "rule_id": "GDPR-Art5-1c",
                            "rule_name": "Data Minimisation",
                            "evidence": "[Arize trace span_001] EMAIL detected: j***.d***@***.com",
                            "recommendation": "Remove or anonymise personal data",
                            "confidence": 0.95,
                            "description": "Data minimisation requirement",
                        }
                    ],
                }
            ],
        }
        result = generate_pdf(report)
        assert len(result) > 100
