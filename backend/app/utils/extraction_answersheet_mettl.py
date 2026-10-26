"""
Answer sheet extraction for the Mettl "Question-Wise Details" report format.

Layout of each question card (questions are numbered per section):

    Section 1 / Section #1                      <- section header
    Q. / Question 1  Time taken ... Marks ...   <- question header (or "Not Attempted")
    Question                                    <- label, followed by the question text
    Response                                    <- label, followed by the student's response
    Words : N            (descriptive questions) <- ends the response
    Answer: / Best answer ...  (short questions) <- Mettl reference answer, NOT the student's

The page cards are drawn as boxes that pdfplumber detects as page-sized tables, so
text is read from word positions (uncropped) instead of page.extract_text().
"""
import re
import json
from collections import Counter
import logging

import pdfplumber

logger = logging.getLogger(__name__)

# Words whose tops are within this distance are on the same visual line
# (arrows like "→" are rendered ~3pt off the text baseline).
_LINE_Y_TOLERANCE = 4.0

_FOOTER_RE = re.compile(r"^(?P<org>.*?)\s*\|\s*(?P<name>.+?)\s+Page\s+\d+\s*/\s*\d+\s*$", re.IGNORECASE)
# "Section 1" shares a visual line with the section stats ("5 25m 32s 0/10")
_SECTION_RE = re.compile(r"^Section\s*#?\s*(\d+)\b", re.IGNORECASE)
_QUESTION_HEADER_RE = re.compile(r"^Question\s+(\d+)\b(.*)$", re.IGNORECASE)
_MARKS_RE = re.compile(r"Marks\s+Scored:\s*([\d.]+)\s*/\s*([\d.]+)", re.IGNORECASE)
_WORDS_RE = re.compile(r"^Words\s*:\s*\d+\s*$", re.IGNORECASE)
_EMAIL_RE = re.compile(r"([a-zA-Z0-9._%+-]+@atriauniversity\.edu\.in)", re.IGNORECASE)
_PARTICIPANT_RE = re.compile(r"Participant\s+ID:\s*-?\s*(\d+)", re.IGNORECASE)


def is_mettl_report(pages_content):
    """Detect the Mettl report layout from the line anchors built by extract_text_tables."""
    has_details = has_response = False
    for page in pages_content or []:
        for ln in page.get("lines", []):
            text = (ln.get("text") or "").strip()
            if text.startswith("Question-Wise Details"):
                has_details = True
            elif text == "Response":
                has_response = True
            if has_details and has_response:
                return True
    return False


def _page_lines(page, page_index):
    """Group words into visual lines: [{page, y, bottom, x0, text}] sorted top-to-bottom."""
    words = sorted(page.extract_words(), key=lambda w: (w["top"], w["x0"]))
    clusters = []
    for w in words:
        if clusters and abs(w["top"] - clusters[-1][0]["top"]) <= _LINE_Y_TOLERANCE:
            clusters[-1].append(w)
        else:
            clusters.append([w])

    lines = []
    for ws in clusters:
        ws.sort(key=lambda w: w["x0"])
        lines.append({
            "page": page_index,
            "y": min(w["top"] for w in ws),
            "bottom": max(w["bottom"] for w in ws),
            "x0": ws[0]["x0"],
            "text": " ".join(w["text"] for w in ws),
            "words": [(w["x0"], w["x1"], w["text"]) for w in ws],
        })
    return lines


# Responses keep the student's horizontal layout (column gaps, indented tree drawings).
# A word gap this many times the normal word spacing, or an indent of this many characters,
# marks a line as laid out.
_LAYOUT_GAP_RATIO = 2.5
_LAYOUT_INDENT_CHARS = 2
_MIN_WIDE_GAP_SPACES = 3


def _char_width(lines):
    """Typical character width of the response font, from the words' own widths."""
    widths = sorted(
        (x1 - x0) / len(text)
        for ln in lines for x0, x1, text in ln.get("words", []) if len(text) >= 3
    )
    return widths[len(widths) // 2] if widths else 6.0


def _space_width(lines, cw):
    """Normal gap between words. Uses the low end of the gaps (plain spaces), capped by the font's
    character width so a short answer made mostly of wide column gaps doesn't inflate it."""
    gaps = sorted(
        b[0] - a[1]
        for ln in lines for a, b in zip(ln.get("words", []), ln.get("words", [])[1:])
        if b[0] > a[1]
    )
    lower_quartile = gaps[len(gaps) // 4] if gaps else cw
    return min(lower_quartile, 0.6 * cw)


def _render_line(line, left, cw, space_w):
    """Rebuild a line with spaces placed by each word's x position. Returns (text, is_laid_out)."""
    words = line.get("words", [])
    laid_out = bool(words) and (words[0][0] - left) / cw >= _LAYOUT_INDENT_CHARS
    laid_out = laid_out or any(b[0] - a[1] >= _LAYOUT_GAP_RATIO * space_w for a, b in zip(words, words[1:]))

    out, prev_x1 = "", None
    for x0, x1, text in words:
        col = max(0, round((x0 - left) / cw))
        if not out:
            pad = col
        else:
            # Line up with the word's page position; a wide gap on the page never collapses below 3 spaces
            min_pad = _MIN_WIDE_GAP_SPACES if (x0 - prev_x1) >= _LAYOUT_GAP_RATIO * space_w else 1
            pad = max(min_pad, col - len(out))
        out += " " * pad + text
        prev_x1 = x1
    return out.rstrip(), laid_out


# Lines drawn only with tree/diagram connectors ("/ \", "|", "--->") are part of a drawing
_EDGE_LINE_RE = re.compile(r"^[\s/\\|_\-=<>^.:*+→←↑↓↔─│┌┐└┘├┤┬┴┼]*[/\\|│─┌┐└┘├┤┬┴┼→←↑↓][\s/\\|_\-=<>^.:*+→←↑↓↔─│┌┐└┘├┤┬┴┼]*$")
# Numbered code line as Mettl prints question code: "1 def operation(head):", or "4" for a blank line
_NUMBERED_LINE_RE = re.compile(r"^(\d{1,3})(?:\s|$)")
# Student-typed code: a statement keyword ("def_k(...)" typos included), an assignment to a
# name/attribute ("head.next = node(15)"), a function call ("insert(rear,45)"), or a line opening a "{" block
_CODE_LINE_RE = re.compile(
    r"^(?:(?:def|class)(?:\b|_)"
    r"|(?:return|for|while|if|elif|else|import|from|print|try|except|with|struct|int|void|public|private)\b"
    r"|[A-Za-z_][\w\[\]]*(?:\([^)]*\))?(?:\.\w+(?:\([^)]*\))?)*\s*(?:=|\+=|-=|\*=|/=)(?!=)\s*\S"
    r"|[A-Za-z_][\w.]*\s*\(.*\)\s*[{:;]?\s*$"
    r"|\S.*\{\s*$)"
)
# A response at least this code-like is boxed as one block from its first to its last code line
_CODE_SHARE_FOR_SINGLE_BLOCK = 0.5
_MIN_CODE_LINES_FOR_SINGLE_BLOCK = 3
# A short token in a drawing: node values and labels ("15", "b)25", "A")
_SHORT_TOKEN_RE = re.compile(r"^(?=.*\d).{1,4}$|^.{1,2}$")
_MAX_SHORT_TOKENS = 8
_MAX_SINGLE_WORD_CHARS = 6   # a lone short word next to a block ("Total" under a table)
# Trailing marks tag on a question line ("... function:   [3M]"): its gap is not layout
_MARKS_TAG_RE = re.compile(r"\s*-?\s*\[\s*\d+(?:\.\d+)?\s*M\s*\]\s*$", re.IGNORECASE)
_PROSE_WORD_RE = re.compile(r"^[A-Za-z][a-z]{2,}[,.;:?!]?$")


def _is_short_token_line(text):
    tokens = text.split()
    if len(tokens) == 1 and len(tokens[0]) <= _MAX_SINGLE_WORD_CHARS:
        return True
    return 0 < len(tokens) <= _MAX_SHORT_TOKENS and all(_SHORT_TOKEN_RE.match(t) for t in tokens)


def _is_prose(text):
    """A sentence-like line: mostly ordinary words."""
    tokens = text.split()
    return len(tokens) >= 5 and sum(bool(_PROSE_WORD_RE.match(t)) for t in tokens) >= 0.6 * len(tokens)


def _is_laid_out(ln, left, cw, space_w):
    """Laid out by position, ignoring a trailing marks tag; indentation alone doesn't make prose laid out."""
    words = list(ln.get("words", []))
    # Drop the trailing marks tag words ("[3M]", "- [6M]") so the gap before them isn't counted
    while words and _MARKS_TAG_RE.search(" ".join(w[2] for w in words)):
        words.pop()
    while words and words[-1][2] in ("-", "–"):
        words.pop()
    has_wide_gap = any(b[0] - a[1] >= _LAYOUT_GAP_RATIO * space_w for a, b in zip(words, words[1:]))
    if has_wide_gap:
        return True
    indented = bool(words) and (words[0][0] - left) / cw >= _LAYOUT_INDENT_CHARS
    return indented and not _is_prose(" ".join(w[2] for w in words))


def _line_kinds(lines, left, cw, space_w):
    """
    Classify each line as "block" (belongs in a code block), "weak" (a short line such as a node
    value that belongs in a block only when it touches one) or "plain".
    Block lines: laid out (indented / wide gaps), drawn with connectors, numbered code
    (3+ consecutive line numbers), or code statements (2+ in a row).
    """
    texts = [ln["text"].strip() for ln in lines]
    kinds = []
    for ln, text in zip(lines, texts):
        if _is_laid_out(ln, left, cw, space_w) or _EDGE_LINE_RE.match(text):
            kinds.append("block")
        elif _CODE_LINE_RE.match(text):
            kinds.append("code")
        elif _is_short_token_line(text):
            kinds.append("weak")
        else:
            kinds.append("plain")

    # Runs of consecutive line numbers (n, n+1, n+2, ...) are listed code
    i = 0
    while i < len(texts):
        m = _NUMBERED_LINE_RE.match(texts[i])
        j = i + 1
        if m:
            expected = int(m.group(1)) + 1
            while j < len(texts):
                mj = _NUMBERED_LINE_RE.match(texts[j])
                if not mj or int(mj.group(1)) != expected:
                    break
                expected += 1
                j += 1
            if j - i >= 3:
                for k in range(i, j):
                    kinds[k] = "block"
        i = j

    # Mostly-code answers: one block from the first to the last code line, so an unrecognised line
    # in the middle (a typo, a comment) doesn't split the code into pieces
    code_idx = [i for i, text in enumerate(texts) if _CODE_LINE_RE.match(text)]
    if (
        len(code_idx) >= _MIN_CODE_LINES_FOR_SINGLE_BLOCK
        and len(code_idx) >= _CODE_SHARE_FOR_SINGLE_BLOCK * len(lines)
    ):
        for k in range(code_idx[0], code_idx[-1] + 1):
            kinds[k] = "block"

    # A single code-looking line inside prose ("area = 5") stays plain
    for i, kind in enumerate(kinds):
        if kind == "code":
            near = [kinds[k] for k in (i - 1, i + 1) if 0 <= k < len(kinds)]
            kinds[i] = "block" if any(n in ("code", "block") for n in near) else "plain"
    return kinds


_WRAP_X_TOLERANCE = 2.0  # a PDF-wrapped line continues at the same x as the line before it


def _join_plain(lines, paragraphs):
    if not paragraphs:
        return [ln["text"] for ln in lines]
    # Questions: PDF-wrapped lines are rejoined; a new line starts at list items, after a sentence,
    # or where the text starts at a different x
    out, prev = [], None
    for ln in lines:
        text = ln["text"]
        wrapped = (
            prev is not None
            and abs(ln["x0"] - prev["x0"]) <= _WRAP_X_TOLERANCE
            and not re.match(r"^(?:\(?[a-zA-Z0-9]{1,2}[.)]|[-•*])\s", text)
            and not out[-1].rstrip().endswith((":", "?", "."))
        )
        if wrapped:
            out[-1] += " " + text
        else:
            out.append(text)
        prev = ln
    return out


def _render_response(lines, paragraphs=False):
    """
    Text with layout preserved: runs of code, drawings (trees, arrows) and aligned columns go into
    a fenced code block so spacing survives Markdown rendering and reaches the model as-is;
    ordinary sentences stay plain text. Short lines such as node values join a block they touch,
    so a drawing's first and last rows stay inside it. `paragraphs` rejoins PDF-wrapped prose lines
    (used for question text).
    """
    if not lines:
        return ""
    left = min(ln["x0"] for ln in lines)
    cw = _char_width(lines)
    space_w = _space_width(lines, cw)
    kinds = _line_kinds(lines, left, cw, space_w)

    # Group consecutive block/weak lines; a group is boxed only if it has at least one block line
    out, plain = [], []
    i = 0
    while i < len(lines):
        if kinds[i] == "plain":
            plain.append(lines[i])
            i += 1
            continue
        j = i
        while j < len(lines) and kinds[j] != "plain":
            j += 1
        group = lines[i:j]
        if any(kinds[k] == "block" for k in range(i, j)):
            out.extend(_join_plain(plain, paragraphs))
            plain = []
            group_left = min(ln["x0"] for ln in group)
            rendered = [_render_line(ln, group_left, cw, space_w)[0] for ln in group]
            out.append("```\n" + "\n".join(rendered) + "\n```")
        else:
            plain.extend(group)
        i = j
    out.extend(_join_plain(plain, paragraphs))
    return "\n".join(out)


def _icon_boxes(page):
    """Small filled shapes: the tick icons Mettl draws (as vector graphics, not text) in
    the RESPONSE / ANSWER columns of an options table."""
    return [
        (c["x0"], c["top"], c["x1"], c["bottom"]) for c in page.curves
        if c.get("fill") and 6 <= c["x1"] - c["x0"] <= 20 and 6 <= c["bottom"] - c["top"] <= 20
    ]


def _mark_icon_cells(table, icons):
    """Table data with "✓" added to every cell that has a tick icon drawn in it."""
    data = table.extract()
    for r, row in enumerate(table.rows):
        for c, cell in enumerate(row.cells):
            if cell is None or r >= len(data) or c >= len(data[r]):
                continue
            if any(cell[0] <= (i[0] + i[2]) / 2 <= cell[2] and cell[1] <= (i[1] + i[3]) / 2 <= cell[3] for i in icons):
                data[r][c] = ((data[r][c] or "") + " ✓").strip()
    return data


def read_layout_lines(pdf_path):
    """Return (lines, tables, images, page_sizes) for the whole document."""
    lines, tables, images, page_sizes = [], [], [], []
    with pdfplumber.open(pdf_path) as pdf:
        for pi, page in enumerate(pdf.pages):
            page_sizes.append((page.width, page.height))
            lines.extend(_page_lines(page, pi))

            icons = _icon_boxes(page)
            for t in page.find_tables(table_settings={"vertical_strategy": "lines", "horizontal_strategy": "lines"}):
                tables.append({"page": pi, "bbox": t.bbox, "data": _mark_icon_cells(t, icons)})

            for img in page.images:
                images.append({"page": pi, "bbox": (img["x0"], img["top"], img["x1"], img["bottom"])})
    return lines, tables, images, page_sizes


def _pos_lt(a, b):
    """(page, y) ordering."""
    return a[0] < b[0] or (a[0] == b[0] and a[1] < b[1])


def _inside(start, end, page, top, bottom):
    """True if the box [top, bottom] on `page` lies fully between start and end positions."""
    return not _pos_lt((page, top), start) and not _pos_lt(end, (page, bottom))


def _is_header_at(lines, idx):
    """A 'Question N ...' line is a question header only if the 'Question' label follows it."""
    if not _QUESTION_HEADER_RE.match(lines[idx]["text"]):
        return False
    for nxt in lines[idx + 1: idx + 4]:
        t = nxt["text"].strip()
        if t == "Question":
            return True
        if t == "Q." or t.isdigit():  # left-hand "Q. / N" badge
            continue
        return False
    return False


def _parse_cards(lines):
    """Walk the lines and build one card per question with positions of its regions."""
    cards = []
    section = None
    state = None  # header | question | response | done
    card = None

    for idx, ln in enumerate(lines):
        text = ln["text"].strip()
        pos = (ln["page"], ln["y"])

        if _FOOTER_RE.match(text):
            continue

        m_section = _SECTION_RE.match(text)
        if m_section and state not in ("question", "response"):
            section = int(m_section.group(1))
            continue

        if _is_header_at(lines, idx):
            if card and state == "response":
                card["response_end"] = pos
            elif card and state == "question":
                card["question_end"] = pos
            m = _QUESTION_HEADER_RE.match(text)
            rest = m.group(2)
            marks = _MARKS_RE.search(rest)
            card = {
                "section": section,
                "section_question_number": int(m.group(1)),
                "attempted": "not attempted" not in rest.lower(),
                "marks_scored": marks.group(1) if marks else None,
                "max_marks": marks.group(2) if marks else None,
                "question_lines": [],
                "question_start": None,
                "question_end": None,
                "response_lines": [],
                "response_start": None,
                "response_end": None,
            }
            cards.append(card)
            state = "header"
            continue

        if card is None:
            continue

        if state == "header":
            if text == "Question":
                state = "question"
                card["question_start"] = (ln["page"], ln["bottom"])
            continue

        if state == "question":
            if text == "Response":
                state = "response"
                card["question_end"] = pos
                card["response_start"] = (ln["page"], ln["bottom"])
            else:
                card["question_lines"].append(ln)
            continue

        if state == "response":
            if _WORDS_RE.match(text) or text == "Answer:":
                card["response_end"] = pos
                state = "done"
            else:
                card["response_lines"].append(ln)
            continue

    if card and state in ("question", "response") and lines:
        last = lines[-1]
        card[f"{state}_end"] = (last["page"], last["bottom"] + 1)

    return cards


def _response_tables(card, tables, page_sizes):
    """Tables drawn fully inside the response region (ignores the page/card layout boxes)."""
    start, end = card["response_start"], card["response_end"]
    if not start or not end:
        return []
    found = []
    for t in tables:
        x0, top, x1, bottom = t["bbox"]
        pw, ph = page_sizes[t["page"]]
        if top < 0 or bottom > ph or (x1 - x0) >= pw:
            continue  # page-spanning layout box
        if _inside(start, end, t["page"], top, bottom):
            found.append(t)
    return found


def _region_images(card, images, region):
    """Images drawn fully inside the card's "question" or "response" region."""
    start, end = card[f"{region}_start"], card[f"{region}_end"]
    if not start or not end:
        return []
    return [img for img in images if _inside(start, end, img["page"], img["bbox"][1], img["bbox"][3])]


def _upload_region_images(pdf_path, images, upload_image, prefix):
    """Render and upload images; returns the file_ids that uploaded."""
    if not images or not upload_image:
        return []
    file_ids = []
    for img_idx, data in enumerate(_render_images(pdf_path, images), start=1):
        if not data:
            continue
        file_id = upload_image(data, f"{prefix}_img{img_idx}")
        if file_id:
            file_ids.append(file_id)
    return file_ids


def _render_images(pdf_path, images):
    """Crop image regions to PNG bytes (same approach as extract_images_from_pdf)."""
    import io
    rendered = []
    with pdfplumber.open(pdf_path) as pdf:
        for img in images:
            try:
                page = pdf.pages[img["page"]]
                x0, top, x1, bottom = img["bbox"]
                bbox = (max(0, x0), max(0, top), min(page.width, x1), min(page.height, bottom))
                pil = page.within_bbox(bbox).to_image(resolution=150).original
                buf = io.BytesIO()
                pil.save(buf, format="PNG")
                rendered.append(buf.getvalue())
            except Exception as e:
                logger.warning(f"[Mettl] Could not render response image on page {img['page'] + 1}: {e}")
                rendered.append(None)
    return rendered


def _student_details(lines):
    details = {"student_name": None, "email": None, "participant_id": None, "assessment_name": None}
    for i, ln in enumerate(lines):
        text = ln["text"].strip()
        if details["email"] is None:
            m = _EMAIL_RE.search(text)
            if m:
                details["email"] = m.group(1)
        if details["participant_id"] is None:
            m = _PARTICIPANT_RE.search(text)
            if m:
                details["participant_id"] = m.group(1)
        if details["assessment_name"] is None and text.startswith("Assessment Name") and i + 1 < len(lines):
            details["assessment_name"] = lines[i + 1]["text"].strip()
        if details["student_name"] is None:
            # Every page footer reads "<org> | <participant name> Page N / M"
            m = _FOOTER_RE.match(text)
            if m:
                details["student_name"] = m.group("name").strip()
    return details


def parse_mettl_answer_sheet(pdf_path, upload_image=None):
    """
    Parse a Mettl report into the same shape split_into_qas returns:
        {"email": ..., "answers": [{"question_number": "1", "student_answer": str | None, ...}], ...}

    question_number runs 1..N across all sections in document order; the section and
    per-section number are kept alongside for traceability.
    """
    lines, tables, images, page_sizes = read_layout_lines(pdf_path)
    details = _student_details(lines)
    cards = _parse_cards(lines)

    if not cards:
        raise ValueError(
            "Failed to extract any questions from the Mettl answer sheet. "
            "Expected 'Question N' cards with 'Question' and 'Response' sections."
        )

    answers = []
    for global_idx, card in enumerate(cards, start=1):
        items = []

        resp_tables = _response_tables(card, tables, page_sizes)
        # Text lines inside a response table are represented by the table itself
        def _in_table(ln):
            return any(
                t["page"] == ln["page"] and t["bbox"][1] <= ln["y"] <= t["bbox"][3]
                for t in resp_tables
            )

        text = _render_response([ln for ln in card["response_lines"] if not _in_table(ln)]).strip()
        if text:
            items.append({"type": "text", "content": text})
        for t in resp_tables:
            items.append({"type": "table", "content": t["data"]})

        for file_id in _upload_region_images(
            pdf_path, _region_images(card, images, "response"), upload_image, f"answer_sheet_q{global_idx}"
        ):
            items.append({"type": "image", "file_id": file_id})
        question_images = _upload_region_images(
            pdf_path, _region_images(card, images, "question"), upload_image, f"question_q{global_idx}"
        )

        if not items:
            student_answer = None
        elif len(items) == 1 and items[0]["type"] == "text":
            student_answer = items[0]["content"]
        else:
            student_answer = json.dumps(items)

        answer = {
            "question_number": str(global_idx),
            "section": card["section"],
            "section_question_number": card["section_question_number"],
            "attempted": card["attempted"] and student_answer is not None,
            "student_answer": student_answer,
            # The question as shown to the student: graded against, and used to match the mark scheme question
            "question_text": _render_response(card["question_lines"], paragraphs=True),
        }
        if question_images:
            answer["question_images"] = question_images
        answers.append(answer)

    logger.info(
        f"[Mettl] Parsed {len(answers)} questions across "
        f"{len({c['section'] for c in cards})} section(s) for {details.get('student_name')}"
    )

    return {
        "email": details["email"],
        "student_name": details["student_name"],
        "participant_id": details["participant_id"],
        "assessment_name": details["assessment_name"],
        "answers": answers,
    }


# ---------- Mark scheme matching (Mettl shuffles question order per student) ----------
# The answer sheet order is what the UI shows, but the mark scheme may list the questions in a
# different order. Each sheet question is matched to its mark scheme question by question text,
# evaluation runs on mark scheme numbers (so the right rubric is always used), and the results
# are put back into the answer sheet's numbering and order afterwards.

_MIN_MATCH_SCORE = 0.6    # share of the sheet question's words found in the mark scheme question
_MIN_MATCH_MARGIN = 0.15  # best match must beat the runner-up by this much

MS_NUMBER_KEY = "mark_scheme_question_number"


def _question_tokens(text):
    text = (text or "").lower()
    text = re.sub(r"^\s*q\s*\d+\s*[.:)]\s*", "", text)   # "Q1." prefix in the mark scheme
    text = re.sub(r"\[\s*\d+\s*m\s*\]", " ", text)        # "[2M]" marks tags
    # Single digits are mostly code line numbers on the sheet; ignore them
    return Counter(t for t in re.findall(r"[a-z0-9_]+", text) if not t.isdigit() or len(t) > 1)


def _match_score(sheet_tokens, ms_tokens):
    """Share of the sheet question's words present in the mark scheme text. The mark scheme
    'question-text' can carry the sample solution after the question, so only the sheet side is
    used as the denominator."""
    if not sheet_tokens or not ms_tokens:
        return 0.0
    return sum((sheet_tokens & ms_tokens).values()) / sum(sheet_tokens.values())


def attach_mark_scheme_numbers(answers, mark_scheme_questions):
    """
    Keep answers in answer sheet order/numbering and add MS_NUMBER_KEY to each one.
    If the match is not confident for every question, nothing is attached (with a warning)
    and evaluation falls back to the sheet numbering.
    """
    if not any(a.get("question_text") for a in answers):
        return answers

    ms = [(str(q.get("questionnumber")), _question_tokens(q.get("question-text"))) for q in mark_scheme_questions or []]
    # A sheet may have fewer questions (skipped or choice questions left out), but not more
    if len(answers) > len(ms):
        logger.warning(
            f"[Mettl] Mark scheme has {len(ms)} questions but the sheet has {len(answers)}; "
            "cannot match questions, using answer sheet numbering"
        )
        return answers

    pairs, ambiguous = [], []
    for ai, a in enumerate(answers):
        at = _question_tokens(a.get("question_text"))
        scores = [_match_score(at, mt) for _, mt in ms]
        ranked = sorted(scores, reverse=True)
        if len(ranked) > 1 and ranked[0] - ranked[1] < _MIN_MATCH_MARGIN:
            ambiguous.append(ai)
        pairs.extend((sc, ai, mi) for mi, sc in enumerate(scores))
    pairs.sort(reverse=True)

    # Best one-to-one pairing: take the highest-scoring pairs first
    assigned, used_ms = {}, set()
    for score, ai, mi in pairs:
        if ai in assigned or mi in used_ms:
            continue
        assigned[ai] = (mi, score)
        used_ms.add(mi)

    weak = [(ai, sc) for ai, (_, sc) in assigned.items() if sc < _MIN_MATCH_SCORE]
    if len(assigned) != len(answers) or weak or ambiguous:
        for ai, sc in weak:
            logger.warning(f"[Mettl] Low match score {sc:.2f} for: {answers[ai].get('question_text', '')[:80]!r}")
        for ai in ambiguous:
            logger.warning(f"[Mettl] Ambiguous match for: {answers[ai].get('question_text', '')[:80]!r}")
        logger.warning("[Mettl] Could not confidently match questions to the mark scheme; using answer sheet numbering")
        return answers

    matched = []
    for ai, a in enumerate(answers):
        mi, score = assigned[ai]
        logger.info(
            f"[Mettl] Sheet Q{a.get('question_number')} (Section {a.get('section')} Q{a.get('section_question_number')}) "
            f"-> mark scheme Q{ms[mi][0]} (match {score:.2f})"
        )
        matched.append({**a, MS_NUMBER_KEY: ms[mi][0]})
    return matched


def _eval_answer(a, question_number):
    """Only the fields the evaluation model needs for one answer."""
    out = {
        "question_number": question_number,
        "question_text": a.get("question_text"),
        "student_answer": a.get("student_answer"),
    }
    if a.get("question_images"):
        out["question_images"] = a["question_images"]
    return out


def to_mark_scheme_numbering(sheet):
    """Copy of an answer sheet for the evaluation request: answers numbered and ordered like the
    mark scheme (sheet numbering when there is no confident mark scheme match)."""
    answers = sheet.get("answers", [])
    if not answers:
        return sheet
    if not all(a.get(MS_NUMBER_KEY) for a in answers):
        return {**sheet, "answers": [_eval_answer(a, a.get("question_number")) for a in answers]}
    renumbered = [_eval_answer(a, a[MS_NUMBER_KEY]) for a in answers]
    renumbered.sort(key=lambda a: int(a["question_number"]) if str(a["question_number"]).isdigit() else 0)
    return {**sheet, "answers": renumbered}


def restore_answer_sheet_order(student, sheet):
    """
    Put an evaluated student's answers back into the answer sheet's numbering and order and attach
    the sheet's section labels, question text and question images. `sheet` is the extracted answer
    sheet (answer sheet order).
    """
    sheet_answers = sheet.get("answers", [])
    if not sheet_answers:
        return student

    if all(a.get(MS_NUMBER_KEY) for a in sheet_answers):
        by_key = {str(a[MS_NUMBER_KEY]): a for a in sheet_answers}
    else:
        # No mark scheme match: evaluation already used the sheet numbering
        by_key = {str(a.get("question_number")): a for a in sheet_answers}

    restored, unmatched = [], []
    for ans in student.get("answers", []):
        src = by_key.get(str(ans.get("question_number")))
        if src is None:
            unmatched.append(ans)
            continue
        new_ans = {**ans, "question_number": src.get("question_number")}
        if src.get("section") is not None:
            new_ans["section"] = src.get("section")
            new_ans["section_question_number"] = src.get("section_question_number")
        if src.get(MS_NUMBER_KEY):
            new_ans[MS_NUMBER_KEY] = src.get(MS_NUMBER_KEY)
        # The model returns only marks and feedback; question and answer come from the sheet itself
        # (sheets without question text get the mark scheme's in the evaluation route)
        if src.get("question_text"):
            new_ans["question_text"] = src["question_text"]
        if src.get("question_images"):
            new_ans["question_images"] = src["question_images"]
        new_ans["student_answer"] = src.get("student_answer")
        restored.append(new_ans)

    if unmatched:
        logger.warning(
            f"[Mettl] {len(unmatched)} evaluated answer(s) for {student.get('file_id')} could not be mapped "
            "back to the answer sheet; appended at the end"
        )
    restored.sort(key=lambda a: int(a["question_number"]) if str(a.get("question_number")).isdigit() else 0)
    result = {**student, "answers": restored + unmatched}
    if unmatched:
        result["unmapped_answers"] = len(unmatched)
    return result
