"""PDF report generator using WeasyPrint + Jinja2."""
from __future__ import annotations

import os
import structlog
from datetime import datetime
from pathlib import Path

from jinja2 import Environment, FileSystemLoader

log = structlog.get_logger()

TEMPLATES_DIR = Path(__file__).parent / "templates"

SEVERITY_COLOURS = {
    "critical": "#DC2626",
    "high": "#EA580C",
    "medium": "#D97706",
    "low": "#16A34A",
    "info": "#6B7280",
}

SCORE_COLOUR_MAP = [
    (90, "#15803D"),
    (75, "#16A34A"),
    (60, "#D97706"),
    (40, "#EA580C"),
    (0,  "#DC2626"),
]


def _score_colour(score: int) -> str:
    for threshold, colour in SCORE_COLOUR_MAP:
        if score >= threshold:
            return colour
    return "#DC2626"


def _score_label(score: int) -> str:
    if score >= 90:
        return "PASS"
    if score >= 75:
        return "LOW RISK"
    if score >= 60:
        return "MEDIUM RISK"
    if score >= 40:
        return "HIGH RISK"
    return "CRITICAL RISK"


def generate_pdf(report: dict) -> bytes:
    """Generate a PDF compliance report from an AuditReport dict."""
    env = Environment(loader=FileSystemLoader(str(TEMPLATES_DIR)), autoescape=True)
    env.globals["severity_colour"] = lambda s: SEVERITY_COLOURS.get(s, "#6B7280")
    env.globals["score_colour"] = _score_colour
    env.globals["score_label"] = _score_label

    template = env.get_template("report.html")

    all_findings = []
    for module in report.get("modules", []):
        for finding in module.get("findings", []):
            finding["module_id"] = module["module_id"]
            all_findings.append(finding)

    critical_count = sum(1 for f in all_findings if f.get("severity") == "critical")
    high_count = sum(1 for f in all_findings if f.get("severity") == "high")
    medium_count = sum(1 for f in all_findings if f.get("severity") == "medium")
    low_count = sum(1 for f in all_findings if f.get("severity") in ("low", "info"))

    html_content = template.render(
        report=report,
        all_findings=all_findings,
        critical_count=critical_count,
        high_count=high_count,
        medium_count=medium_count,
        low_count=low_count,
        generated_at=datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC"),
        score_colour=_score_colour(report.get("overall_score", 0)),
        score_label=_score_label(report.get("overall_score", 0)),
    )

    try:
        from weasyprint import HTML, CSS
        pdf_bytes = HTML(string=html_content, base_url=str(TEMPLATES_DIR)).write_pdf()
        log.info("pdf_generator.generated", size=len(pdf_bytes))
        return pdf_bytes
    except Exception as exc:
        log.error("pdf_generator.weasyprint_failed", error=str(exc))
        return _fallback_pdf(html_content)


def _fallback_pdf(html_content: str) -> bytes:
    """Fallback: return HTML as bytes if WeasyPrint unavailable."""
    log.warning("pdf_generator.using_html_fallback")
    return html_content.encode("utf-8")
