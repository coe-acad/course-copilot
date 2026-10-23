"""Shared helpers for rendering the sprint-structure timetable in downloads.

A sprint-structure table is a markdown table with "Coffee Break" and "Lunch"
columns. Its cells are "Activity – topic" and are colour-coded by activity, the
same way the app renders them (keep in sync with frontend/src/utils/sprintStructure.js).
"""

from __future__ import annotations

import re
from typing import List, Optional, Tuple

HEADER_BG = "000000"
HEADER_FG = "FFFFFF"
WEEKEND_BG = "B7B7B7"
WEEKEND_FG = "4B5563"
BREAK_BG = "D9D9D9"
BREAK_FG = "374151"

# Default legend from the sprint-structure prompt: (fill, font colour, bold).
_LECTURE = ("CFE2F3", "000000", False)
_PROJECT = ("00FF00", "000000", False)
_ASSIGNMENT = ("FF9900", "000000", False)
_GREY = (BREAK_BG, BREAK_FG, False)

# (normalised label prefix, (fill, font colour, bold)). First match wins, so
# "codingchallenge" is listed before "coding". Labels outside the legend
# (Problem Solving, Assessment, Coding, Code Comprehension, Meme creation) reuse
# the closest legend entry.
ACTIVITY_COLOURS = [
    ("lecture", _LECTURE),
    ("problemsolving", _LECTURE),
    ("paperpen", ("FFF2CC", "000000", False)),
    ("simulation", ("EAD1DC", "000000", False)),
    ("livecoding", ("EAD1DC", "000000", False)),
    ("codingchallenge", ("8E7CC3", "FFFFFF", True)),
    ("jigsaw", ("46BDC6", "000000", False)),
    ("reflection", ("FFD966", "000000", False)),
    ("assessment", _ASSIGNMENT),
    ("assignment", _ASSIGNMENT),
    ("project", _PROJECT),
    ("codecomprehension", _PROJECT),
    ("coding", _PROJECT),
    ("meme", _PROJECT),
    ("coffeebreak", _GREY),
    ("lunch", _GREY),
]


def normalise(text: str) -> str:
    return re.sub(r"[^a-z0-9]", "", (text or "").lower())


def plain(text: str) -> str:
    """Cell text without markdown emphasis/code markers."""
    t = re.sub(r"\*\*(.+?)\*\*|__(.+?)__", lambda m: m.group(1) or m.group(2), text or "")
    t = re.sub(r"`([^`]+)`", r"\1", t)
    return t.strip()


def activity_colour(text: str) -> Optional[Tuple[str, str, bool]]:
    """(fill, font colour, bold) for an activity cell, or None."""
    key = normalise(plain(text))
    if not key:
        return None
    for prefix, colour in ACTIVITY_COLOURS:
        if key.startswith(prefix):
            return colour
    return None


def is_break(text: str) -> bool:
    return normalise(plain(text)) in ("coffeebreak", "lunch")


def is_weekend_row(row: List[str]) -> bool:
    return bool(row) and normalise(plain(row[0])) == "weekend"


def is_sprint_table(headers: List[str]) -> bool:
    keys = {normalise(plain(h)) for h in headers}
    return "coffeebreak" in keys and "lunch" in keys


def has_sprint_table(blocks: List[dict]) -> bool:
    return any(b.get("type") == "table" and is_sprint_table(b.get("headers", [])) for b in blocks)


WIDE_TABLE_COLUMNS = 9


def needs_landscape(blocks: List[dict]) -> bool:
    """Sprint timetables and other very wide tables read better on landscape pages."""
    return has_sprint_table(blocks) or any(
        b.get("type") == "table" and len(b.get("headers", [])) >= WIDE_TABLE_COLUMNS for b in blocks
    )


def is_sprint_legend(block: dict, doc_has_sprint: bool) -> bool:
    """The one-column "Colour Key" table that follows a sprint timetable."""
    return doc_has_sprint and block.get("type") == "table" and len(block.get("headers", [])) == 1


def split_label(text: str) -> Optional[Tuple[str, str]]:
    """Split an "Activity – topic" cell into (activity, topic) when the activity is known."""
    m = re.match(r"^(.+?)\s+[–—-]\s+(.+)$", plain(text), flags=re.S)
    if m and activity_colour(m.group(1)):
        return m.group(1).strip(), m.group(2).strip()
    return None


def break_runs(headers: List[str], rows: List[List[str]]) -> List[Tuple[int, int, int]]:
    """(column, first_row, last_row) runs of break cells to merge vertically.

    Row indexes are 0-based into ``rows``; runs are split by weekend rows.
    """
    runs = []
    for c, h in enumerate(headers):
        if not is_break(h):
            continue
        start = None
        for r in range(len(rows) + 1):
            cell = rows[r][c] if r < len(rows) and c < len(rows[r]) else ""
            if r < len(rows) and is_break(cell):
                if start is None:
                    start = r
            elif start is not None:
                runs.append((c, start, r - 1))
                start = None
    return runs


def column_weights(headers: List[str], rows: List[List[str]]) -> List[float]:
    """Relative column widths for a sprint timetable: narrow breaks/day, wide slots."""
    weights = []
    for c, h in enumerate(headers):
        key = normalise(plain(h))
        if is_break(h):
            weights.append(0.55)
        elif key == "day":
            weights.append(0.5)
        elif key == "date":
            weights.append(1.1)
        else:
            weights.append(2.0)
    return weights
