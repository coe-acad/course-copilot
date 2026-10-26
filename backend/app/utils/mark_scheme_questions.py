"""Keep the question text in a generated mark scheme identical to the extracted paper.

The mark-scheme model also sees the original PDF, and for PDFs it tends to copy a
question's page layout (tables drawn with spaces, code without fences) instead of
the clean Markdown produced by the question-extraction step. Since that step
already holds every question's exact text, it is put back verbatim here.
"""
import json
import logging
import re

logger = logging.getLogger(__name__)

_QUESTION_NUMBER = re.compile(r"\**\s*Question\s*number\s*:\**\s*", re.IGNORECASE)
_QUESTION_TEXT = re.compile(r"(\**\s*Question\s*text\s*:\**[ \t]*)", re.IGNORECASE)
_MARKING_SCHEME = re.compile(r"\n[ \t]*[#*]*\s*Marking\s*scheme", re.IGNORECASE)


def _question_key(value) -> str:
    """'Q15', '15', 'Question 15' -> '15' (sub-part letters kept, e.g. '14a')."""
    m = re.search(r"\d+(?:[a-z](?![a-z]))?", str(value or ""), re.IGNORECASE)
    return m.group(0).lower() if m else ""


# A function/procedure header line: "def operation(head):", "QuickSort(A, low, high):",
# "INSERT_AT_END(head, value):", "class Node:".
_CODE_HEADER = re.compile(r"^\s*(?:def\s+\w+\s*\(.*\)|class\s+\w+.*|[A-Za-z_]\w*\s*\([^()]*\))\s*:\s*$")


def fence_unfenced_code(text: str) -> str:
    """Wrap code the extraction left as plain lines in a ``` block.

    A block starts at a function header and runs over the indented lines, blank
    lines and further headers after it; the first unindented non-header line
    ends it. Text that already has a fence is returned unchanged.
    """
    if not text or "```" in text:
        return text
    lines = text.split("\n")
    out = []
    i = 0
    while i < len(lines):
        if not _CODE_HEADER.match(lines[i]):
            out.append(lines[i])
            i += 1
            continue
        j = i + 1
        while j < len(lines) and (
            not lines[j].strip() or lines[j][:1] in (" ", "\t") or _CODE_HEADER.match(lines[j])
        ):
            j += 1
        block = lines[i:j]
        while block and not block[-1].strip():
            block.pop()
        # A lone header with no indented body is just a sentence, not code.
        if len(block) < 2:
            out.append(lines[i])
            i += 1
            continue
        indent = min(len(l) - len(l.lstrip()) for l in block if l.strip())
        if out and out[-1].strip():
            out.append("")
        out.append("```")
        out.extend(l[indent:].rstrip() for l in block)
        out.append("```")
        out.append("")
        i = i + len(block)
        while i < len(lines) and not lines[i].strip():
            i += 1
    return "\n".join(out).rstrip()


def parse_extracted_questions(text: str) -> dict:
    """Map question key -> question text from the qp-extraction JSON output.

    Returns {} when the output isn't parseable JSON; callers then leave the
    mark scheme untouched.
    """
    if not text:
        return {}
    start, end = text.find("["), text.rfind("]")
    if start < 0 or end <= start:
        return {}
    try:
        items = json.loads(text[start:end + 1])
    except json.JSONDecodeError as e:
        logger.warning(f"[mark-scheme] extracted questions are not valid JSON: {e}")
        return {}
    questions = {}
    for item in items if isinstance(items, list) else []:
        if not isinstance(item, dict):
            continue
        number = next((v for k, v in item.items() if re.sub(r"[\s_]", "", k).lower() == "questionnumber"), None)
        body = next((v for k, v in item.items() if re.sub(r"[\s_]", "", k).lower() == "questiontext"), None)
        key = _question_key(number)
        if key in questions:
            # Numbering restarts per set/section, so a number can't identify the question.
            logger.warning(f"[mark-scheme] question number {key} repeats in the paper; not restoring question texts")
            return {}
        if key and isinstance(body, str) and body.strip():
            questions[key] = fence_unfenced_code(body.strip())
    return questions


def restore_question_texts(mark_scheme: str, extracted_questions: str) -> str:
    """Replace each "Question text:" section of the mark scheme with the text the
    extraction step produced for that question number. Sections whose number or
    layout can't be matched are left as the model wrote them."""
    questions = parse_extracted_questions(extracted_questions)
    if not mark_scheme or not questions:
        return mark_scheme

    starts = [m.start() for m in _QUESTION_NUMBER.finditer(mark_scheme)]
    if not starts:
        return mark_scheme
    pieces = [mark_scheme[:starts[0]]]
    replaced = 0
    for idx, start in enumerate(starts):
        end = starts[idx + 1] if idx + 1 < len(starts) else len(mark_scheme)
        section = mark_scheme[start:end]
        number_match = _QUESTION_NUMBER.match(section)
        key = _question_key(section[number_match.end():number_match.end() + 20])
        label = _QUESTION_TEXT.search(section)
        scheme = _MARKING_SCHEME.search(section, label.end()) if label else None
        if key in questions and label and scheme:
            section = (
                section[:label.end()].rstrip() + "\n"
                + questions[key] + "\n\n"
                + section[scheme.start():].lstrip("\n")
            )
            replaced += 1
        pieces.append(section)
    logger.info(f"[mark-scheme] restored extracted text for {replaced}/{len(starts)} questions")
    return "".join(pieces)
