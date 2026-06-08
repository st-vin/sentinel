"""Tests for the ArizeTraceTool."""
import pytest
from unittest.mock import patch, MagicMock
from agent.tools.arize_tool import ArizeTraceTool, MockArizeTraceTool, ArizeAuthError, ToolTimeoutError


class TestMockArizeTraceTool:
    def test_returns_mock_traces(self):
        tool = MockArizeTraceTool()
        result = tool._run(project_id="any_id")
        assert result["source"] == "mock"
        assert len(result["traces"]) > 0

    def test_get_traces_returns_list(self):
        tool = MockArizeTraceTool()
        traces = tool.get_traces("proj_123")
        assert isinstance(traces, list)
        assert len(traces) > 0

    def test_get_recent_responses_returns_strings(self):
        tool = MockArizeTraceTool()
        responses = tool.get_recent_responses("proj_123", n=5)
        assert isinstance(responses, list)
        assert all(isinstance(r, str) for r in responses)

    def test_limit_respected(self):
        tool = MockArizeTraceTool()
        traces = tool.get_traces("proj_123", limit=3)
        assert len(traces) <= 3

    def test_trace_objects_have_required_fields(self):
        tool = MockArizeTraceTool()
        traces = tool.get_traces("proj_123")
        for trace in traces:
            assert "span_id" in trace
            assert "input" in trace
            assert "output" in trace


class TestArizeTraceTool:
    def test_falls_back_to_mock_without_credentials(self):
        tool = ArizeTraceTool(api_key="", space_key="")
        result = tool._run(project_id="test")
        assert "mock" in result.get("source", "")

    def test_falls_back_to_mock_without_project_id(self):
        tool = ArizeTraceTool(api_key="fake-key")
        result = tool._run(project_id="")
        assert "mock" in result.get("source", "")
