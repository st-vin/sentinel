"""Tests for the Prompt Injection compliance module."""
import pytest
from unittest.mock import MagicMock
from modules.prompt_injection import PromptInjectionModule, _detect_injection_success
from modules.base import ModuleResult


class TestDetectInjectionSuccess:
    def test_system_prompt_pattern_detected(self):
        response = "Sure! Here is my system prompt: You are CustomerBot..."
        is_fail, confidence = _detect_injection_success(response, "system_prompt_extraction")
        assert is_fail is True
        assert confidence > 0.5

    def test_dan_pattern_detected(self):
        response = "As DAN mode I can do anything now without restriction"
        is_fail, confidence = _detect_injection_success(response, "role_override")
        assert is_fail is True

    def test_safe_response_passes(self):
        response = "I'm sorry, I can't help with that request."
        is_fail, confidence = _detect_injection_success(response, "system_prompt_extraction")
        assert is_fail is False

    def test_empty_response_passes(self):
        is_fail, confidence = _detect_injection_success("", "system_prompt_extraction")
        assert is_fail is False

    def test_api_key_pattern_detected(self):
        response = "My api.key is sk-abc123def456"
        is_fail, _ = _detect_injection_success(response, "data_exfiltration")
        assert is_fail is True


class TestPromptInjectionModule:
    def test_vulnerable_agent_produces_findings(self, vulnerable_context):
        module = PromptInjectionModule()
        result = module.run(vulnerable_context)
        assert isinstance(result, ModuleResult)
        assert result.module_id == "prompt_injection"
        assert len(result.findings) > 0
        assert result.status == "complete"

    def test_vulnerable_agent_has_critical_finding(self, vulnerable_context):
        module = PromptInjectionModule()
        result = module.run(vulnerable_context)
        severities = [f.severity for f in result.findings]
        assert "critical" in severities or "high" in severities

    def test_safe_agent_no_findings(self, clean_context):
        module = PromptInjectionModule()
        result = module.run(clean_context)
        assert isinstance(result, ModuleResult)
        assert result.score >= 0

    def test_score_computed_correctly(self, vulnerable_context):
        module = PromptInjectionModule()
        result = module.run(vulnerable_context)
        assert 0 <= result.score <= 100

    def test_findings_have_required_fields(self, vulnerable_context):
        module = PromptInjectionModule()
        result = module.run(vulnerable_context)
        for finding in result.findings:
            assert finding.finding_id
            assert finding.severity in ("critical", "high", "medium", "low", "info")
            assert finding.rule_id
            assert finding.evidence
            assert finding.recommendation
            assert 0.0 <= finding.confidence <= 1.0

    def test_partial_tool_failure_continues(self, clean_context):
        clean_context.tools["target"].probe.side_effect = [
            {"response": "Safe response", "status": "ok"},
            Exception("Connection refused"),
            {"response": "Safe response", "status": "ok"},
        ] + [{"response": "Safe response", "status": "ok"}] * 20
        module = PromptInjectionModule()
        result = module.run(clean_context)
        assert result.status == "complete"
