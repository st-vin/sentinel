"""Evaluation runner — Framework Phase 6: Evaluation Framework.

Runs the 20-case eval dataset against Sentinel's core components and
reports pass/fail with a structured summary.

Usage:
    python -m eval.runner
    python -m eval.runner --verbose
    python -m eval.runner --module prompt_injection
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Optional
from unittest.mock import MagicMock
from dataclasses import dataclass

# Ensure backend root is on path
sys.path.insert(0, str(Path(__file__).parent.parent))

from modules.prompt_injection import _detect_injection_success
from modules.pii_leakage import _scan_text, _redact
from modules.hallucination import _score_response_locally, FAIL_THRESHOLD
from output.aggregator import compute_module_score
from modules.base import Finding
from agent.reflection import reflect, ReflectionResult
from agent.tools.policy_tool import PolicyLibraryTool

DATASET_PATH = Path(__file__).parent / "dataset.json"
POLICY_TOOL = PolicyLibraryTool()


@dataclass
class EvalResult:
    case_id: str
    module: str
    eval_type: str
    description: str
    passed: bool
    actual: dict
    expected: dict
    failure_reason: Optional[str] = None


def _make_finding(d: dict) -> Finding:
    return Finding(
        finding_id=d.get("finding_id", "f_eval"),
        module_id=d.get("module_id", "test"),
        severity=d.get("severity", "high"),
        rule_id=d.get("rule_id", ""),
        rule_name=d.get("rule_name", ""),
        evidence=d.get("evidence", ""),
        recommendation=d.get("recommendation", ""),
        confidence=d.get("confidence", 0.8),
    )


def run_pi_case(case: dict) -> EvalResult:
    """Evaluate a prompt injection case."""
    probe = case["probe"]
    mock_response = case["mock_response"]
    category = case["category"]
    expected = case["expected"]

    is_detected, confidence = _detect_injection_success(mock_response, category)

    actual = {"detected": is_detected, "confidence": confidence}

    fail_reason = None
    if expected["detected"] != is_detected:
        fail_reason = f"Expected detected={expected['detected']}, got {is_detected}"
    elif is_detected and "min_confidence" in expected:
        if confidence < expected["min_confidence"]:
            fail_reason = f"Confidence {confidence:.2f} < required {expected['min_confidence']}"

    return EvalResult(
        case_id=case["id"],
        module=case["module"],
        eval_type=case["eval_type"],
        description=case["description"],
        passed=fail_reason is None,
        actual=actual,
        expected=expected,
        failure_reason=fail_reason,
    )


def run_pii_case(case: dict) -> EvalResult:
    """Evaluate a PII leakage case."""
    text = case["trace_output"]
    expected = case["expected"]

    hits = _scan_text(text)
    detected = len(hits) > 0

    actual: dict = {"detected": detected, "hits": len(hits)}
    fail_reason = None

    if expected["detected"] != detected:
        fail_reason = f"Expected detected={expected['detected']}, got {detected}"
    elif detected:
        if "pii_type" in expected:
            types = {h["pii_type"] for h in hits}
            if expected["pii_type"] not in types:
                fail_reason = f"Expected pii_type={expected['pii_type']}, found {types}"
        if "severity" in expected:
            sevs = {h["severity"] for h in hits}
            if expected["severity"] not in sevs:
                fail_reason = f"Expected severity={expected['severity']}, found {sevs}"
        if "rule_id" in expected:
            rule_ids = {h["rule_id"] for h in hits}
            if expected["rule_id"] not in rule_ids:
                fail_reason = f"Expected rule_id={expected['rule_id']}, found {rule_ids}"
        if "rule_id_prefix" in expected:
            if not any(h["rule_id"].startswith(expected["rule_id_prefix"]) for h in hits):
                fail_reason = f"Expected rule_id prefix={expected['rule_id_prefix']}"
        if expected.get("evidence_redacted") or expected.get("evidence_contains_raw_email") is False:
            for hit in hits:
                raw = hit.get("raw", "")
                redacted = _redact(raw, hit["pii_type"])
                if raw in redacted:
                    fail_reason = f"PII not properly redacted: {raw} still visible"

    return EvalResult(
        case_id=case["id"],
        module=case["module"],
        eval_type=case["eval_type"],
        description=case["description"],
        passed=fail_reason is None,
        actual=actual,
        expected=expected,
        failure_reason=fail_reason,
    )


def run_hall_case(case: dict) -> EvalResult:
    """Evaluate a hallucination risk case."""
    response = case["response"]
    expected = case["expected"]

    score, reason = _score_response_locally(response)
    detected = score < FAIL_THRESHOLD

    actual = {"score": round(score, 3), "detected": detected, "reason": reason}
    fail_reason = None

    if "detected" in expected and expected["detected"] != detected:
        fail_reason = f"Expected detected={expected['detected']}, got {detected} (score={score:.2f})"
    elif "score_below" in expected and score >= expected["score_below"]:
        fail_reason = f"Expected score < {expected['score_below']}, got {score:.2f}"
    elif "score_above" in expected and score <= expected["score_above"]:
        fail_reason = f"Expected score > {expected['score_above']}, got {score:.2f}"

    return EvalResult(
        case_id=case["id"],
        module=case["module"],
        eval_type=case["eval_type"],
        description=case["description"],
        passed=fail_reason is None,
        actual=actual,
        expected=expected,
        failure_reason=fail_reason,
    )


def run_reflection_case(case: dict) -> EvalResult:
    """Evaluate the reflection validator."""
    finding_dict = case["finding"]
    expected = case["expected"]

    finding = _make_finding(finding_dict)
    mock_result = MagicMock()
    mock_result.findings = [finding]

    result = reflect([mock_result], POLICY_TOOL)

    actual = {
        "citation_errors": result.citation_errors,
        "pii_leaks": result.pii_leaks,
        "quality": result.reflection_quality,
    }

    fail_reason = None
    if "citation_error" in expected:
        if expected["citation_error"] and result.citation_errors == 0:
            fail_reason = "Expected citation error, but none found"
        elif not expected["citation_error"] and result.citation_errors > 0:
            fail_reason = f"Unexpected citation errors: {result.citation_errors}"
    if "pii_leak_detected" in expected:
        if expected["pii_leak_detected"] and result.pii_leaks == 0:
            fail_reason = "Expected PII leak in evidence, but none detected"
        elif not expected["pii_leak_detected"] and result.pii_leaks > 0:
            fail_reason = f"Unexpected PII detected in evidence: {result.pii_leaks}"
    if "quality" in expected and result.reflection_quality != expected["quality"]:
        fail_reason = f"Expected quality={expected['quality']}, got {result.reflection_quality}"
    if "quality_not" in expected and result.reflection_quality == expected["quality_not"]:
        fail_reason = f"Expected quality != {expected['quality_not']}, but got it anyway"

    return EvalResult(
        case_id=case["id"],
        module=case["module"],
        eval_type=case["eval_type"],
        description=case["description"],
        passed=fail_reason is None,
        actual=actual,
        expected=expected,
        failure_reason=fail_reason,
    )


def run_score_case(case: dict) -> EvalResult:
    """Evaluate the aggregation scorer."""
    findings = [_make_finding(f) for f in case["findings"]]
    score = compute_module_score(findings)
    expected = case["expected"]

    passed = score == expected["score"]
    return EvalResult(
        case_id=case["id"],
        module=case["module"],
        eval_type=case["eval_type"],
        description=case["description"],
        passed=passed,
        actual={"score": score},
        expected=expected,
        failure_reason=None if passed else f"Expected score={expected['score']}, got {score}",
    )


RUNNERS = {
    "prompt_injection": run_pi_case,
    "pii_leakage": run_pii_case,
    "hallucination_risk": run_hall_case,
    "reflection": run_reflection_case,
    "aggregator": run_score_case,
}


def run_all(module_filter: Optional[str] = None, verbose: bool = False) -> list[EvalResult]:
    with open(DATASET_PATH) as f:
        dataset = json.load(f)

    cases = dataset["cases"]
    if module_filter:
        cases = [c for c in cases if c["module"] == module_filter]

    results = []
    for case in cases:
        runner = RUNNERS.get(case["module"])
        if not runner:
            continue
        try:
            result = runner(case)
        except Exception as exc:
            result = EvalResult(
                case_id=case["id"],
                module=case["module"],
                eval_type=case["eval_type"],
                description=case["description"],
                passed=False,
                actual={},
                expected=case["expected"],
                failure_reason=f"EXCEPTION: {exc}",
            )
        results.append(result)

    return results


def print_report(results: list[EvalResult], verbose: bool = False) -> None:
    passed = sum(1 for r in results if r.passed)
    failed = sum(1 for r in results if not r.passed)
    total = len(results)
    pct = round(passed / total * 100) if total else 0

    print()
    print("=" * 60)
    print(f"  SENTINEL EVALUATION REPORT")
    print(f"  Framework Phase 6 — Evaluation Framework")
    print("=" * 60)
    print(f"  Total cases: {total}")
    print(f"  Passed:      {passed} ({pct}%)")
    print(f"  Failed:      {failed}")
    print("=" * 60)

    # Group by module
    modules = {}
    for r in results:
        modules.setdefault(r.module, []).append(r)

    for mod, mod_results in modules.items():
        mod_passed = sum(1 for r in mod_results if r.passed)
        print(f"\n  [{mod.upper()}] {mod_passed}/{len(mod_results)} passed")
        for r in mod_results:
            icon = "✓" if r.passed else "✗"
            print(f"    {icon} [{r.case_id}] {r.description[:60]}")
            if not r.passed and (verbose or True):
                print(f"        → {r.failure_reason}")

    print()
    if failed == 0:
        print("  ✓ All eval cases passed.")
    else:
        print(f"  ✗ {failed} case(s) failed. Run error analysis: python -m eval.error_analysis")
    print()

    return passed, failed


def main():
    parser = argparse.ArgumentParser(description="Sentinel evaluation runner")
    parser.add_argument("--module", help="Filter by module name")
    parser.add_argument("--verbose", action="store_true", help="Verbose output")
    args = parser.parse_args()

    start = time.monotonic()
    results = run_all(module_filter=args.module, verbose=args.verbose)
    elapsed = time.monotonic() - start

    passed, failed = print_report(results, verbose=args.verbose)
    print(f"  Completed in {elapsed:.1f}s")
    print()

    sys.exit(0 if failed == 0 else 1)


if __name__ == "__main__":
    main()
