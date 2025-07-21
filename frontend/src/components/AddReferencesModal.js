// backend integration: integrate file upload and reference management with backend
import React from "react";
import { ModalBase } from "./Modal";

const addReferencesModalStyle = {
  minWidth: 520,
  maxWidth: 700,
  width: "100%",
  minHeight: 250,
  maxHeight: 500,
  height: "auto",
  padding: "36px 32px 40px 32px",
  borderRadius: 16,
  display: "flex",
  flexDirection: "column",
  justifyContent: "center",
};

export default function AddReferencesModal({ open, onClose, children }) {
  return (
    <ModalBase open={open} onClose={onClose} modalStyle={addReferencesModalStyle}>
      {children}
    </ModalBase>
  );
} 