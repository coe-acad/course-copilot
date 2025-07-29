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

const sectionMap = {
  "course-outcomes": "Curriculum",
  "modules-topics": "Curriculum",
  "concept-map": "Curriculum",
  "lesson-plans": "Curriculum",
  "course-notes": "Curriculum",
  "brainstorm": "Assessments"
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
    setChatMessages((prev) => [...prev, newMsg]);
    setInputMessage("");
    setIsLoading(true);

    try {
      // TODO: Replace with backend chat API call
      const botResponse = {
        type: "bot",
        text: "This is a placeholder response from the AI assistant."
      };
      setChatMessages((prev) => [...prev, botResponse]);
    } catch (err) {
      console.error("Chat error:", err);
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
    // TODO: Implement backend download
    console.log("Download message:", message);
  };

  const handleSaveToAsset = async (message) => {
    // TODO: Send asset message to backend and associate with course/section
    const section = sectionMap[option] || "Other";
    const assetName = optionTitles[option] || option;

    const newAsset = {
      name: assetName,
      message: message,
      timestamp: new Date().toISOString()
    };

    console.log(`🔄 TODO: Save this asset to backend under section ${section}:`, newAsset);
  };

  const handleSaveToResource = (message) => {
    // TODO: Send resource to backend store
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
          fileInputRef={{ current: null }}
          onFileChange={() => {}}
        />
      }
    >
      <div
        style={{
          background: "#fff",
          borderRadius: 12,
          padding: 16,
          boxShadow: "0 2px 12px #0001",
          flex: 1,
          height: "400px",
          overflow: "hidden",
          display: "flex",
          flexDirection: "column"
        }}
      >
        <div
          style={{
            flex: 1,
            overflowY: "auto",
            paddingRight: 8
          }}
        >
          {chatMessages.map((msg, i) => (
            <div
              key={i}
              style={{
                display: "flex",
                justifyContent:
                  msg.type === "user" ? "flex-end" : "flex-start",
                marginBottom: 12
              }}
            >
              <div
                style={{
                  background:
                    msg.type === "user" ? "#e0f2ff" : "transparent",
                  borderRadius: 10,
                  padding: "10px 12px 26px 12px",
                  minWidth: msg.type === "user" ? "120px" : "0",
                  maxWidth: msg.type === "user" ? "60%" : "100%",
                  position: "relative",
                  color: "#222",
                  fontSize: 15,
                  textAlign: msg.type === "user" ? "right" : "left",
                  wordBreak: "break-word"
                }}
              >
                <div style={{ marginBottom: 6 }}>{msg.text}</div>
                <div
                  style={{
                    position: "absolute",
                    bottom: 6,
                    right: msg.type === "user" ? 12 : "auto",
                    left: msg.type === "user" ? "auto" : 12,
                    display: "flex",
                    gap: 10,
                    fontSize: 15,
                    color: "#888"
                  }}
                >
                  <FaDownload
                    title="Download"
                    style={{ cursor: "pointer", opacity: 0.8 }}
                    onClick={() => handleDownload(msg.text)}
                  />
                  <FaFolderPlus
                    title="Save to Asset"
                    style={{ cursor: "pointer", opacity: 0.8 }}
                    onClick={() => handleSaveToAsset(msg.text)}
                  />
                  <FaSave
                    title="Save to Resource"
                    style={{ cursor: "pointer", opacity: 0.8 }}
                    onClick={() => handleSaveToResource(msg.text)}
                  />
                </div>
              </div>
            </div>
          ))}
          <div ref={bottomRef}></div>
        </div>
      </div>

      <div style={{ display: "flex", gap: 12, marginTop: 16 }}>
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
        <button
          onClick={handleSend}
          disabled={isLoading}
          style={{
            padding: "10px 18px",
            borderRadius: 8,
            background: "#2563eb",
            color: "#fff",
            border: "none",
            fontWeight: 500,
            cursor: isLoading ? "not-allowed" : "pointer"
          }}
        >
          {isLoading ? "..." : "Send"}
        </button>
      </div>
    </AssetStudioLayout>
  );
}
