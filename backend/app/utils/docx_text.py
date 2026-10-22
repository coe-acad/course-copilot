"""Plain-text extraction for uploaded Word (.docx) resources."""
import io

from docx import Document
from docx.table import Table
from docx.text.paragraph import Paragraph


def extract_docx_text(data: bytes) -> str:
    """Extract the text of a .docx (paragraphs and tables, in document order).

    Word files are stored as plain-text resources — the model can't take a .docx
    as an input_file the way it takes a PDF.
    """
    doc = Document(io.BytesIO(data))
    parts: list = []
    for child in doc.element.body.iterchildren():
        tag = child.tag.rsplit("}", 1)[-1]
        if tag == "p":
            text = Paragraph(child, doc).text
            if text.strip():
                parts.append(text)
        elif tag == "tbl":
            table_md = _table_to_markdown(Table(child, doc))
            if table_md:
                # Blank lines around the table so Markdown parses it as a table
                # rather than folding it into the surrounding paragraph.
                parts.extend(["", table_md, ""])
    return "\n".join(parts)


def _table_to_markdown(table) -> str:
    """Render a python-docx table as a GFM Markdown table (first row = header)."""
    rows: list = []
    for row in table.rows:
        cells: list = []
        prev_tc = None
        for c in row.cells:
            # python-docx repeats a horizontally merged cell once per grid column;
            # keep its text in the first column only so it isn't duplicated.
            text = "" if c._tc is prev_tc else c.text
            prev_tc = c._tc
            cells.append(" ".join(text.split()).replace("|", "\\|"))
        rows.append(cells)
    rows = [r for r in rows if any(r)]
    if not rows:
        return ""
    width = max(len(r) for r in rows)
    rows = [r + [""] * (width - len(r)) for r in rows]
    lines = ["| " + " | ".join(r) + " |" for r in rows]
    lines.insert(1, "|" + " --- |" * width)
    return "\n".join(lines)
