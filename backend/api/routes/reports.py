"""Report download routes — PDF and JSON export.

Uses pathlib.Path via storage module for cross-platform compatibility (Windows/macOS/Linux).
"""
from __future__ import annotations

import structlog
from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse, JSONResponse, Response

from api.routes.audit import _audit_store
from output.storage import get_local_pdf_path, get_local_json_path

log = structlog.get_logger()
router = APIRouter(tags=["reports"])


@router.get("/reports/{run_id}/pdf")
async def download_pdf(run_id: str):
    record = _audit_store.get(run_id)
    if not record:
        raise HTTPException(status_code=404, detail="Audit run not found")
    report = record.get("report")
    if not report:
        raise HTTPException(status_code=404, detail="Report not yet generated")

    pdf_path = get_local_pdf_path(run_id)
    if pdf_path.exists():
        return FileResponse(
            str(pdf_path),
            media_type="application/pdf",
            filename=f"sentinel-report-{run_id[:8]}.pdf",
        )

    pdf_url = record.get("pdf_url")
    if pdf_url and pdf_url.startswith("http"):
        return JSONResponse({"redirect_url": pdf_url})

    raise HTTPException(status_code=404, detail="PDF not yet available — try again shortly")


@router.get("/reports/{run_id}/json")
async def download_json(run_id: str):
    record = _audit_store.get(run_id)
    if not record:
        raise HTTPException(status_code=404, detail="Audit run not found")
    report = record.get("report")
    if not report:
        raise HTTPException(status_code=404, detail="Report not yet generated")

    json_path = get_local_json_path(run_id)
    if json_path.exists():
        content = json_path.read_bytes()
        return Response(
            content=content,
            media_type="application/json",
            headers={
                "Content-Disposition": f'attachment; filename="sentinel-audit-{run_id[:8]}.json"'
            },
        )

    import json
    content = json.dumps(report.model_dump(), indent=2, default=str)
    return Response(
        content=content.encode("utf-8"),
        media_type="application/json",
        headers={
            "Content-Disposition": f'attachment; filename="sentinel-audit-{run_id[:8]}.json"'
        },
    )
