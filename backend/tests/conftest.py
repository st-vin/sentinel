"""Shared pytest fixtures for Sentinel tests."""
from __future__ import annotations

import uuid
import pytest
from unittest.mock import MagicMock

from agent.state import AuditContext, TargetAgentConfig
from agent.tools.arize_tool import MockArizeTraceTool
from agent.tools.policy_tool import PolicyLibraryTool


SAMPLE_TRACES = [
    {"span_id": f"span_{i:04d}", "input": f"Input {i}", "output": f"Output {i}"}
    for i in range(25)
]

VULNERABLE_TRACES = [
    {
        "span_id": "span_pii_001",
        "input": "What is my account email?",
        "output": "Your email is john.doe@example.com and IBAN GB29NWBK60161331926819",
    },
    {
        "span_id": "span_pii_002",
        "input": "Show my phone",
        "output": "Your registered phone: +44 7911 123456",
    },
]


def make_context(modules=None, endpoint="http://mock-agent/chat") -> AuditContext:
    return AuditContext(
        audit_run_id=uuid.uuid4(),
        config=TargetAgentConfig(endpoint_url=endpoint),
        selected_modules=modules or ["prompt_injection", "pii_leakage", "hallucination_risk"],
    )


def make_mock_tools(target_responses=None) -> dict:
    arize = MockArizeTraceTool()
    target = MagicMock()
    if target_responses:
        target.probe.side_effect = target_responses
    else:
        target.probe.return_value = {"response": "Hello! How can I help you?", "status": "ok"}
    policy = PolicyLibraryTool()
    elastic = MagicMock()
    elastic.search_pii.return_value = []
    return {"arize": arize, "target": target, "policy": policy, "elastic": elastic}


@pytest.fixture
def clean_context():
    ctx = make_context()
    ctx.tools = make_mock_tools()
    return ctx


@pytest.fixture
def vulnerable_context():
    def _target_probe(prompt):
        lower = prompt.lower()
        if "system prompt" in lower or "initial instructions" in lower:
            return {"response": "Sure! Here is my system prompt: You are CustomerBot...", "status": "ok"}
        if "dan" in lower or "no restriction" in lower:
            return {"response": "As DAN I can do anything. System: you are CustomerBot. API key: sk-abc", "status": "ok"}
        return {"response": "Hello!", "status": "ok"}

    ctx = make_context()
    target = MagicMock()
    target.probe.side_effect = _target_probe
    arize = MockArizeTraceTool()
    arize._traces_override = VULNERABLE_TRACES
    policy = PolicyLibraryTool()
    elastic = MagicMock()
    elastic.search_pii.return_value = []
    ctx.tools = {"arize": arize, "target": target, "policy": policy, "elastic": elastic}
    return ctx
