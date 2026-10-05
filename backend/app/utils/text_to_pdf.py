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

from PIL import Image as PILImage
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_JUSTIFY
from reportlab.lib.pagesizes import LETTER, landscape
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import (
    HRFlowable,
    Image,
    ListFlowable,
    ListItem,
    Paragraph,
    Preformatted,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

import base64
import requests

from . import sprint_structure as ss

from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfbase.pdfmetrics import registerFontFamily

_IMAGE_LINE = re.compile(r"^!\[([^\]]*)\]\(([^)\s]+)(?:\s+\"[^\"]*\")?\)$")
_COURSE_IMAGE_RE = re.compile(r"/courses/([^/]+)/images/([^/?#\s]+)")


def parse_image_line(stripped_line: str) -> Optional[Tuple[str, str]]:
    """Return (alt, src) if the line is a standalone markdown image, else None."""
    match = _IMAGE_LINE.match(stripped_line.strip())
    if not match:
        return None
    return match.group(1).strip(), match.group(2).strip()


# def fetch_image_stream(src: str) -> Optional[BytesIO]:
#     """Fetch image into a BytesIO stream with support for mongo lookup, base64, and URLs."""
#     try:
#         if not src:
#             return None

#         # 1) Direct MongoDB lookup for internal course images
#         course_img_match = _COURSE_IMAGE_RE.search(src)
#         if course_img_match:
#             try:
#                 from app.services.mongo import get_resource_image_by_id
#                 course_id, image_id = course_img_match.group(1), course_img_match.group(2)
#                 mongo_img = get_resource_image_by_id(course_id, image_id)
#                 if mongo_img and mongo_img.get("image_base64"):
#                     img_data = base64.b64decode(mongo_img["image_base64"])
#                     stream = BytesIO(img_data)
#                     stream.seek(0)
#                     return stream
#             except Exception:
#                 pass

#         # 2) Base64 data URIs
#         if src.startswith("data:"):
#             header, _, data = src.partition(",")
#             if ";base64" in header and data:
#                 stream = BytesIO(base64.b64decode(data))
#                 stream.seek(0)
#                 return stream
#             return None

#         # 3) HTTP(S) URLs
#         if src.startswith("http://") or src.startswith("https://"):
#             response = requests.get(src, timeout=8.0)
#             response.raise_for_status()
#             if not response.content:
#                 return None
#             stream = BytesIO(response.content)
#             stream.seek(0)
#             return stream
#     except Exception:
#         return None
#     return None


def fetch_image_stream(src: str) -> Optional[BytesIO]:
    """Fetch image into a BytesIO stream with support for mongo lookup, base64, and URLs."""
    if not src:
        logger.warning("fetch_image_stream: Empty image source")
        return None

    try:
        # 1. Base64 data URI
        if src.startswith("data:"):
            header, _, data = src.partition(",")
            if ";base64" in header and data:
                img_data = base64.b64decode(data)
                stream = BytesIO(img_data)
                stream.seek(0)
                return stream
            return None

        # 2. Internal course / knowledge base image path
        course_img_match = _COURSE_IMAGE_RE.search(src)
        if course_img_match:
            course_id = course_img_match.group(1)
            image_id = course_img_match.group(2)

            from app.services.mongo import get_one_from_collection
            mongo_img = get_one_from_collection("resource_images", {
                "course_id": course_id,
                "$or": [
                    {"image_id": image_id},
                    {"resource_name": image_id},
                    {"resource_name": image_id.replace("_", " ")},
                    {"image_id": image_id.replace(".", "_")},
                    {"image_id": f"res_{image_id.replace('.', '_')}"},
                ]
            })
            if not mongo_img:
                mongo_img = get_one_from_collection("resource_images", {
                    "$or": [
                        {"image_id": image_id},
                        {"resource_name": image_id},
                    ]
                })

            if mongo_img and mongo_img.get("image_base64"):
                image_base64 = mongo_img["image_base64"]
                if "," in image_base64 and image_base64.startswith("data:"):
                    image_base64 = image_base64.split(",", 1)[1]
                img_data = base64.b64decode(image_base64)
                if img_data:
                    stream = BytesIO(img_data)
                    stream.seek(0)
                    return stream

        # 3. Direct MongoDB lookup by image_id or resource_name
        if not src.startswith("http://") and not src.startswith("https://"):
            from app.services.mongo import get_one_from_collection
            clean_src = src.lstrip("/")
            mongo_img = get_one_from_collection("resource_images", {
                "$or": [
                    {"image_id": clean_src},
                    {"resource_name": clean_src},
                    {"image_id": clean_src.replace(".", "_")},
                ]
            })
            if mongo_img and mongo_img.get("image_base64"):
                image_base64 = mongo_img["image_base64"]
                if "," in image_base64 and image_base64.startswith("data:"):
                    image_base64 = image_base64.split(",", 1)[1]
                img_data = base64.b64decode(image_base64)
                if img_data:
                    stream = BytesIO(img_data)
                    stream.seek(0)
                    return stream

        # 4. HTTP(S) URLs
        if src.startswith("http://") or src.startswith("https://"):
            response = requests.get(src, timeout=10)
            if response.ok and response.content:
                stream = BytesIO(response.content)
                stream.seek(0)
                return stream

        return None

    except Exception as e:
        logger.error(f"fetch_image_stream error for '{src}': {e}")
        return None


def latex_to_text(text: str) -> str:
    """Clean LaTeX math markers for clear readable text."""
    if not text:
        return ""
    # Strip basic \[ ... \], \( ... \), $$ ... $$, $ ... $
    text = re.sub(r"\\\[(.+?)\\\]", r"\1", text, flags=re.DOTALL)
    text = re.sub(r"\\\((.+?)\\\)", r"\1", text, flags=re.DOTALL)
    text = re.sub(r"\$\$(.+?)\$\$", r"\1", text, flags=re.DOTALL)
    text = re.sub(r"(?<!\\)\$(?!\$)([^\n$]+?)(?<!\\)\$", r"\1", text)
    return text


PdfBytes = bytes
PathLike = Union[str, Path]

_FONTS_DIR = Path(__file__).parent / "fonts"


def _register_unicode_fonts() -> tuple[str, str]:
    """Register the bundled DejaVu fonts for full Unicode (math/Greek) coverage.

    The built-in Type-1 fonts (Helvetica/Courier) lack glyphs for math symbols
    and sub/superscripts, so equations render as tofu boxes. DejaVu covers them.
    Returns ``(body_font, mono_font)`` names, falling back to the built-in fonts
    if the TTF files are missing so PDF generation never breaks.
    """
    try:
        variants = {
            "DejaVuSans": "DejaVuSans.ttf",
            "DejaVuSans-Bold": "DejaVuSans-Bold.ttf",
            "DejaVuSans-Oblique": "DejaVuSans-Oblique.ttf",
            "DejaVuSans-BoldOblique": "DejaVuSans-BoldOblique.ttf",
            "DejaVuSansMono": "DejaVuSansMono.ttf",
            "DejaVuSansMono-Bold": "DejaVuSansMono-Bold.ttf",
        }
        for name, filename in variants.items():
            path = _FONTS_DIR / filename
            if not path.exists():
                raise FileNotFoundError(path)
            if name not in pdfmetrics.getRegisteredFontNames():
                pdfmetrics.registerFont(TTFont(name, str(path)))
        # Let reportlab resolve -Bold / -Oblique and inline <b>/<i> markup.
        registerFontFamily(
            "DejaVuSans",
            normal="DejaVuSans",
            bold="DejaVuSans-Bold",
            italic="DejaVuSans-Oblique",
            boldItalic="DejaVuSans-BoldOblique",
        )
        return "DejaVuSans", "DejaVuSansMono"
    except Exception:
        # Fonts unavailable — degrade to the built-ins rather than fail.
        return "Helvetica", "Courier"


_DEFAULT_FONT_NAME, _MONO_FONT_NAME = _register_unicode_fonts()
_DEFAULT_FONT_SIZE = 11
_DEFAULT_PAGE_SIZE = LETTER
_H_MARGIN = 0.85 * inch
_V_MARGIN = 1.0 * inch
# Cap embedded-image height so a tall image never overflows the page frame
# (reportlab raises LayoutError otherwise). ~0.85 of the usable text height.
# Maximum height for normal standalone images
_MAX_IMAGE_HEIGHT = (_DEFAULT_PAGE_SIZE[1] - 2 * _V_MARGIN) * 0.60

# Smaller maximum height for images inside table cells.
# This prevents a question row from becoming taller than the PDF page.
_MAX_TABLE_IMAGE_HEIGHT = 2.2 * inch

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

    # Convert LaTeX math to readable plain text so equations don't render raw.
    text = latex_to_text(text)

    title = _extract_title(text) or _DEFAULT_TITLE

    # Sprint timetables and other wide tables are laid out on landscape pages.
    blocks = _split_blocks(text)
    has_sprint = ss.has_sprint_table(blocks)
    if ss.needs_landscape(blocks) and page_size == _DEFAULT_PAGE_SIZE:
        page_size = landscape(_DEFAULT_PAGE_SIZE)

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
    # Layout facts the table builder needs (it only receives the styles dict).
    styles["_content_width"] = page_size[0] - 2 * _H_MARGIN
    styles["_has_sprint"] = has_sprint
    flowables = _markdown_to_flowables(text, styles, title)

    decorator = lambda canvas, doc_: _decorate_page(canvas, doc_, title)
    # try:
    #     doc.build(flowables, onFirstPage=decorator, onLaterPages=decorator)
    # except Exception:
    #     # Fallback: if document layout fails on complex/oversized flowables, retry with safe text fallbacks for images
    #     buffer = BytesIO()
    #     doc = SimpleDocTemplate(
    #         buffer,
    #         pagesize=page_size,
    #         leftMargin=_H_MARGIN,
    #         rightMargin=_H_MARGIN,
    #         topMargin=_V_MARGIN,
    #         bottomMargin=_V_MARGIN,
    #         title=title,
    #     )
    #     safe_flowables = _markdown_to_flowables(text, styles, title, fallback_images=True)
    #     doc.build(safe_flowables, onFirstPage=decorator, onLaterPages=decorator)

    try:
        doc.build(
            flowables,
            onFirstPage=decorator,
            onLaterPages=decorator
        )

    except Exception as e:
        print("PDF BUILD ERROR:", repr(e))

        raise RuntimeError(
            f"PDF generation failed: {e}"
        ) from e


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
        fontName=_MONO_FONT_NAME,
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

    # Header and Footer removed as per request
    
    canvas.restoreState()


# ---------------------------------------------------------------------------
# Markdown-ish parsing
# ---------------------------------------------------------------------------

def _markdown_to_flowables(text: str, styles: dict, title: str, fallback_images: bool = False) -> List:
    """Convert markdown text to ReportLab flowables, preserving original formatting."""
    flowables: List = []
    
    # Track global counter for ordered lists to maintain sequential numbering
    ol_counter = 1
    
    # Don't add title separately - it will be in the content
    
    for block in _split_blocks(text):
        b_type = block.get("type")

        if b_type == "header1":
            flowables.append(_safe_paragraph(_convert_inline(block["text"]), styles["header1"]))
            
        elif b_type == "header2":
            flowables.append(_safe_paragraph(_convert_inline(block["text"]), styles["header2"]))
            
        elif b_type == "header3":
            flowables.append(_safe_paragraph(_convert_inline(block["text"]), styles["header3"]))
            
        elif b_type in {"ul", "ol"}:
            items = block.get("items", [])
            
            if b_type == "ol":
                # For ordered lists, use global counter to maintain sequential numbering
                for item_text in items:
                    if _INLINE_IMAGE_RE.search(item_text):
                        remaining = _INLINE_IMAGE_RE.sub("", item_text).strip()
                        if remaining:
                            numbered_text = f"{ol_counter}. {_convert_inline(remaining)}"
                            flowables.append(_safe_paragraph(numbered_text, styles["numbered"]))
                        for m in _INLINE_IMAGE_RE.finditer(item_text):
                            flowables.append(_build_image({"alt": m.group(1), "src": m.group(2)}, styles, fallback_only=fallback_images))
                    else:
                        numbered_text = f"{ol_counter}. {_convert_inline(item_text)}"
                        flowables.append(_safe_paragraph(numbered_text, styles["numbered"]))
                    ol_counter += 1
            else:
                # For unordered lists, use ListFlowable with bullet points
                for item_text in items:
                    if _INLINE_IMAGE_RE.search(item_text):
                        remaining = _INLINE_IMAGE_RE.sub("", item_text).strip()
                        if remaining:
                            flowables.append(
                                ListFlowable(
                                    [ListItem(_safe_paragraph(_convert_inline(remaining), styles["bullet"]))],
                                    bulletType="bullet",
                                    leftIndent=32,
                                    bulletDedent=18,
                                    bulletFontName=styles["body"].fontName,
                                    bulletFontSize=styles["body"].fontSize,
                                    bulletAnchor="start",
                                    bulletOffsetY=2,
                                )
                            )
                        for m in _INLINE_IMAGE_RE.finditer(item_text):
                            flowables.append(_build_image({"alt": m.group(1), "src": m.group(2)}, styles, fallback_only=fallback_images))
                    else:
                        flowables.append(
                            ListFlowable(
                                [ListItem(_safe_paragraph(_convert_inline(item_text), styles["bullet"]))],
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
            flowables.append(_safe_paragraph(_convert_inline(quote_text), styles["quote"]))
            
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

        elif b_type == "table":
            table_flowable = _build_table(block, styles, fallback_images=fallback_images)
            if table_flowable is not None:
                flowables.append(table_flowable)

        elif b_type == "image":
            flowables.append(_build_image(block, styles, fallback_only=fallback_images))

        else:
            # Regular paragraph - join lines with spaces for proper wrapping
            paragraph_text = " ".join(
                line.strip() for line in block.get("lines", []) if line.strip()
            )
            if paragraph_text:
                if _INLINE_IMAGE_RE.search(paragraph_text):
                    remaining = _INLINE_IMAGE_RE.sub("", paragraph_text).strip()
                    if remaining:
                        flowables.append(_safe_paragraph(_convert_inline(remaining), styles["body"]))
                    for m in _INLINE_IMAGE_RE.finditer(paragraph_text):
                        flowables.append(_build_image({"alt": m.group(1), "src": m.group(2)}, styles, fallback_only=fallback_images))
                else:
                    flowables.append(_safe_paragraph(_convert_inline(paragraph_text), styles["body"]))

        flowables.append(Spacer(1, _PARAGRAPH_SPACING))

    return flowables or [_safe_paragraph("", styles["body"])]



def _is_table_separator_line(s: str) -> bool:
    """True if a line is a markdown table separator row (e.g. '---|:--:|---').

    Used to recognise GFM tables that omit the leading/trailing pipes, so
    ``CO# | Name`` followed by ``---|---`` is treated as a table, not a paragraph.
    """
    s = (s or "").strip()
    if "-" not in s:
        return False
    cells = [c.strip() for c in s.strip("|").split("|") if c.strip()]
    return bool(cells) and all(re.match(r"^:?-+:?$", c) for c in cells)


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

        # Standalone images: ![alt](src)
        image_match = parse_image_line(stripped)
        if image_match:
            alt, src = image_match
            blocks.append({"type": "image", "alt": alt, "src": src})
            idx += 1
            continue

        # Markdown tables — a pipe-led row (| a | b |) OR a GFM pipe-less header
        # row (a | b) immediately followed by a separator row (---|---).
        next_line = lines[idx + 1] if idx + 1 < total else ""
        if stripped.startswith("|") or ("|" in stripped and _is_table_separator_line(next_line)):
            table_lines = []
            while idx < total and "|" in lines[idx] and lines[idx].strip():
                table_lines.append(lines[idx].strip())
                idx += 1

            def _parse_row(row_str):
                cells = row_str.strip().strip("|").split("|")
                return [c.strip() for c in cells]

            def _is_separator(row_str):
                cells = [c.strip() for c in row_str.strip().strip("|").split("|") if c.strip()]
                return bool(cells) and all(re.match(r"^:?-+:?$", c) for c in cells)

            headers: List[str] = []
            rows: List[List[str]] = []
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
                or stripped_la.startswith("|")
                or ("|" in stripped_la and idx + 1 < total and _is_table_separator_line(lines[idx + 1]))
                or parse_image_line(stripped_la)
            ):
                break
            paragraph_lines.append(lookahead)
            idx += 1
        blocks.append({"type": "paragraph", "lines": paragraph_lines})

    return blocks


def _split_url_trailing(url: str):
    """Split trailing sentence punctuation a bare-URL match greedily swallowed."""
    trail = ""
    while url and url[-1] in ".,!?":
        trail = url[-1] + trail
        url = url[:-1]
    while url.endswith(")") and url.count("(") < url.count(")"):
        trail = ")" + trail
        url = url[:-1]
    return url, trail


def _safe_paragraph(xml_text: str, style) -> Paragraph:
    """Create a ReportLab Paragraph safely, recovering gracefully from XML parsing errors."""
    try:
        return Paragraph(xml_text, style)
    except Exception as e:
        logger.warning(f"ReportLab Paragraph parse error: {e}. Attempting recovery on: {ascii(xml_text)}")
        # 1. Try stripping unsupported or unclosed tags while keeping basic ones
        cleaned = re.sub(r"<(?!/?(?:br|b|i|u|font|a|strike|sub|sup)\b)[^>]*>", "", xml_text)
        try:
            return Paragraph(cleaned, style)
        except Exception:
            # 2. Strip all formatting tags except <br/>
            clean_basic = re.sub(r"</?(?:b|i|u|font|a|strike|sub|sup)[^>]*>", "", xml_text)
            clean_basic = clean_basic.replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">")
            clean_basic = clean_basic.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            clean_basic = clean_basic.replace("&lt;br/&gt;", "<br/>").replace("&lt;br&gt;", "<br/>")
            try:
                return Paragraph(clean_basic, style)
            except Exception:
                # 3. Ultimate fallback: pure plain text
                plain = re.sub(r"<[^>]+>", "", xml_text)
                plain = plain.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
                return Paragraph(plain, style)


def _convert_inline(text: str) -> str:
    """Convert inline markdown and HTML to ReportLab Paragraph XML."""
    if not text:
        return ""

    # Strip any leading <br> tags at start of text
    text = re.sub(r"^(?:\s*&lt;br\s*/?&gt;|\s*<br\s*/?>\s*)+", "", text, flags=re.IGNORECASE)

    # 0. Stash code spans FIRST (both markdown `code` and HTML <code>code</code>) so that
    # any underscores or special characters inside code are NEVER mangled by italic/bold markdown passes.
    stashed_code: List[str] = []
    def _stash_code_span(match: "re.Match") -> str:
        code_content = match.group(1)
        code_escaped = (
            code_content.replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace("\t", "    ")
        )
        token = f"\x00CODE{len(stashed_code)}\x00"
        stashed_code.append(f'<font face="{_MONO_FONT_NAME}" color="#dc2626">{code_escaped}</font>')
        return token

    # Stash HTML <code>...</code> first
    text = re.sub(r"<code(?:\s+[^>]*)?>([\s\S]*?)</code>", _stash_code_span, text, flags=re.IGNORECASE)
    # Stash markdown inline code `...`
    text = re.sub(r"`([^`\n]+)`", _stash_code_span, text)

    # 1. Stash existing HTML tags to preserve them during entity escaping
    stashed_tags: List[str] = []
    def _stash_html_tag(match: "re.Match") -> str:
        token = f"\x00HTML{len(stashed_tags)}\x00"
        full = match.group(0)
        tag_name = match.group(1).lower()
        is_closing = full.startswith("</")

        if tag_name in ("b", "strong"):
            tag_rep = "</b>" if is_closing else "<b>"
        elif tag_name in ("i", "em"):
            tag_rep = "</i>" if is_closing else "<i>"
        elif tag_name == "u":
            tag_rep = "</u>" if is_closing else "<u>"
        elif tag_name in ("s", "strike", "del"):
            tag_rep = "</strike>" if is_closing else "<strike>"
        elif tag_name == "sub":
            tag_rep = "</sub>" if is_closing else "<sub>"
        elif tag_name == "sup":
            tag_rep = "</sup>" if is_closing else "<sup>"
        elif tag_name == "br":
            tag_rep = "<br/>"
        else:
            tag_rep = ""  # Strip other unsupported HTML tags

        stashed_tags.append(tag_rep)
        return token

    text = re.sub(r"</?([a-zA-Z0-9]+)\s*[^>]*?/?>", _stash_html_tag, text)

    # Escape HTML entities in raw content
    text = (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace("\t", "    ")
    )
    
    # Extract [text](url) links first (excluding markdown images ![alt](url)),
    # stashing each URL behind a token so emphasis passes can style the link label.
    stashed_urls: List[str] = []

    def _stash_link(match: "re.Match") -> str:
        label, url = match.group(1), match.group(2)
        token = f"\x00U{len(stashed_urls)}\x00"
        stashed_urls.append(url)
        return f'<a href="{token}" color="#2563eb"><u>{label}</u></a>'

    # Note the negative lookbehind (?<!\!) to avoid mangling ![alt](url)
    text = re.sub(r"(?<!\!)\[([^\]]+)\]\(([^)\s]+)\)", _stash_link, text)

    # Autolink bare URLs (http(s)://… or www.…) that aren't already markdown links
    def _stash_bare_url(match: "re.Match") -> str:
        raw = match.group(0)
        url, trail = _split_url_trailing(raw)
        href = url if url.lower().startswith("http") else "https://" + url
        token = f"\x00U{len(stashed_urls)}\x00"
        stashed_urls.append(href)
        return f'<a href="{token}" color="#2563eb"><u>{url}</u></a>{trail}'

    text = re.sub(r"(?:https?://|www\.)[^\s<>\[\]\"']+", _stash_bare_url, text)

    # Apply inline formatting (order matters!)
    conversions = [
        (r"\*\*\*(.+?)\*\*\*", r"<b><i>\1</i></b>"),  # Bold + italic
        (r"(?<!\w)___(?!\s)(.+?)(?<!\s)___(?!\w)", r"<b><i>\1</i></b>"),  # Bold + italic
        (r"\*\*(.+?)\*\*", r"<b>\1</b>"),  # Bold
        (r"(?<!\w)__(?!\s)(.+?)(?<!\s)__(?!\w)", r"<b>\1</b>"),  # Bold
        (r"\*(.+?)\*", r"<i>\1</i>"),  # Italic
        (r"(?<!\w)_(?!\s)([^_\n]+?)(?<!\s)_(?!\w)", r"<i>\1</i>"),  # Italic
        (r"~~(.+?)~~", r"<strike>\1</strike>"),  # Strikethrough
    ]

    for pattern, replacement in conversions:
        text = re.sub(pattern, replacement, text)

    # Restore the stashed code spans
    for idx, code_html in enumerate(stashed_code):
        text = text.replace(f"\x00CODE{idx}\x00", code_html)

    # Restore the stashed URLs into the href attributes
    for idx, url in enumerate(stashed_urls):
        text = text.replace(f"\x00U{idx}\x00", url)

    # Restore the stashed HTML tags
    for idx, tag in enumerate(stashed_tags):
        text = text.replace(f"\x00HTML{idx}\x00", tag)

    # Auto-format inline sub-questions (i), (ii), (iii), (a), (b), (c) that follow text onto clean new lines
    subq_pattern = r"(?<!^)(?<!<br/>)(?<!<br>)(?<!\n)(?:;\s*and\s+|;\s*|,\s*and\s+|,\s*|\s+and\s+|\s+)(\((?:[a-h]|i{1,3}|iv|v|vi{1,3}|ix|x|[1-9])\)\s+)"
    text = re.sub(subq_pattern, r"<br/><br/>\1", text, flags=re.IGNORECASE)

    # Clean up any excessive line break stacking
    text = re.sub(r"(?:<br/>\s*){3,}", "<br/><br/>", text)

    return text



# Inline markdown image inside a larger string (e.g. within a table cell or question paragraph).
_INLINE_IMAGE_RE = re.compile(r"!\[([^\]]*)\]\(([^)\s]+)\)")


# def _build_scaled_image(src: str, alt: str, max_width: float, style, fallback_only: bool = False):
#     """An Image flowable scaled to fit ``max_width``; falls back to alt/link text."""
#     if not fallback_only:
#         stream = fetch_image_stream(src)
#         if stream is not None:
#             try:
#                 stream.seek(0)
#                 img = Image(stream)
#                 if img.drawWidth > max_width:
#                     ratio = max_width / img.drawWidth
#                     img.drawWidth = max_width
#                     img.drawHeight = img.drawHeight * ratio
#                 if img.drawHeight > _MAX_IMAGE_HEIGHT:
#                     ratio = _MAX_IMAGE_HEIGHT / img.drawHeight
#                     img.drawHeight = _MAX_IMAGE_HEIGHT
#                     img.drawWidth = img.drawWidth * ratio
#                 img.hAlign = "CENTER"
#                 return img
#             except Exception:
#                 pass
#     fallback = alt or src
#     label = f"[Image: {fallback}]" if fallback else "[Image]"
#     return Paragraph(_convert_inline(label), style)



def _build_scaled_image(
    src: str,
    alt: str,
    max_width: float,
    style,
    fallback_only: bool = False,
    max_height: float = _MAX_TABLE_IMAGE_HEIGHT,
):
    """Build and scale an image for use inside a table cell."""

    print(f"PDF IMAGE: Building image from: {src}")

    if not fallback_only:
        stream = fetch_image_stream(src)

        if stream is not None:
            try:
                stream.seek(0)

                img = Image(stream)

                original_width = img.drawWidth
                original_height = img.drawHeight

                print(
                    f"PDF IMAGE: Original size "
                    f"{original_width} x {original_height}"
                )

                # Scale by width
                if img.drawWidth > max_width:
                    ratio = max_width / img.drawWidth
                    img.drawWidth = max_width
                    img.drawHeight = img.drawHeight * ratio

                # Scale by height
                if img.drawHeight > max_height:
                    ratio = max_height / img.drawHeight
                    img.drawHeight = max_height
                    img.drawWidth = img.drawWidth * ratio

                img.hAlign = "CENTER"

                print(
                    f"PDF IMAGE SUCCESS: Final size "
                    f"{img.drawWidth} x {img.drawHeight}"
                )

                return img

            except Exception as e:
                print(
                    f"PDF IMAGE ERROR: ReportLab could not create image: {e}"
                )

    fallback = alt or src
    label = f"[Image: {fallback}]" if fallback else "[Image]"

    return _safe_paragraph(
        _convert_inline(label),
        style
    )




def _build_cell(text: str, style, img_max_width: float, fallback_images: bool = False):
    """Build a table cell's content.

    If the cell contains inline markdown image(s), return a list of flowables
    preserving the natural reading order (text before image -> image -> text after image).
    """
    if not _INLINE_IMAGE_RE.search(text or ""):
        return _safe_paragraph(_convert_inline(text), style)

    flowables = []
    last_idx = 0
    for m in _INLINE_IMAGE_RE.finditer(text):
        before = text[last_idx:m.start()].strip()
        if before:
            flowables.append(_safe_paragraph(_convert_inline(before), style))
        flowables.append(_build_scaled_image(m.group(2), m.group(1), img_max_width, style, fallback_only=fallback_images))
        last_idx = m.end()

    after = text[last_idx:].strip()
    if after:
        flowables.append(_safe_paragraph(_convert_inline(after), style))

    return flowables or _safe_paragraph(_convert_inline(text), style)


def _build_table(block: dict, styles: dict, fallback_images: bool = False):
    """Build a ReportLab Table flowable from a parsed markdown table block."""
    headers = block.get("headers", [])
    rows = block.get("rows", [])
    col_count = max(len(headers), max((len(r) for r in rows), default=0))
    if col_count == 0:
        return None

    content_width = styles.get("_content_width", _DEFAULT_PAGE_SIZE[0] - 2 * _H_MARGIN)
    if ss.is_sprint_table(headers):
        return _build_sprint_table(headers, rows, styles, content_width)
    if ss.is_sprint_legend(block, styles.get("_has_sprint", False)):
        return _build_sprint_legend(headers, rows, styles)

    cell_style = ParagraphStyle(
        "TableCell",
        parent=styles["body"],
        fontSize=styles["body"].fontSize - 1,
        leading=(styles["body"].fontSize - 1) * 1.3,
        spaceAfter=0,
        spaceBefore=0,
    )
    header_style = ParagraphStyle(
        "TableHeaderCell",
        parent=cell_style,
        fontName=f"{styles['body'].fontName}-Bold",
        textColor=colors.HexColor("#1f2937"),
    )

    # Calculate proportional column widths
    lower_headers = [h.strip().lower() for h in headers]
    if any("question" in h for h in lower_headers):
        col_weights = []
        for h in lower_headers:
            if "q.no" in h or "q. no" in h or "sl" in h:
                col_weights.append(0.08)
            elif "question" in h:
                col_weights.append(0.68)
            elif "mark" in h or "score" in h:
                col_weights.append(0.08)
            elif "co" in h or "mapping" in h or "outcome" in h:
                col_weights.append(0.16)
            else:
                col_weights.append(1.0 / col_count)
        total_w = sum(col_weights)
        col_widths = [(w / total_w) * content_width for w in col_weights]
    else:
        col_text_lens = []
        for c_idx in range(col_count):
            h_len = len(headers[c_idx]) if c_idx < len(headers) else 0
            r_lens = [len(r[c_idx]) if c_idx < len(r) else 0 for r in rows]
            max_len = max([h_len] + r_lens + [1])
            col_text_lens.append(min(max(max_len, 5), 100))
        total_len = sum(col_text_lens)
        col_widths = [(l / total_len) * content_width for l in col_text_lens]

    col_widths = _enforce_min_widths(
        col_widths,
        content_width,
        _column_min_widths(headers, rows, col_count, header_style.fontName, header_style.fontSize, content_width),
    )

    def _pad(cells, style):
        padded = list(cells) + [""] * (col_count - len(cells))
        return [_build_cell(c, style, max(col_widths[i] - 12 if i < len(col_widths) else 24, 24), fallback_images=fallback_images) for i, c in enumerate(padded)]

    data = [_pad(headers, header_style)]
    for row in rows:
        data.append(_pad(row, cell_style))

    table = Table(data, colWidths=col_widths, hAlign="LEFT", repeatRows=1)
    table.setStyle(
        TableStyle(
            [
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#d1d5db")),
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#f9fafb")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 6),
                ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ]
        )
    )
    return table


_MIN_COL_WIDTH = 28  # points; narrower columns leave no room for text after padding


def _enforce_min_widths(col_widths: List[float], content_width: float,
                        min_widths: Optional[List[float]] = None) -> List[float]:
    """Raise narrow proportional columns to their minimum, shrinking the others.

    Without this a short column (e.g. "Day", "Marks") next to long ones gets a
    width below its longest word, or even below its cell padding, in which case
    words split mid-word or ReportLab cannot lay the table out at all.
    """
    n = len(col_widths)
    mins = [max(m, _MIN_COL_WIDTH) for m in (min_widths or [_MIN_COL_WIDTH] * n)]
    if n == 0:
        return []
    if sum(mins) >= content_width:
        # Not enough room for every minimum: share the page in proportion to them.
        return [m / sum(mins) * content_width for m in mins]
    widths = list(col_widths)
    fixed: set = set()
    for _ in range(n):
        newly = [i for i in range(n) if i not in fixed and widths[i] < mins[i]]
        if not newly:
            break
        fixed.update(newly)
        flexible = sum(w for i, w in enumerate(widths) if i not in fixed)
        remaining = content_width - sum(mins[i] for i in fixed)
        widths = [mins[i] if i in fixed else (w * remaining / flexible if flexible else w)
                  for i, w in enumerate(widths)]
    return widths


def _column_min_widths(headers: List[str], rows: List[List[str]], col_count: int,
                       font_name: str, font_size: float, content_width: float) -> List[float]:
    """Width each column needs to fit its longest word without breaking it."""
    padding = 14  # left + right cell padding plus a little slack
    mins = []
    for c in range(col_count):
        texts = [headers[c] if c < len(headers) else ""] + [r[c] if c < len(r) else "" for r in rows]
        words = [w for t in texts for w in re.sub(r"[*_`]|<br\s*/?>", " ", t or "").split()]
        longest = max((pdfmetrics.stringWidth(w, font_name, font_size) for w in words), default=0)
        mins.append(min(longest + padding, content_width / 3))
    return mins


def _sprint_styles(styles: dict):
    """Paragraph styles for sprint timetable cells, keyed by text colour."""
    base = ParagraphStyle(
        "SprintCell",
        parent=styles["body"],
        fontSize=7.5,
        leading=9.2,
        alignment=TA_CENTER,
        spaceAfter=0,
        spaceBefore=0,
    )
    cache = {}

    def get(fg: str, bold: bool = False, size: Optional[float] = None):
        key = (fg, bold, size)
        if key not in cache:
            cache[key] = ParagraphStyle(
                f"SprintCell-{fg}-{bold}-{size}",
                parent=base,
                textColor=colors.HexColor(f"#{fg}"),
                fontName=f"{styles['body'].fontName}-Bold" if bold else styles["body"].fontName,
                fontSize=size or base.fontSize,
                leading=(size or base.fontSize) * 1.22,
            )
        return cache[key]

    return get


def _sprint_cell_paragraph(text: str, style_for):
    """Activity cell: activity label above its topic, in the activity's legend font."""
    colour = ss.activity_colour(text)
    fg = colour[1] if colour else "111827"
    bold = bool(colour and colour[2])  # only activities the legend marks bold
    split = ss.split_label(text)
    if split:
        label, topic = split
        xml = f"{_convert_inline(label)}<br/>{_convert_inline(topic)}"
    else:
        xml = _convert_inline(ss.plain(text))
    if bold:
        xml = f"<b>{xml}</b>"
    return _safe_paragraph(xml, style_for(fg))


def _build_sprint_table(headers: List[str], rows: List[List[str]], styles: dict, content_width: float):
    """Colour-coded sprint timetable: black header, activity colours, merged grey breaks."""
    col_count = len(headers)
    rows = [(list(r) + [""] * col_count)[:col_count] for r in rows]
    style_for = _sprint_styles(styles)

    weights = ss.column_weights(headers, rows)
    col_widths = [w / sum(weights) * content_width for w in weights]

    data = [[
        _safe_paragraph(
            # "Coffee<br/>Break": one word per line fits the narrow break column.
            "<b>" + "<br/>".join(_convert_inline(w) for w in ss.plain(h).split()) + "</b>"
            if ss.is_break(h) else f"<b>{_convert_inline(ss.plain(h))}</b>",
            style_for(ss.HEADER_FG, size=6 if ss.is_break(h) else 8),
        )
        for h in headers
    ]]
    commands = [
        ("GRID", (0, 0), (-1, -1), 0.75, colors.black),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 3),
        ("RIGHTPADDING", (0, 0), (-1, -1), 3),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor(f"#{ss.HEADER_BG}")),
    ]
    for c, h in enumerate(headers):
        if ss.is_break(h):
            commands += [("LEFTPADDING", (c, 0), (c, -1), 1), ("RIGHTPADDING", (c, 0), (c, -1), 1)]

    row_heights = [None]
    for r, row in enumerate(rows, start=1):
        if ss.is_weekend_row(row):
            data.append([_safe_paragraph(f"<b>{_convert_inline(ss.plain(row[0]))}</b>", style_for(ss.WEEKEND_FG))]
                        + [""] * (col_count - 1))
            commands.append(("BACKGROUND", (0, r), (-1, r), colors.HexColor(f"#{ss.WEEKEND_BG}")))
            row_heights.append(16)
            continue
        cells = []
        for c, text in enumerate(row):
            if ss.is_break(text):
                cells.append("")  # grey band; the header names the break
                commands.append(("BACKGROUND", (c, r), (c, r), colors.HexColor(f"#{ss.BREAK_BG}")))
                continue
            colour = ss.activity_colour(text)
            if colour:
                commands.append(("BACKGROUND", (c, r), (c, r), colors.HexColor(f"#{colour[0]}")))
            cells.append(_sprint_cell_paragraph(text, style_for))
        data.append(cells)
        row_heights.append(None)

    # Each week's break cells read as one grey band: paint the grid lines between
    # them grey. (Not a SPAN — a spanned block can't split across pages, and a
    # week of long cells is taller than a page.)
    for c, first, last in ss.break_runs(headers, rows):
        if last > first:
            commands.append(("LINEBELOW", (c, first + 1), (c, last), 0.75, colors.HexColor(f"#{ss.BREAK_BG}")))

    table = Table(data, colWidths=col_widths, rowHeights=row_heights, hAlign="LEFT", repeatRows=1)
    table.setStyle(TableStyle(commands))
    return table


def _build_sprint_legend(headers: List[str], rows: List[List[str]], styles: dict):
    """The sprint "Colour Key" table, each activity shown in its colour."""
    style_for = _sprint_styles(styles)
    data = [[_safe_paragraph(f"<b>{_convert_inline(ss.plain(headers[0]))}</b>", style_for(ss.HEADER_FG, size=8))]]
    commands = [
        ("GRID", (0, 0), (-1, -1), 0.75, colors.black),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("BACKGROUND", (0, 0), (0, 0), colors.HexColor(f"#{ss.HEADER_BG}")),
    ]
    for r, row in enumerate(rows, start=1):
        text = row[0] if row else ""
        colour = ss.activity_colour(text)
        if colour:
            commands.append(("BACKGROUND", (0, r), (0, r), colors.HexColor(f"#{colour[0]}")))
        data.append([_sprint_cell_paragraph(text, style_for)])
    table = Table(data, colWidths=[170], hAlign="LEFT")
    table.setStyle(TableStyle(commands))
    return table


def _build_image(block: dict, styles: dict, fallback_only: bool = False):
    """Build an Image flowable from a markdown image block.

    Falls back to a paragraph with the alt text/link if the image cannot be
    fetched, so a broken/expired image never breaks the whole document.
    """
    src = block.get("src", "")
    alt = block.get("alt", "")
    if not fallback_only:
        stream = fetch_image_stream(src)
        if stream is not None:
            try:
                stream.seek(0)
                img = Image(stream)
                content_width = _DEFAULT_PAGE_SIZE[0] - 2 * _H_MARGIN
                if img.drawWidth > content_width:
                    ratio = content_width / img.drawWidth
                    img.drawWidth = content_width
                    img.drawHeight = img.drawHeight * ratio
                if img.drawHeight > _MAX_IMAGE_HEIGHT:
                    ratio = _MAX_IMAGE_HEIGHT / img.drawHeight
                    img.drawHeight = _MAX_IMAGE_HEIGHT
                    img.drawWidth = img.drawWidth * ratio
                img.hAlign = "CENTER"
                return img
            except Exception:
                pass

    fallback = alt or src
    label = f"[Image: {fallback}]" if fallback else "[Image]"
    return _safe_paragraph(_convert_inline(label), styles["body"])



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
