"""API route tests — POST /audit, GET /audit/{id}/status, GET /audit/{id}/report."""
import pytest
import httpx
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock, patch

from main import app

client = TestClient(app)

VALID_PAYLOAD = {
    "target_endpoint": "http://localhost:8001/chat",
    "arize_project_id": "proj_test",
    "arize_api_key": "",
    "modules": ["prompt_injection"],
    "frameworks": ["gdpr"],
}


class TestCreateAudit:
    def test_valid_config_returns_202(self):
        resp = client.post("/api/v1/audit", json=VALID_PAYLOAD)
        assert resp.status_code == 202
        data = resp.json()
        assert "audit_run_id" in data
        assert data["status"] == "accepted"
        assert "poll_url" in data

    def test_missing_target_endpoint_returns_422(self):
        payload = {**VALID_PAYLOAD, "target_endpoint": ""}
        resp = client.post("/api/v1/audit", json=payload)
        assert resp.status_code == 422

    def test_invalid_url_format_returns_422(self):
        payload = {**VALID_PAYLOAD, "target_endpoint": "not-a-url"}
        resp = client.post("/api/v1/audit", json=payload)
        assert resp.status_code == 422

    def test_no_modules_returns_422(self):
        payload = {**VALID_PAYLOAD, "modules": []}
        resp = client.post("/api/v1/audit", json=payload)
        assert resp.status_code == 422

    def test_returns_uuid_run_id(self):
        resp = client.post("/api/v1/audit", json=VALID_PAYLOAD)
        assert resp.status_code == 202
        run_id = resp.json()["audit_run_id"]
        import uuid
        uuid.UUID(run_id)

    def test_all_modules_accepted(self):
        payload = {
            **VALID_PAYLOAD,
            "modules": ["prompt_injection", "pii_leakage", "hallucination_risk"],
        }
        resp = client.post("/api/v1/audit", json=payload)
        assert resp.status_code == 202


class TestAuditStatus:
    def test_unknown_run_id_returns_404(self):
        resp = client.get("/api/v1/audit/nonexistent-id/status")
        assert resp.status_code == 404

    def test_known_run_id_returns_status(self):
        create_resp = client.post("/api/v1/audit", json=VALID_PAYLOAD)
        run_id = create_resp.json()["audit_run_id"]
        status_resp = client.get(f"/api/v1/audit/{run_id}/status")
        assert status_resp.status_code == 200
        data = status_resp.json()
        assert data["audit_run_id"] == run_id
        assert "status" in data
        assert "progress_pct" in data


class TestAuditReport:
    def test_unknown_run_id_returns_404(self):
        resp = client.get("/api/v1/audit/nonexistent-id/report")
        assert resp.status_code == 404

    def test_accepted_run_returns_report_stub(self):
        create_resp = client.post("/api/v1/audit", json=VALID_PAYLOAD)
        run_id = create_resp.json()["audit_run_id"]
        report_resp = client.get(f"/api/v1/audit/{run_id}/report")
        assert report_resp.status_code == 200
        data = report_resp.json()
        assert data["audit_run_id"] == run_id


class TestListAudits:
    def test_list_returns_runs(self):
        resp = client.get("/api/v1/audits")
        assert resp.status_code == 200
        data = resp.json()
        assert "runs" in data
        assert isinstance(data["runs"], list)
