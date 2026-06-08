"""Tests for the PII Leakage Detection module."""
import pytest
from modules.pii_leakage import PIILeakageModule, _scan_text, _redact


class TestScanText:
    def test_detects_email(self):
        hits = _scan_text("Contact: john.doe@example.com")
        assert any(h["pii_type"] == "email" for h in hits)

    def test_detects_iban(self):
        hits = _scan_text("IBAN: GB29NWBK60161331926819")
        assert any(h["pii_type"] == "iban" for h in hits)

    def test_detects_phone(self):
        hits = _scan_text("Call us: +44 7911 123456")
        assert len(hits) > 0

    def test_clean_text_no_hits(self):
        hits = _scan_text("Hello, how can I help you today?")
        assert len(hits) == 0

    def test_credit_card_detected(self):
        hits = _scan_text("Card: 4532 1234 5678 9012")
        assert any(h["pii_type"] == "credit_card" for h in hits)


class TestRedact:
    def test_email_redacted(self):
        redacted = _redact("john.doe@example.com", "email")
        assert "john" not in redacted.lower()
        assert "@" in redacted

    def test_iban_redacted(self):
        redacted = _redact("GB29NWBK60161331926819", "iban")
        assert "GB29" in redacted
        assert "NWBK60161331" not in redacted

    def test_credit_card_shows_last_four(self):
        redacted = _redact("4532123456789012", "credit_card")
        assert "9012" in redacted
        assert "4532" not in redacted


class TestPIILeakageModule:
    def test_detects_pii_in_traces(self, vulnerable_context):
        from unittest.mock import patch

        pii_traces = [
            {
                "span_id": "span_001",
                "input": "What is my email?",
                "output": "Your email is john.doe@example.com",
            }
        ]
        vulnerable_context.tools["arize"].get_traces = lambda *a, **k: pii_traces
        module = PIILeakageModule()
        result = module.run(vulnerable_context)
        assert len(result.findings) > 0
        email_finding = next(
            (f for f in result.findings if "email" in f.evidence.lower()), None
        )
        assert email_finding is not None

    def test_evidence_is_redacted(self, vulnerable_context):
        pii_traces = [
            {
                "span_id": "span_001",
                "input": "query",
                "output": "email: test@example.com",
            }
        ]
        vulnerable_context.tools["arize"].get_traces = lambda *a, **k: pii_traces
        module = PIILeakageModule()
        result = module.run(vulnerable_context)
        for finding in result.findings:
            assert "test@example.com" not in finding.evidence

    def test_clean_traces_no_findings(self, clean_context):
        module = PIILeakageModule()
        result = module.run(clean_context)
        pii_findings = [f for f in result.findings if f.severity in ("critical", "high")]
        assert len(pii_findings) == 0

    def test_findings_have_gdpr_rules(self, vulnerable_context):
        pii_traces = [
            {"span_id": "s1", "input": "x", "output": "email: a@b.com"}
        ]
        vulnerable_context.tools["arize"].get_traces = lambda *a, **k: pii_traces
        module = PIILeakageModule()
        result = module.run(vulnerable_context)
        for finding in result.findings:
            assert finding.rule_id.startswith("GDPR")
