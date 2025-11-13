import React, { useState } from "react";

export default function EvaluationTypeModal({ open, onClose, onSelectType }) {
  const [selectedType, setSelectedType] = useState("digital");

  if (!open) return null;

  const handleConfirm = () => {
    onSelectType(selectedType);
    onClose();
  };

  return (
    <div
      style={{
        position: "fixed",
        top: 0,
        left: 0,
        right: 0,
        bottom: 0,
        background: "rgba(0, 0, 0, 0.5)",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        zIndex: 9999,
      }}
      onClick={onClose}
    >
      <div
        style={{
          background: "#fff",
          borderRadius: "16px",
          padding: "32px",
          maxWidth: "500px",
          width: "90%",
          boxShadow: "0 8px 32px rgba(0, 0, 0, 0.12)",
        }}
        onClick={(e) => e.stopPropagation()}
      >
        <h2
          style={{
            margin: "0 0 12px 0",
            fontSize: "24px",
            fontWeight: 700,
            color: "#2563eb",
          }}
        >
          Select Evaluation Type
        </h2>
        <p
          style={{
            margin: "0 0 24px 0",
            fontSize: "14px",
            color: "#666",
          }}
        >
          Choose the type of evaluation workflow you want to use
        </p>

        <div style={{ display: "flex", flexDirection: "column", gap: "12px", marginBottom: "24px" }}>
          {/* Digital Evaluation Option */}
          <div
            onClick={() => setSelectedType("digital")}
            style={{
              padding: "16px 20px",
              border: selectedType === "digital" ? "2px solid #2563eb" : "2px solid #e5e7eb",
              borderRadius: "12px",
              cursor: "pointer",
              transition: "all 0.2s",
              background: selectedType === "digital" ? "#f0f9ff" : "#fff",
            }}
          >
            <div style={{ display: "flex", alignItems: "center", gap: "12px" }}>
              <div
                style={{
                  width: "20px",
                  height: "20px",
                  borderRadius: "50%",
                  border: selectedType === "digital" ? "6px solid #2563eb" : "2px solid #9ca3af",
                  transition: "all 0.2s",
                }}
              />
              <div>
                <div style={{ fontWeight: 600, fontSize: "16px", color: "#111" }}>
                  Digital Evaluation
                </div>
                <div style={{ fontSize: "13px", color: "#666", marginTop: "4px" }}>
                  For digitally typed answer sheets (PDF format)
                </div>
              </div>
            </div>
          </div>

          {/* Handwritten Evaluation Option */}
          <div
            onClick={() => setSelectedType("handwritten")}
            style={{
              padding: "16px 20px",
              border: selectedType === "handwritten" ? "2px solid #2563eb" : "2px solid #e5e7eb",
              borderRadius: "12px",
              cursor: "pointer",
              transition: "all 0.2s",
              background: selectedType === "handwritten" ? "#f0f9ff" : "#fff",
            }}
          >
            <div style={{ display: "flex", alignItems: "center", gap: "12px" }}>
              <div
                style={{
                  width: "20px",
                  height: "20px",
                  borderRadius: "50%",
                  border: selectedType === "handwritten" ? "6px solid #2563eb" : "2px solid #9ca3af",
                  transition: "all 0.2s",
                }}
              />
              <div>
                <div style={{ fontWeight: 600, fontSize: "16px", color: "#111" }}>
                  Handwritten Evaluation
                </div>
                <div style={{ fontSize: "13px", color: "#666", marginTop: "4px" }}>
                  For handwritten answer sheets (scanned images/PDFs)
                </div>
              </div>
            </div>
          </div>
        </div>

        <div style={{ display: "flex", gap: "12px", justifyContent: "flex-end" }}>
          <button
            onClick={onClose}
            style={{
              padding: "10px 20px",
              borderRadius: "8px",
              border: "1px solid #d1d5db",
              background: "#fff",
              color: "#374151",
              fontWeight: 600,
              fontSize: "14px",
              cursor: "pointer",
              transition: "all 0.2s",
            }}
          >
            Cancel
          </button>
          <button
            onClick={handleConfirm}
            style={{
              padding: "10px 24px",
              borderRadius: "8px",
              border: "none",
              background: "#2563eb",
              color: "#fff",
              fontWeight: 600,
              fontSize: "14px",
              cursor: "pointer",
              transition: "all 0.2s",
            }}
          >
            Continue
          </button>
        </div>
      </div>
    </div>
  );
}

