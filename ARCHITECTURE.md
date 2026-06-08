# Sentinel — Architecture Reference

> Phase 3 of the Agent Engineering Framework: System Design (Six Layers)

---

## Architecture Pattern

**Pattern 3: Workflow Graph** — recommended for production systems.

```
User (audit config)
      ↓
  FastAPI Route
      ↓
  AuditOrchestrator
  ┌─────────────────────────────────────────┐
  │  STAGE 1: PLAN                          │
  │  Validate config, confirm modules       │
  │             ↓                           │
  │  STAGE 2: RETRIEVE                      │
  │  Arize MCP → traces                     │
  │  Elastic MCP → logs                     │
  │             ↓                           │
  │  STAGE 3: EXECUTE                       │
  │  Prompt Injection Module                │
  │  PII Leakage Module                     │
  │  Hallucination Risk Module              │
  │             ↓                           │
  │  STAGE 4: REFLECT                       │
  │  Critique findings quality              │
  │  Verify regulatory citations            │
  │  Confirm PII redaction                  │
  │             ↓                           │
  │  STAGE 5: SCORE                         │
  │  Weighted aggregation (40/40/20)        │
  │             ↓                           │
  │  STAGE 6: REPORT                        │
  │  PDF + JSON + Storage                   │
  └─────────────────────────────────────────┘
      ↓
  Dashboard (Next.js 14)
```

---

## Layer 1: Reasoning

**Strategy: ReAct + Workflow Graph + Level 2 Reflection**

The agent does NOT use a free-form ReAct loop (too unpredictable for compliance work). Instead it uses a **deterministic workflow graph** with a reflection checkpoint.

```text
Planning:
  Confirm which modules to run. Validate that all required tools
  are reachable. Log the audit plan before execution begins.

Execution:
  Each module is a deterministic function: given traces and probes,
  return structured findings. No LLM decision-making in the hot path.

Reflection (Level 2 — External Feedback):
  After all modules complete, a critique pass reviews:
  - Are regulatory article citations accurate?
  - Is PII properly redacted in evidence strings?
  - Are remediation steps specific and actionable?
  - Are confidence scores calibrated correctly?
  Findings that fail critique are flagged with a warning.

Scoring:
  Pure arithmetic — no LLM involved. Deterministic and auditable.
```

**Why no free-form ReAct for the main path?**
Compliance findings must be reproducible and auditable. An LLM deciding which tools to call introduces non-determinism that is unacceptable in a regulatory context. The LLM is used only in Reflection and Hallucination scoring — both optional and bounded.

---

## Layer 2: Tooling

| Tool | Purpose | Input | Output | Failure Mode |
|------|---------|-------|--------|-------------|
| `ArizeTraceTool` | Fetch LLM traces from Arize MCP | project_id, limit | list of spans | Falls back to mock fixture |
| `ElasticSearchTool` | Search logs for PII patterns | index, regex patterns | list of hits | Falls back to mock fixture |
| `TargetAgentTool` | Send adversarial probes to target | prompt text | response text | Returns error dict, does not crash |
| `PolicyLibraryTool` | Lookup regulatory rules by ID | rule_id or module_id | rule dict with citation | Returns None, caller handles |

Full tool specs: see `TOOL_CATALOG.md`.

---

## Layer 3: Memory

| Memory Type | Implementation | Contents |
|-------------|---------------|---------|
| Working Memory | `AuditContext` dataclass | Current audit state, tool handles, findings |
| Session Memory | In-memory dict keyed by `audit_run_id` | All audit records for current server process |
| Long-Term Memory | Not used in v1.0 | Future: Firestore for cross-instance history |
| Knowledge Memory | `PolicyLibraryTool` (policy JSON files) | GDPR + EU AI Act rule library |

**Design decision**: In-memory audit store is intentional for v1.0 (simplest viable). The `STORAGE_BACKEND=local` setting writes PDFs and JSON to disk for persistence. Replace with Firestore for production multi-instance.

---

## Layer 4: State

The `AuditContext` is a full state machine. It tracks:

```python
@dataclass
class AuditContext:
    audit_run_id: UUID       # Identity
    config: TargetAgentConfig  # Input
    selected_modules: list[str]  # Goal
    frameworks: list[str]       # Goal
    tools: dict               # Resources
    findings: list            # Completed tasks
    status: str               # Current step
    current_stage: str        # Substep
    errors: list[dict]        # Error log
    retries: dict             # Retry counters
    stage_timings: dict       # Observability
```

Stage transitions:
```
accepted → planning → retrieving → executing → reflecting → scoring → reporting → complete
                                                                          └→ partial (some modules failed)
                                                                          └→ failed (all modules failed)
```

---

## Layer 5: Evaluation

See `eval/` directory.

**Eval types used** (framework Phase 6):
- `eval/dataset.json` — 20 ground-truth examples covering all three modules
- `eval/runner.py` — Runs each case, computes pass/fail
- `eval/error_analysis.py` — Categorises failures by type

**Eval categories for agents** (framework Phase 6):
- Planning Quality: Did the orchestrator select the correct modules?
- Tool Selection: Did tools return expected data?
- Tool Accuracy: Are findings correctly mapped to regulatory articles?
- Reflection Quality: Did the reflection catch citation errors?
- Final Output Quality: Is the PDF complete and accurate?

---

## Layer 6: Human Oversight

**Current implementation (v1.0)**:
- All findings require human review before remediation action
- PDF report is the review artefact — structured for legal/compliance sign-off
- Severity thresholds documented; no automated remediation is ever taken

**Escalation triggers**:
- `critical` severity finding → immediate review required (noted in PDF)
- `overall_score < 40` → audit flagged as CRITICAL RISK in report header

**Future (v2.0)**:
- Webhook callback when audit completes (Human-in-the-Loop approval gate)
- Slack/email notification on critical findings
- CI/CD gate: fail build if `overall_score < threshold`

---

## Observability

Following framework Phase 8:

| Signal | Tool | What is tracked |
|--------|------|----------------|
| Structured Logging | `structlog` | Every stage start/end, tool call, finding |
| Trace data source | Arize MCP | Agent traces, spans, latency, model used |
| Log data source | Elastic MCP | Raw log entries with PII patterns |
| Metrics (future) | OpenTelemetry | Per-stage latency, cost per token, error rate |

Every tool call logs: input summary, output summary, latency, source (real/mock).

---

## Cost & Latency (Framework Phase 11)

Optimisation order applied:
1. **Parallelisation**: modules run sequentially today (safe for thread safety); future: `asyncio.gather()` with per-module timeouts
2. **Caching**: `PolicyLibraryTool` caches all rules at startup
3. **Smaller models**: Gemini 1.5 Flash used for hallucination scoring (cheapest capable model)
4. **No over-engineering**: LLM only called where pattern matching is insufficient

Current typical run: **60–120 seconds** end-to-end with mock data. With real Arize + Gemini: ~90–150 seconds.
