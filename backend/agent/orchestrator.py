"""AuditOrchestrator — Workflow Graph agent driver.

Framework Phase 9, Pattern 3: Workflow Graph
Planner → Retriever → Executor → Reflector → Scorer → Reporter

Framework Phase 5: Level 2 Reflection (external feedback after execution)
Framework Phase 8: Observability — every stage is timed and logged
"""
from __future__ import annotations

import asyncio
import os
import structlog
from datetime import datetime, timezone
from typing import Optional

from agent.state import AuditContext, StageRecord, TERMINAL_STATES
from agent.reflection import reflect, ReflectionResult
from agent.tools.arize_tool import ArizeTraceTool, MockArizeTraceTool
from agent.tools.elastic_tool import ElasticSearchTool
from agent.tools.target_tool import TargetAgentTool
from agent.tools.policy_tool import PolicyLibraryTool
from modules.prompt_injection import PromptInjectionModule
from modules.pii_leakage import PIILeakageModule
from modules.hallucination import HallucinationRiskModule
from modules.base import ModuleResult
from output.aggregator import compute_module_score, compute_overall_score
from output.json_serialiser import serialise_report
from output.pdf_generator import generate_pdf
from output.storage import upload_json, upload_pdf

log = structlog.get_logger()

MODULE_REGISTRY = {
    "prompt_injection": PromptInjectionModule,
    "pii_leakage": PIILeakageModule,
    "hallucination_risk": HallucinationRiskModule,
}

# Per-stage timeouts (seconds) — framework Phase 11
STAGE_TIMEOUTS = {
    "planning":   30,
    "retrieving": 45,
    "executing":  210,
    "reflecting": 30,
    "scoring":    10,
    "reporting":  45,
}

MAX_RETRIES_PER_MODULE = 1


class AuditReport:
    """Structured result of a completed audit run."""

    def __init__(
        self,
        audit_run_id: str,
        target_agent: dict,
        overall_score: int,
        status: str,
        modules: list,
        created_at: str,
        reflection: Optional[dict] = None,
        timing: Optional[dict] = None,
        json_url: Optional[str] = None,
        pdf_url: Optional[str] = None,
    ):
        self.audit_run_id = audit_run_id
        self.target_agent = target_agent
        self.overall_score = overall_score
        self.status = status
        self.modules = modules
        self.created_at = created_at
        self.reflection = reflection or {}
        self.timing = timing or {}
        self.json_url = json_url
        self.pdf_url = pdf_url

    def model_dump(self) -> dict:
        return {
            "audit_run_id": self.audit_run_id,
            "created_at": self.created_at,
            "target_agent": self.target_agent,
            "overall_score": self.overall_score,
            "status": self.status,
            "modules": [
                m.model_dump() if hasattr(m, "model_dump") else m
                for m in self.modules
            ],
            "reflection": self.reflection,
            "timing": self.timing,
            "json_url": self.json_url,
            "pdf_url": self.pdf_url,
        }


class _ModuleResult:
    def __init__(self, module_id: str, score: int, findings: list, status: str, **_):
        self.module_id = module_id
        self.score = score
        self.findings = findings
        self.status = status

    def model_dump(self) -> dict:
        return {
            "module_id": self.module_id,
            "score": self.score,
            "findings": [
                f.__dict__ if hasattr(f, "__dict__") else f
                for f in self.findings
            ],
            "status": self.status,
        }


class AuditOrchestrator:
    """
    Single-orchestrator Workflow Graph agent.

    Framework Pattern 3 stages:
    1. PLAN    — validate config, confirm modules and tool availability
    2. RETRIEVE — fetch traces (Arize) and logs (Elastic), cache results
    3. EXECUTE  — run each compliance module against cached data
    4. REFLECT  — Level 2 External Feedback Reflection (citation/PII/specificity)
    5. SCORE    — weighted aggregation (no LLM — deterministic)
    6. REPORT   — generate PDF + JSON, upload to storage
    """

    def __init__(self):
        self._policy_tool = PolicyLibraryTool()

    def _build_tools(self, context: AuditContext) -> dict:
        cfg = context.config
        use_mock_arize = not cfg.arize_api_key or not cfg.arize_project_id
        arize = MockArizeTraceTool() if use_mock_arize else ArizeTraceTool(api_key=cfg.arize_api_key)
        elastic = ElasticSearchTool(api_key=cfg.elastic_api_key, cloud_id=cfg.elastic_cloud_id)
        target = TargetAgentTool(endpoint_url=cfg.endpoint_url)
        return {
            "arize": arize,
            "elastic": elastic,
            "target": target,
            "policy": self._policy_tool,
        }

    async def run_audit(self, context: AuditContext) -> AuditReport:
        run_id = str(context.audit_run_id)
        log.info("orchestrator.start", run_id=run_id, modules=context.selected_modules)

        context.tools = self._build_tools(context)
        module_results: list[ModuleResult] = []
        reflection_result: Optional[ReflectionResult] = None

        # ── STAGE 1: PLAN ────────────────────────────────────────────────
        stage = context.transition_to("planning")
        try:
            await asyncio.wait_for(self._plan(context), timeout=STAGE_TIMEOUTS["planning"])
            stage.complete()
        except asyncio.TimeoutError:
            stage.fail("planning timeout")
            context.record_error("Planning Failure", "Planning stage timed out")
            log.warning("orchestrator.planning_timeout", run_id=run_id)

        # ── STAGE 2: RETRIEVE ─────────────────────────────────────────────
        stage = context.transition_to("retrieving")
        try:
            await asyncio.wait_for(self._retrieve(context), timeout=STAGE_TIMEOUTS["retrieving"])
            stage.complete()
        except asyncio.TimeoutError:
            stage.fail("retrieval timeout")
            context.record_error("Retrieval Failure", "Data retrieval timed out — continuing with empty dataset")
            log.warning("orchestrator.retrieval_timeout", run_id=run_id)

        # ── STAGE 3: EXECUTE ──────────────────────────────────────────────
        stage = context.transition_to("executing")
        try:
            module_results = await asyncio.wait_for(
                self._execute(context), timeout=STAGE_TIMEOUTS["executing"]
            )
            stage.complete()
        except asyncio.TimeoutError:
            stage.fail("execution timeout")
            context.record_error("Tool Failure", "Module execution timed out — report will be partial")
            log.error("orchestrator.execution_timeout", run_id=run_id)

        # ── STAGE 4: REFLECT ──────────────────────────────────────────────
        stage = context.transition_to("reflecting")
        try:
            reflection_result = await asyncio.wait_for(
                self._reflect(context, module_results),
                timeout=STAGE_TIMEOUTS["reflecting"],
            )
            stage.complete()
        except asyncio.TimeoutError:
            stage.fail("reflection timeout")
            context.record_error("Reasoning Failure", "Reflection stage timed out — proceeding without critique")
            log.warning("orchestrator.reflection_timeout", run_id=run_id)

        # ── STAGE 5: SCORE ────────────────────────────────────────────────
        stage = context.transition_to("scoring")
        overall_score = compute_overall_score(module_results)
        stage.complete()

        # ── STAGE 6: REPORT ───────────────────────────────────────────────
        stage = context.transition_to("reporting")
        report = await asyncio.wait_for(
            self._report(context, module_results, overall_score, reflection_result),
            timeout=STAGE_TIMEOUTS["reporting"],
        )
        stage.complete()

        context.transition_to(report.status)
        log.info(
            "orchestrator.complete",
            run_id=run_id,
            score=report.overall_score,
            status=report.status,
            timing=context.timing_summary(),
        )
        return report

    # ── Stage implementations ─────────────────────────────────────────────

    async def _plan(self, context: AuditContext) -> None:
        """Validate configuration and log the audit plan."""
        unknown = [m for m in context.selected_modules if m not in MODULE_REGISTRY]
        for m in unknown:
            context.record_error("Planning Failure", f"Unknown module '{m}' will be skipped")
            log.warning("orchestrator.unknown_module", module_id=m)
        context.selected_modules = [m for m in context.selected_modules if m in MODULE_REGISTRY]
        log.info("orchestrator.plan_confirmed", modules=context.selected_modules, frameworks=context.frameworks)
        await asyncio.sleep(0)

    async def _retrieve(self, context: AuditContext) -> None:
        """
        Pre-fetch all data sources and cache in context.tool_results.

        Framework Layer 3 (Memory / Knowledge): retrieved data is working memory
        for all downstream modules — avoids duplicate API calls.
        """
        loop = asyncio.get_event_loop()
        cfg = context.config

        try:
            traces = await loop.run_in_executor(
                None,
                lambda: context.tools["arize"].get_traces(cfg.arize_project_id, limit=50)
            )
            context.tool_results["arize_traces"] = traces
            log.info("orchestrator.retrieved_arize", count=len(traces))
        except Exception as exc:
            context.record_error("Retrieval Failure", f"Arize retrieval failed: {exc}")
            context.tool_results["arize_traces"] = []

        try:
            elastic_hits = await loop.run_in_executor(
                None,
                lambda: context.tools["elastic"].search_pii()
            )
            context.tool_results["elastic_hits"] = elastic_hits
            log.info("orchestrator.retrieved_elastic", count=len(elastic_hits))
        except Exception as exc:
            context.record_error("Retrieval Failure", f"Elastic retrieval failed: {exc}")
            context.tool_results["elastic_hits"] = []

    async def _execute(self, context: AuditContext) -> list[ModuleResult]:
        """Run each compliance module, with one retry on exception."""
        results: list[ModuleResult] = []
        loop = asyncio.get_event_loop()

        for module_id in context.selected_modules:
            module_cls = MODULE_REGISTRY[module_id]
            module = module_cls()
            attempt = 0

            while attempt <= MAX_RETRIES_PER_MODULE:
                try:
                    log.info("orchestrator.module_start", module_id=module_id, attempt=attempt)
                    result: ModuleResult = await loop.run_in_executor(None, module.run, context)
                    results.append(result)
                    log.info(
                        "orchestrator.module_done",
                        module_id=module_id,
                        score=result.score,
                        findings=len(result.findings),
                    )
                    break
                except Exception as exc:
                    attempt += 1
                    context.increment_retry(module_id)
                    context.record_error("Tool Failure", f"{module_id} attempt {attempt} failed: {exc}")
                    log.error("orchestrator.module_error", module_id=module_id, attempt=attempt, error=str(exc))
                    if attempt > MAX_RETRIES_PER_MODULE:
                        results.append(ModuleResult(
                            module_id=module_id,
                            score=0,
                            findings=[],
                            status="failed",
                        ))

        return results

    async def _reflect(self, context: AuditContext, module_results: list[ModuleResult]) -> ReflectionResult:
        """
        Level 2 Reflection — framework Phase 5.

        Runs deterministic validators against all findings:
        1. Citation checker
        2. PII redaction verifier
        3. Remediation specificity checker
        4. Confidence calibration checker

        Logs warnings without modifying findings (findings are immutable after execution).
        """
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            None,
            lambda: reflect(module_results, context.tools.get("policy"))
        )

        if result.reflection_quality == "poor":
            log.warning(
                "orchestrator.reflection_quality_poor",
                citation_errors=result.citation_errors,
                pii_leaks=result.pii_leaks,
            )

        return result

    async def _report(
        self,
        context: AuditContext,
        module_results: list[ModuleResult],
        overall_score: int,
        reflection_result: Optional[ReflectionResult],
    ) -> AuditReport:
        run_id = str(context.audit_run_id)

        # Determine overall status
        all_failed = all(r.status == "failed" for r in module_results) if module_results else True
        any_failed = any(r.status == "failed" for r in module_results)
        status = "failed" if all_failed else ("partial" if any_failed else "complete")

        module_dicts = []
        for r in module_results:
            module_dicts.append({
                "module_id": r.module_id,
                "score": r.score,
                "findings": [
                    f.__dict__ if hasattr(f, "__dict__") else f
                    for f in r.findings
                ],
                "status": r.status,
            })

        reflection_dict = {}
        if reflection_result:
            reflection_dict = {
                "quality": reflection_result.reflection_quality,
                "total_findings": reflection_result.total_findings,
                "citation_errors": reflection_result.citation_errors,
                "pii_leaks_in_evidence": reflection_result.pii_leaks,
                "generic_remediations": reflection_result.generic_remediations,
                "warnings": [
                    {
                        "finding_id": w.finding_id,
                        "check": w.check,
                        "message": w.message,
                        "severity": w.severity,
                    }
                    for w in reflection_result.warnings
                ],
            }

        report = AuditReport(
            audit_run_id=run_id,
            created_at=datetime.now(timezone.utc).isoformat(),
            target_agent={
                "endpoint": context.config.endpoint_url,
                "arize_project_id": context.config.arize_project_id,
            },
            overall_score=overall_score,
            status=status,
            modules=module_dicts,
            reflection=reflection_dict,
            timing=context.timing_summary(),
        )

        # Upload outputs
        json_url = None
        pdf_url = None

        try:
            json_bytes = serialise_report(report.model_dump())
            json_url = await upload_json(run_id, json_bytes)
        except Exception as exc:
            context.record_error("Formatting Failure", f"JSON serialisation failed: {exc}")
            log.error("orchestrator.json_failed", error=str(exc))

        try:
            pdf_bytes = generate_pdf(report.model_dump())
            pdf_url = await upload_pdf(run_id, pdf_bytes)
        except Exception as exc:
            context.record_error("Formatting Failure", f"PDF generation failed: {exc}")
            log.error("orchestrator.pdf_failed", error=str(exc))

        report.json_url = json_url
        report.pdf_url = pdf_url
        return report
