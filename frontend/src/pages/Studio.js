import React, { useState, useEffect, useRef } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { useResources } from "../context/ResourcesContext";
import AddReferencesModal from "../components/AddReferencesModal";
import { createBrainstormThread } from "../services/brainstorm";

const optionTitles = {
  "brainstorm": "Brainstorm",
  "course-outcomes": "Course Outcomes",
  "modules-topics": "Modules & Topics",
  "lesson-plans": "Lesson Plans",
  "concept-map": "Concept Map",
  "course-notes": "Course Notes"
};

const btnStyle = {
  padding: "7px 14px",
  borderRadius: 5,
  border: "1px solid #bbb",
  background: "#fff",
  cursor: "pointer",
  fontSize: 14,
  fontWeight: 500,
};

export default function Studio() {
  const { option } = useParams();
  const navigate = useNavigate();
  const {
    getAllResources,
    addPendingFiles,
    commitPendingFiles,
    resetCommit,
    loadResources,
    removeResource,
    updateResource,
    checkedInFiles,
    checkedOutFiles
  } = useResources();
  const title = optionTitles[option] || option;
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState("");
  const [input, setInput] = useState("");
  const [messages, setMessages] = useState([]);
  const [threadId, setThreadId] = useState(null);
  const [selectedRefOption, setSelectedRefOption] = useState(0);
  const [addRefStep, setAddRefStep] = useState(0);
  // 1. Add state for session uploads (like old_frontend)
  const [sessionUploadedCount, setSessionUploadedCount] = useState(0);
  const [sessionUploadedFiles, setSessionUploadedFiles] = useState([]);
  // Fix: define courseId, loading, resources, modalFileInputRef, showAddContentModal
  const courseId = localStorage.getItem("currentCourseId");
  const [showAddContentModal, setShowAddContentModal] = useState(false);
  const modalFileInputRef = useRef();
  const [loading, setLoading] = useState(false);
  // const resources = getAllResources(courseId) || [];

  // Fix: handleAddContentClick, handleAddContentModalClose, handleCommitFiles
  const handleAddContentClick = () => {
    setAddRefStep(0);
    setShowAddContentModal(true);
  };
  const handleAddContentModalClose = () => {
    setShowAddContentModal(false);
  };
  const handleCommitFiles = async () => {
    setUploading(true);
    await commitPendingFiles(courseId);
    await loadResources(courseId);
    setUploading(false);
    resetCommit();
  };

  // 2. Add chat thread logic (reuse or create thread for non-brainstorm)
  useEffect(() => {
    let isMounted = true;
    async function initializeThread() {
      if (!courseId) {
        if (isMounted) setMessages([{
          role: "assistant",
          content: "Error: No course ID found. Please return to the dashboard and select a course.",
          timestamp: new Date().toISOString(),
          error: true
        }]);
        return;
      }
      try {
        let newThreadId;
        if (option === "brainstorm") {
          const response = await createBrainstormThread(courseId);
          newThreadId = response.thread_id;
        } else {
          // For general chat, check for existing thread or create new
          try {
            const courseData = await import("../services/course").then(m => m.getCourse(courseId));
            if (courseData.free_chat_thread_id) {
              newThreadId = courseData.free_chat_thread_id;
            } else {
              const response = await import("../services/brainstorm").then(m => m.createChatThread(courseId));
              newThreadId = response.thread_id;
            }
          } catch {
            const response = await import("../services/brainstorm").then(m => m.createChatThread(courseId));
            newThreadId = response.thread_id;
          }
        }
        if (isMounted) setThreadId(newThreadId);
        // Load existing messages
        try {
          if (option === "brainstorm") {
            const messagesResponse = await import("../services/brainstorm").then(m => m.getBrainstormMessages(courseId, newThreadId));
            if (isMounted) setMessages(messagesResponse.messages || []);
          } else {
            const messagesResponse = await import("../services/brainstorm").then(m => m.getChatMessages(courseId, newThreadId));
            if (isMounted) setMessages(messagesResponse.messages || []);
          }
        } catch {
          // Ignore message load errors
        }
      } catch (error) {
        if (isMounted) setMessages([{
          role: "assistant",
          content: "Error: Could not initialize chat. Please check your connection and try again.",
          timestamp: new Date().toISOString(),
          error: true
        }]);
      }
    }
    initializeThread();
    return () => { isMounted = false; };
  }, [courseId, option]);

  // 3. Update handleSend to support both brainstorm and chat streaming
  const handleSend = async () => {
    if (!input.trim() || !threadId || !courseId) return;
    setLoading(true);
    const userMessage = {
      role: "user",
      content: input.trim(),
      timestamp: new Date().toISOString()
    };
    setMessages(prev => [...prev, userMessage]);
    setInput("");
    const assistantMessage = {
      role: "assistant",
      content: "",
      timestamp: new Date().toISOString(),
      isStreaming: true
    };
    setMessages(prev => [...prev, assistantMessage]);
    try {
      const onToken = (token, isComplete) => {
        setMessages(prev => {
          const newMessages = [...prev];
          for (let i = newMessages.length - 1; i >= 0; i--) {
            if (newMessages[i].role === "assistant" && newMessages[i].isStreaming) {
              newMessages[i].content += token;
              if (isComplete) newMessages[i].isStreaming = false;
              break;
            }
          }
          return newMessages;
        });
      };
      if (option === "brainstorm") {
        await import("../services/brainstorm").then(m => m.sendBrainstormMessageStream(courseId, threadId, userMessage.content, onToken, checkedInFiles, checkedOutFiles));
      } else {
        await import("../services/brainstorm").then(m => m.sendChatMessageStream(courseId, threadId, userMessage.content, onToken, checkedInFiles, checkedOutFiles));
      }
    } catch (error) {
      setMessages(prev => [
        ...prev.slice(0, -1),
        {
          role: "assistant",
          content: `Sorry, I encountered an error: ${error.message}. Please try again.`,
          timestamp: new Date().toISOString(),
          error: true
        }
      ]);
    } finally {
      setLoading(false);
    }
  };

  // 4. Add drag & drop and session file logic for resource upload
  const handleModalFileChange = (e) => {
    const files = Array.from(e.target.files);
    addPendingFiles(files);
    setSessionUploadedFiles(prev => [
      ...prev,
      ...files.map(f => ({ name: f.name, type: f.type, checked: false, file: f }))
    ]);
    setSessionUploadedCount(prev => prev + files.length);
    e.target.value = null;
  };
  const handleDrop = (e) => {
    e.preventDefault();
    const files = Array.from(e.dataTransfer.files);
    if (files.length > 0) {
      const fakeEvent = { target: { files } };
      handleModalFileChange(fakeEvent);
    }
  };
  const handleDeleteSessionFile = (index) => {
    setSessionUploadedFiles(prev => prev.filter((_, i) => i !== index));
    setSessionUploadedCount(prev => prev - 1);
  };

  // 5. Add commit logic for session files
  const handleAddReferencesUpload = async () => {
    if (selectedRefOption === 0 && sessionUploadedFiles.length > 0) {
      setUploading(true);
      setError("");
      try {
        await addPendingFiles(sessionUploadedFiles.map(f => f.file || f));
        await commitPendingFiles(courseId);
        await loadResources(courseId);
        setSessionUploadedFiles([]);
        setSessionUploadedCount(0);
        setShowAddContentModal(false);
      } catch (err) {
        setError(err.message || "Failed to upload files");
      } finally {
        setUploading(false);
      }
    } else {
      setShowAddContentModal(false);
    }
  };

  const refOptions = [
    {
      label: "Upload references",
      icon: "📤",
      desc: "",
    },
    {
      label: "Select from an existing course",
      icon: "📚",
      desc: "",
    },
    {
      label: "Discover references",
      icon: "🔍",
      desc: "",
    },
  ];

  // Use flat resource list for sidebar (robust, backend-compatible)
  const resourcesFlat = getAllResources(courseId, false) || [];

  return (
    <div style={{ minHeight: "100vh", background: "#cbe0f7", padding: 0 }}>
      {/* Header */}
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", padding: "18px 32px 0 18px" }}>
        <div style={{ fontWeight: 700, fontSize: 22, display: "flex", alignItems: "center", gap: 8 }}>
          <span style={{ fontSize: 22 }}>✨</span> AI Studio
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: 14 }}>
          
          <button style={btnStyle}>Settings</button>
          <button style={btnStyle} onClick={() => navigate(-1)}>Close</button>
          <button style={{ ...btnStyle, background: "#222", color: "#fff", border: "none" }} onClick={handleCommitFiles} disabled={uploading}>
            {uploading ? "Uploading..." : "Save"}
          </button>
        </div>
      </div>
      
      {/* Error Message */}
      {error && (
        <div style={{ 
          background: "#fee", 
          color: "#c33", 
          padding: "12px 16px", 
          margin: "16px 32px 0 32px", 
          borderRadius: 6, 
          fontSize: 14 
        }}>
          {error}
        </div>
      )}
      
      {/* Main Content */}
      <div style={{ display: "flex", maxWidth: 1200, margin: "24px auto 0 auto", gap: 18, alignItems: "flex-start" }}>
        {/* Chat Area */}
        <div style={{ flex: 3, background: "#fff", borderRadius: 14, minHeight: 520, display: "flex", flexDirection: "column", boxShadow: "0 1px 4px #0001" }}>
          <div style={{ fontWeight: 600, fontSize: 18, padding: "18px 18px 8px 18px", borderBottom: "1px solid #e0e0e0" }}>{title}</div>
          <div style={{ flex: 1, padding: 18, overflowY: "auto" }}>
            {option === "brainstorm" && messages.length === 0 && !loading && (
              <div style={{ textAlign: "center", padding: "40px 20px", color: "#666" }}>
                <div style={{ fontSize: 48, marginBottom: 16 }}>💡</div>
                <h3 style={{ margin: "0 0 8px 0", fontSize: 18 }}>Start Brainstorming</h3>
                <p style={{ margin: 0, fontSize: 14 }}>Ask questions about your course content, structure, or ideas to get started.</p>
              </div>
            )}
            
            {messages.map((msg, index) => (
              <div key={index} style={{ 
                display: "flex", 
                marginBottom: 16, 
                alignItems: msg.role === "user" ? "flex-end" : "flex-start",
                flexDirection: msg.role === "user" ? "row-reverse" : "row"
              }}>
                <div style={{ 
                  background: msg.role === "user" ? "#2563eb" : "#f5f5f5", 
                  color: msg.role === "user" ? "#fff" : "#333",
                  padding: "12px 16px", 
                  borderRadius: 18, 
                  maxWidth: "70%",
                  fontSize: 14,
                  lineHeight: 1.4
                }}>
                  {msg.content}
                </div>
              </div>
            ))}
            
            {loading && (
              <div style={{ display: "flex", marginBottom: 16, alignItems: "flex-start" }}>
                <div style={{ 
                  background: "#f5f5f5", 
                  padding: "12px 16px", 
                  borderRadius: 18, 
                  fontSize: 14,
                  color: "#666"
                }}>
                  Thinking...
                </div>
              </div>
            )}
          </div>
          <div style={{ borderTop: "1px solid #e0e0e0", padding: 16, display: "flex", alignItems: "center", gap: 8 }}>
            <input
              type="text"
              placeholder={option === "brainstorm" ? "Ask about your course ideas, structure, or content..." : "Type a prompt to generate a lesson, quiz, or outcome..."}
              style={{ flex: 1, border: "none", outline: "none", fontSize: 15, padding: "12px 16px", borderRadius: 8, background: "#f5f7fa" }}
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyPress={(e) => {
                if (e.key === 'Enter' && !loading) {
                  handleSend();
                }
              }}
              disabled={loading}
            />
            <button 
              style={{ 
                background: "#1976d2", 
                color: "#fff", 
                border: "none", 
                borderRadius: 8, 
                padding: "12px 20px", 
                fontWeight: 600, 
                fontSize: 14, 
                cursor: loading ? "not-allowed" : "pointer",
                opacity: loading ? 0.6 : 1
              }} 
              onClick={handleSend} 
              disabled={loading || !input.trim()}
            >
              {loading ? "Sending..." : "Send"}
            </button>
          </div>
        </div>
        {/* Sidebar */}
        <div style={{ flex: 1, minWidth: 280 }}>
          <div style={{ background: "#fff", borderRadius: 12, boxShadow: "0 1px 4px #0001", padding: 18 }}>
            <div style={{ fontWeight: 600, fontSize: 16, marginBottom: 4 }}>Knowledge base</div>
            <div style={{ color: "#888", fontSize: 13, marginBottom: 10 }}>Guides AI for content generation.</div>
            {/* Removed standalone file input. File upload is now only via Add Content modal. */}
            <button style={{ width: "100%", marginBottom: 12, padding: "8px 0", borderRadius: 6, border: "1px solid #bbb", background: "#fff", fontWeight: 500, fontSize: 15, cursor: "pointer" }} onClick={handleAddContentClick}>Add Content</button>
            <div style={{ marginBottom: 8 }}>
              <label style={{ display: "flex", alignItems: "center", gap: 8, fontWeight: 500, fontSize: 14 }}>
                <input type="checkbox" checked={resourcesFlat.every(res => (checkedInFiles || []).includes(res.fileName || res.name))} onChange={e => {}} /> Select All References
              </label>
            </div>
            {/* Knowledge base resource list */}
            <ul style={{ listStyle: "none", padding: 0, margin: 0 }}>
              {resourcesFlat.filter(Boolean).map((res, i) => {
                const fileName = res.fileName || res.name;
                // Use backend status if available, fallback to local checkedInFiles
                const checked = res.status === 'checked_in' || (checkedInFiles || []).includes(fileName);
                return (
                  <li key={res.fileId || res.fileName || i} style={{ display: "flex", alignItems: "center", justifyContent: "space-between", padding: "7px 0", borderBottom: i < resourcesFlat.length - 1 ? "1px solid #f0f0f0" : "none" }}>
                    <label style={{ display: "flex", alignItems: "center", gap: 8, fontSize: 15, flex: 1 }}>
                      <input
                        type="checkbox"
                        checked={checked}
                        onChange={async e => {
                          // Always update backend status
                          if (e.target.checked) {
                            if (!(checkedInFiles || []).includes(fileName)) {
                              const updatedIn = [...(checkedInFiles || []), fileName];
                              const updatedOut = (checkedOutFiles || []).filter(name => name !== fileName);
                              localStorage.setItem(`checkedInFiles_${courseId}`, JSON.stringify(updatedIn));
                              localStorage.setItem(`checkedOutFiles_${courseId}`, JSON.stringify(updatedOut));
                              window.dispatchEvent(new Event('storage'));
                            }
                            if (res.fileId) await updateResource(courseId, res.fileId, { status: 'checked_in' });
                          } else {
                            if (!(checkedOutFiles || []).includes(fileName)) {
                              const updatedOut = [...(checkedOutFiles || []), fileName];
                              const updatedIn = (checkedInFiles || []).filter(name => name !== fileName);
                              localStorage.setItem(`checkedInFiles_${courseId}`, JSON.stringify(updatedIn));
                              localStorage.setItem(`checkedOutFiles_${courseId}`, JSON.stringify(updatedOut));
                              window.dispatchEvent(new Event('storage'));
                            }
                            if (res.fileId) await updateResource(courseId, res.fileId, { status: 'checked_out' });
                          }
                        }}
                        style={{ width: 18, height: 18, accentColor: checked ? '#43a047' : '#fb8c00', cursor: 'pointer' }}
                      />
                      <span style={{ marginRight: 6 }}>{getFileIcon(res)}</span> {res.fileName || res.name}
                    </label>
                    <span style={{ cursor: "pointer", fontSize: 18 }} onClick={async () => {
                      if (res.fileId) {
                        await removeResource(courseId, res.fileId);
                      }
                    }}>🗑️</span>
                  </li>
                );
              })}
            </ul>
          </div>
        </div>
      </div>
      <AddReferencesModal open={showAddContentModal} onClose={handleAddContentModalClose}>
        {addRefStep === 0 && (
          <>
            <div style={{ fontWeight: 700, fontSize: 20, marginBottom: 6 }}>Add References</div>
            <div style={{ color: "#444", fontSize: 15, marginBottom: 18 }}>To start building your course, select any of the following</div>
            <div style={{ display: "flex", gap: 18, marginBottom: 24 }}>
              {refOptions.map((opt, i) => (
                <div
                  key={opt.label}
                  onClick={() => {
                    setSelectedRefOption(i);
                    if (i === 0) setAddRefStep(1);
                  }}
                  style={{
                    position: 'relative',
                    flex: 1,
                    minWidth: 120,
                    background: selectedRefOption === i ? "#f0f7ff" : "#fafbfc",
                    border: selectedRefOption === i ? "2px solid #1976d2" : "1px solid #ddd",
                    borderRadius: 10,
                    padding: "24px 18px",
                    cursor: "pointer",
                    display: "flex",
                    flexDirection: "column",
                    alignItems: "center",
                    gap: 10,
                    boxShadow: selectedRefOption === i ? "0 2px 8px #1976d222" : "none"
                  }}
                >
                  <div style={{ fontSize: 28 }}>{opt.icon}</div>
                  <div style={{ fontWeight: 600, fontSize: 16, textAlign: "center" }}>{opt.label}</div>
                  {i === 0 && sessionUploadedCount > 0 && (
                    <span style={{ position: 'absolute', left: 18, top: 18, background: '#eafaf1', color: '#219653', borderRadius: 6, fontSize: 13, fontWeight: 600, padding: '2px 10px' }}>{sessionUploadedCount} files uploaded</span>
                  )}
                </div>
              ))}
            </div>
            <div style={{ display: "flex", justifyContent: "flex-end", gap: 12 }}>
              <button onClick={handleAddContentModalClose} style={{ padding: "8px 18px", borderRadius: 6, border: "1px solid #bbb", background: "#fff", fontWeight: 500, fontSize: 15, cursor: "pointer" }}>Cancel</button>
              <button
                onClick={handleAddReferencesUpload}
                style={{ padding: "8px 18px", borderRadius: 6, border: "none", background: "#222", color: "#fff", fontWeight: 500, fontSize: 15, cursor: "pointer" }}
                disabled={uploading}
              >
                {uploading ? "Uploading..." : "Add"}
              </button>
            </div>
          </>
        )}
        {addRefStep === 1 && (
          <div>
            <div style={{ fontWeight: 700, fontSize: 20, marginBottom: 6 }}>Upload References</div>
            <div style={{ color: "#444", fontSize: 15, marginBottom: 12 }}>Accepted formats: PDF, DOCX, PPTX, TXT, CSV, Images</div>
            <div
              onDrop={handleDrop}
              onDragOver={e => e.preventDefault()}
              style={{ border: "2px dashed #1976d2", borderRadius: 10, padding: 32, textAlign: "center", marginBottom: 18, background: "#f5f7fa", cursor: "pointer" }}
              onClick={() => modalFileInputRef.current && modalFileInputRef.current.click()}
            >
              <div style={{ fontSize: 32, marginBottom: 8 }}>📂</div>
              <div style={{ fontWeight: 500, fontSize: 16 }}>Drag & drop files here or <span style={{ color: "#1976d2", textDecoration: "underline" }}>Browse</span></div>
              <input
                type="file"
                multiple
                ref={modalFileInputRef}
                style={{ display: "none" }}
                onChange={handleModalFileChange}
                accept=".pdf,.doc,.docx,.ppt,.pptx,.txt,.csv,image/*"
              />
            </div>
            <div style={{ marginBottom: 12 }}>
              {sessionUploadedFiles.map((file, i) => (
                <div key={i} style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 6 }}>
                  <span>{file.name}</span>
                  <span style={{ cursor: "pointer", color: "#d32f2f" }} onClick={() => handleDeleteSessionFile(i)}>🗑️</span>
                </div>
              ))}
            </div>
            <div style={{ display: "flex", justifyContent: "flex-end", gap: 12 }}>
              <button onClick={handleAddContentModalClose} style={{ padding: "8px 18px", borderRadius: 6, border: "1px solid #bbb", background: "#fff", fontWeight: 500, fontSize: 15, cursor: "pointer" }}>Cancel</button>
              <button onClick={() => setAddRefStep(0)} style={{ padding: "8px 18px", borderRadius: 6, border: "1px solid #1976d2", background: "#f0f7ff", color: "#1976d2", fontWeight: 500, fontSize: 15, cursor: "pointer" }}>Back to Add References</button>
            </div>
          </div>
        )}
      </AddReferencesModal>
    </div>
  );
}

function getFileIcon(file) {
  if (!file || !file.name) return "📁";
  if (file.type && file.type.startsWith("image/")) return "🖼️";
  if (file.type === "application/pdf") return "📄";
  if (file.name.endsWith(".doc") || file.name.endsWith(".docx")) return "📄";
  if (file.name.endsWith(".ppt") || file.name.endsWith(".pptx")) return "📊";
  if (file.name.endsWith(".xls") || file.name.endsWith(".xlsx")) return "📊";
  if (file.name.endsWith(".txt")) return "📄";
  if (file.name.endsWith(".zip") || file.name.endsWith(".rar")) return "🗜️";
  if (file.name.endsWith(".csv")) return "📑";
  if (file.name.endsWith(".mp4") || file.name.endsWith(".mov")) return "🎞️";
  if (file.name.endsWith(".mp3") || file.name.endsWith(".wav")) return "🎵";
  if (file.name.endsWith(".html") || file.name.endsWith(".htm")) return "🌐";
  if (file.name.endsWith(".json")) return "🗂️";
  if (file.name.endsWith(".js")) return "📜";
  if (file.name.endsWith(".py")) return "🐍";
  if (file.name.endsWith(".java")) return "☕";
  if (file.name.endsWith(".c") || file.name.endsWith(".cpp")) return "💻";
  if (file.name.endsWith(".md")) return "📝";
  if (file.name.endsWith(".svg")) return "🖼️";
  if (file.name.endsWith(".xml")) return "🗂️";
  if (file.name.endsWith(".yml") || file.name.endsWith(".yaml")) return "🗂️";
  return "📁";
}

 