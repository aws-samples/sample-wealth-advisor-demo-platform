# PDF generation - markdown to HTML to PDF
import re
from pathlib import Path

from markdown import markdown
from weasyprint import HTML


def markdown_to_html(markdown_text: str, chart_svgs: dict[str, str]) -> str:
    """
    Convert markdown to HTML with embedded CSS and charts.

    Args:
        markdown_text: Report content in markdown format
        chart_svgs: Dict mapping chart names to SVG strings

    Returns:
        Complete HTML document with styling
    """
    # Convert markdown to HTML
    html_body = markdown(markdown_text, extensions=["tables"])

    # Replace chart image references with embedded SVGs
    for chart_name, svg_content in chart_svgs.items():
        # Match ![alt](chart_name.svg) patterns
        pattern = rf'<img alt="[^"]*" src="{chart_name}\.svg" />'
        html_body = re.sub(pattern, svg_content, html_body)

    # Load CSS
    css_path = Path(__file__).parent / "report_style.css"
    css_content = css_path.read_text()

    # Build complete HTML document
    html = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <style>
{css_content}
    </style>
</head>
<body>
{html_body}
</body>
</html>
"""
    return html


def html_to_pdf(html: str) -> bytes:
    """
    Convert HTML to PDF bytes.

    Args:
        html: Complete HTML document

    Returns:
        PDF as bytes
    """
    pdf = HTML(string=html).write_pdf()
    return pdf
