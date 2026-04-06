import React from "react";

export function ModalBase({ open, onClose, children, modalStyle: customModalStyle }) {
  if (!open) return null;
  return (
    <div style={overlayStyle} onClick={onClose}>
      <div style={{ ...modalStyle, ...customModalStyle }} onClick={e => e.stopPropagation()}>
        {children}
      </div>
    </div>
  );
}

export default function Modal(props) {
  return <ModalBase {...props} />;
}

const overlayStyle = {
  position: "fixed",
  top: 0,
  left: 0,
  width: "100vw",
  height: "100vh",
  background: "rgba(0,0,0,0.12)",
  display: "flex",
  alignItems: "center",
  justifyContent: "center",
  padding: "20px",
  overflowY: "hidden",
  zIndex: 1000,
};

const modalStyle = {
  background: "#fff",
  borderRadius: 16,
  boxShadow: "0 24px 48px rgba(0,0,0,0.12)",
  padding: "24px",
  minWidth: 560,
  maxWidth: 720,
  width: "min(720px, 100%)",
  maxHeight: "calc(100vh - 40px)",
  overflowY: "auto",
  display: "flex",
  flexDirection: "column",
  justifyContent: "flex-start"
}; 