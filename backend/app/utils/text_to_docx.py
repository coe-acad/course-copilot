"""
Utility helpers to convert rich text (markdown) into DOCX documents.
"""

from __future__ import annotations

import re
from io import BytesIO
from typing import List, Optional, Union
from pathlib import Path

import base64
import requests

from docx import Document
from docx.shared import Pt, RGBColor, Inches, Emu
from docx.oxml.ns import qn
from docx.oxml import OxmlElement
from docx.opc.constants import RELATIONSHIP_TYPE as _RT
from docx.enum.section import WD_ORIENT
from docx.enum.table import WD_CELL_VERTICAL_ALIGNMENT, WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH

from . import sprint_structure as ss

_IMAGE_LINE = re.compile(r"^!\[([^\]]*)\]\(([^)\s]+)(?:\s+\"[^\"]*\")?\)$")
_COURSE_IMAGE_RE = re.compile(r"/courses/([^/]+)/images/([^/?#\s]+)")


def parse_image_line(stripped_line: str) -> Optional[Tuple[str, str]]:
    """Return (alt, src) if the line is a standalone markdown image, else None."""
    match = _IMAGE_LINE.match(stripped_line.strip())
    if not match:
        return None
    return match.group(1).strip(), match.group(2).strip()


def fetch_image_stream(src: str) -> Optional[BytesIO]:
    """Fetch image into a BytesIO stream with support for mongo lookup, base64, and URLs."""
    if not src:
        return None

    try:
        # 1. Base64 data URIs
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
            response = requests.get(src, timeout=10.0)
            if response.ok and response.content:
                stream = BytesIO(response.content)
                stream.seek(0)
                return stream

        return None
    except Exception:
        return None


def latex_to_text(text: str) -> str:
    """Clean LaTeX math markers for clear readable text."""
    if not text:
        return ""
    text = re.sub(r"\\\[(.+?)\\\]", r"\1", text, flags=re.DOTALL)
    text = re.sub(r"\\\((.+?)\\\)", r"\1", text, flags=re.DOTALL)
    text = re.sub(r"\$\$(.+?)\$\$", r"\1", text, flags=re.DOTALL)
    text = re.sub(r"(?<!\\)\$(?!\$)([^\n$]+?)(?<!\\)\$", r"\1", text)
    return text


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

    # Convert LaTeX math to readable plain text so equations don't render raw.
    text = latex_to_text(text)

    doc = Document()

    # Set default page margins
    for section in doc.sections:
        section.top_margin = Inches(1.0)
        section.bottom_margin = Inches(1.0)
        section.left_margin = Inches(0.85)
        section.right_margin = Inches(0.85)

    # Sprint timetables and other wide tables are laid out on landscape pages.
    if ss.needs_landscape(_split_blocks(text)):
        for section in doc.sections:
            section.orientation = WD_ORIENT.LANDSCAPE
            section.page_width, section.page_height = section.page_height, section.page_width
            section.top_margin = section.bottom_margin = Inches(0.7)
            section.left_margin = section.right_margin = Inches(0.6)

    _apply_default_styles(doc)
    _ensure_hyperlink_style(doc)
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

def _add_abstract_num(numbering, abstract_id: int, num_fmt: str, lvl_text: str, font: Optional[str]):
    """Append a single-level ``<w:abstractNum>`` definition to numbering.xml."""
    abstract = OxmlElement("w:abstractNum")
    abstract.set(qn("w:abstractNumId"), str(abstract_id))
    lvl = OxmlElement("w:lvl")
    lvl.set(qn("w:ilvl"), "0")
    start = OxmlElement("w:start")
    start.set(qn("w:val"), "1")
    fmt = OxmlElement("w:numFmt")
    fmt.set(qn("w:val"), num_fmt)
    text_el = OxmlElement("w:lvlText")
    text_el.set(qn("w:val"), lvl_text)
    jc = OxmlElement("w:lvlJc")
    jc.set(qn("w:val"), "left")
    ppr = OxmlElement("w:pPr")
    ind = OxmlElement("w:ind")
    ind.set(qn("w:left"), "720")
    ind.set(qn("w:hanging"), "360")
    ppr.append(ind)
    for child in (start, fmt, text_el, jc, ppr):
        lvl.append(child)
    if font:
        rpr = OxmlElement("w:rPr")
        rfonts = OxmlElement("w:rFonts")
        rfonts.set(qn("w:ascii"), font)
        rfonts.set(qn("w:hAnsi"), font)
        rfonts.set(qn("w:hint"), "default")
        rpr.append(rfonts)
        lvl.append(rpr)
    abstract.append(lvl)
    # All <w:abstractNum> must precede every <w:num> in the schema, so insert
    # abstracts at the front (nums are always appended at the end).
    numbering.insert(0, abstract)


def _add_num(numbering, num_id: int, abstract_id: int):
    """Append a ``<w:num>`` pointing at an abstract definition."""
    num = OxmlElement("w:num")
    num.set(qn("w:numId"), str(num_id))
    abstract_ref = OxmlElement("w:abstractNumId")
    abstract_ref.set(qn("w:val"), str(abstract_id))
    num.append(abstract_ref)
    numbering.append(num)


def _init_list_numbering(doc: Document) -> dict:
    """Create the shared bullet + decimal abstract definitions once per document.

    Applying the "List Bullet"/"List Number" *style* alone does not attach a
    numbering definition, so Word shows no bullet/number glyph. We add real
    ``<w:abstractNum>`` definitions and cache state (the shared bullet num id,
    the decimal abstract id, and the next free num id) on the document.
    """
    state = getattr(doc, "_list_num_state", None)
    if state is not None:
        return state

    numbering = doc.part.numbering_part.element  # <w:numbering>

    # Pick IDs that don't collide with anything already in the template.
    existing_abstract = [
        int(e.get(qn("w:abstractNumId")))
        for e in numbering.findall(qn("w:abstractNum"))
        if e.get(qn("w:abstractNumId")) is not None
    ]
    existing_num = [
        int(e.get(qn("w:numId")))
        for e in numbering.findall(qn("w:num"))
        if e.get(qn("w:numId")) is not None
    ]
    bullet_abstract = max(existing_abstract, default=0) + 1
    decimal_abstract = bullet_abstract + 1
    _add_abstract_num(numbering, bullet_abstract, "bullet", "•", "Symbol")
    _add_abstract_num(numbering, decimal_abstract, "decimal", "%1.", None)

    # Bullets don't count, so all bullet lists can share one num. Numbered lists
    # each get a fresh num (see _new_ordered_num_id) so their counters restart.
    bullet_num_id = max(existing_num, default=0) + 1
    _add_num(numbering, bullet_num_id, bullet_abstract)

    state = {
        "numbering": numbering,
        "decimal_abstract": decimal_abstract,
        "bullet_num_id": bullet_num_id,
        "next_num_id": bullet_num_id + 1,
    }
    doc._list_num_state = state
    return state


def _bullet_num_id(doc: Document) -> int:
    """Return the shared bullet numbering id (bullets never need to restart)."""
    return _init_list_numbering(doc)["bullet_num_id"]


def _new_ordered_num_id(doc: Document) -> int:
    """Allocate a fresh num id for one ordered list so its count restarts at 1."""
    state = _init_list_numbering(doc)
    num_id = state["next_num_id"]
    state["next_num_id"] += 1
    _add_num(state["numbering"], num_id, state["decimal_abstract"])
    return num_id


def _apply_list_number(paragraph, num_id: int):
    """Attach direct numbering (numPr) so the bullet/number actually renders."""
    ppr = paragraph._p.get_or_add_pPr()
    numpr = OxmlElement("w:numPr")
    ilvl = OxmlElement("w:ilvl")
    ilvl.set(qn("w:val"), "0")
    num = OxmlElement("w:numId")
    num.set(qn("w:val"), str(num_id))
    numpr.append(ilvl)
    numpr.append(num)
    ppr.append(numpr)


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
    blocks = _split_blocks(text)
    has_sprint = ss.has_sprint_table(blocks)
    for block in blocks:
        b_type = block.get("type")

        if b_type == "table" and ss.is_sprint_table(block.get("headers", [])):
            _add_sprint_table(doc, block["headers"], block.get("rows", []))
            continue
        if ss.is_sprint_legend(block, has_sprint):
            _add_sprint_legend(doc, block["headers"], block.get("rows", []))
            continue

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
            bullet_num_id = _bullet_num_id(doc)
            for item in block.get("items", []):
                if _INLINE_IMAGE_RE.search(item):
                    remaining = _INLINE_IMAGE_RE.sub("", item).strip()
                    p = doc.add_paragraph(style="List Bullet")
                    _apply_list_number(p, bullet_num_id)
                    _add_inline_runs(p, remaining)
                    for m in _INLINE_IMAGE_RE.finditer(item):
                        _add_image(doc, {"alt": m.group(1), "src": m.group(2)})
                else:
                    p = doc.add_paragraph(style="List Bullet")
                    _apply_list_number(p, bullet_num_id)
                    _add_inline_runs(p, item)

        elif b_type == "ol":
            number_num_id = _new_ordered_num_id(doc)  # fresh id -> restarts at 1
            for item in block.get("items", []):
                if _INLINE_IMAGE_RE.search(item):
                    remaining = _INLINE_IMAGE_RE.sub("", item).strip()
                    p = doc.add_paragraph(style="List Number")
                    _apply_list_number(p, number_num_id)
                    _add_inline_runs(p, remaining)
                    for m in _INLINE_IMAGE_RE.finditer(item):
                        _add_image(doc, {"alt": m.group(1), "src": m.group(2)})
                else:
                    p = doc.add_paragraph(style="List Number")
                    _apply_list_number(p, number_num_id)
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
            try:
                section = doc.sections[-1]
                usable = section.page_width - section.left_margin - section.right_margin
                cell_img_width = int(usable / col_count * 0.9)  # fit within the column
            except Exception:
                cell_img_width = None
            for ri, row_cells in enumerate(rows):
                tbl_row = table.rows[ri + 1]
                for ci in range(col_count):
                    cell_text = row_cells[ci].strip() if ci < len(row_cells) else ""
                    _add_cell_content(tbl_row.cells[ci], cell_text, cell_img_width)

        elif b_type == "image":
            _add_image(doc, block)

        elif b_type == "rule":
            _add_horizontal_rule(doc)

        else:
            # Regular paragraph
            lines = block.get("lines", [])
            paragraph_text = " ".join(line.strip() for line in lines if line.strip())
            if paragraph_text:
                if _INLINE_IMAGE_RE.search(paragraph_text):
                    remaining = _INLINE_IMAGE_RE.sub("", paragraph_text).strip()
                    if remaining:
                        p = doc.add_paragraph()
                        _add_inline_runs(p, remaining)
                    for m in _INLINE_IMAGE_RE.finditer(paragraph_text):
                        _add_image(doc, {"alt": m.group(1), "src": m.group(2)})
                else:
                    p = doc.add_paragraph()
                    _add_inline_runs(p, paragraph_text)


# ---------------------------------------------------------------------------
# Inline markdown & HTML → runs
# ---------------------------------------------------------------------------

# Bare URL autolink: http(s):// or www. up to the next space/bracket/quote.
_URL_RE = re.compile(r"(?:https?://|www\.)[^\s<>()\[\]\"']+", re.IGNORECASE)


def _split_trailing_punct(url: str):
    """Split sentence punctuation that a bare URL match greedily swallowed.

    ``https://x.com/page.`` -> (``https://x.com/page``, ``.``). Also releases a
    dangling ``)`` when the URL has no matching ``(``.
    """
    trail = ""
    while url and url[-1] in ".,!?":
        trail = url[-1] + trail
        url = url[:-1]
    while url.endswith(")") and url.count("(") < url.count(")"):
        trail = ")" + trail
        url = url[:-1]
    return url, trail


def _ensure_hyperlink_style(doc: Document):
    """Create a blue+underlined 'Hyperlink' character style if the template lacks one."""
    from docx.enum.style import WD_STYLE_TYPE

    if any(s.name == "Hyperlink" for s in doc.styles):
        return
    style = doc.styles.add_style("Hyperlink", WD_STYLE_TYPE.CHARACTER)
    style.font.color.rgb = RGBColor(0x25, 0x63, 0xEB)
    style.font.underline = True


def _add_hyperlink(para, text: str, url: str):
    """Add a clickable external hyperlink run (blue, underlined) to a paragraph."""
    part = para.part
    r_id = part.relate_to(url, _RT.HYPERLINK, is_external=True)

    hyperlink = OxmlElement("w:hyperlink")
    hyperlink.set(qn("r:id"), r_id)

    run = OxmlElement("w:r")
    rpr = OxmlElement("w:rPr")
    # Reference the Hyperlink character style AND set explicit color/underline so
    # the link looks right whether or not the viewer honours the style.
    rstyle = OxmlElement("w:rStyle")
    rstyle.set(qn("w:val"), "Hyperlink")
    color = OxmlElement("w:color")
    color.set(qn("w:val"), "2563EB")
    underline = OxmlElement("w:u")
    underline.set(qn("w:val"), "single")
    rpr.append(rstyle)
    rpr.append(color)
    rpr.append(underline)
    run.append(rpr)

    text_el = OxmlElement("w:t")
    text_el.set(qn("xml:space"), "preserve")
    text_el.text = text
    run.append(text_el)

    hyperlink.append(run)
    para._p.append(hyperlink)


_INLINE_PATTERN = re.compile(
    r'(?P<link>\[(?P<ltext>[^\]]+)\]\((?P<lurl>[^)\s]+)\))'  # [text](url)
    r'|(?P<url>(?:https?://|www\.)[^\s<>\[\]"\']+)'            # bare url autolink
    r'|(?P<br><br\s*/?>)'                                      # <br> or <br/>
    r'|(?P<bi>\*\*\*(?P<bitext>.+?)\*\*\*|___(?P<bi_utext>.+?)___)' # bold + italic
    r'|(?P<b>\*\*(?P<btext>.+?)\*\*|__(?P<b_utext>.+?)__|<b>(?P<hbtext>.+?)</b>|<strong>(?P<strongtext>.+?)</strong>)' # bold
    r'|(?P<i>\*(?P<itext>.+?)\*|_(?P<i_utext>.+?)_|<i>(?P<hitext>.+?)</i>|<em>(?P<emtext>.+?)</em>)' # italic
    r'|(?P<u><u>(?P<utext>.+?)</u>)'                          # underline
    r'|(?P<code>`(?P<ctext>[^`]+)`|<code>(?P<hctext>.+?)</code>)' # inline code
    r'|(?P<strike>~~(?P<stext>.+?)~~|<s>(?P<stext_s>.+?)</s>|<strike>(?P<stext_strike>.+?)</strike>|<del>(?P<stext_del>.+?)</del>)' # strikethrough
    r'|(?P<sub><sub>(?P<subtext>.+?)</sub>)'                  # subscript
    r'|(?P<sup><sup>(?P<suptext>.+?)</sup>)',                 # superscript
    re.IGNORECASE | re.DOTALL
)


def _add_inline_runs(para, text: str):
    """Parse inline markdown and HTML and add styled runs to a paragraph."""
    if not text:
        return

    # Auto-format inline sub-questions (i), (ii), (iii), (a), (b), (c) that follow text onto clean new lines
    subq_pattern = r"(?<!^)(?<!<br/>)(?<!<br>)(?<!\n)(?:;\s*and\s+|;\s*|,\s*and\s+|,\s*|\s+and\s+|\s+)(\((?:[a-h]|i{1,3}|iv|v|vi{1,3}|ix|x|[1-9])\)\s+)"
    text = re.sub(subq_pattern, r"<br/>\1", text, flags=re.IGNORECASE)

    pos = 0
    for m in _INLINE_PATTERN.finditer(text):
        # Add plain text before this match
        if m.start() > pos:
            run = para.add_run(text[pos:m.start()])

            run.font.color.rgb = RGBColor(0x37, 0x41, 0x51)

        if m.group("link"):
            _add_hyperlink(para, m.group("ltext"), m.group("lurl"))
        elif m.group("url"):  # bare URL -> autolink
            url, trail = _split_trailing_punct(m.group("url"))
            href = url if url.lower().startswith("http") else "https://" + url
            _add_hyperlink(para, url, href)
            if trail:
                run = para.add_run(trail)
                run.font.color.rgb = RGBColor(0x37, 0x41, 0x51)
        elif m.group("br"):
            run = para.add_run()
            run.add_break()
        elif m.group("bi"):
            txt = m.group("bitext") or m.group("bi_utext") or ""
            run = para.add_run(txt)
            run.bold = True
            run.italic = True
        elif m.group("b"):
            txt = m.group("btext") or m.group("b_utext") or m.group("hbtext") or m.group("strongtext") or ""
            run = para.add_run(txt)
            run.bold = True
        elif m.group("i"):
            txt = m.group("itext") or m.group("i_utext") or m.group("hitext") or m.group("emtext") or ""
            run = para.add_run(txt)
            run.italic = True
        elif m.group("u"):
            txt = m.group("utext") or ""
            run = para.add_run(txt)
            run.underline = True
        elif m.group("code"):
            txt = m.group("ctext") or m.group("hctext") or ""
            run = para.add_run(txt)
            run.font.name = "Courier New"
            run.font.size = Pt(10)
            run.font.color.rgb = RGBColor(0xDC, 0x26, 0x26)
        elif m.group("strike"):
            txt = m.group("stext") or m.group("stext_s") or m.group("stext_strike") or m.group("stext_del") or ""
            run = para.add_run(txt)
            run.font._element.get_or_add_rPr().append(OxmlElement('w:strike'))
        elif m.group("sub"):
            txt = m.group("subtext") or ""
            run = para.add_run(txt)
            run.font.subscript = True
        elif m.group("sup"):
            txt = m.group("suptext") or ""
            run = para.add_run(txt)
            run.font.superscript = True

        pos = m.end()

    # Remaining plain text
    if pos < len(text):
        run = para.add_run(text[pos:])
        run.font.color.rgb = RGBColor(0x37, 0x41, 0x51)



# ---------------------------------------------------------------------------
# Block parser (reuses logic from text_to_pdf.py)
# ---------------------------------------------------------------------------

def _is_table_separator_line(s: str) -> bool:
    """True if a line is a markdown table separator row (e.g. '---|:--:|---').

    Lets GFM tables that omit leading/trailing pipes be recognised as tables.
    """
    s = (s or "").strip()
    if "-" not in s:
        return False
    cells = [c.strip() for c in s.strip("|").split("|") if c.strip()]
    return bool(cells) and all(re.match(r"^:?-+:?$", c) for c in cells)


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
                or ("|" in stripped_la and idx + 1 < total and _is_table_separator_line(lines[idx + 1]))
                or parse_image_line(stripped_la)
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


def _add_image(doc: Document, block: dict):
    """Embed a markdown image into the document.

    Falls back to italic alt text/link if the image cannot be fetched, so a
    broken/expired image never breaks the whole document.
    """
    src = block.get("src", "")
    alt = block.get("alt", "")
    stream = fetch_image_stream(src)
    if stream is not None:
        try:
            para = doc.add_paragraph()
            para.alignment = 1  # WD_ALIGN_PARAGRAPH.CENTER
            shape = para.add_run().add_picture(stream)
            # Constrain to the page's content width, preserving aspect ratio.
            section = doc.sections[-1]
            content_width = section.page_width - section.left_margin - section.right_margin
            if shape.width and shape.width > content_width:
                ratio = content_width / shape.width
                shape.width = Emu(int(shape.width * ratio))
                shape.height = Emu(int(shape.height * ratio))
            return
        except Exception:
            pass

    fallback = alt or src
    p = doc.add_paragraph()
    run = p.add_run(f"[Image: {fallback}]" if fallback else "[Image]")
    run.font.italic = True
    run.font.color.rgb = RGBColor(0x6B, 0x72, 0x80)


# Inline markdown image inside a larger string (e.g. within a table cell). Unlike
# markdown_media.parse_image_line this does NOT require the image to be the whole
# line, so it matches an image embedded alongside question text in a cell.
_INLINE_IMAGE_RE = re.compile(r"!\[([^\]]*)\]\(([^)\s]+)\)")


def _add_cell_image(cell, src: str, alt: str, max_width: Optional[int] = None):
    """Embed an image inside a table cell, scaled to ``max_width`` (EMU) if given.

    Falls back to italic alt/link text if the image can't be fetched, mirroring
    ``_add_image`` so a broken image never breaks the document.
    """
    stream = fetch_image_stream(src)
    if stream is not None:
        try:
            para = cell.add_paragraph()
            para.alignment = 1  # WD_ALIGN_PARAGRAPH.CENTER
            shape = para.add_run().add_picture(stream)
            if max_width and shape.width and shape.width > max_width:
                ratio = max_width / shape.width
                shape.width = Emu(int(shape.width * ratio))
                shape.height = Emu(int(shape.height * ratio))
            return
        except Exception:
            pass
    fallback = alt or src
    para = cell.add_paragraph()
    run = para.add_run(f"[Image: {fallback}]" if fallback else "[Image]")
    run.font.italic = True
    run.font.color.rgb = RGBColor(0x6B, 0x72, 0x80)


def _add_cell_content(cell, text: str, img_max_width: Optional[int] = None):
    """Fill a table cell, preserving the natural reading order (text before image -> image -> text after image)."""
    if not _INLINE_IMAGE_RE.search(text or ""):
        _add_inline_runs(cell.paragraphs[0], text)
        return

    last_idx = 0
    first_para = True
    for m in _INLINE_IMAGE_RE.finditer(text):
        before = text[last_idx:m.start()].strip()
        if before:
            para = cell.paragraphs[0] if first_para else cell.add_paragraph()
            _add_inline_runs(para, before)
            first_para = False
        _add_cell_image(cell, m.group(2), m.group(1), img_max_width)
        first_para = False
        last_idx = m.end()

    after = text[last_idx:].strip()
    if after:
        para = cell.paragraphs[0] if first_para else cell.add_paragraph()
        _add_inline_runs(para, after)


def _usable_width(doc: Document) -> int:
    section = doc.sections[-1]
    return section.page_width - section.left_margin - section.right_margin


def _set_cell_margins(cell, twips: int):
    tcPr = cell._tc.get_or_add_tcPr()
    mar = OxmlElement("w:tcMar")
    for side in ("top", "left", "bottom", "right"):
        el = OxmlElement(f"w:{side}")
        el.set(qn("w:w"), str(twips))
        el.set(qn("w:type"), "dxa")
        mar.append(el)
    tcPr.append(mar)


def _set_table_borders(table, hex_color: str, size: int = 8):
    tblPr = table._tbl.tblPr
    borders = OxmlElement("w:tblBorders")
    for edge in ("top", "left", "bottom", "right", "insideH", "insideV"):
        el = OxmlElement(f"w:{edge}")
        el.set(qn("w:val"), "single")
        el.set(qn("w:sz"), str(size))
        el.set(qn("w:color"), hex_color)
        borders.append(el)
    tblPr.append(borders)


def _set_fixed_layout(table, widths: List[int]):
    """Fixed column widths (Word otherwise autofits and squeezes short columns)."""
    table.autofit = False
    layout = OxmlElement("w:tblLayout")
    layout.set(qn("w:type"), "fixed")
    table._tbl.tblPr.append(layout)
    for row in table.rows:
        for c, cell in enumerate(row.cells):
            cell.width = widths[c]


def _sprint_run(para, text: str, fg: str, *, bold=False, size=8):
    run = para.add_run(text)
    run.bold = bold
    run.font.size = Pt(size)
    run.font.color.rgb = RGBColor.from_string(fg)
    return run


def _fill_sprint_cell(cell, text: str):
    """Activity cell: activity label above its topic, in the activity's legend colours."""
    colour = ss.activity_colour(text)
    fg = colour[1] if colour else "111827"
    bold = bool(colour and colour[2])  # only activities the legend marks bold
    if colour:
        _shade_cell(cell, colour[0])
    para = cell.paragraphs[0]
    para.alignment = WD_ALIGN_PARAGRAPH.CENTER
    para.paragraph_format.space_after = Pt(0)
    split = ss.split_label(text)
    if split:
        _sprint_run(para, split[0], fg, bold=bold)
        _sprint_run(para, "\n" + split[1], fg, bold=bold, size=7.5)
    else:
        _sprint_run(para, ss.plain(text), fg, bold=bold)


def _add_sprint_table(doc: Document, headers: List[str], rows: List[List[str]]):
    """Colour-coded sprint timetable: black header, activity colours, merged grey breaks."""
    col_count = len(headers)
    rows = [(list(r) + [""] * col_count)[:col_count] for r in rows]
    table = doc.add_table(rows=1 + len(rows), cols=col_count)
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    _set_table_borders(table, "000000", size=8)

    weights = ss.column_weights(headers, rows)
    usable = _usable_width(doc)
    _set_fixed_layout(table, [int(w / sum(weights) * usable) for w in weights])

    for c, h in enumerate(headers):
        cell = table.rows[0].cells[c]
        _shade_cell(cell, ss.HEADER_BG)
        cell.vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.CENTER
        _set_cell_margins(cell, 30 if ss.is_break(h) else 60)
        para = cell.paragraphs[0]
        para.alignment = WD_ALIGN_PARAGRAPH.CENTER
        label = "\n".join(ss.plain(h).split()) if ss.is_break(h) else ss.plain(h)
        _sprint_run(para, label, ss.HEADER_FG, bold=True, size=6 if ss.is_break(h) else 8.5)
    # Repeat the header row on every page.
    trPr = table.rows[0]._tr.get_or_add_trPr()
    trPr.append(OxmlElement("w:tblHeader"))

    for r, row in enumerate(rows, start=1):
        cells = table.rows[r].cells
        weekend = ss.is_weekend_row(row)
        for c, text in enumerate(row):
            cell = cells[c]
            cell.vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.CENTER
            _set_cell_margins(cell, 30 if ss.is_break(headers[c]) else 60)
            if weekend:
                _shade_cell(cell, ss.WEEKEND_BG)
                if c == 0:
                    _sprint_run(cells[0].paragraphs[0], ss.plain(text), ss.WEEKEND_FG, bold=True)
            elif ss.is_break(text):
                _shade_cell(cell, ss.BREAK_BG)  # grey band; the header names the break
            else:
                _fill_sprint_cell(cell, text)
        # Keep each day on one page.
        table.rows[r]._tr.get_or_add_trPr().append(OxmlElement("w:cantSplit"))

    for c, first, last in ss.break_runs(headers, rows):
        if last > first:
            table.cell(first + 1, c).merge(table.cell(last + 1, c))


def _add_sprint_legend(doc: Document, headers: List[str], rows: List[List[str]]):
    """The sprint "Colour Key" table, each activity shown in its colour."""
    table = doc.add_table(rows=1 + len(rows), cols=1)
    _set_table_borders(table, "000000", size=8)
    _set_fixed_layout(table, [Inches(2.2)])
    head = table.rows[0].cells[0]
    _shade_cell(head, ss.HEADER_BG)
    head.paragraphs[0].alignment = WD_ALIGN_PARAGRAPH.CENTER
    _sprint_run(head.paragraphs[0], ss.plain(headers[0]), ss.HEADER_FG, bold=True, size=9)
    for r, row in enumerate(rows, start=1):
        _fill_sprint_cell(table.rows[r].cells[0], row[0] if row else "")


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
