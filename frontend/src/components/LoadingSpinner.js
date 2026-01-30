import React from "react";

const containerStyle = {
  display: "flex",
  alignItems: "center",
  justifyContent: "center",
  minHeight: "40vh",
};

const dotsWrapperStyle = {
  display: "flex",
  gap: 10,
};

const dotBaseStyle = {
  width: 10,
  height: 10,
  borderRadius: "999px",
  background: "#2563eb",
  opacity: 0.25,
  animation: "blink 1.1s ease-in-out infinite",
};

const keyframes = `
@keyframes blink {
  0% { transform: translateY(0); opacity: 0.25; }
  25% { transform: translateY(-6px); opacity: 1; }
  50% { transform: translateY(0); opacity: 0.6; }
  100% { transform: translateY(0); opacity: 0.25; }
}
`;

export default function LoadingSpinner() {
  return (
    <div style={containerStyle} aria-label="Loading">
      <style>{keyframes}</style>
      <div style={dotsWrapperStyle}>
        <div style={{ ...dotBaseStyle, animationDelay: "0s" }} />
        <div style={{ ...dotBaseStyle, animationDelay: "0.15s" }} />
        <div style={{ ...dotBaseStyle, animationDelay: "0.3s" }} />
        <div style={{ ...dotBaseStyle, animationDelay: "0.45s" }} />
      </div>
    </div>
  );
}