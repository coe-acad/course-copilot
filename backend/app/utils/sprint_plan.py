import re
from typing import Dict, List


def _parse_markdown_table(text: str) -> List[List[str]]:
    rows = []
    for line in (text or "").splitlines():
        if "|" not in line:
            continue
        stripped = line.strip()
        if not stripped or set(stripped.replace("|", "").strip()) <= {"-", ":"}:
            continue
        parts = [p.strip() for p in stripped.strip("|").split("|")]
        if len(parts) >= 2:
            rows.append(parts)
    return rows


def _parse_course_outcomes(co_content: str) -> List[Dict[str, str]]:
    rows = _parse_markdown_table(co_content)
    if not rows:
        return []
    header = [h.lower() for h in rows[0]]
    data_rows = rows[1:]

    def col_index(name: str) -> int:
        for i, h in enumerate(header):
            if name in h:
                return i
        return -1

    co_idx = col_index("co")
    name_idx = col_index("name")
    desc_idx = col_index("description")
    bloom_idx = col_index("bloom")

    outcomes = []
    for row in data_rows:
        if co_idx < 0 or co_idx >= len(row):
            continue
        co_id = row[co_idx].strip()
        name = row[name_idx].strip() if 0 <= name_idx < len(row) else ""
        desc = row[desc_idx].strip() if 0 <= desc_idx < len(row) else ""
        blooms = row[bloom_idx].strip() if 0 <= bloom_idx < len(row) else ""
        if not co_id:
            continue
        outcomes.append(
            {
                "id": co_id,
                "name": name,
                "description": desc,
                "blooms": blooms,
            }
        )
    return outcomes


def _split_modules(modules_content: str, max_modules: int = 4) -> List[str]:
    if not modules_content:
        return []
    pattern = re.compile(r"(?=^Module\s+\d+\s*:)", re.MULTILINE)
    parts = [p.strip() for p in pattern.split(modules_content) if p.strip()]
    if parts:
        return parts[:max_modules]
    return [modules_content.strip()] if modules_content.strip() else []


def _build_bloom_table(outcomes: List[Dict[str, str]]) -> str:
    headers = ["CO", "Description", "Remember", "Understand", "Apply", "Analyze", "Evaluate", "Create"]
    rows = ["| " + " | ".join(headers) + " |", "|" + "|".join(["---"] * len(headers)) + "|"]

    def mark(blooms: str, level: str) -> str:
        return "✓" if level.lower() in blooms.lower() else ""

    for outcome in outcomes[:4]:
        desc = outcome["name"] or outcome["description"]
        blooms = outcome["blooms"] or ""
        row = [
            outcome["id"],
            desc,
            mark(blooms, "Remember"),
            mark(blooms, "Understand"),
            mark(blooms, "Apply"),
            mark(blooms, "Analyze"),
            mark(blooms, "Evaluate"),
            mark(blooms, "Create"),
        ]
        rows.append("| " + " | ".join(row) + " |")
    return "\n".join(rows)


def _build_po_pso_table(outcomes: List[Dict[str, str]]) -> str:
    headers = ["Course", "PO1", "PO2", "PO3", "PO4", "PO5", "PO6", "PO7", "PO8", "PO9", "PO10", "PO11", "PO12", "PSO1", "PSO2", "PSO3"]
    rows = ["| " + " | ".join(headers) + " |", "|" + "|".join(["---"] * len(headers)) + "|"]
    for outcome in outcomes[:4]:
        rows.append("| " + " | ".join([outcome["id"]] + [""] * (len(headers) - 1)) + " |")
    return "\n".join(rows)


def build_sprint_plan(
    *,
    course_name: str,
    course_description: str,
    course_outcomes_content: str,
    modules_content: str,
    po_pso_content: str,
) -> str:
    outcomes = _parse_course_outcomes(course_outcomes_content)
    modules = _split_modules(modules_content)

    sprint_outcomes_lines = []
    for idx, outcome in enumerate(outcomes[:4], start=1):
        text = outcome["description"] or outcome["name"] or ""
        if text:
            sprint_outcomes_lines.append(f"CO{idx}: {text}")
        else:
            sprint_outcomes_lines.append(f"CO{idx}: ")

    if not sprint_outcomes_lines:
        sprint_outcomes_lines = [
            "CO1: ",
            "CO2: ",
            "CO3: ",
            "CO4: ",
        ]

    bloom_table = _build_bloom_table(outcomes) if outcomes else _build_bloom_table([{"id": "CO1", "name": "", "description": "", "blooms": ""}])

    mapping_table = "<<AI_CO_PO_PSO_TABLE>>"

    modules_block = "\n\n".join(modules) if modules else "Module 1:\nModule name: \nDuration in hours: \nMapped to CO's: \nDescription: \n"

    sprint_body = (
        f"**Sprint Description:**\n{course_description}\n\n"
        f"---\n\n"
        f"**Sprint Outcomes: (maximum 4)**\n\n"
        + "\n".join(sprint_outcomes_lines)
        + "\n\n---\n\n"
        f"**Bloom's Learning Level Table:**\n\n{bloom_table}\n\n"
        f"---\n\n"
        f"**CO-PO-PSO Mapping Table:**\n\n{mapping_table}\n\n"
        f"---\n\n"
        f"**Module Descriptions:**\n\n{modules_block}\n\n"
        f"---\n\n"
        f"**3 Textbook Titles:**\n\n<<AI_TEXTBOOKS>>\n\n"
        f"---\n\n"
        f"**3 Reference Books:**\n\n<<AI_REFERENCES>>\n\n"
        f"---"
    )

    cover_table = (
        f"| Name of the Sprint | {course_name} |\n"
        f"|---|---|\n"
        f"| Sprint code | To be filled by Academic Operations |\n"
        f"| CoE Offering it | |\n"
        f"| Number of Credits | 4 |\n"
        f"| Credit Structure (Lecture:Tutorial:Practical:Self-study) | To be filled by Academic Operations |\n"
        f"| Total Hours | 72 |\n"
        f"| Number of Weeks in a Sprint | 3 |\n"
        f"| Total Course Marks | 200 |\n"
        f"| Pass Criteria | As per academic regulations |\n"
        f"| Attendance Criteria | As per academic regulations |\n"
    )

    return f"{cover_table}\n\n{sprint_body}"
