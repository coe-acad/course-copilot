import React, { useEffect, useRef, useState } from "react";
import { useLocation, useParams } from "react-router-dom";
import AssetStudioLayout from "../layouts/AssetStudioLayout";
import KnowledgeBase from "../components/KnowledgBase";
import { FaDownload, FaFolderPlus, FaSave } from "react-icons/fa";
import { getAllResources } from "../services/resources";
import { assetService } from "../services/asset";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

const optionTitles = {
  "course-outcomes": "Course Outcomes",
  "modules-topics": "Modules & Topics",
  "lesson-plans": "Lesson Plans",
  "concept-map": "Concept Map",
  "course-notes": "Course Notes",
  "brainstorm": "Brainstorm",
  "quiz": "Quiz",
  "assignment": "Assignment",
  "viva": "Viva",
  "sprint-plan": "Sprint Plan"
};


export default function AssetStudioContent() {
  const params = useParams();
  const option = params.feature;
  const location = useLocation();
  const bottomRef = useRef(null);
  const title = optionTitles[option] || option;

  // ✅ Pre-select only those passed from Dashboard
  const selectedFiles = location.state?.selectedFiles || [];
  const initialSelectedIds = selectedFiles.map(file => file.id);
  const [selectedIds, setSelectedIds] = useState(initialSelectedIds);

  const [chatMessages, setChatMessages] = useState([]);
  const [inputMessage, setInputMessage] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [resources, setResources] = useState([]);
  const [, setResourcesLoading] = useState(true);
  const [threadId, setThreadId] = useState(null);
  const [showSaveModal, setShowSaveModal] = useState(false);
  const [saveModalMessage, setSaveModalMessage] = useState("");
  const [assetName, setAssetName] = useState("");

  useEffect(() => {
    if (bottomRef.current) {
      bottomRef.current.scrollIntoView({ behavior: "smooth" });
    }
  }, [chatMessages]);

  useEffect(() => {
    const fetchResources = async () => {
      try {
        setResourcesLoading(true);
        const courseId = localStorage.getItem('currentCourseId');
        if (!courseId) {
          console.error('No current course ID found');
          setResources([]);
          return;
        }
        
        const resourcesData = await getAllResources(courseId);
        setResources(resourcesData.resources);
      } catch (error) {
        console.error("Error fetching resources:", error);
        setResources([]);
      } finally {
        setResourcesLoading(false);
      }
    };

    fetchResources();
  }, []);

  // Create initial AI message when component loads
  useEffect(() => {
    const createInitialMessage = async () => {
      try {
        setIsLoading(true);
        const courseId = localStorage.getItem('currentCourseId');
        if (!courseId) {
          console.error('No course ID found');
          return;
        }

        // Create asset chat with all available files (or empty array if no files)
        const fileNames = resources.map(file => file.resourceName || file.fileName || file.id);

        // Create asset chat with available files
        const response = await assetService.createAssetChat(courseId, option, fileNames);
        console.log("Response:", response);
        
        if (response && response.response) {
          setChatMessages([{
            type: "bot",
            text: response.response
          }]);
          setThreadId(response.thread_id);
          console.log("Thread ID:", response.thread_id);
        }
      } catch (error) {
        console.error("Error creating initial message:", error);
        // Don't show any error message to user - just log it
      } finally {
        setIsLoading(false);
      }
    };

    // Only create initial message if resources are loaded and we haven't created one yet
    if (resources.length > 0 && chatMessages.length === 0) {
      createInitialMessage();
    }
  }, [resources, option, chatMessages.length]);

  const toggleSelect = (id) => {
    setSelectedIds((prev) =>
      prev.includes(id) ? prev.filter((f) => f !== id) : [...prev, id]
    );
  };

  const handleSend = async () => {
    if (!inputMessage.trim()) return;
    const newMsg = { type: "user", text: inputMessage };
    setChatMessages((prev) => [...prev, newMsg]);
    setInputMessage("");
    setIsLoading(true);

    try {
      if (!threadId) {
        throw new Error("No active chat thread");
      }

      const courseId = localStorage.getItem('currentCourseId');
      if (!courseId) {
        throw new Error("No course ID found");
      }

      console.log("Sending chat message:", {
        courseId,
        assetName: option,
        threadId,
        userPrompt: inputMessage
      });

      // Continue the conversation with the backend
      const response = await assetService.continueAssetChat(courseId, option, threadId, inputMessage);
      
      console.log("Backend response:", response);
      
      if (response && response.response) {
        const botResponse = {
          type: "bot",
          text: response.response
        };
        setChatMessages((prev) => [...prev, botResponse]);
      }
    } catch (err) {
      console.error("Chat error:", err);
      console.error("Error details:", err.message);
      const errorResponse = {
        type: "bot",
        text: "Sorry, I encountered an error. Please try again."
      };
      setChatMessages((prev) => [...prev, errorResponse]);
    } finally {
      setIsLoading(false);
    }
  };

  const handleDownload = (message) => {
    // TODO: Implement backend download
    console.log("Download message:", message);
  };

  const handleSaveToAsset = (message) => {
    setSaveModalMessage(message);
    setAssetName("");
    setShowSaveModal(true);
  };

  const handleSaveAssetConfirm = async () => {
    try {
      const courseId = localStorage.getItem('currentCourseId');
      if (!courseId) {
        console.error('No course ID found');
        return;
      }

      const assetType = option;

      await assetService.saveAsset(courseId, assetName, assetType, saveModalMessage);
      console.log(`✅ Asset "${assetName}" saved successfully!`);
      
      // Close modal and reset
      setShowSaveModal(false);
      setSaveModalMessage("");
      setAssetName("");
    } catch (error) {
      console.error("Error saving asset:", error);
    }
  };

  const handleSaveAssetCancel = () => {
    setShowSaveModal(false);
    setSaveModalMessage("");
    setAssetName("");
  };

  const handleSaveToResource = (message) => {
    // TODO: Send resource to backend store
    console.log("Save to Resource:", message);
  };

  const handleFileUpload = () => {
    // For mock data, we'll just log the upload
    console.log("File upload triggered - in real implementation this would refresh from API");
  };

  return (
    <AssetStudioLayout
      title={title}
      rightPanel={
        <KnowledgeBase
          resources={resources}
          showCheckboxes
          selected={selectedIds}
          onSelect={toggleSelect}
          fileInputRef={{ current: null }}
          onFileChange={handleFileUpload}
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
                  background: msg.type === "user" ? "#e0f2ff" : "transparent",
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
                <div 
                  style={{ 
                    marginBottom: 6,
                    lineHeight: "1.5"
                  }}
                >
                  {msg.type === "bot" ? (
                    <div style={{ 
                      fontSize: "15px",
                      lineHeight: "1.6",
                      color: "#222"
                    }}>
                      <ReactMarkdown
                        remarkPlugins={[remarkGfm]}
                        components={{
                          h1: ({node, ...props}) => <h1 style={{ fontSize: "20px", fontWeight: "bold", margin: "8px 0", color: "#222" }}>{props.children}</h1>,
                          h2: ({node, ...props}) => <h2 style={{ fontSize: "18px", fontWeight: "bold", margin: "8px 0", color: "#222" }}>{props.children}</h2>,
                          h3: ({node, ...props}) => <h3 style={{fontSize: "16px", fontWeight: "bold", margin: "8px 0", color: "#222"}}> {props.children} </h3>,
                          p: ({node, ...props}) => <p style={{ margin: "8px 0", color: "#222" }}>{props.children}</p>,
                          li: ({node, ...props}) => <li style={{ margin: "4px 0", color: "#222" }}>{props.children}</li>,
                          ul: ({node, ...props}) => <ul style={{margin: "8px 0", paddingLeft: "20px", color: "#222"}} {...props.children} />,
                          ol: ({node, ...props}) => <ol style={{margin: "8px 0", paddingLeft: "20px", color: "#222"}} {...props.children} />,
                          // li: ({node, ...props}) => <li style={{margin: "4px 0", color: "#222"}} {...props.children} />,
                          strong: ({node, ...props}) => <strong style={{fontWeight: "bold", color: "#222"}} {...props.children} />,
                          em: ({node, ...props}) => <em style={{fontStyle: "italic", color: "#222"}} {...props.children} />,
                          code: ({node, ...props}) => <code style={{backgroundColor: "#f0f0f0", padding: "2px 4px", borderRadius: "3px", fontFamily: "monospace", fontSize: "14px", color: "#222"}} {...props.children} />,
                          pre: ({node, ...props}) => <pre style={{backgroundColor: "#f0f0f0", padding: "8px", borderRadius: "4px", overflow: "auto", margin: "8px 0", fontSize: "14px", color: "#222"}} {...props.children} />,
                          blockquote: ({node, ...props}) => <blockquote style={{borderLeft: "4px solid #ddd", paddingLeft: "12px", margin: "8px 0", color: "#666"}} {...props.children} />,
                          table: ({node, ...props}) => <table style={{borderCollapse: "collapse", width: "100%", margin: "8px 0", border: "1px solid #ddd", tableLayout: "fixed"}} {...props.children} />,
                          thead: ({node, ...props}) => <thead style={{backgroundColor: "#f5f5f5"}} {...props.children} />,
                          tbody: ({node, ...props}) => <tbody {...props.children} />,
                          tr: ({node, ...props}) => <tr style={{borderBottom: "1px solid #ddd"}} {...props.children} />,
                          th: ({node, ...props}) => <th style={{padding: "12px 8px", textAlign: "left", border: "1px solid #ddd", fontWeight: "bold", backgroundColor: "#f5f5f5", verticalAlign: "top", wordWrap: "break-word"}} {...props.children} />,
                          td: ({node, ...props}) => <td style={{padding: "12px 8px", textAlign: "left", border: "1px solid #ddd", verticalAlign: "top", wordWrap: "break-word", lineHeight: "1.4"}} {...props.children} />
                        }}
                      >
                        {msg.text}
                      </ReactMarkdown>
                    </div>
                  ) : (
                    <div style={{ color: "#222" }}>{msg.text}</div>
                  )}
                </div>
                {msg.type !== "user" && (
              <div
                style={{
                  position: "absolute",
                  bottom: 6,
                  left: 12,
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
            )}
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

      {/* Save Asset Modal */}
      {showSaveModal && (
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
            zIndex: 1000
          }}
        >
          <div
            style={{
              background: "#fff",
              borderRadius: 12,
              padding: 24,
              width: "400px",
              maxWidth: "90vw",
              boxShadow: "0 4px 20px rgba(0, 0, 0, 0.15)"
            }}
          >
            <h3 style={{ margin: "0 0 16px 0", fontSize: 18, fontWeight: 600 }}>
              Save Asset
            </h3>
            
            <div style={{ marginBottom: 16 }}>
              <label style={{ display: "block", marginBottom: 8, fontWeight: 500 }}>
                Asset Name:
              </label>
              <input
                type="text"
                value={assetName}
                onChange={(e) => setAssetName(e.target.value)}
                style={{
                  width: "100%",
                  padding: "10px 12px",
                  borderRadius: 6,
                  border: "1px solid #ccc",
                  fontSize: 14,
                  boxSizing: "border-box"
                }}
                placeholder="Enter asset name..."
              />
            </div>

            <div style={{ display: "flex", gap: 12, justifyContent: "flex-end" }}>
              <button
                onClick={handleSaveAssetCancel}
                style={{
                  padding: "8px 16px",
                  borderRadius: 6,
                  border: "1px solid #ccc",
                  background: "#fff",
                  cursor: "pointer",
                  fontSize: 14
                }}
              >
                Cancel
              </button>
              <button
                onClick={handleSaveAssetConfirm}
                disabled={!assetName.trim()}
                style={{
                  padding: "8px 16px",
                  borderRadius: 6,
                  border: "none",
                  background: assetName.trim() ? "#2563eb" : "#ccc",
                  color: "#fff",
                  cursor: assetName.trim() ? "pointer" : "not-allowed",
                  fontSize: 14,
                  fontWeight: 500
                }}
              >
                Save Asset
              </button>
            </div>
          </div>
        </div>
      )}
    </AssetStudioLayout>
  );
}
