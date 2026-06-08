"""Pydantic request/response schemas for the Sentinel API."""
from __future__ import annotations

from typing import Literal, Optional
from uuid import UUID

from pydantic import BaseModel, HttpUrl, field_validator


class AuditConfigRequest(BaseModel):
    target_endpoint: str
    arize_project_id: str = ""
    arize_api_key: str = ""
    elastic_api_key: str = ""
    elastic_cloud_id: str = ""
    system_prompt: Optional[str] = None
    modules: list[Literal["prompt_injection", "pii_leakage", "hallucination_risk"]]
    frameworks: list[Literal["gdpr", "eu_ai_act"]] = ["gdpr", "eu_ai_act"]

    @field_validator("modules")
    @classmethod
    def at_least_one_module(cls, v: list) -> list:
        if not v:
            raise ValueError("at least one module required")
        return v

    @field_validator("target_endpoint")
    @classmethod
    def valid_url(cls, v: str) -> str:
        if not v.startswith(("http://", "https://")):
            raise ValueError("invalid URL format — must start with http:// or https://")
        return v


class AuditAcceptedResponse(BaseModel):
    audit_run_id: str
    status: str = "accepted"
    poll_url: str


class AuditStatusResponse(BaseModel):
    audit_run_id: str
    status: str
    current_stage: Optional[str] = None
    progress_pct: int = 0
    findings_so_far: int = 0


class ReportSummaryResponse(BaseModel):
    audit_run_id: str
    status: str
    overall_score: Optional[int] = None
    dashboard_url: Optional[str] = None
    json_url: Optional[str] = None
    pdf_url: Optional[str] = None
