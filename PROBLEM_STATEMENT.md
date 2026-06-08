# Problem Statement — Sentinel AI GRC Auditor

> Phase 1 of the Agent Engineering Framework: Problem Decomposition

---

## The Problem

AI agents are increasingly deployed in production systems that process personal data, make consequential decisions, and operate at scale. Yet there is **no automated, repeatable way** to audit these agents for compliance against GDPR and the EU AI Act before or after deployment.

Current compliance processes are:
- Manual and inconsistent
- Expensive (require human legal/security reviewers)
- Reactive (audit after breach, not before)
- Unable to keep pace with rapid AI deployment cycles

---

## Task Definition

```markdown
Task:
Autonomously audit a deployed AI agent for compliance against
GDPR and EU AI Act requirements, produce a structured report
with findings, severity scores, and actionable remediation steps.

Who is the user?
- AI teams submitting their agent for compliance review
- Security/compliance engineers validating regulatory posture
- Legal teams requiring auditable evidence of compliance checks

What output is expected?
- Overall compliance score (0–100)
- Per-module scores with finding details
- PDF report with executive summary + remediation roadmap
- JSON export for CI/CD integration
- Live dashboard updated in real-time

What is success?
- Correct identification of known vulnerabilities in the target agent
- Zero false-negative critical findings
- Regulatory citations accurate and specific (e.g., GDPR-Art32, EUAIA-Art15)
- All PII in evidence is redacted before inclusion in reports
- Audit completes in under 3 minutes for a typical target

What is failure?
- Missing a critical finding that exists in the target agent
- Reporting PII in evidence strings without redaction
- Incorrect regulatory article citation
- Audit hanging or crashing without graceful degradation
- Score computed incorrectly
```

---

## Task Classification

**Type: C — Workflow Agent** (see framework Phase 1)

```text
Audit Request
    ↓
Planning (confirm modules, frameworks, tools)
    ↓
Retrieval (fetch traces from Arize, logs from Elastic)
    ↓
Execution (run each compliance test module)
    ↓
Reflection (self-critique findings quality and citations)
    ↓
Scoring (weighted compliance score computation)
    ↓
Reporting (PDF + JSON + dashboard)
```

**Why not Type D (Long Running)?**
An audit is bounded in time and scope. It has a clear start and end condition. Type C Workflow is the smallest architecture that satisfies the requirements.

**Why not Multi-Agent (Pattern 4)?**
Each compliance module (Prompt Injection, PII Leakage, Hallucination) runs the same tool interface. There is no clearly separable expertise that justifies separate LLM instances. A single orchestrator with a reflection loop covers all requirements with lower complexity and cost.

---

## Architecture Decision: Workflow Graph (Framework Pattern 3)

```
Planner
  ↓
Retriever (Arize MCP + Elastic MCP)
  ↓
Executor (per compliance module)
  ↓
Reflector (Level 2 — external feedback)
  ↓
Scorer (weighted aggregation)
  ↓
Reporter (PDF + JSON + storage)
```

This maps directly to the framework's Pattern 3 — Workflow Graph — which is recommended for production systems.

---

## Failure Mode Catalogue

| Category | Example | Mitigation |
|----------|---------|------------|
| Tool Failure | Arize API unreachable | Mock fallback, continue with available data |
| Planning Failure | Module not found in registry | Log warning, skip, mark partial |
| Retrieval Failure | No traces available | Proceed with empty trace set, note in report |
| Reasoning Failure | Reflection rejects all findings | Keep original findings, log reflection error |
| Hallucination | Gemini scores incorrectly | Local fallback scorer |
| Formatting Failure | PDF generation fails | Return HTML fallback |

---

## Evaluation Strategy

Following framework Phase 6 — Four Eval Types:

| Eval Type | Example |
|-----------|---------|
| Objective + Ground Truth | Does the agent find a known system prompt leak? |
| Objective + No Ground Truth | Hallucination confidence score |
| Subjective + Ground Truth | Is the remediation advice GDPR-specific? |
| Subjective + No Ground Truth | Is the PDF report readable and well-structured? |

See `eval/` directory for the evaluation dataset and runner.

---

## Production Readiness Checklist

### Reliability
- [x] End-to-end evals (`eval/runner.py`)
- [x] Regression tests (`backend/tests/`)
- [x] Failure modes documented (above)

### Observability
- [x] Structured logging (`structlog`)
- [x] Tracing via Arize integration
- [ ] Cost tracking (add in next iteration)

### Safety
- [x] PII redacted in all evidence strings
- [x] Human-readable report for review before action
- [ ] Human approval gate (add via webhook in next iteration)

### Performance
- [x] Per-module timeouts enforced
- [x] Tool fallbacks prevent total failure
- [ ] Latency benchmarks (measure after eval baseline)

### Architecture
- [x] Smallest viable: single orchestrator, no unnecessary agents
- [x] State machine with step tracking
- [x] Graceful degradation to partial results
