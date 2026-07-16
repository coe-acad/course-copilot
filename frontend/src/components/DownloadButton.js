import React, { useState } from "react";
import { FiDownload, FiFileText, FiFile } from "react-icons/fi";
import { ModalBase } from "./Modal";
import { assetService } from "../services/asset";

/**
 * Common download control used everywhere content can be downloaded (chat
 * message, asset card view, resource view). Renders a trigger, opens a
 * PDF / Word format chooser, and downloads through assetService.downloadContent
 * so the output format is identical no matter where it is triggered from.
 *
 * Props:
 *  - courseId : string
 *  - filename : string        base name (no extension)
 *  - content  : string | () => (string | Promise<string>)
 *                             the markdown content, or a resolver for it
 *  - renderTrigger : (open) => ReactNode   optional custom trigger (e.g. an icon)
 *  - title    : string        tooltip for the default button
 */
export default function DownloadButton({
  courseId,
  filename,
  content,
  renderTrigger,
  title = "Download",
}) {
  const [showFormatModal, setShowFormatModal] = useState(false);
  const [showDownloadMessage, setShowDownloadMessage] = useState(false);
  const [downloading, setDownloading] = useState(false);
  const [nameInput, setNameInput] = useState("");

  const openModal = () => {
    setNameInput(filename || "");
    setShowFormatModal(true);
  };
  const closeModal = () => {
    if (!downloading) setShowFormatModal(false);
  };

  const resolveContent = async () =>
    typeof content === "function" ? await content() : content;

  const handleFormatSelect = async (format) => {
    if (downloading) return;
    setDownloading(true);
    try {
      const text = await resolveContent();
      if (!text) {
        throw new Error("No content to download");
      }
      const chosenName = (nameInput || "").trim() || filename || "document";
      await assetService.downloadContent(courseId, chosenName, text, format);
      setShowFormatModal(false);
      setShowDownloadMessage(true);
      setTimeout(() => setShowDownloadMessage(false), 2000);
    } catch (error) {
      console.error("Download failed:", error);
      alert(error?.message || "Failed to download file. Please try again.");
    } finally {
      setDownloading(false);
    }
  };

  return (
    <>
      {renderTrigger ? (
        renderTrigger(openModal)
      ) : (
        <button
          onClick={openModal}
          style={{
            background: "#2563eb",
            border: "none",
            borderRadius: "6px",
            padding: "8px 12px",
            cursor: "pointer",
            display: "flex",
            alignItems: "center",
            gap: "6px",
            fontSize: "14px",
            color: "white",
            transition: "all 0.2s ease",
          }}
          onMouseEnter={(e) => {
            e.currentTarget.style.background = "#1d4ed8";
          }}
          onMouseLeave={(e) => {
            e.currentTarget.style.background = "#2563eb";
          }}
          title={title}
        >
          <FiDownload size={16} />
          Download
        </button>
      )}

      {showDownloadMessage && (
        <div
          style={{
            position: "absolute",
            top: "-40px",
            left: "50%",
            transform: "translateX(-50%)",
            background: "#2563eb",
            color: "white",
            padding: "6px 12px",
            borderRadius: "6px",
            fontSize: "12px",
            fontWeight: 500,
            whiteSpace: "nowrap",
            zIndex: 1000,
          }}
        >
          ✓ Downloaded successfully!
        </div>
      )}

      <ModalBase
        open={showFormatModal}
        onClose={closeModal}
        modalStyle={{ minWidth: 380, maxWidth: 440 }}
      >
        <h3
          style={{
            margin: "0 0 6px 0",
            fontSize: "18px",
            fontWeight: 700,
            color: "#1f2937",
          }}
        >
          Choose download format
        </h3>
        <p style={{ margin: "0 0 16px 0", fontSize: "14px", color: "#6b7280" }}>
          The document keeps its formatting — headings, tables, images and code
          — in either format.
        </p>
        <label
          style={{
            display: "block",
            fontSize: "13px",
            fontWeight: 600,
            color: "#374151",
            marginBottom: "6px",
          }}
        >
          File name
        </label>
        <input
          type="text"
          value={nameInput}
          onChange={(e) => setNameInput(e.target.value)}
          disabled={downloading}
          placeholder="Enter a file name"
          style={{
            width: "100%",
            boxSizing: "border-box",
            padding: "9px 12px",
            marginBottom: "20px",
            borderRadius: "8px",
            border: "1px solid #d1d5db",
            fontSize: "14px",
            color: "#1f2937",
            outline: "none",
          }}
        />
        <div style={{ display: "flex", gap: "12px" }}>
          <FormatOption
            icon={<FiFileText size={22} />}
            label="Word"
            sub=".docx"
            disabled={downloading}
            onClick={() => handleFormatSelect("docx")}
          />
          <FormatOption
            icon={<FiFile size={22} />}
            label="PDF"
            sub=".pdf"
            disabled={downloading}
            onClick={() => handleFormatSelect("pdf")}
          />
        </div>
        {downloading && (
          <div
            style={{
              marginTop: "16px",
              fontSize: "13px",
              color: "#6b7280",
              textAlign: "center",
            }}
          >
            Preparing your download…
          </div>
        )}
      </ModalBase>
    </>
  );
}

function FormatOption({ icon, label, sub, onClick, disabled }) {
  return (
    <button
      onClick={onClick}
      disabled={disabled}
      style={{
        flex: 1,
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        gap: "6px",
        padding: "18px 12px",
        borderRadius: "10px",
        border: "1px solid #d1d5db",
        background: "#fff",
        cursor: disabled ? "not-allowed" : "pointer",
        color: "#1f2937",
        opacity: disabled ? 0.6 : 1,
        transition: "all 0.2s ease",
      }}
      onMouseEnter={(e) => {
        if (!disabled) {
          e.currentTarget.style.borderColor = "#2563eb";
          e.currentTarget.style.background = "#f8faff";
        }
      }}
      onMouseLeave={(e) => {
        e.currentTarget.style.borderColor = "#d1d5db";
        e.currentTarget.style.background = "#fff";
      }}
    >
      <span style={{ color: "#2563eb" }}>{icon}</span>
      <span style={{ fontSize: "15px", fontWeight: 600 }}>{label}</span>
      <span style={{ fontSize: "12px", color: "#6b7280" }}>{sub}</span>
    </button>
  );
}
