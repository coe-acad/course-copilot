import React from "react";

export default function SectionCard({ title, description, buttonLabel, style, onButtonClick }) {
  return (
    <div style={{ background: "#fff", borderRadius: 12, boxShadow: "0 1px 4px #0001", padding: "32px 36px", minHeight: 140, display: "flex", flexDirection: "column", justifyContent: "center", ...style }}>
      <div style={{ display: "flex", alignItems: "center", gap: 16 }}>
        <h2 style={{ margin: 0, fontSize: 24, fontWeight: 600, flex: 1 }}>{title}</h2>
      </div>
      {description && <span style={{ fontSize: 16, color: "#222", marginTop: 12, marginBottom: 24 }}>{description}</span>}
      {buttonLabel && (
        <div style={{ display: "flex", justifyContent: "center", marginTop: description ? 0 : 24 }}>
          <button style={btnStyle} onClick={onButtonClick}>{buttonLabel}</button>
        </div>
      )}
    </div>
  );
}

const btnStyle = {
  padding: "8px 22px",
  borderRadius: 6,
  border: "1px solid #bbb",
  background: "#fff",
  fontWeight: 500,
  fontSize: 15,
  cursor: "pointer",
  marginLeft: 0,
  boxShadow: "0 1px 2px #0001",
  transition: "background 0.2s",
}; 