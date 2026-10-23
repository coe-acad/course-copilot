"""Repair Markdown tables that a model flattened into plain pipe-separated lines."""
import re


_UNESCAPED_PIPE = re.compile(r"(?<!\\)\|")
_TABLE_LABEL = re.compile(r"^(\**[^|:*]{1,40}:\**)\s+(\S.*)$")
_TABLE_SEPARATOR = re.compile(r"^\|?\s*:?-{3,}:?\s*(\|\s*:?-{3,}:?\s*)*\|?$")


def _split_pipe_row(line: str) -> list:
    s = line.strip()
    if s.startswith("|"):
        # GFM style: the outer pipes are borders, not empty cells.
        s = s[1:]
        if s.endswith("|") and not s.endswith("\\|"):
            s = s[:-1]
    return [c.strip() for c in _UNESCAPED_PIPE.split(s)]


def _is_pipe_row(line: str) -> bool:
    return bool(_UNESCAPED_PIPE.search(line)) and not line.strip().startswith("```")


def _unfence_pipe_tables(lines: list) -> list:
    """Drop the ``` fence around a block that holds nothing but pipe rows — the
    model sometimes puts a flattened table in a code block along with the code."""
    out = []
    i = 0
    while i < len(lines):
        if lines[i].strip().startswith("```"):
            j = i + 1
            while j < len(lines) and not lines[j].strip().startswith("```"):
                j += 1
            body = [l for l in lines[i + 1:j] if l.strip()]
            # Only plain/text fences, and 3+ columns, so real code that happens
            # to use pipes (shell pipelines, `a | b`) stays a code block.
            info = lines[i].strip()[3:].strip().lower()
            if (j < len(lines) and info in ("", "text", "plaintext", "markdown", "md")
                    and len(body) >= 2 and all(_is_pipe_row(l) for l in body)
                    and min(len(_split_pipe_row(l)) for l in body) >= 3):
                out.extend(["", *body, ""])
                i = j + 1
                continue
            out.extend(lines[i:j + 1])
            i = j + 1
            continue
        out.append(lines[i])
        i += 1
    return out


def repair_pipe_tables(text: str) -> str:
    """Turn runs of pipe-separated lines that lack a ``| --- |`` separator row
    (how the model tends to flatten a question paper's table) into real GFM
    tables, so they render as tables in the viewer and the PDF/DOCX exports.
    Rows split by blank lines or wrapped in a pipe-only code fence are handled
    too. Other fenced code and tables that already have a separator are left
    untouched.
    """
    if not text or "|" not in text:
        return text
    lines = _unfence_pipe_tables(text.split("\n"))
    out = []
    in_fence = False
    i = 0
    while i < len(lines):
        line = lines[i]
        if line.strip().startswith("```"):
            in_fence = not in_fence
        if in_fence or not _is_pipe_row(line):
            out.append(line)
            i += 1
            continue
        # Collect the run of pipe rows, stepping over blank lines between rows.
        j = i
        while j < len(lines):
            if _is_pipe_row(lines[j]):
                j += 1
                continue
            k = j
            while k < len(lines) and not lines[k].strip():
                k += 1
            if k > j and k < len(lines) and _is_pipe_row(lines[k]):
                j = k
                continue
            break
        group = lines[i:j]
        block = [l for l in group if l.strip()]
        already_table = any(_TABLE_SEPARATOR.match(l.strip()) for l in block)
        if len(block) < 2 or already_table:
            out.extend(group)
            i = j
            continue
        rows = [_split_pipe_row(l) for l in block]
        # Width = header width, unless a body row has real content beyond it. A
        # trailing "|" on a row ("1 | | |") only adds empty cells, which are dropped.
        def _filled(r):
            return max((n + 1 for n, c in enumerate(r) if c), default=0)
        width = max([len(rows[0])] + [_filled(r) for r in rows[1:]])
        if width < 2:
            out.extend(group)
            i = j
            continue
        rows = [(r + [""] * width)[:width] for r in rows]
        # A label glued to the header row ("Question text: Partition | ...") goes
        # on its own line above the table instead of into the first header cell.
        label = _TABLE_LABEL.match(rows[0][0])
        if label:
            out.append(label.group(1))
            rows[0][0] = label.group(2)
        if out and out[-1].strip():
            out.append("")
        out.append("| " + " | ".join(rows[0]) + " |")
        out.append("|" + " --- |" * width)
        out.extend("| " + " | ".join(r) + " |" for r in rows[1:])
        if j < len(lines) and lines[j].strip():
            out.append("")
        i = j
    return "\n".join(out)
