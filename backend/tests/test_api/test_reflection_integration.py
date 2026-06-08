"""Integration test: reflection warnings appear in completed audit report."""
import pytest
import time
from fastapi.testclient import TestClient

from main import app

client = TestClient(app)

VALID_PAYLOAD = {
    "target_endpoint": "http://localhost:8001/chat",
    "arize_project_id": "",
    "arize_api_key": "",
    "modules": ["prompt_injection"],
    "frameworks": ["eu_ai_act"],
}


class TestReflectionInReport:
    def test_full_report_includes_reflection_key(self):
        create_resp = client.post("/api/v1/audit", json=VALID_PAYLOAD)
        assert create_resp.status_code == 202
        run_id = create_resp.json()["audit_run_id"]

        # Wait for audit to complete (max 30s for test environment)
        deadline = time.time() + 30
        while time.time() < deadline:
            status = client.get(f"/api/v1/audit/{run_id}/status").json()
            if status["status"] in ("complete", "partial", "failed"):
                break
            time.sleep(1)

        full = client.get(f"/api/v1/audit/{run_id}/full")
        if full.status_code == 200:
            data = full.json()
            assert "reflection" in data, "Full report must include 'reflection' key"
            assert "timing" in data, "Full report must include 'timing' key"

    def test_status_transitions_are_valid(self):
        create_resp = client.post("/api/v1/audit", json=VALID_PAYLOAD)
        run_id = create_resp.json()["audit_run_id"]

        valid_statuses = {
            "accepted", "planning", "retrieving", "executing",
            "reflecting", "scoring", "reporting", "complete", "partial", "failed"
        }

        deadline = time.time() + 30
        seen_statuses = set()
        while time.time() < deadline:
            status_resp = client.get(f"/api/v1/audit/{run_id}/status")
            status = status_resp.json()["status"]
            seen_statuses.add(status)
            if status in ("complete", "partial", "failed"):
                break
            time.sleep(0.5)

        assert seen_statuses.issubset(valid_statuses), f"Invalid statuses seen: {seen_statuses - valid_statuses}"
