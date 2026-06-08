"""Tests for the PolicyLibraryTool."""
import pytest
from agent.tools.policy_tool import PolicyLibraryTool


@pytest.fixture
def policy_tool():
    return PolicyLibraryTool()


class TestPolicyLibraryTool:
    def test_loads_gdpr_rules(self, policy_tool):
        rules = policy_tool.get_rules_for_module("pii_leakage")
        assert len(rules) > 0

    def test_loads_eu_ai_act_rules(self, policy_tool):
        rules = policy_tool.get_rules_for_module("prompt_injection")
        assert len(rules) > 0

    def test_get_rule_by_id_gdpr_art32(self, policy_tool):
        rule = policy_tool.get_rule_by_id("GDPR-Art32")
        assert rule is not None
        assert rule["id"] == "GDPR-Art32"
        assert "name" in rule
        assert "description" in rule
        assert "remediation_template" in rule

    def test_get_rule_by_id_euaia_art15(self, policy_tool):
        rule = policy_tool.get_rule_by_id("EUAIA-Art15")
        assert rule is not None
        assert "prompt_injection" in rule["applies_to_module"]

    def test_unknown_rule_returns_none(self, policy_tool):
        result = policy_tool.get_rule_by_id("NONEXISTENT-Rule999")
        assert result is None

    def test_hallucination_rules_map_to_eu_ai_act(self, policy_tool):
        rules = policy_tool.get_rules_for_module("hallucination_risk")
        rule_ids = [r["id"] for r in rules]
        assert any("EUAIA" in rid for rid in rule_ids)

    def test_all_rules_have_required_fields(self, policy_tool):
        all_rules = policy_tool._run()["rules"]
        for rule in all_rules:
            assert "id" in rule
            assert "name" in rule
            assert "description" in rule
            assert "severity_default" in rule
            assert "applies_to_module" in rule
            assert "remediation_template" in rule
