# Evaluation Strategy — Sentinel AI GRC Auditor

> Framework Phase 6: Evaluation Framework

---

## Philosophy

From the Agent Engineering Framework:
> The most important phase. Design evals before scaling.

Sentinel follows the four eval types:

| Type | Example in Sentinel |
|------|-------------------|
| Objective + Ground Truth | Does the agent detect a known system prompt leak? |
| Objective + No Ground Truth | Hallucination confidence score falls in expected range |
| Subjective + Ground Truth | Is the finding's rule_id a valid GDPR citation? |
| Subjective + No Ground Truth | Is the remediation advice specific enough? (rubric) |

---

## Dataset

`eval/dataset.json` — 20 cases covering all modules.

| Module | Cases | Eval Types Used |
|--------|-------|----------------|
| Prompt Injection | 5 | Objective + Ground Truth |
| PII Leakage | 6 | Objective GT, Subjective GT |
| Hallucination Risk | 5 | Objective GT, Objective No-GT |
| Reflection | 3 | Objective + Ground Truth |
| Aggregator/Scoring | 1 | Objective + Ground Truth |

Starting at 20 examples (framework recommendation). Target: 100+ in production.

---

## Running Evals

```bash
# Run all 20 cases
python -m eval.runner

# Filter by module
python -m eval.runner --module prompt_injection
python -m eval.runner --module pii_leakage
python -m eval.runner --module hallucination_risk

# After failures — run error analysis
python -m eval.error_analysis

# Save analysis to file
python -m eval.error_analysis --save results/error_analysis.json
```

---

## Agent-Specific Eval Dimensions

Following the framework's agent-specific evaluation checklist:

| Dimension | Metric | How Measured |
|-----------|--------|-------------|
| Planning Quality | Correct modules selected | PI-003 false positive test |
| Tool Selection | Correct tool used per module | Tool mock fixture results |
| Tool Accuracy | Findings correctly mapped to regulations | PII-005, PII-006 rule_id checks |
| Memory Usage | Cached traces reused across modules | Integration test (future) |
| Reasoning Quality | Hallucination scorer confidence calibration | HALL-001 to HALL-004 |
| Reflection Quality | Citation errors caught | REFL-001, REFL-002, REFL-003 |
| Final Output Quality | PDF completeness | test_pdf_generator.py |

---

## Error Analysis Process

Framework Phase 7 — Never blindly improve prompts:

1. Run `python -m eval.runner`
2. If failures exist, run `python -m eval.error_analysis`
3. Identify the largest failure category
4. Fix the root cause in that category first
5. Re-run evals to confirm improvement
6. Move to next largest category

### Failure Categories

```text
Tool Failure         → Fix tool inputs/outputs
Planning Failure     → Fix module registry or validation
Memory Failure       → Fix caching propagation
Reasoning Failure    → Fix reflection validators
Retrieval Failure    → Fix trace schema or mock data
Hallucination        → Recalibrate local scorer thresholds
Formatting Failure   → Fix output schema
```

---

## Adding New Eval Cases

Add to `eval/dataset.json`:

```json
{
  "id": "PI-006",
  "module": "prompt_injection",
  "category": "role_override",
  "eval_type": "objective_ground_truth",
  "description": "Brief description of what this tests",
  "probe": "The adversarial prompt sent to the target",
  "mock_response": "The mocked response from the target agent",
  "expected": {
    "detected": true,
    "min_confidence": 0.80,
    "severity": "high"
  }
}
```

Then run `python -m eval.runner` to confirm the new case passes.

---

## Production Eval Target

Following the framework progression:
- v1.0: 20 cases (current) ← we are here
- v1.5: 100 cases (add edge cases, borderline inputs, multi-language)
- v2.0: Production dataset (real failing cases from deployed audits)
