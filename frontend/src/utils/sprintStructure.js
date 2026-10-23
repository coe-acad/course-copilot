import React from "react";

// Asset types rendered as a colour-coded sprint timetable. "sprint-plan-doc" is
// the old name of "sprint-structure", kept so previously saved assets still render.
export const SPRINT_STRUCTURE_TYPES = ["sprint-structure", "sprint-plan-doc"];

export const isSprintStructure = (assetType) => SPRINT_STRUCTURE_TYPES.includes(assetType);

// Default legend from the sprint-structure prompt (keep in sync with
// backend/app/utils/sprint_structure.py). Labels outside the legend (Problem
// Solving, Assessment, Coding, Code Comprehension, Meme creation) reuse the
// closest legend entry.
const LECTURE = { background: "#cfe2f3", color: "#000000" };
const PROJECT = { background: "#00ff00", color: "#000000" };
const ASSIGNMENT = { background: "#ff9900", color: "#000000" };
const GREY = { background: "#d9d9d9", color: "#374151" };

// Activity labels (normalised: lowercase, letters/digits only) -> cell colours.
// Order matters: the first matching prefix wins ("codingchallenge" before "coding").
const ACTIVITY_COLOURS = [
  ["lecture", LECTURE],
  ["problemsolving", LECTURE],
  ["paperpen", { background: "#fff2cc", color: "#000000" }],
  ["simulation", { background: "#ead1dc", color: "#000000" }],
  ["livecoding", { background: "#ead1dc", color: "#000000" }],
  ["codingchallenge", { background: "#8e7cc3", color: "#ffffff", fontWeight: 700 }],
  ["jigsaw", { background: "#46bdc6", color: "#000000" }],
  ["reflection", { background: "#ffd966", color: "#000000" }],
  ["assessment", ASSIGNMENT],
  ["assignment", ASSIGNMENT],
  ["project", PROJECT],
  ["codecomprehension", PROJECT],
  ["coding", PROJECT],
  ["meme", PROJECT],
  ["coffeebreak", GREY],
  ["lunch", GREY],
];

const normalise = (text) => (text || "").toLowerCase().replace(/[^a-z0-9]/g, "");

const activityColour = (text) => {
  const key = normalise(text);
  if (!key) return null;
  const match = ACTIVITY_COLOURS.find(([prefix]) => key.startsWith(prefix));
  return match ? match[1] : null;
};

const isBreak = (text) => ["coffeebreak", "lunch"].includes(normalise(text));

// Plain text of rendered React children (strings, arrays, <strong> etc.).
const childrenText = (children) => {
  if (children === null || children === undefined || typeof children === "boolean") return "";
  if (typeof children === "string" || typeof children === "number") return String(children);
  if (Array.isArray(children)) return children.map(childrenText).join("");
  if (React.isValidElement(children)) return childrenText(children.props.children);
  return "";
};

// Plain text of a hast node (react-markdown passes the source node as `node`).
const hastText = (node) => {
  if (!node) return "";
  if (node.type === "text") return node.value || "";
  return (node.children || []).map(hastText).join("");
};

const HEADER_WIDTHS = { date: "118px", day: "52px", coffeebreak: "46px", lunch: "46px" };

const cellBase = {
  border: "1px solid #000000",
  padding: "8px 6px",
  textAlign: "center",
  verticalAlign: "middle",
  fontSize: "13px",
  lineHeight: "1.35",
  wordWrap: "break-word",
};

// Break cells are plain grey bands (the header names the break), like the merged
// break columns of the spreadsheet timetable.
const breakCell = { ...cellBase, ...GREY, padding: 0, fontSize: 0, borderTopColor: GREY.background, borderBottomColor: GREY.background };

// Number of columns in a table's first row (hast), used to size the legend.
const columnCount = (tableNode) => {
  const firstRow = (tableNode?.children || [])
    .filter((c) => c.type === "element")
    .flatMap((section) => (section.children || []).filter((c) => c.type === "element"))[0];
  return (firstRow?.children || []).filter((c) => c.type === "element").length;
};

// Overrides that turn markdown tables into the colour-coded sprint timetable:
// black header, one colour per activity type, grey breaks and weekend rows.
export const sprintStructureComponents = {
  table: ({ node, children }) => {
    // The timetable spans the full width; small tables (the legend) stay compact.
    const isTimetable = columnCount(node) > 2;
    return (
      <div style={{ overflowX: "auto", margin: "14px 0" }}>
        <table style={isTimetable
          ? { borderCollapse: "collapse", width: "100%", minWidth: "880px", tableLayout: "fixed", fontSize: "13px" }
          : { borderCollapse: "collapse", width: "260px", fontSize: "13px" }}>{children}</table>
      </div>
    );
  },
  thead: ({ children }) => <thead>{children}</thead>,
  tbody: ({ children }) => <tbody>{children}</tbody>,
  tr: ({ node, children }) => {
    const firstCell = (node?.children || []).find((c) => c.type === "element");
    const isWeekend = normalise(hastText(firstCell)) === "weekend";
    return <tr style={isWeekend ? { background: "#b7b7b7", height: "26px" } : undefined}>{children}</tr>;
  },
  th: ({ children }) => {
    const text = childrenText(children);
    const width = HEADER_WIDTHS[normalise(text)];
    return (
      <th style={{ ...cellBase, background: "#000000", color: "#ffffff", fontWeight: 700, width, fontSize: width && isBreak(text) ? "10px" : "13px" }}>
        {children}
      </th>
    );
  },
  td: ({ children }) => {
    const text = childrenText(children);
    if (normalise(text) === "weekend") {
      return <td style={{ ...cellBase, color: "#4b5563", fontWeight: 600 }}>{children}</td>;
    }
    if (isBreak(text)) {
      return <td style={breakCell}>{children}</td>;
    }
    // Blank cells stay transparent so a weekend row's grey shows through.
    const colour = normalise(text) ? activityColour(text) || { background: "#ffffff", color: "#111827" } : null;
    // "Label – topic" cells show the activity label above its topic, in the
    // legend's font (bold only where the legend says so).
    const split = colour && text.match(/^(.+?)\s+[–—-]\s+(.+)$/);
    if (split && activityColour(split[1])) {
      return (
        <td style={{ ...cellBase, ...colour }}>
          <div>{split[1]}</div>
          <div style={{ fontSize: "12px", marginTop: "3px" }}>{split[2]}</div>
        </td>
      );
    }
    return <td style={{ ...cellBase, ...colour }}>{children}</td>;
  },
};
