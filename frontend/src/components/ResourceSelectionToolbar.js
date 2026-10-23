import React from "react";

// Bulk-selection bar shared by the AI Studio Knowledge Base panel and the
// "Select Knowledge Base Files" modal. "Select all" is offered only when every
// resource fits under the cap, so it never silently picks an arbitrary subset.
export default function ResourceSelectionToolbar({ total, selectedCount, max = 10, onSelectAll, onClear, style }) {
  if (total === 0) return null;

  const canSelectAll = total <= max;
  const allSelected = selectedCount === total;
  const atLimit = selectedCount >= max;

  return (
    <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 8, fontSize: 13, ...style }}>
      {canSelectAll ? (
        <button
          type="button"
          onClick={onSelectAll}
          disabled={allSelected}
          style={{ ...linkStyle, color: allSelected ? "#9ca3af" : "#2563eb", cursor: allSelected ? "default" : "pointer" }}
        >
          Select all
        </button>
      ) : (
        <span style={{ color: "#6b7280" }}>Pick up to {max}</span>
      )}

      <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
        <span style={{ color: atLimit ? "#b45309" : "#6b7280" }}>
          <strong style={{ color: atLimit ? "#b45309" : "#111827", fontWeight: 600 }}>{selectedCount}</strong> / {max} selected
        </span>
        {selectedCount > 0 && (
          <button type="button" onClick={onClear} style={{ ...linkStyle, color: "#6b7280" }}>
            Clear
          </button>
        )}
      </div>
    </div>
  );
}

const linkStyle = {
  background: "none",
  border: "none",
  padding: 0,
  fontSize: 13,
  fontWeight: 500,
  cursor: "pointer",
};
