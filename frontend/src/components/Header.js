import React from "react";

export default function Header() {
  return (
    <header style={{ background: "#fff", borderBottom: "1px solid #eee", padding: "0.75rem 2rem", display: "flex", alignItems: "center" }}>
      <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
        <span style={{
          display: "inline-flex",
          alignItems: "center",
          justifyContent: "center",
          width: 32,
          height: 32,
          borderRadius: 8,
          background: "#2563eb",
          color: "#fff",
          fontWeight: 700,
          fontSize: 20,
          fontFamily: 'Inter, sans-serif',
        }}>
          C
        </span>
        <span style={{ fontWeight: 600, fontSize: 18, color: "#222", fontFamily: 'Inter, sans-serif' }}>Creators Copilot</span>
      </div>
    </header>
  );
} 