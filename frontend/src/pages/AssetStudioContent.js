import React, { useEffect, useRef, useState } from "react";
import { useLocation, useParams } from "react-router-dom";
import AssetStudioLayout from "../layouts/AssetStudioLayout";
import KnowledgeBase from "../components/KnowledgBase";
import { FaDownload, FaFolderPlus, FaSave } from "react-icons/fa";

const optionTitles = {
  "course-outcomes": "Course Outcomes",
  "modules-topics": "Modules & Topics",
  "lesson-plans": "Lesson Plans",
  "concept-map": "Concept Map",
  "course-notes": "Course Notes",
  "brainstorm": "Brainstorm"
};

export default function AssetStudioContent() {
  const { option } = useParams();
  const location = useLocation();
  const [chatMessages, setChatMessages] = useState([]);
  const [inputMessage, setInputMessage] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [selectedFiles] = useState(location.state?.selectedFiles || []);
  const [selectedIds, setSelectedIds] = useState([]);
  const bottomRef = useRef(null);
  const title = optionTitles[option] || option;

  useEffect(() => {
    if (bottomRef.current) {
      bottomRef.current.scrollIntoView({ behavior: "smooth" });
    }
  }, [chatMessages]);

  const handleSend = async () => {
    if (!inputMessage.trim()) return;

    const newMsg = { type: "user", text: inputMessage };
    setChatMessages(prev => [...prev, newMsg]);
    setInputMessage("");
    setIsLoading(true);

    try {
      // TODO: Call backend chat API
      const botResponse = {
        type: "bot",
        text: "This is a placeholder response from the AI assistant."
      };
      setChatMessages(prev => [...prev, botResponse]);
    } catch (err) {
      console.error("Error:", err);
    } finally {
      setIsLoading(false);
    }
  };

  const toggleSelect = (id) => {
    setSelectedIds((prev) =>
      prev.includes(id) ? prev.filter((f) => f !== id) : [...prev, id]
    );
  };

  const handleDownload = (message) => {
    // TODO: Trigger download logic from backend
    console.log("Download message:", message);
  };

  const handleSaveToAsset = (message) => {
    // TODO: Send this to backend and push to dashboard asset
    console.log("Save to Asset:", message);
    // e.g., save to localStorage or context
  };

  const handleSaveToResource = (message) => {
    // TODO: Trigger resource save API
    console.log("Save to Resource:", message);
  };

  return (
    <AssetStudioLayout
      title={title}
      rightPanel={
        <KnowledgeBase
          resources={selectedFiles}
          showCheckboxes
          selected={selectedIds}
          onSelect={toggleSelect}
          fileInputRef={{ current: null }} // TODO: hook this to actual file input
          onFileChange={() => {}} // TODO: hook file upload here
        />
      }
    >
      <div style={{ fontSize: 15, marginBottom: 18, color: "#333" }}>
        <strong>Using references:</strong>{" "}
        {selectedIds.map((id) => {
          const match = selectedFiles.find((f) => f.id === id || f.fileName === id);
          return match?.fileName || match?.title || id;
        }).join(", ") || "None selected"}
      </div>

      <div style={{
        background: "#fff",
        borderRadius: 12,
        padding: 24,
        boxShadow: "0 2px 12px #0001",
        minHeight: 360,
        maxHeight: 500,
        overflowY: "auto",
        marginBottom: 16
      }}>
        {chatMessages.map((msg, i) => (
          <div key={i} style={{
            background: msg.type === "user" ? "#e0f2ff" : "#f3f3f3",
            borderRadius: 8,
            padding: "8px 12px",
            margin: "6px 0",
            textAlign: "left",
            position: "relative"
          }}>
            <div style={{ marginBottom: 6 }}>{msg.text}</div>
            <div style={{ display: "flex", gap: 10, fontSize: 14 }}>
              <FaDownload
                title="Download"
                style={{ cursor: "pointer" }}
                onClick={() => handleDownload(msg.text)}
              />
              <FaFolderPlus
                title="Save to Asset"
                style={{ cursor: "pointer" }}
                onClick={() => handleSaveToAsset(msg.text)}
              />
              <FaSave
                title="Save to Resource"
                style={{ cursor: "pointer" }}
                onClick={() => handleSaveToResource(msg.text)}
              />
            </div>
          </div>
        ))}
        <div ref={bottomRef}></div>
      </div>

      <div style={{ display: "flex", gap: 12 }}>
        <input
          value={inputMessage}
          onChange={(e) => setInputMessage(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && handleSend()}
          placeholder="Type your message..."
          style={{
            flex: 1,
            padding: "10px 12px",
            borderRadius: 8,
            border: "1px solid #ccc",
            fontSize: 15
          }}
        />
        <button onClick={handleSend} disabled={isLoading} style={{
          padding: "10px 18px",
          borderRadius: 8,
          background: "#2563eb",
          color: "#fff",
          border: "none",
          fontWeight: 500,
          cursor: isLoading ? "not-allowed" : "pointer"
        }}>
          {isLoading ? "..." : "Send"}
        </button>
      </div>
    </AssetStudioLayout>
  );
}
