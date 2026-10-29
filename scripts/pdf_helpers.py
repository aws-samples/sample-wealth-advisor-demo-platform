"""Shared PDF generation helpers using fpdf2."""

import os
from fpdf import FPDF

OUTPUT_DIR = os.path.join(
    os.path.dirname(__file__),
    "..",
    "packages",
    "portfolio_dd",
    "source_docs",
)

os.makedirs(OUTPUT_DIR, exist_ok=True)


def _latin1_safe(text: str) -> str:
    """Replace unicode chars that can't be encoded in latin-1."""
    replacements = {
        "—": "--",   # em dash
        "–": "-",    # en dash
        "‘": "'",    # left single quote
        "’": "'",    # right single quote
        "“": '"',    # left double quote
        "”": '"',    # right double quote
        "•": "-",    # bullet
        "…": "...",  # ellipsis
        " ": " ",    # non-breaking space
    }
    for k, v in replacements.items():
        text = text.replace(k, v)
    return text


class DocPDF(FPDF):
    """Base PDF class with consistent formatting."""

    def __init__(self, title: str, subtitle: str = ""):
        super().__init__()
        self.doc_title = _latin1_safe(title)
        self.doc_subtitle = _latin1_safe(subtitle)
        self.set_auto_page_break(auto=True, margin=20)

    def header(self):
        self.set_font("Helvetica", "B", 9)
        self.set_text_color(100, 100, 100)
        self.cell(0, 5, self.doc_title, align="R")
        self.ln(8)

    def footer(self):
        self.set_y(-15)
        self.set_font("Helvetica", "I", 8)
        self.set_text_color(128, 128, 128)
        self.cell(0, 10, f"Page {self.page_no()}", align="C")

    def cover_page(self, fund_name: str, doc_type: str, date: str, manager: str):
        fund_name = _latin1_safe(fund_name)
        doc_type = _latin1_safe(doc_type)
        date = _latin1_safe(date)
        manager = _latin1_safe(manager)
        self.add_page()
        self.ln(40)
        self.set_font("Helvetica", "B", 24)
        self.set_text_color(0, 51, 102)
        self.multi_cell(0, 12, fund_name, align="C")
        self.ln(5)
        self.set_font("Helvetica", "", 16)
        self.set_text_color(80, 80, 80)
        self.multi_cell(0, 10, doc_type, align="C")
        self.ln(10)
        self.set_font("Helvetica", "", 12)
        self.cell(0, 8, date, align="C")
        self.ln(20)
        self.set_font("Helvetica", "I", 11)
        self.cell(0, 8, f"Issued by: {manager}", align="C")
        self.ln(30)
        self.set_font("Helvetica", "", 9)
        self.set_text_color(120, 120, 120)
        self.multi_cell(
            0,
            5,
            "SAMPLE DOCUMENT FOR DEMONSTRATION PURPOSES ONLY. "
            "This document contains synthetic data inspired by publicly available "
            "information and does not constitute financial advice.",
            align="C",
        )

    def section(self, title: str):
        self.ln(4)
        self.set_font("Helvetica", "B", 13)
        self.set_text_color(0, 51, 102)
        self.cell(0, 8, _latin1_safe(title))
        self.ln(10)
        self.set_text_color(0, 0, 0)

    def subsection(self, title: str):
        self.ln(2)
        self.set_font("Helvetica", "B", 11)
        self.set_text_color(40, 40, 40)
        self.cell(0, 7, _latin1_safe(title))
        self.ln(8)
        self.set_text_color(0, 0, 0)

    def body(self, text: str):
        self.set_font("Helvetica", "", 10)
        self.multi_cell(0, 5, _latin1_safe(text))
        self.ln(3)

    def bullet(self, text: str):
        self.set_font("Helvetica", "", 10)
        x = self.get_x()
        self.cell(5, 5, "-")
        self.multi_cell(0, 5, _latin1_safe(text))
        self.set_x(x)

    def table_row(self, label: str, value: str):
        self.set_font("Helvetica", "B", 10)
        self.cell(60, 6, _latin1_safe(label))
        self.set_font("Helvetica", "", 10)
        self.cell(0, 6, _latin1_safe(value))
        self.ln(7)

    def save(self, filename: str):
        path = os.path.join(OUTPUT_DIR, filename)
        self.output(path)
        print(f"  Created: {filename} ({self.page_no()} pages)")
        return path
