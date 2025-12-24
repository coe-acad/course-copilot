"""
Utility helpers to convert rich text (markdown) into PDF documents.

Enhanced version that faithfully renders markdown with clean formatting.
"""

from __future__ import annotations

import argparse
import re
from datetime import datetime
from io import BytesIO
from pathlib import Path
from typing import List, Optional, Union

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_JUSTIFY
from reportlab.lib.pagesizes import LETTER
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import (
    HRFlowable,
    ListFlowable,
    ListItem,
    Paragraph,
    Preformatted,
    SimpleDocTemplate,
    Spacer,
)

PdfBytes = bytes
PathLike = Union[str, Path]

_DEFAULT_FONT_NAME = "Helvetica"
_DEFAULT_FONT_SIZE = 11
_DEFAULT_PAGE_SIZE = LETTER
_H_MARGIN = 0.85 * inch
_V_MARGIN = 1.0 * inch
_PARAGRAPH_SPACING = 0.12 * inch
_DEFAULT_TITLE = "Document"


def text_to_pdf(
    text: str,
    *,
    output_path: Optional[PathLike] = None,
    font_name: str = _DEFAULT_FONT_NAME,
    font_size: int = _DEFAULT_FONT_SIZE,
    page_size=_DEFAULT_PAGE_SIZE,
) -> Union[PdfBytes, Path]:
    """Convert plain/markdown text into a professionally formatted PDF with proper word wrapping."""

    if not text:
        raise ValueError("text must be a non-empty string")

    title = _extract_title(text) or _DEFAULT_TITLE
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=page_size,
        leftMargin=_H_MARGIN,
        rightMargin=_H_MARGIN,
        topMargin=_V_MARGIN,
        bottomMargin=_V_MARGIN,
        title=title,
    )

    styles = _build_styles(font_name, font_size)
    flowables = _markdown_to_flowables(text, styles, title)

    decorator = lambda canvas, doc_: _decorate_page(canvas, doc_, title)
    doc.build(flowables, onFirstPage=decorator, onLaterPages=decorator)

    pdf_bytes = buffer.getvalue()

    if output_path:
        path_obj = Path(output_path)
        path_obj.write_bytes(pdf_bytes)
        return path_obj

    return pdf_bytes


def _cli() -> None:
    """Simple CLI to help with manual testing."""

    parser = argparse.ArgumentParser(
        description="Render plain/markdown text into a PDF with professional formatting."
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--text", help="Literal text to render into the PDF.")
    group.add_argument(
        "--input-path",
        type=Path,
        help="Path to a UTF-8 text file whose contents will become the PDF.",
    )
    parser.add_argument(
        "--output-path",
        type=Path,
        required=True,
        help="Where to write the generated PDF.",
    )
    args = parser.parse_args()

    content = args.text or ""
    if args.input_path:
        content = args.input_path.read_text(encoding="utf-8")

    result_path = text_to_pdf(content, output_path=args.output_path)
    print(f"PDF written to {result_path}")


# ---------------------------------------------------------------------------
# Layout helpers
# ---------------------------------------------------------------------------

def _build_styles(font_name: str, font_size: int):
    """Build comprehensive styles with proper word wrapping settings."""
    base_styles = getSampleStyleSheet()
    
    body = ParagraphStyle(
        "Body",
        parent=base_styles["Normal"],
        fontName=font_name,
        fontSize=font_size,
        leading=font_size * 1.5,
        spaceAfter=0.1 * inch,
        spaceBefore=0,
        alignment=TA_LEFT,
        wordWrap='LTR',
        splitLongWords=True,
        textColor=colors.HexColor("#1f2937"),
    )
    
    header1 = ParagraphStyle(
        "Header1",
        parent=body,
        fontSize=font_size + 6,
        leading=(font_size + 6) * 1.4,
        spaceAfter=0.15 * inch,
        spaceBefore=0.25 * inch,
        textColor=colors.HexColor("#0f172a"),
        fontName=f"{font_name}-Bold",
        alignment=TA_LEFT,
        keepWithNext=True,
        wordWrap='LTR',
    )
    
    header2 = ParagraphStyle(
        "Header2",
        parent=body,
        fontSize=font_size + 4,
        leading=(font_size + 4) * 1.4,
        textColor=colors.HexColor("#1f2937"),
        spaceBefore=0.2 * inch,
        spaceAfter=0.12 * inch,
        fontName=f"{font_name}-Bold",
        alignment=TA_LEFT,
        keepWithNext=True,
        wordWrap='LTR',
    )
    
    header3 = ParagraphStyle(
        "Header3",
        parent=body,
        fontSize=font_size + 2,
        leading=(font_size + 2) * 1.4,
        textColor=colors.HexColor("#374151"),
        spaceBefore=0.15 * inch,
        spaceAfter=0.1 * inch,
        fontName=f"{font_name}-Bold",
        alignment=TA_LEFT,
        keepWithNext=True,
        wordWrap='LTR',
    )
    
    bullet_style = ParagraphStyle(
        "Bullets",
        parent=body,
        leftIndent=0,
        bulletIndent=0,
        firstLineIndent=0,
        alignment=TA_LEFT,
        wordWrap='LTR',
        splitLongWords=True,
        spaceAfter=0.05 * inch,
    )
    
    numbered_style = ParagraphStyle(
        "Numbered",
        parent=body,
        leftIndent=18,
        alignment=TA_LEFT,
        wordWrap='LTR',
        splitLongWords=True,
        spaceAfter=0.05 * inch,
    )
    
    title_style = ParagraphStyle(
        "Title",
        parent=body,
        fontSize=font_size + 10,
        leading=(font_size + 10) * 1.3,
        alignment=TA_CENTER,
        spaceAfter=0.3 * inch,
        fontName=f"{font_name}-Bold",
        textColor=colors.HexColor("#0f172a"),
        wordWrap='LTR',
    )
    
    code_style = ParagraphStyle(
        "Code",
        parent=body,
        fontName="Courier",
        fontSize=font_size - 1,
        leading=(font_size - 1) * 1.4,
        backColor=colors.HexColor("#f9fafb"),
        borderColor=colors.HexColor("#e5e7eb"),
        borderWidth=1,
        borderPadding=8,
        leftIndent=8,
        rightIndent=8,
        alignment=TA_LEFT,
        wordWrap='LTR',
        splitLongWords=True,
        textColor=colors.HexColor("#1f2937"),
    )
    
    quote_style = ParagraphStyle(
        "Quote",
        parent=body,
        fontSize=font_size,
        leading=font_size * 1.5,
        leftIndent=0.4 * inch,
        rightIndent=0.2 * inch,
        borderColor=colors.HexColor("#3b82f6"),
        borderWidth=3,
        borderPadding=10,
        textColor=colors.HexColor("#374151"),
        fontName=f"{font_name}-Oblique",
        alignment=TA_LEFT,
        wordWrap='LTR',
        splitLongWords=True,
    )
    
    return {
        "body": body,
        "header1": header1,
        "header2": header2,
        "header3": header3,
        "bullet": bullet_style,
        "numbered": numbered_style,
        "title": title_style,
        "code": code_style,
        "quote": quote_style,
    }


def _decorate_page(canvas, doc, title: str):
    """Add professional headers and footers to each page."""
    canvas.saveState()
    width, height = doc.pagesize

    # Header
    canvas.setFont("Helvetica-Bold", 9)
    canvas.setFillColor(colors.HexColor("#374151"))
    canvas.drawString(_H_MARGIN, height - 0.6 * inch, title or _DEFAULT_TITLE)

    # Header line
    canvas.setStrokeColor(colors.HexColor("#d1d5db"))
    canvas.setLineWidth(0.8)
    canvas.line(_H_MARGIN, height - 0.65 * inch, width - _H_MARGIN, height - 0.65 * inch)

    # Footer
    canvas.setFont("Helvetica", 8)
    canvas.setFillColor(colors.HexColor("#6b7280"))
    canvas.drawString(
        _H_MARGIN,
        0.55 * inch,
        datetime.utcnow().strftime("Generated on %B %d, %Y at %H:%M UTC"),
    )
    canvas.drawRightString(
        width - _H_MARGIN,
        0.55 * inch,
        f"Page {doc.page}",
    )
    
    # Footer line
    canvas.setStrokeColor(colors.HexColor("#e5e7eb"))
    canvas.setLineWidth(0.5)
    canvas.line(_H_MARGIN, 0.75 * inch, width - _H_MARGIN, 0.75 * inch)
    
    canvas.restoreState()


# ---------------------------------------------------------------------------
# Markdown-ish parsing
# ---------------------------------------------------------------------------

def _markdown_to_flowables(text: str, styles: dict, title: str) -> List:
    """Convert markdown text to ReportLab flowables, preserving original formatting."""
    flowables: List = []
    
    # Track global counter for ordered lists to maintain sequential numbering
    ol_counter = 1
    
    # Don't add title separately - it will be in the content
    
    for block in _split_blocks(text):
        b_type = block.get("type")

        if b_type == "header1":
            flowables.append(Paragraph(_convert_inline(block["text"]), styles["header1"]))
            
        elif b_type == "header2":
            flowables.append(Paragraph(_convert_inline(block["text"]), styles["header2"]))
            
        elif b_type == "header3":
            flowables.append(Paragraph(_convert_inline(block["text"]), styles["header3"]))
            
        elif b_type in {"ul", "ol"}:
            items = block.get("items", [])
            
            if b_type == "ol":
                # For ordered lists, use global counter to maintain sequential numbering
                for item_text in items:
                    # Create a paragraph with sequential numbering
                    numbered_text = f"{ol_counter}. {_convert_inline(item_text)}"
                    flowables.append(Paragraph(numbered_text, styles["numbered"]))
                    ol_counter += 1
            else:
                # For unordered lists, use ListFlowable with bullet points
                list_items = [
                    ListItem(Paragraph(_convert_inline(item_text), styles["bullet"]))
                    for item_text in items
                ]
                flowables.append(
                    ListFlowable(
                        list_items,
                        bulletType="bullet",
                        leftIndent=32,
                        bulletDedent=18,
                        bulletFontName=styles["body"].fontName,
                        bulletFontSize=styles["body"].fontSize,
                        bulletAnchor="start",
                        bulletOffsetY=2,
                    )
                )
            
        elif b_type == "code":
            # Wrap code in Preformatted for proper line breaking
            code_text = block["text"]
            max_chars = 80
            lines = code_text.split("\n")
            wrapped_lines = []
            for line in lines:
                if len(line) > max_chars:
                    while len(line) > max_chars:
                        wrapped_lines.append(line[:max_chars])
                        line = line[max_chars:]
                    if line:
                        wrapped_lines.append(line)
                else:
                    wrapped_lines.append(line)
            flowables.append(Preformatted("\n".join(wrapped_lines), styles["code"]))
            
        elif b_type == "quote":
            quote_text = " ".join(block.get("lines", []))
            flowables.append(Paragraph(_convert_inline(quote_text), styles["quote"]))
            
        elif b_type == "rule":
            flowables.append(
                HRFlowable(
                    width="100%",
                    thickness=1.5,
                    color=colors.HexColor("#d1d5db"),
                    spaceAfter=0.15 * inch,
                    spaceBefore=0.15 * inch,
                )
            )
            
        else:
            # Regular paragraph - join lines with spaces for proper wrapping
            paragraph_text = " ".join(
                line.strip() for line in block.get("lines", []) if line.strip()
            )
            if paragraph_text:
                flowables.append(Paragraph(_convert_inline(paragraph_text), styles["body"]))

        flowables.append(Spacer(1, _PARAGRAPH_SPACING))

    return flowables or [Paragraph("", styles["body"])]


def _split_blocks(text: str) -> List[dict]:
    """Parse markdown text into structured blocks, handling numbered text as regular paragraphs."""
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

        # Empty lines
        if stripped == "":
            idx += 1
            continue

        # Horizontal rules
        if stripped in {"---", "***", "___"} or re.match(r"^-{3,}$|^\*{3,}$|^_{3,}$", stripped):
            blocks.append({"type": "rule"})
            idx += 1
            continue

        # Blockquotes
        if stripped.startswith(">"):
            quote_lines = []
            while idx < total and lines[idx].strip().startswith(">"):
                quote_lines.append(lines[idx].strip()[1:].strip())
                idx += 1
            blocks.append({"type": "quote", "lines": quote_lines})
            continue

        # Headers (H3-H6)
        header_match = re.match(r"^(#{3,6})\s+(.*)", stripped)
        if header_match:
            blocks.append({"type": "header3", "text": header_match.group(2).strip()})
            idx += 1
            continue

        # Headers (H2)
        header2_match = re.match(r"^(#{2})\s+(.*)", stripped)
        if header2_match:
            blocks.append({"type": "header2", "text": header2_match.group(2).strip()})
            idx += 1
            continue

        # Headers (H1)
        header1_match = re.match(r"^#\s+(.*)", stripped)
        if header1_match:
            blocks.append({"type": "header1", "text": header1_match.group(1).strip()})
            idx += 1
            continue

        # Unordered lists - ONLY if line starts with bullet at position 0 or after whitespace
        # AND the line doesn't start with "1 " or "2 " etc (number + space)
        if re.match(r"^\s*[-*+]\s+", line) and not re.match(r"^\d+\s+", stripped):
            items: List[str] = []
            
            while idx < total:
                current = lines[idx]
                current_stripped = current.strip()
                
                if current_stripped == "":
                    idx += 1
                    continue
                    
                # Only match actual bullet lists, not "1 Introduction" style text
                if not re.match(r"^\s*[-*+]\s+", current) or re.match(r"^\d+\s+", current_stripped):
                    break
                
                # Remove bullet and any leading whitespace
                item_text = re.sub(r"^\s*[-*+]\s+", "", current).strip()
                items.append(item_text)
                idx += 1
                
            if items:
                blocks.append({"type": "ul", "items": items})
            continue

        # Ordered lists - ONLY actual markdown ordered lists (digit + dot + space)
        # NOT lines like "1 Introduction" or "2 Analyze"
        if re.match(r"^\s*\d+\.\s+", line):
            items = []
            
            while idx < total:
                current = lines[idx]
                current_stripped = current.strip()
                
                if current_stripped == "":
                    idx += 1
                    continue
                    
                # Only match "1. " style, not "1 " style
                if not re.match(r"^\s*\d+\.\s+", current):
                    break
                
                # Remove number and dot
                item_text = re.sub(r"^\s*\d+\.\s+", "", current).strip()
                items.append(item_text)
                idx += 1
                
            if items:
                blocks.append({"type": "ol", "items": items})
            continue

        # Regular paragraphs - everything else including "1 Title" style lines
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
            ):
                break
            paragraph_lines.append(lookahead)
            idx += 1
        blocks.append({"type": "paragraph", "lines": paragraph_lines})

    return blocks


def _convert_inline(text: str) -> str:
    """Convert inline markdown to HTML for ReportLab."""
    # Escape HTML entities first
    text = (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace("\t", "    ")
    )
    
    # Apply inline formatting (order matters!)
    conversions = [
        (r"\*\*\*(.+?)\*\*\*", r"<b><i>\1</i></b>"),  # Bold + italic
        (r"___(.+?)___", r"<b><i>\1</i></b>"),  # Bold + italic
        (r"\*\*(.+?)\*\*", r"<b>\1</b>"),  # Bold
        (r"__(.+?)__", r"<b>\1</b>"),  # Bold
        (r"\*(.+?)\*", r"<i>\1</i>"),  # Italic
        (r"_(.+?)_", r"<i>\1</i>"),  # Italic
        (r"`([^`]+)`", r'<font face="Courier" color="#dc2626">\1</font>'),  # Inline code
        (r"~~(.+?)~~", r"<strike>\1</strike>"),  # Strikethrough
    ]
    
    for pattern, replacement in conversions:
        text = re.sub(pattern, replacement, text)
    
    return text


def _extract_title(text: str) -> Optional[str]:
    """Extract title from the first H1 header or first bold line."""
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        # Check for H1
        header_match = re.match(r"^#\s+(.*)", stripped)
        if header_match:
            return header_match.group(1).strip()
        # Check for bold text as title
        bold_match = re.match(r"^\*\*(.+?)\*\*$", stripped)
        if bold_match:
            return bold_match.group(1).strip()
        # Use first non-empty line if nothing else
        if stripped:
            return stripped[:80]
    return None
