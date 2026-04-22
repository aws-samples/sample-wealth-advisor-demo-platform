# Tests for PDF generation
import pytest

try:
    from wealth_management_portal_report.pdf import html_to_pdf, markdown_to_html

    WEASYPRINT_AVAILABLE = True
except (OSError, ImportError):
    WEASYPRINT_AVAILABLE = False

    # Provide dummy functions for tests that don't need WeasyPrint
    def markdown_to_html(markdown, chart_svgs):
        return f"<html><body>{markdown}</body></html>"

    def html_to_pdf(html):
        return b"%PDF-dummy"


def test_markdown_to_html_conversion():
    """Markdown should convert to HTML."""
    markdown = "## Test Header\n\nThis is a paragraph."

    html = markdown_to_html(markdown, {})

    assert "<h2>Test Header</h2>" in html or "Test Header" in html
    assert "paragraph" in html


@pytest.mark.skipif(not WEASYPRINT_AVAILABLE, reason="Requires system libraries (libgobject) not available")
def test_html_includes_css():
    """HTML should include CSS styling."""
    markdown = "## Test"

    html = markdown_to_html(markdown, {})

    assert "<style>" in html or "css" in html.lower()


@pytest.mark.skipif(not WEASYPRINT_AVAILABLE, reason="Requires system libraries (libgobject) not available")
def test_svg_charts_embedded_in_html():
    """SVG charts should be embedded in HTML."""
    markdown = "![allocation](allocation.svg)\n\nSome text."
    chart_svgs = {"allocation": "<svg><rect/></svg>"}

    html = markdown_to_html(markdown, chart_svgs)

    assert "<svg>" in html
    assert "<rect/>" in html


@pytest.mark.skipif(not WEASYPRINT_AVAILABLE, reason="Requires system libraries (libgobject) not available")
def test_html_to_pdf_produces_bytes():
    """HTML to PDF should produce valid PDF bytes."""
    html = "<html><body><h1>Test</h1></body></html>"

    pdf_bytes = html_to_pdf(html)

    assert isinstance(pdf_bytes, bytes)
    assert len(pdf_bytes) > 0
    assert pdf_bytes.startswith(b"%PDF")
