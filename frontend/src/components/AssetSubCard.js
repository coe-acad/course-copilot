import React from "react";

export default function AssetSubCard({ label, name, updatedBy = "Joseph Chackon", timestamp }) {
  return (
    <div
      style={{
        minWidth: 240,
        background: "#fff",
        border: "1px solid #e5e7eb",
        borderRadius: 14,
        boxShadow: "0 2px 8px #0001",
        padding: "18px 20px",
        display: "flex",
        flexDirection: "column",
        alignItems: "flex-start",
        position: "relative",
        marginRight: 12,
      }}
    >
      {/* Pill label */}
      <div
        style={{
          background: "#f3f4f6",
          color: "#444",
          fontWeight: 600,
          fontSize: 13,
          borderRadius: 16,
          padding: "2px 12px",
          marginBottom: 10,
          display: "inline-block",
        }}
      >
        {label}
      </div>
      {/* Asset name */}
      <div
        style={{
          fontWeight: 700,
          fontSize: 18,
          marginBottom: 8,
        }}
      >
        {name}
      </div>
      {/* Last updated info */}
      <div
        style={{
          fontSize: 13,
          color: "#888",
        }}
      >
        Last updated {updatedBy}
        <br />
        {timestamp
          ? new Date(timestamp).toLocaleString("en-US", {
              month: "short",
              day: "numeric",
              hour: "numeric",
              minute: "2-digit",
            })
          : ""}
      </div>
    </div>
  );
}