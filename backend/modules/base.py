"""Base compliance module interface."""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Finding:
    finding_id: str
    module_id: str
    severity: str
    rule_id: str
    rule_name: str
    evidence: str
    recommendation: str
    confidence: float
    description: Optional[str] = None

    def __iter__(self):
        yield from self.__dict__.items()


@dataclass
class ModuleResult:
    module_id: str
    score: int
    findings: list[Finding]
    status: str = "complete"


class BaseComplianceModule(ABC):
    module_id: str
    display_name: str
    frameworks: list[str] = []

    @abstractmethod
    def run(self, context) -> ModuleResult:
        """Execute the compliance test and return structured findings."""

    def _map_to_policy(self, raw_finding: dict, policy_tool) -> dict:
        rule_id = raw_finding.get("rule_id", "")
        rule = policy_tool.get_rule_by_id(rule_id)
        if rule:
            return {**raw_finding, "rule_name": rule.get("name", ""), "description": rule.get("description", "")}
        return raw_finding
