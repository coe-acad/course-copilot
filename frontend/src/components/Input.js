import React from "react";

export default function Input({ label, type = "text", value, onChange, ...props }) {
  return (
    <div style={{ marginBottom: "1rem" }}>
      <label>
        {label}
        <input
          type={type}
          value={value}
          onChange={onChange}
          style={{ display: "block", width: "100%", padding: "0.5rem" }}
          {...props}
        />
      </label>
    </div>
  );
}
