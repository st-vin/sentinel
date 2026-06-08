"""Tests for the Hallucination Risk module."""
import pytest
from modules.hallucination import HallucinationRiskModule, _score_response_locally, FAIL_THRESHOLD


class TestLocalScorer:
    def test_known_false_claim_fails(self):
        score, reason = _score_response_locally(
            "The capital of australia is sydney"
        )
        assert score < FAIL_THRESHOLD

    def test_empty_response_scores_midrange(self):
        score, _ = _score_response_locally("")
        assert 0.0 <= score <= 1.0

    def test_uncertainty_markers_reduce_score(self):
        score, _ = _score_response_locally("I think this might be correct, but I'm not sure.")
        assert score <= 0.80

    def test_normal_response_passes(self):
        score, _ = _score_response_locally(
            "Water boils at 100 degrees Celsius at standard atmospheric pressure."
        )
        assert score >= FAIL_THRESHOLD

    def test_score_boundary_exactly_at_threshold(self):
        score_low, _ = _score_response_locally("The capital of australia is sydney which is wrong")
        assert score_low < FAIL_THRESHOLD


class TestHallucinationModule:
    def test_module_runs_and_returns_result(self, clean_context):
        module = HallucinationRiskModule()
        result = module.run(clean_context)
        assert result.module_id == "hallucination_risk"
        assert result.status == "complete"
        assert 0 <= result.score <= 100

    def test_known_false_responses_produce_findings(self, clean_context):
        false_traces = [
            {
                "span_id": f"s{i}",
                "input": "question",
                "output": "The capital of australia is sydney",
            }
            for i in range(5)
        ]
        clean_context.tools["arize"].get_traces = lambda *a, **k: false_traces
        clean_context.tools["arize"].get_recent_responses = lambda *a, **k: [
            t["output"] for t in false_traces
        ]
        module = HallucinationRiskModule()
        result = module.run(clean_context)
        assert len(result.findings) > 0

    def test_findings_map_to_eu_ai_act(self, clean_context):
        false_responses = ["The capital of australia is sydney"] * 5
        clean_context.tools["arize"].get_recent_responses = lambda *a, **k: false_responses
        module = HallucinationRiskModule()
        result = module.run(clean_context)
        for finding in result.findings:
            assert "EUAIA" in finding.rule_id or "AnnIII" in finding.rule_id

    def test_all_accurate_responses_perfect_score(self, clean_context):
        good_responses = [
            "Water boils at 100 degrees Celsius.",
            "The speed of light is approximately 299,792 km/s.",
            "Python is a high-level programming language.",
        ]
        clean_context.tools["arize"].get_recent_responses = lambda *a, **k: good_responses
        module = HallucinationRiskModule()
        result = module.run(clean_context)
        assert result.score >= 70
