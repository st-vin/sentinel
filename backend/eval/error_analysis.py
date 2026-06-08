"""Error Analysis — Framework Phase 7: Error Analysis.

Never blindly improve prompts.
Collect failures → Categorize → Quantify → Focus on largest category.

Categories (from framework):
  Tool Failure         — tool returned error or unexpected output
  Planning Failure     — wrong module selected or skipped
  Memory Failure       — cached data missing or stale
  Reasoning Failure    — reflection produced wrong verdict
  Retrieval Failure    — no traces or logs available
  Hallucination        — LLM scorer gave wrong confidence
  Formatting Failure   — output missing required fields

Usage:
    python -m eval.error_analysis
    python -m eval.error_analysis --save results.json
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from eval.runner import run_all, EvalResult

FAILURE_CATEGORIES = {
    "prompt_injection": "Tool Failure",
    "pii_leakage": "Tool Failure",
    "hallucination_risk": "Hallucination",
    "reflection": "Reasoning Failure",
    "aggregator": "Tool Failure",
}

REMEDIATION_MAP = {
    "Tool Failure":       "Review tool inputs/outputs. Check mock data matches expected schema.",
    "Planning Failure":   "Verify module registry. Check selected_modules validation.",
    "Memory Failure":     "Check cached tool_results propagation to modules.",
    "Reasoning Failure":  "Review reflection validator logic. Check KNOWN_VALID_RULE_IDS set.",
    "Retrieval Failure":  "Check Arize/Elastic mock data. Verify trace schema.",
    "Hallucination":      "Recalibrate local scorer thresholds. Check KNOWN_FALSE_PATTERNS list.",
    "Formatting Failure": "Check output schema and required fields.",
}


def categorise_failure(result: EvalResult) -> str:
    if result.passed:
        return "PASS"
    return FAILURE_CATEGORIES.get(result.module, "Tool Failure")


def run_analysis(save_path: str = None) -> dict:
    results = run_all()
    failures = [r for r in results if not r.passed]
    total = len(results)

    if not failures:
        print("\n  ✓ No failures to analyse. All eval cases passed.\n")
        return {"total": total, "failures": 0, "categories": {}}

    # Categorise
    categories = Counter(categorise_failure(r) for r in failures)
    total_failures = len(failures)

    # Build report
    analysis = {
        "total_cases": total,
        "total_failures": total_failures,
        "pass_rate": f"{(total - total_failures) / total * 100:.1f}%",
        "categories": dict(categories.most_common()),
        "recommendations": [
            {
                "category": cat,
                "count": count,
                "pct": f"{count / total_failures * 100:.0f}%",
                "focus_first": i == 0,
                "remediation": REMEDIATION_MAP.get(cat, "Review the failing cases."),
            }
            for i, (cat, count) in enumerate(categories.most_common())
        ],
        "failing_cases": [
            {
                "id": r.case_id,
                "module": r.module,
                "category": categorise_failure(r),
                "description": r.description,
                "reason": r.failure_reason,
                "actual": r.actual,
                "expected": r.expected,
            }
            for r in failures
        ],
    }

    # Print report
    print()
    print("=" * 60)
    print("  SENTINEL ERROR ANALYSIS")
    print("  Framework Phase 7 — Error Analysis")
    print("=" * 60)
    print(f"  Pass rate: {analysis['pass_rate']} ({total - total_failures}/{total})")
    print()
    print("  Failure breakdown by category:")
    for rec in analysis["recommendations"]:
        focus = " ← FOCUS HERE" if rec["focus_first"] else ""
        print(f"    {rec['pct']:>4}  {rec['category']} ({rec['count']} cases){focus}")

    print()
    print("  Recommendations (largest failure source first):")
    for rec in analysis["recommendations"]:
        print(f"\n  [{rec['category']}]")
        print(f"    {rec['remediation']}")

    print()
    print("  Failing cases:")
    for case in analysis["failing_cases"]:
        print(f"    [{case['id']}] {case['category']}: {case['reason']}")

    print()

    if save_path:
        Path(save_path).write_text(json.dumps(analysis, indent=2))
        print(f"  Analysis saved to {save_path}")
        print()

    return analysis


def main():
    parser = argparse.ArgumentParser(description="Sentinel error analysis")
    parser.add_argument("--save", help="Save analysis JSON to file")
    args = parser.parse_args()
    run_analysis(save_path=args.save)


if __name__ == "__main__":
    main()
