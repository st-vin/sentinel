"""AuditContext — full state machine for the Sentinel audit workflow.

Framework Phase 3, Layer 4: State
Tracks current step, completed tasks, tool results, errors, and retries.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Optional
from uuid import UUID

# All valid stage transitions (deterministic workflow graph)
STAGE_TRANSITIONS = {
    "accepted":    "planning",
    "planning":    "retrieving",
    "retrieving":  "executing",
    "executing":   "reflecting",
    "reflecting":  "scoring",
    "scoring":     "reporting",
    "reporting":   "complete",
}

# Terminal states — no further transitions
TERMINAL_STATES = {"complete", "partial", "failed"}


@dataclass
class TargetAgentConfig:
    endpoint_url: str
    arize_project_id: str = ""
    arize_api_key: str = ""
    elastic_api_key: str = ""
    elastic_cloud_id: str = ""
    system_prompt: Optional[str] = None


@dataclass
class StageRecord:
    """Tracks timing and outcome of a single workflow stage."""
    stage: str
    started_at: float = field(default_factory=time.monotonic)
    ended_at: Optional[float] = None
    status: str = "running"  # running | complete | failed | skipped
    error: Optional[str] = None

    @property
    def duration_ms(self) -> Optional[float]:
        if self.ended_at is not None:
            return round((self.ended_at - self.started_at) * 1000, 1)
        return None

    def complete(self) -> None:
        self.ended_at = time.monotonic()
        self.status = "complete"

    def fail(self, error: str) -> None:
        self.ended_at = time.monotonic()
        self.status = "failed"
        self.error = error


@dataclass
class AuditContext:
    """
    Full state machine for a single audit run.

    Framework Phase 3, Layer 4:
    - current_stage: current position in the workflow graph
    - stage_records: completed stages with timing
    - errors: categorised error log (Tool Failure / Planning Failure / etc.)
    - retries: per-tool retry counters
    - tool_results: cached retrieval results (avoid re-fetching)
    """
    audit_run_id: UUID
    config: TargetAgentConfig
    selected_modules: list[str]
    frameworks: list[str] = field(default_factory=lambda: ["gdpr", "eu_ai_act"])

    # Resources
    tools: dict = field(default_factory=dict)

    # State machine
    status: str = "accepted"
    current_stage: Optional[str] = None

    # Observability — framework Phase 8
    stage_records: list[StageRecord] = field(default_factory=list)
    errors: list[dict] = field(default_factory=list)
    retries: dict = field(default_factory=dict)

    # Cached data from retrieval stage
    tool_results: dict = field(default_factory=dict)
    findings: list = field(default_factory=list)

    def transition_to(self, stage: str) -> StageRecord:
        """Advance to the next workflow stage and start timing."""
        record = StageRecord(stage=stage)
        self.stage_records.append(record)
        self.current_stage = stage
        self.status = stage
        return record

    def record_error(self, category: str, detail: str, stage: Optional[str] = None) -> None:
        """
        Categorised error log — framework Phase 7 (Error Analysis).
        Categories: Tool Failure | Planning Failure | Memory Failure |
                    Reasoning Failure | Retrieval Failure | Hallucination | Formatting Failure
        """
        self.errors.append({
            "category": category,
            "detail": detail,
            "stage": stage or self.current_stage,
            "timestamp": time.time(),
        })

    def increment_retry(self, tool_name: str) -> int:
        """Track retry count per tool — framework Phase 3 Layer 4."""
        self.retries[tool_name] = self.retries.get(tool_name, 0) + 1
        return self.retries[tool_name]

    def timing_summary(self) -> dict:
        """Return per-stage timing for observability."""
        return {
            r.stage: {
                "status": r.status,
                "duration_ms": r.duration_ms,
                "error": r.error,
            }
            for r in self.stage_records
        }
