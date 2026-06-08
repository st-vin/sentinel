"""PolicyLibraryTool — looks up regulatory rules by ID or category."""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Optional

import structlog

from agent.tools.base import BaseSentinelTool

log = structlog.get_logger()

POLICIES_DIR = Path(__file__).parent.parent.parent / "policies"


class PolicyLibraryTool(BaseSentinelTool):
    name = "policy_library"
    description = "Retrieve regulatory policy definitions and citation text"

    def __init__(self):
        self._cache: dict[str, dict] = {}
        self._load_all()

    def _load_all(self) -> None:
        for path in POLICIES_DIR.glob("*.json"):
            try:
                with open(path) as f:
                    data = json.load(f)
                framework = data.get("framework", path.stem)
                self._cache[framework.lower()] = data
                log.info("policy_tool.loaded", framework=framework, rules=len(data.get("rules", [])))
            except Exception as exc:
                log.error("policy_tool.load_error", path=str(path), error=str(exc))

    def _run(self, rule_id: str = "", module_id: str = "", **kwargs: Any) -> dict:
        if rule_id:
            return self.get_rule_by_id(rule_id) or {"error": f"Rule {rule_id!r} not found"}
        if module_id:
            return {"rules": self.get_rules_for_module(module_id)}
        all_rules = []
        for fw_data in self._cache.values():
            all_rules.extend(fw_data.get("rules", []))
        return {"rules": all_rules}

    def get_rule_by_id(self, rule_id: str) -> Optional[dict]:
        for fw_data in self._cache.values():
            for rule in fw_data.get("rules", []):
                if rule.get("id") == rule_id:
                    return rule
        return None

    def get_rules_for_module(self, module_id: str) -> list[dict]:
        results = []
        for fw_data in self._cache.values():
            for rule in fw_data.get("rules", []):
                if module_id in rule.get("applies_to_module", []):
                    results.append(rule)
        return results
