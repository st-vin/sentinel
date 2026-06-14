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


# ── Intercept session schemas ─────────────────────────────────────────────────

class InterceptSessionRequest(BaseModel):
    """Request body for POST /api/v1/intercept/session."""

    upstream_llm_url: str
    """Base URL of the real LLM provider, e.g. 'https://api.openai.com/v1'.
    Provided per-session so different sessions can target different providers."""

    upstream_api_key: Optional[str] = None
    """API key for the upstream LLM.  Falls back to OPENAI_API_KEY env var."""

    proxy_port: int = 8787
    """Preferred local port for the proxy.  Auto-scans upward if the port is taken."""

    block_on_pii: bool = False
    """If True, any detected PII causes a 403 BLOCK instead of silent REDACT."""

    block_on_injection: bool = True
    """If True (default), any detected injection pattern causes a 403 BLOCK."""

    @field_validator("upstream_llm_url")
    @classmethod
    def valid_upstream_url(cls, v: str) -> str:
        if not v.startswith(("http://", "https://")):
            raise ValueError("upstream_llm_url must start with http:// or https://")
        return v.rstrip("/")

    @field_validator("proxy_port")
    @classmethod
    def valid_port(cls, v: int) -> int:
        if not (1024 <= v <= 65535):
            raise ValueError("proxy_port must be in range 1024–65535")
        return v


class InterceptSessionResponse(BaseModel):
    """Response body for POST /api/v1/intercept/session."""

    session_id: str
    status: str                 # "starting" | "running" | "failed"
    proxy_port: int
    proxy_base_url: str         # e.g. "http://127.0.0.1:8787/v1"
    ledger_path: str            # absolute path to the JSONL ledger file
    upstream_llm_url: str


class InterceptStatusResponse(BaseModel):
    """Response body for GET /api/v1/intercept/session/{id}/status."""

    session_id: str
    status: str                              # "starting" | "running" | "stopped" | "failed"
    proxy_port: Optional[int] = None
    proxy_base_url: Optional[str] = None
    transactions_processed: int = 0
    allowed_count: int = 0
    redacted_count: int = 0
    blocked_count: int = 0
    pii_types_encountered: list[str] = []
    ledger_path: Optional[str] = None
