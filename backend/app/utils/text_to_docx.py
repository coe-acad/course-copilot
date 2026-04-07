"""
Utility helpers to convert rich text (markdown) into DOCX documents.
"""

from __future__ import annotations

import re
from io import BytesIO
from typing import List, Optional, Union
from pathlib import Path

from docx import Document
from docx.shared import Pt, RGBColor, Inches
from docx.oxml.ns import qn
from docx.oxml import OxmlElement

DocxBytes = bytes
PathLike = Union[str, Path]


def text_to_docx(
    text: str,
    *,
    output_path: Optional[PathLike] = None,
) -> Union[DocxBytes, Path]:
    """Convert plain/markdown text into a professionally formatted DOCX document."""

    if not text:
        raise ValueError("text must be a non-empty string")

    doc = Document()

    # Set default page margins
    for section in doc.sections:
        section.top_margin = Inches(1.0)
        section.bottom_margin = Inches(1.0)
        section.left_margin = Inches(0.85)
        section.right_margin = Inches(0.85)

    _apply_default_styles(doc)
    _markdown_to_docx(doc, text)

    buffer = BytesIO()
    doc.save(buffer)
    docx_bytes = buffer.getvalue()

    if output_path:
        path_obj = Path(output_path)
        path_obj.write_bytes(docx_bytes)
        return path_obj

    return docx_bytes


# ---------------------------------------------------------------------------
# Style helpers
# ---------------------------------------------------------------------------

def _apply_default_styles(doc: Document):
    """Configure the document's built-in styles."""
    style = doc.styles["Normal"]
    font = style.font
    font.name = "Calibri"
    font.size = Pt(11)
    font.color.rgb = RGBColor(0x1F, 0x29, 0x37)


def _set_paragraph_color(para, rgb: RGBColor):
    for run in para.runs:
        run.font.color.rgb = rgb


# ---------------------------------------------------------------------------
# Markdown parser
# ---------------------------------------------------------------------------

def _markdown_to_docx(doc: Document, text: str):
    """Parse markdown blocks and add them to the document."""
    for block in _split_blocks(text):
        b_type = block.get("type")

        if b_type == "header1":
            p = doc.add_heading(block["text"], level=1)
            p.runs[0].font.color.rgb = RGBColor(0x0F, 0x17, 0x2A)
            p.runs[0].font.size = Pt(20)
            p.runs[0].bold = True

        elif b_type == "header2":
            p = doc.add_heading(block["text"], level=2)
            p.runs[0].font.color.rgb = RGBColor(0x1F, 0x29, 0x37)
            p.runs[0].font.size = Pt(16)
            p.runs[0].bold = True

        elif b_type == "header3":
            p = doc.add_heading(block["text"], level=3)
            p.runs[0].font.color.rgb = RGBColor(0x37, 0x41, 0x51)
            p.runs[0].font.size = Pt(13)
            p.runs[0].bold = True

        elif b_type == "ul":
            for item in block.get("items", []):
                p = doc.add_paragraph(style="List Bullet")
                _add_inline_runs(p, item)

        elif b_type == "ol":
            for item in block.get("items", []):
                p = doc.add_paragraph(style="List Number")
                _add_inline_runs(p, item)

        elif b_type == "code":
            p = doc.add_paragraph()
            run = p.add_run(block["text"])
            run.font.name = "Courier New"
            run.font.size = Pt(10)
            run.font.color.rgb = RGBColor(0x1F, 0x29, 0x37)
            # Light grey shading
            _shade_paragraph(p, "F3F4F6")

        elif b_type == "quote":
            quote_text = " ".join(block.get("lines", []))
            p = doc.add_paragraph()
            p.paragraph_format.left_indent = Inches(0.4)
            run = p.add_run(quote_text)
            run.font.italic = True
            run.font.color.rgb = RGBColor(0x6B, 0x72, 0x80)

        elif b_type == "table":
            headers = block.get("headers", [])
            rows = block.get("rows", [])
            col_count = max(len(headers), max((len(r) for r in rows), default=0))
            if col_count == 0:
                continue
            table = doc.add_table(rows=1 + len(rows), cols=col_count)
            table.style = "Table Grid"

            # Header row
            hdr_row = table.rows[0]
            for ci, cell_text in enumerate(headers):
                cell = hdr_row.cells[ci]
                p = cell.paragraphs[0]
                _add_inline_runs(p, cell_text.strip())
                for run in p.runs:
                    run.bold = True
                    run.font.color.rgb = RGBColor(0x1F, 0x29, 0x37)
                _shade_cell(cell, "F9FAFB")

            # Data rows
            for ri, row_cells in enumerate(rows):
                tbl_row = table.rows[ri + 1]
                for ci in range(col_count):
                    cell_text = row_cells[ci].strip() if ci < len(row_cells) else ""
                    p = tbl_row.cells[ci].paragraphs[0]
                    _add_inline_runs(p, cell_text)

        elif b_type == "rule":
            _add_horizontal_rule(doc)

        else:
            # Regular paragraph
            lines = block.get("lines", [])
            paragraph_text = " ".join(line.strip() for line in lines if line.strip())
            if paragraph_text:
                p = doc.add_paragraph()
                _add_inline_runs(p, paragraph_text)


# ---------------------------------------------------------------------------
# Inline markdown → runs
# ---------------------------------------------------------------------------

def _add_inline_runs(para, text: str):
    """Parse inline markdown and add styled runs to a paragraph."""
    # Pattern: **bold**, *italic*, `code`, ***bold+italic***
    pattern = re.compile(
        r'(\*\*\*(.+?)\*\*\*)'   # bold + italic
        r'|(\*\*(.+?)\*\*)'       # bold
        r'|(\*(.+?)\*)'           # italic
        r'|(`([^`]+)`)'           # inline code
        r'|(~~(.+?)~~)'           # strikethrough
    )

    pos = 0
    for m in pattern.finditer(text):
        # Add plain text before this match
        if m.start() > pos:
            run = para.add_run(text[pos:m.start()])
            run.font.color.rgb = RGBColor(0x37, 0x41, 0x51)

        if m.group(1):  # bold + italic
            run = para.add_run(m.group(2))
            run.bold = True
            run.italic = True
        elif m.group(3):  # bold
            run = para.add_run(m.group(4))
            run.bold = True
        elif m.group(5):  # italic
            run = para.add_run(m.group(6))
            run.italic = True
        elif m.group(7):  # inline code
            run = para.add_run(m.group(8))
            run.font.name = "Courier New"
            run.font.size = Pt(10)
            run.font.color.rgb = RGBColor(0xDC, 0x26, 0x26)
        elif m.group(9):  # strikethrough
            run = para.add_run(m.group(10))
            # python-docx doesn't have a direct strikethrough property on font
            # but we can set it via the XML
            run.font._element.get_or_add_rPr().append(OxmlElement('w:strike'))

        pos = m.end()

    # Remaining plain text
    if pos < len(text):
        run = para.add_run(text[pos:])
        run.font.color.rgb = RGBColor(0x37, 0x41, 0x51)


# ---------------------------------------------------------------------------
# Block parser (reuses logic from text_to_pdf.py)
# ---------------------------------------------------------------------------

def _split_blocks(text: str) -> List[dict]:
    blocks: List[dict] = []
    lines = text.splitlines()
    idx = 0
    total = len(lines)

    while idx < total:
        line = lines[idx].rstrip("\n")
        stripped = line.strip()

        # Code blocks
        if stripped.startswith("```"):
            idx += 1
            code_lines = []
            while idx < total and not lines[idx].strip().startswith("```"):
                code_lines.append(lines[idx].rstrip())
                idx += 1
            if idx < total:
                idx += 1
            blocks.append({"type": "code", "text": "\n".join(code_lines)})
            continue

        if stripped == "":
            idx += 1
            continue

        if stripped in {"---", "***", "___"} or re.match(r"^-{3,}$|^\*{3,}$|^_{3,}$", stripped):
            blocks.append({"type": "rule"})
            idx += 1
            continue

        if stripped.startswith(">"):
            quote_lines = []
            while idx < total and lines[idx].strip().startswith(">"):
                quote_lines.append(lines[idx].strip()[1:].strip())
                idx += 1
            blocks.append({"type": "quote", "lines": quote_lines})
            continue

        header_match = re.match(r"^(#{3,6})\s+(.*)", stripped)
        if header_match:
            blocks.append({"type": "header3", "text": header_match.group(2).strip()})
            idx += 1
            continue

        header2_match = re.match(r"^#{2}\s+(.*)", stripped)
        if header2_match:
            blocks.append({"type": "header2", "text": header2_match.group(1).strip()})
            idx += 1
            continue

        header1_match = re.match(r"^#\s+(.*)", stripped)
        if header1_match:
            blocks.append({"type": "header1", "text": header1_match.group(1).strip()})
            idx += 1
            continue

        if re.match(r"^\s*[-*+]\s+", line) and not re.match(r"^\d+\s+", stripped):
            items: List[str] = []
            while idx < total:
                current = lines[idx]
                current_stripped = current.strip()
                if current_stripped == "":
                    idx += 1
                    continue
                if not re.match(r"^\s*[-*+]\s+", current) or re.match(r"^\d+\s+", current_stripped):
                    break
                items.append(re.sub(r"^\s*[-*+]\s+", "", current).strip())
                idx += 1
            if items:
                blocks.append({"type": "ul", "items": items})
            continue

        if re.match(r"^\s*\d+\.\s+", line):
            items = []
            while idx < total:
                current = lines[idx]
                current_stripped = current.strip()
                if current_stripped == "":
                    idx += 1
                    continue
                if not re.match(r"^\s*\d+\.\s+", current):
                    break
                items.append(re.sub(r"^\s*\d+\.\s+", "", current).strip())
                idx += 1
            if items:
                blocks.append({"type": "ol", "items": items})
            continue

        # Markdown tables — lines starting with |
        if stripped.startswith("|"):
            table_lines = []
            while idx < total and lines[idx].strip().startswith("|"):
                table_lines.append(lines[idx].strip())
                idx += 1

            def _parse_row(row_str):
                # Strip leading/trailing pipes then split on |
                cells = row_str.strip().strip("|").split("|")
                return [c.strip() for c in cells]

            def _is_separator(row_str):
                return all(re.match(r"^:?-+:?$", c.strip()) for c in row_str.strip().strip("|").split("|") if c.strip())

            headers = []
            rows = []
            for i, tl in enumerate(table_lines):
                if i == 0:
                    headers = _parse_row(tl)
                elif _is_separator(tl):
                    continue
                else:
                    rows.append(_parse_row(tl))

            if headers:
                blocks.append({"type": "table", "headers": headers, "rows": rows})
            continue

        paragraph_lines = [line]
        idx += 1
        while idx < total:
            lookahead = lines[idx]
            stripped_la = lookahead.strip()
            if not stripped_la:
                idx += 1
                break
            if (
                stripped_la.startswith("```")
                or stripped_la in {"---", "***", "___"}
                or (re.match(r"^\s*[-*+]\s+", lookahead) and not re.match(r"^\d+\s+", stripped_la))
                or re.match(r"^\s*\d+\.\s+", lookahead)
                or stripped_la.startswith("#")
                or stripped_la.startswith(">")
                or stripped_la.startswith("|")
            ):
                break
            paragraph_lines.append(lookahead)
            idx += 1
        blocks.append({"type": "paragraph", "lines": paragraph_lines})

    return blocks


# ---------------------------------------------------------------------------
# XML helpers
# ---------------------------------------------------------------------------

def _shade_paragraph(para, hex_color: str):
    """Add a background shading to a paragraph."""
    pPr = para._p.get_or_add_pPr()
    shd = OxmlElement('w:shd')
    shd.set(qn('w:val'), 'clear')
    shd.set(qn('w:color'), 'auto')
    shd.set(qn('w:fill'), hex_color)
    pPr.append(shd)


def _shade_cell(cell, hex_color: str):
    """Add a background shading to a table cell."""
    tc = cell._tc
    tcPr = tc.get_or_add_tcPr()
    shd = OxmlElement('w:shd')
    shd.set(qn('w:val'), 'clear')
    shd.set(qn('w:color'), 'auto')
    shd.set(qn('w:fill'), hex_color)
    tcPr.append(shd)


def _add_horizontal_rule(doc: Document):
    """Add a horizontal rule (border bottom on an empty paragraph)."""
    p = doc.add_paragraph()
    pPr = p._p.get_or_add_pPr()
    pBdr = OxmlElement('w:pBdr')
    bottom = OxmlElement('w:bottom')
    bottom.set(qn('w:val'), 'single')
    bottom.set(qn('w:sz'), '6')
    bottom.set(qn('w:space'), '1')
    bottom.set(qn('w:color'), 'D1D5DB')
    pBdr.append(bottom)
    pPr.append(pBdr)
