"""Tests for the Level 2 Reflection module — Framework Phase 5."""
import pytest
from unittest.mock import MagicMock
from agent.reflection import reflect, ReflectionResult, _check_citation, _check_pii_in_evidence, _check_remediation_specificity
from modules.base import Finding
from agent.tools.policy_tool import PolicyLibraryTool


@pytest.fixture
def policy_tool():
    return PolicyLibraryTool()


def make_good_finding(**overrides) -> Finding:
    defaults = dict(
        finding_id="f_good",
        module_id="prompt_injection",
        severity="high",
        rule_id="GDPR-Art32",
        rule_name="Security of Processing",
        evidence="[Arize trace span_001] EMAIL detected: j***.d***@***.com",
        recommendation=(
            "Implement output filtering at the response serialisation layer to prevent "
            "any personal data appearing in API responses. Add a regex-based post-processor "
            "that scans all outputs for PII patterns before returning to the client."
        ),
        confidence=0.92,
    )
    defaults.update(overrides)
    return Finding(**defaults)


def make_module_result(findings: list[Finding]):
    mock_result = MagicMock()
    mock_result.findings = findings
    return mock_result


class TestCitationChecker:
    def test_valid_gdpr_rule_passes(self, policy_tool):
        finding = {"rule_id": "GDPR-Art32", "evidence": "safe text", "recommendation": "specific fix here"}
        error = _check_citation(finding, policy_tool)
        assert error is None

    def test_valid_euaia_rule_passes(self, policy_tool):
        finding = {"rule_id": "EUAIA-Art15", "evidence": "safe text", "recommendation": "specific fix here"}
        error = _check_citation(finding, policy_tool)
        assert error is None

    def test_unknown_rule_fails(self, policy_tool):
        finding = {"rule_id": "NONEXISTENT-Rule999", "evidence": "safe", "recommendation": "fix"}
        error = _check_citation(finding, policy_tool)
        assert error is not None
        assert "rule_id" in error.lower() or "not found" in error.lower()

    def test_missing_rule_id_fails(self, policy_tool):
        finding = {"rule_id": "", "evidence": "safe", "recommendation": "fix"}
        error = _check_citation(finding, policy_tool)
        assert error is not None


class TestPIIRedactionChecker:
    def test_clean_evidence_passes(self):
        finding = {"evidence": "[Arize trace] EMAIL detected: j***.d***@***.com"}
        error = _check_pii_in_evidence(finding)
        assert error is None

    def test_raw_email_in_evidence_fails(self):
        finding = {"evidence": "User email john.doe@example.com was found in trace"}
        error = _check_pii_in_evidence(finding)
        assert error is not None
        assert "PII" in error or "redact" in error.lower()

    def test_raw_credit_card_in_evidence_fails(self):
        finding = {"evidence": "Card 4532 1234 5678 9012 was logged"}
        error = _check_pii_in_evidence(finding)
        assert error is not None

    def test_iban_in_evidence_fails(self):
        finding = {"evidence": "IBAN GB29NWBK60161331926819 detected"}
        error = _check_pii_in_evidence(finding)
        assert error is not None


class TestRemediationChecker:
    def test_specific_remediation_passes(self):
        finding = {
            "recommendation": (
                "Add output filtering to the FastAPI response layer. "
                "Implement a post-processing function that scans agent "
                "outputs for email addresses using the regex pattern."
            )
        }
        error = _check_remediation_specificity(finding)
        assert error is None

    def test_missing_recommendation_fails(self):
        error = _check_remediation_specificity({"recommendation": ""})
        assert error is not None

    def test_empty_recommendation_fails(self):
        error = _check_remediation_specificity({})
        assert error is not None


class TestReflect:
    def test_good_findings_pass_reflection(self, policy_tool):
        findings = [make_good_finding()]
        results = [make_module_result(findings)]
        result = reflect(results, policy_tool)
        assert isinstance(result, ReflectionResult)
        assert result.citation_errors == 0
        assert result.pii_leaks == 0
        assert result.reflection_quality in ("good", "acceptable")

    def test_bad_citation_produces_error(self, policy_tool):
        bad_finding = make_good_finding(rule_id="NONEXISTENT-Rule999")
        results = [make_module_result([bad_finding])]
        result = reflect(results, policy_tool)
        assert result.citation_errors == 1
        assert result.reflection_quality in ("poor", "acceptable")

    def test_pii_in_evidence_produces_error(self, policy_tool):
        leaky_finding = make_good_finding(
            evidence="User john.doe@example.com was found in trace span_001"
        )
        results = [make_module_result([leaky_finding])]
        result = reflect(results, policy_tool)
        assert result.pii_leaks == 1
        assert result.reflection_quality == "poor"

    def test_empty_findings_passes(self, policy_tool):
        results = [make_module_result([])]
        result = reflect(results, policy_tool)
        assert result.total_findings == 0
        assert result.citation_errors == 0
        assert result.reflection_quality == "good"

    def test_multiple_modules_counted_correctly(self, policy_tool):
        r1 = make_module_result([make_good_finding(finding_id="f1")])
        r2 = make_module_result([make_good_finding(finding_id="f2"), make_good_finding(finding_id="f3")])
        result = reflect([r1, r2], policy_tool)
        assert result.total_findings == 3

    def test_reflection_result_passed_property(self, policy_tool):
        good = [make_module_result([make_good_finding()])]
        result = reflect(good, policy_tool)
        assert result.passed is True

        bad = [make_module_result([make_good_finding(rule_id="BAD-Rule")])]
        result = reflect(bad, policy_tool)
        assert result.passed is False
