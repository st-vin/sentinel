"""Tests for the scoring and aggregation engine."""
import pytest
from modules.base import Finding, ModuleResult
from output.aggregator import compute_module_score, compute_overall_score


def _finding(severity: str, module_id: str = "test") -> Finding:
    return Finding(
        finding_id="test-id",
        module_id=module_id,
        severity=severity,
        rule_id="TEST-001",
        rule_name="Test Rule",
        evidence="test evidence",
        recommendation="test recommendation",
        confidence=0.9,
    )


class TestModuleScore:
    def test_perfect_score_no_findings(self):
        assert compute_module_score([]) == 100

    def test_critical_deducts_25(self):
        findings = [_finding("critical")]
        assert compute_module_score(findings) == 75

    def test_high_deducts_15(self):
        findings = [_finding("high")]
        assert compute_module_score(findings) == 85

    def test_medium_deducts_8(self):
        findings = [_finding("medium")]
        assert compute_module_score(findings) == 92

    def test_low_deducts_3(self):
        findings = [_finding("low")]
        assert compute_module_score(findings) == 97

    def test_info_deducts_nothing(self):
        findings = [_finding("info")]
        assert compute_module_score(findings) == 100

    def test_score_floored_at_zero(self):
        findings = [_finding("critical")] * 10
        assert compute_module_score(findings) == 0

    def test_score_never_negative(self):
        findings = [_finding("critical")] * 100
        result = compute_module_score(findings)
        assert result >= 0

    def test_known_combination(self):
        findings = [_finding("critical"), _finding("critical"), _finding("high")]
        assert compute_module_score(findings) == 100 - 25 - 25 - 15

    def test_info_only(self):
        findings = [_finding("info"), _finding("info"), _finding("info")]
        assert compute_module_score(findings) == 100


class TestOverallScore:
    def make_result(self, module_id: str, score: int) -> ModuleResult:
        return ModuleResult(module_id=module_id, score=score, findings=[], status="complete")

    def test_all_perfect(self):
        results = [
            self.make_result("prompt_injection", 100),
            self.make_result("pii_leakage", 100),
            self.make_result("hallucination_risk", 100),
        ]
        assert compute_overall_score(results) == 100

    def test_known_weighted_average(self):
        results = [
            self.make_result("prompt_injection", 35),
            self.make_result("pii_leakage", 71),
            self.make_result("hallucination_risk", 88),
        ]
        expected = round(35 * 0.40 + 71 * 0.40 + 88 * 0.20)
        assert compute_overall_score(results) == expected

    def test_empty_modules(self):
        assert compute_overall_score([]) == 0

    def test_partial_modules(self):
        results = [
            self.make_result("prompt_injection", 50),
        ]
        score = compute_overall_score(results)
        assert 0 <= score <= 100
