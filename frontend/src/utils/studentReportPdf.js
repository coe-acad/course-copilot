import { latexToText } from "./latexToText";

/**
 * Student report PDF, built from the evaluated student data (same content as the report modal):
 * header, summary tiles, then one card per question grouped by section.
 */

const COLORS = {
  text: [17, 24, 39],
  body: [55, 65, 81],
  muted: [107, 114, 128],
  faint: [148, 163, 184],
  border: [232, 236, 242],
  tile: [248, 250, 252],
  blue: [37, 99, 235],
  blueLine: [191, 219, 254],
  answerBg: [245, 248, 255],
  answerBorder: [219, 229, 251],
  codeBg: [241, 245, 249],
  green: [16, 185, 129],
  red: [248, 113, 113],
};

const PILL = {
  success: { bg: [236, 253, 245], fg: [4, 120, 87] },
  danger: { bg: [254, 242, 242], fg: [185, 28, 28] },
  warning: { bg: [255, 247, 237], fg: [194, 65, 12] },
  neutral: { bg: [241, 245, 249], fg: [100, 116, 139] },
};

// Question number to show: the section's number on Mettl sheets; on other sheets the mark scheme
// question the answer was matched to (a student may skip questions), else its position
export const questionLabel = (answer, position) => {
  if (answer?.section != null && answer?.section_question_number != null) return answer.section_question_number;
  if (answer?.section_question_number == null && answer?.mark_scheme_question_number) return answer.mark_scheme_question_number;
  return position;
};

const scoreTone = (score, max) => {
  if (!max) return PILL.neutral;
  if (score >= max) return PILL.success;
  if (score > 0) return PILL.warning;
  return PILL.danger;
};

// The built-in PDF fonts only cover Latin-1: spell out symbols they can't draw
const SYMBOL_MAP = {
  "→": "->", "←": "<-", "↔": "<->", "⇒": "=>", "⇐": "<=", "⇔": "<=>", "↑": "^", "↓": "v",
  "≤": "<=", "≥": ">=", "≠": "!=", "≈": "~", "≡": "==", "∼": "~", "∓": "-/+", "∗": "*", "⋆": "*",
  "∈": " in ", "∉": " not in ", "⊂": " subset ", "⊆": " subset= ", "∪": " U ", "∩": " n ",
  "∅": "{}", "∀": "for all ", "∃": "exists ", "∧": " and ", "∨": " or ", "¬": "not ",
  "Σ": "sum", "∏": "prod", "∫": "integral", "√": "sqrt", "∞": "infinity", "∂": "d", "∇": "nabla",
  "⌊": "floor(", "⌋": ")", "⌈": "ceil(", "⌉": ")", "…": "...", "⋯": "...",
  "–": "-", "—": "-", "‘": "'", "’": "'", "“": '"', "”": '"', "•": "-", "✓": "(ok)", "✔": "(ok)",
  "✗": "x", "✘": "x", "\t": " ",
  α: "alpha", β: "beta", γ: "gamma", δ: "delta", ε: "epsilon", ζ: "zeta", η: "eta", θ: "theta",
  ι: "iota", κ: "kappa", λ: "lambda", μ: "mu", ν: "nu", ξ: "xi", π: "pi", ρ: "rho", σ: "sigma",
  ς: "sigma", τ: "tau", υ: "upsilon", φ: "phi", χ: "chi", ψ: "psi", ω: "omega",
  Γ: "Gamma", Δ: "Delta", Θ: "Theta", Λ: "Lambda", Ξ: "Xi", Π: "Pi", Φ: "Phi", Ψ: "Psi", Ω: "Omega",
};

export function toPdfText(text) {
  if (text === null || text === undefined) return "";
  let out = "";
  for (const ch of String(text)) {
    if (SYMBOL_MAP[ch] !== undefined) out += SYMBOL_MAP[ch];
    else if (ch.codePointAt(0) <= 0xff) out += ch;
    else out += "?";
  }
  return out;
}

const stripMarkdown = (text) => String(text || "")
  .replace(/\*\*(.+?)\*\*/g, "$1")
  .replace(/__(.+?)__/g, "$1")
  .replace(/`([^`\n]+)`/g, "$1")
  .replace(/^#{1,6}\s+/gm, "")
  .replace(/^\s*[*]\s+/gm, "- ");

const cleanText = (text) => toPdfText(stripMarkdown(latexToText(text || ""))).replace(/\r/g, "");

// The model echoes the mark scheme's own number ("Q5. ..."); the heading already numbers the question
const cleanQuestionText = (text) => cleanText(text).replace(/^\s*Q\s*\d+\s*[.:)]\s*/i, "");

/** Split a stored answer into text / code (laid-out) / note segments. */
function answerSegments(raw) {
  if (typeof raw !== "string" || !raw.trim()) return [];

  let parts = [{ type: "text", content: raw }];
  if (raw.trim().startsWith("[")) {
    try {
      const items = JSON.parse(raw);
      if (Array.isArray(items)) {
        parts = items.map((item) => {
          if (item?.type === "text") return { type: "text", content: item.content || "" };
          if (item?.type === "table" && Array.isArray(item.content)) {
            const rows = item.content.map((r) => (Array.isArray(r) ? r : []).map((c) => toPdfText(String(c ?? "").replace(/\n/g, " "))));
            const widths = [];
            rows.forEach((r) => r.forEach((c, i) => { widths[i] = Math.max(widths[i] || 0, c.length); }));
            return { type: "code", lines: rows.map((r) => r.map((c, i) => c.padEnd(widths[i])).join(" | ")) };
          }
          if (item?.type === "image") return { type: "note", text: "[Image attached to this answer]" };
          return null;
        }).filter(Boolean);
      }
    } catch { /* plain text that happens to start with "[" */ }
  }

  // Fenced blocks hold laid-out answers (aligned columns, drawn trees)
  const segments = [];
  for (const part of parts) {
    if (part.type !== "text") { segments.push(part); continue; }
    let buffer = [];
    let inCode = false;
    const flush = () => {
      if (!buffer.length) return;
      if (inCode) segments.push({ type: "code", lines: buffer.map(toPdfText) });
      else {
        const text = cleanText(buffer.join("\n")).trim();
        if (text) segments.push({ type: "text", content: text });
      }
      buffer = [];
    };
    for (const line of String(part.content).split("\n")) {
      if (line.trim().startsWith("```")) { flush(); inCode = !inCode; continue; }
      buffer.push(line);
    }
    flush();
  }
  return segments;
}

// Minimum score (fraction of total marks) a student needs to pass.
export const PASS_MARK = 0.4;

export function buildStudentReportPdf(JsPDF, { student, name, passMark = PASS_MARK }) {
  const doc = new JsPDF({ unit: "mm", format: "a4" });
  const W = doc.internal.pageSize.getWidth();
  const H = doc.internal.pageSize.getHeight();
  const left = 16;
  const right = W - 16;
  const width = right - left;
  const top = 16;
  const bottom = H - 18;
  let y = top;

  const font = (size, style = "normal", color = COLORS.text, family = "helvetica") => {
    doc.setFont(family, style);
    doc.setFontSize(size);
    doc.setTextColor(...color);
  };
  const lineH = (size) => size * 0.3528 * 1.45;
  const newPage = () => { doc.addPage(); y = top; };
  const ensure = (h) => { if (y + h > bottom) newPage(); };

  const wrap = (text, w) => String(text).split("\n").flatMap((p) => (p.trim() ? doc.splitTextToSize(p, w) : [""]));

  // Monospace lines keep their spacing; long lines are cut at the width instead of reflowed
  const wrapMono = (lines, w, size) => {
    const maxChars = Math.max(10, Math.floor(w / (size * 0.3528 * 0.6)));
    return lines.flatMap((ln) => {
      const s = ln.replace(/\s+$/, "");
      if (s.length <= maxChars) return [s];
      const out = [];
      for (let i = 0; i < s.length; i += maxChars) out.push(s.slice(i, i + maxChars));
      return out;
    });
  };

  /** Draw lines (already wrapped) in an optional box, continuing onto new pages as needed. */
  const drawLines = (lines, { size, style = "normal", color = COLORS.body, family = "helvetica", bg = null, border = null, padX = 0, padY = 0 }) => {
    const lh = lineH(size);
    let i = 0;
    while (i < lines.length) {
      const room = Math.floor((bottom - y - 2 * padY) / lh);
      if (room < 1 || (room < 2 && lines.length - i > 1 && y > top + 1)) { newPage(); continue; }
      const chunk = lines.slice(i, i + room);
      const h = chunk.length * lh + 2 * padY;
      if (bg) {
        doc.setFillColor(...bg);
        if (border) doc.setDrawColor(...border);
        doc.setLineWidth(0.2);
        doc.roundedRect(left, y, width, h, 1.6, 1.6, border ? "FD" : "F");
      }
      font(size, style, color, family);
      const firstBaseline = y + padY + lh * 0.72;
      for (let k = 0; k < chunk.length; k += 1) doc.text(chunk[k], left + padX, firstBaseline + lh * k);
      y += h;
      i += chunk.length;
    }
  };

  // A label is never left alone at the bottom of a page: keep room for it plus the first lines below
  const label = (text) => {
    ensure(5 + 16);
    font(7, "bold", COLORS.muted);
    doc.text(text.toUpperCase(), left, y + 3);
    y += 5;
  };

  const pill = (text, tone, xRight, yTop, size = 8) => {
    font(size, "bold", tone.fg);
    const w = doc.getTextWidth(text) + 5;
    const h = size * 0.3528 + 2.6;
    doc.setFillColor(...tone.bg);
    doc.roundedRect(xRight - w, yTop, w, h, h / 2, h / 2, "F");
    doc.text(text, xRight - w / 2, yTop + h / 2 + size * 0.3528 * 0.35, { align: "center" });
    return w;
  };

  const answers = Array.isArray(student?.answers) ? student.answers : [];
  const total = student?.total_score ?? 0;
  const max = student?.max_total_score ?? 0;
  const pct = max ? total / max : null;
  const passed = pct !== null && pct >= passMark;
  const answered = answers.filter((a) => typeof a.student_answer === "string" && a.student_answer.trim()).length;
  const safeName = toPdfText(String(name || "Student").replace(/\.pdf$/i, ""));

  // ---- Header ----
  font(8, "bold", COLORS.muted);
  doc.text("STUDENT REPORT", left, y + 3);
  y += 5;
  font(16, "bold", COLORS.text);
  const nameLines = doc.splitTextToSize(safeName, width);
  nameLines.forEach((ln) => { doc.text(ln, left, y + 5.5); y += lineH(16); });
  font(9, "normal", COLORS.muted);
  const dateStr = new Date().toLocaleDateString("en-GB", { day: "numeric", month: "long", year: "numeric" });
  doc.text(`Generated on ${dateStr}`, left, y + 3.5);
  y += 8;
  doc.setDrawColor(...COLORS.border);
  doc.setLineWidth(0.3);
  doc.line(left, y, right, y);
  y += 6;

  // ---- Summary tiles ----
  const gap = 4;
  const tileW = (width - 3 * gap) / 4;
  const tileH = 20;
  const tiles = [
    { title: "Total marks", value: `${total}/${max}`, sub: pct !== null ? `${Math.round(pct * 100)}%` : "", bar: true },
    { title: "Result", pill: pct === null ? ["-", PILL.neutral] : [passed ? "Passed" : "Failed", passed ? PILL.success : PILL.danger] },
    { title: "Status", pill: student?.status === "modified" ? ["Modified", PILL.warning] : ["Unmodified", PILL.neutral] },
    { title: "Answered", value: `${answered}/${answers.length}` },
  ];
  tiles.forEach((t, i) => {
    const x = left + i * (tileW + gap);
    doc.setFillColor(...COLORS.tile);
    doc.setDrawColor(...COLORS.border);
    doc.setLineWidth(0.2);
    doc.roundedRect(x, y, tileW, tileH, 2, 2, "FD");
    font(7, "bold", COLORS.muted);
    doc.text(t.title.toUpperCase(), x + 4, y + 5.5);
    if (t.value) {
      font(13, "bold", COLORS.text);
      doc.text(t.value, x + 4, y + 12.5);
      if (t.sub) {
        const vw = doc.getTextWidth(t.value);
        font(9, "normal", COLORS.muted);
        doc.text(`(${t.sub})`, x + 6 + vw, y + 12.5);
      }
    }
    if (t.pill) {
      font(8, "bold");
      const pw = doc.getTextWidth(t.pill[0]) + 5;
      pill(t.pill[0], t.pill[1], x + 4 + pw, y + 8.5);
    }
    if (t.bar && pct !== null) {
      const bw = tileW - 8;
      doc.setFillColor(...COLORS.border);
      doc.roundedRect(x + 4, y + 15.5, bw, 1.4, 0.7, 0.7, "F");
      doc.setFillColor(...(passed ? COLORS.green : COLORS.red));
      doc.roundedRect(x + 4, y + 15.5, Math.max(1.4, bw * Math.min(1, pct)), 1.4, 0.7, 0.7, "F");
    }
  });
  y += tileH + 8;

  // ---- Questions ----
  answers.forEach((answer, index) => {
    const hasSection = answer.section != null && answer.section_question_number != null;
    const prev = answers[index - 1];
    if (hasSection && (!prev || prev.section !== answer.section)) {
      ensure(30);
      if (index > 0) y += 3;
      font(9.5, "bold", COLORS.blue);
      doc.text(`SECTION ${answer.section}`, left, y + 3.5);
      y += 5.5;
      doc.setDrawColor(...COLORS.blueLine);
      doc.setLineWidth(0.4);
      doc.line(left, y, right, y);
      y += 4;
    }

    // Card header: question number + score pill (kept with the start of its content)
    ensure(10 + 30);
    const headerH = 9;
    doc.setFillColor(...COLORS.tile);
    doc.setDrawColor(...COLORS.border);
    doc.setLineWidth(0.2);
    doc.roundedRect(left, y, width, headerH, 1.6, 1.6, "FD");
    font(10.5, "bold", COLORS.text);
    doc.text(`Question ${questionLabel(answer, index + 1)}`, left + 4, y + 6);
    const score = answer.score ?? 0;
    const scoreW = pill(`${score}/${answer.max_score ?? "?"}`, scoreTone(score, answer.max_score), right - 3, y + 2);
    if (answer.counted === false) pill("Not counted (choice)", PILL.neutral, right - 3 - scoreW - 2, y + 2);
    y += headerH + 4;

    // Question
    label("Question");
    font(9.5, "normal");
    drawLines(wrap(cleanQuestionText(answer.question_text) || "Question text not available", width), { size: 9.5, color: COLORS.text });
    y += 3;

    // Student answer
    label("Student answer");
    const segments = answerSegments(answer.student_answer);
    if (!segments.length) {
      drawLines(["Not attempted"], { size: 9.5, style: "italic", color: COLORS.faint, bg: COLORS.answerBg, border: COLORS.answerBorder, padX: 3.5, padY: 2.4 });
    }
    segments.forEach((seg, k) => {
      if (k > 0) y += 1.5;
      if (seg.type === "code") {
        drawLines(wrapMono(seg.lines, width - 7, 8.5), { size: 8.5, family: "courier", color: COLORS.text, bg: COLORS.codeBg, border: COLORS.border, padX: 3.5, padY: 2.4 });
      } else if (seg.type === "note") {
        drawLines([seg.text], { size: 9, style: "italic", color: COLORS.muted, bg: COLORS.answerBg, border: COLORS.answerBorder, padX: 3.5, padY: 2.4 });
      } else {
        font(9.5, "normal");
        drawLines(wrap(seg.content, width - 7), { size: 9.5, color: COLORS.text, bg: COLORS.answerBg, border: COLORS.answerBorder, padX: 3.5, padY: 2.4 });
      }
    });
    y += 3;

    // Feedback
    if (answer.feedback) {
      label("Feedback");
      font(9.5, "normal");
      drawLines(wrap(cleanText(answer.feedback), width), { size: 9.5, color: COLORS.body });
    }
    y += 7;
  });

  // ---- Footer on every page ----
  const pages = doc.getNumberOfPages();
  for (let p = 1; p <= pages; p += 1) {
    doc.setPage(p);
    doc.setDrawColor(...COLORS.border);
    doc.setLineWidth(0.2);
    doc.line(left, H - 12, right, H - 12);
    font(8, "normal", COLORS.faint);
    const footerName = doc.splitTextToSize(`${safeName} - Student report`, width - 30)[0];
    doc.text(footerName, left, H - 7.5);
    doc.text(`Page ${p} of ${pages}`, right, H - 7.5, { align: "right" });
  }
  return doc;
}

export const studentReportFileName = (name) => {
  const base = String(name || "student").replace(/\.pdf$/i, "").replace(/[^a-zA-Z0-9]+/g, "_").replace(/^_+|_+$/g, "");
  return `${base || "student"}_report_${new Date().toISOString().split("T")[0]}.pdf`;
};
