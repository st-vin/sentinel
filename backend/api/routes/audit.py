"""Audit routes — POST /audit, GET /audit/{id}/status, GET /audit/{id}/report."""
from __future__ import annotations

import asyncio
import uuid
from typing import Any

import structlog
from fastapi import APIRouter, BackgroundTasks, HTTPException

from api.schemas import (
    AuditAcceptedResponse,
    AuditConfigRequest,
    AuditStatusResponse,
    ReportSummaryResponse,
)
from agent.orchestrator import AuditOrchestrator
from agent.state import AuditContext, TargetAgentConfig

log = structlog.get_logger()
router = APIRouter(tags=["audit"])

# In-memory store — keyed by audit_run_id
# Replace with Firestore for production multi-instance deployments
_audit_store: dict[str, dict[str, Any]] = {}


def _get_run_or_404(run_id: str) -> dict:
    record = _audit_store.get(run_id)
    if not record:
        raise HTTPException(status_code=404, detail=f"Audit run {run_id!r} not found")
    return record


async def _run_audit_background(run_id: str, request: AuditConfigRequest) -> None:
    record = _audit_store[run_id]
    try:
        config = TargetAgentConfig(
            endpoint_url=request.target_endpoint,
            arize_project_id=request.arize_project_id,
            arize_api_key=request.arize_api_key,
            elastic_api_key=request.elastic_api_key,
            elastic_cloud_id=request.elastic_cloud_id,
            system_prompt=request.system_prompt,
        )
        context = AuditContext(
            audit_run_id=uuid.UUID(run_id),
            config=config,
            selected_modules=request.modules,
            frameworks=request.frameworks,
        )
        orchestrator = AuditOrchestrator()
        report = await orchestrator.run_audit(context)

        record["status"] = report.status
        record["report"] = report
        record["overall_score"] = report.overall_score
        record["json_url"] = report.json_url
        record["pdf_url"] = report.pdf_url
        log.info("audit.complete", run_id=run_id, score=report.overall_score)
    except Exception as exc:
        log.error("audit.failed", run_id=run_id, error=str(exc))
        record["status"] = "failed"
        record["error"] = str(exc)


@router.post("/audit", response_model=AuditAcceptedResponse, status_code=202)
async def create_audit(request: AuditConfigRequest, background_tasks: BackgroundTasks):
    run_id = str(uuid.uuid4())
    _audit_store[run_id] = {
        "run_id": run_id,
        "status": "accepted",
        "config": request.model_dump(exclude={"arize_api_key", "elastic_api_key"}),
        "report": None,
    }
    background_tasks.add_task(_run_audit_background, run_id, request)
    log.info("audit.accepted", run_id=run_id, modules=request.modules)
    return AuditAcceptedResponse(
        audit_run_id=run_id,
        poll_url=f"/api/v1/audit/{run_id}/status",
    )


@router.get("/audit/{run_id}/status", response_model=AuditStatusResponse)
async def get_audit_status(run_id: str):
    record = _get_run_or_404(run_id)
    report = record.get("report")
    findings_so_far = 0
    current_stage = None
    progress_pct = 0

    if report:
        # report.modules may contain either model objects or dicts.
        findings_so_far = sum(
            len(m.findings) if hasattr(m, "findings") else len(m.get("findings", []))
            for m in report.modules
        )
        current_stage = report.status
        progress_pct = 100 if report.status in ("complete", "partial") else 50
    else:
        current_stage = record.get("status", "accepted")

    stage_progress = {
        "accepted": 0,
        "initialising": 5,
        "planning": 10,
        "executing": 50,
        "reasoning": 80,
        "reporting": 90,
        "complete": 100,
        "partial": 100,
        "failed": 100,
    }
    progress_pct = stage_progress.get(current_stage or "accepted", 0)

    return AuditStatusResponse(
        audit_run_id=run_id,
        status=record["status"],
        current_stage=current_stage,
        progress_pct=progress_pct,
        findings_so_far=findings_so_far,
    )


@router.get("/audit/{run_id}/report", response_model=ReportSummaryResponse)
async def get_audit_report(run_id: str):
    record = _get_run_or_404(run_id)
    report = record.get("report")
    return ReportSummaryResponse(
        audit_run_id=run_id,
        status=record["status"],
        overall_score=record.get("overall_score"),
        dashboard_url=f"/audit/{run_id}",
        json_url=record.get("json_url"),
        pdf_url=record.get("pdf_url"),
    )


@router.get("/audit/{run_id}/full")
async def get_full_report(run_id: str):
    """Return the full AuditReport as JSON (for the dashboard)."""
    record = _get_run_or_404(run_id)
    report = record.get("report")
    if not report:
        raise HTTPException(status_code=404, detail="Report not yet available")
    return report.model_dump()


@router.get("/audits")
async def list_audits():
    """List all audit runs (most recent first)."""
    runs = []
    for record in _audit_store.values():
        cfg = record.get("config", {})
        runs.append({
            "run_id": record["run_id"],
            "status": record["status"],
            "target_endpoint": cfg.get("target_endpoint", ""),
            "overall_score": record.get("overall_score"),
            "modules": cfg.get("modules", []),
        })
    return {"runs": list(reversed(runs))}
