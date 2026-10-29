"""Render DD report to HTML and PDF."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from jinja2 import Environment, FileSystemLoader

_TEMPLATE_DIR = Path(__file__).parent / "templates"
_env = Environment(loader=FileSystemLoader(str(_TEMPLATE_DIR)), autoescape=False)


def render_html(report: dict, portfolio_name: str = "", manager_name: str = "") -> str:
    template = _env.get_template("dd_report.html")
    return template.render(
        portfolio_name=portfolio_name or report.get("portfolio_name", ""),
        manager_name=manager_name or report.get("manager_name", ""),
        overall_score=report.get("overall_score", 0),
        recommendation=report.get("recommendation", ""),
        executive_summary=report.get("narrative", report.get("executive_summary", "")),
        category_summaries=report.get("category_summaries", []),
        assessments=report.get("assessments", []),
        hitl_reasons=report.get("hitl_reasons", []),
        sections=report.get("sections", []),
        generated_at=report.get("generated_at", datetime.utcnow().isoformat()),
    )


def render_pdf(report: dict, portfolio_name: str = "", manager_name: str = "") -> bytes:
    try:
        from weasyprint import HTML
    except ImportError:
        return b""

    html_content = render_html(report, portfolio_name, manager_name)
    return HTML(string=html_content).write_pdf()
