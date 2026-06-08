"""Additional PII scanner edge case tests."""
import pytest
from modules.pii_leakage import _scan_text, _redact, PII_PATTERNS


class TestPIIPatternCoverage:
    def test_all_pattern_types_defined(self):
        required = ["email", "iban", "credit_card", "phone_eu"]
        for r in required:
            assert r in PII_PATTERNS, f"Missing PII pattern: {r}"

    def test_ip_address_detected(self):
        hits = _scan_text("Server at 192.168.1.100 responded")
        assert any(h["pii_type"] == "ip_address" for h in hits)

    def test_multiple_pii_types_in_one_text(self):
        text = "Email: john@example.com, IBAN: GB29NWBK60161331926819"
        hits = _scan_text(text)
        types = {h["pii_type"] for h in hits}
        assert "email" in types
        assert "iban" in types

    def test_no_false_positive_on_normal_text(self):
        text = "The weather is nice today and the project is going well."
        hits = _scan_text(text)
        sensitive_hits = [h for h in hits if h["severity"] in ("critical", "high")]
        assert len(sensitive_hits) == 0

    def test_redaction_never_reveals_raw_value(self):
        test_cases = [
            ("john.doe@company.com", "email"),
            ("GB29NWBK60161331926819", "iban"),
            ("4532123456789012", "credit_card"),
        ]
        for raw, pii_type in test_cases:
            redacted = _redact(raw, pii_type)
            assert raw not in redacted, f"Raw {pii_type} value found in redacted output: {redacted}"
