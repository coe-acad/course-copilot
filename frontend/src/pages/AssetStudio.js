import React, { useRef, useState, useEffect } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { useFilesContext } from "../context/FilesContext";
import AddReferencesModal from "../components/AddReferencesModal";
import { getCourseResources, uploadCourseResources, checkinResource, checkoutResource, addAllFilesToAssistant } from "../services/resources";
import SettingsModal from "../components/SettingsModal";
import ReactMarkdown from 'react-markdown';
import { createPDFBlob, createPDFBlobForUpload } from '../utils/pdfGenerator';
import { RxDownload, RxPlusCircled, RxBookmark, RxPencil2 } from "react-icons/rx";
import { assetConfig } from "../config/assetConfig";


const optionTitles = {
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

const blinkingDotStyle = `
  @keyframes blink {
    0%, 50% { opacity: 1; }
    51%, 100% { opacity: 0; }
  }
  .blinking-dot {
    display: inline-block;
    width: 12px;
    height: 12px;
    background-color: #90a4c7;
    border-radius: 50%;
    margin-left: 4px;
    animation: blink 1.5s infinite;
    vertical-align: middle;
  }
`;

export default function AssetStudio() {
  const { option } = useParams();
  const { feature } = useParams();
  const navigate = useNavigate();
  const config = assetConfig[feature];
  const { updateFileChecked, setAllChecked, addFiles } = useFilesContext();
  const [resources, setResources] = useState([]);
  const [resourceLoading, setResourceLoading] = useState(false);
  const [resourceError, setResourceError] = useState("");
  const courseId = localStorage.getItem("currentCourseId");
  const [showAddContentModal, setShowAddContentModal] = useState(false);
  const [addRefStep, setAddRefStep] = useState(0);
  const [selectedRefOption, setSelectedRefOption] = useState(0);
  const [sessionUploadedCount, setSessionUploadedCount] = useState(0);
  const [sessionUploadedFiles, setSessionUploadedFiles] = useState([]);
  const fileInputRef = useRef();
  const title = optionTitles[option] || option;


  // State for chat/messages logic
  const [threadId, setThreadId] = useState(null);
  const [messages, setMessages] = useState([]);
  const [chatLoading, setChatLoading] = useState(false);
  const [chatError, setChatError] = useState("");
  const [inputValue, setInputValue] = useState("");
  const [streaming, setStreaming] = useState(false);
  const [, setSavingMessageId] = useState(null);

  // State for settings modal
  const [showSettingsModal, setShowSettingsModal] = useState(false);

  // ... (resource handlers, file upload, etc. remain unchanged) ...

  // Fetch resources from backend on mount and after upload
  useEffect(() => {
    if (!courseId) return;
    setResourceLoading(true);
    getCourseResources(courseId)
      .then(data => setResources(data.resources || []))
      .catch(() => setResourceError("Failed to fetch resources"))
      .finally(() => setResourceLoading(false));
  }, [courseId]);

  // Fetch or create thread and load messages on mount or when feature changes
  useEffect(() => {
    if (!courseId || !config) return;
    setChatLoading(true);
    setChatError("");
    setMessages([]);
    async function initThread() {
      try {
        let thread_id;
        if (config.createThread) {
          const thread = await config.createThread(courseId);
          thread_id = thread.thread_id || thread.id || thread.threadId;
        }
        setThreadId(thread_id);
        if (thread_id) {
          try {
            await addAllFilesToAssistant(courseId, thread_id);
          } catch (e) {
            console.warn('Failed to link all files to thread:', e);
          }
        }
        let data;
        if (config.getMessages) {
          data = await config.getMessages(courseId, thread_id) || {};
        }
        setMessages(Array.isArray(data.messages) ? data.messages : []);
      } catch (err) {
        setChatError(err.message || 'Failed to load thread/messages');
      } finally {
        setChatLoading(false);
      }
    }
    initThread();
  }, [courseId, feature, config]);

  // Send message handler (with streaming)
  const handleSendMessage = async () => {
    if (!inputValue.trim() || !threadId || !config?.sendMessage) return;
    setStreaming(true);
    setChatError("");
    let newMsg = { role: 'user', content: inputValue };
    setMessages(prev => [...prev, newMsg, { role: 'assistant', content: '' }]);
    setInputValue("");
    try {
      let content = "";
      await config.sendMessage(courseId, threadId, inputValue, (token, isComplete) => {
        content += token;
        setMessages(prev => {
          const updated = [...prev];
          updated[updated.length - 1] = { role: 'assistant', content };
          return updated;
        });
        if (isComplete) setStreaming(false);
      });
    } catch (err) {
      setChatError(err.message || 'Failed to send message');
      setStreaming(false);
    }
  };

  // Handler for individual checkbox
  const handleResourceCheck = async (id, checked) => {
    setResourceLoading(true);
    // Optimistically update UI
    const prevResources = [...resources];
    setResources(resources.map(r =>
      (r.fileId || r.id || r.fileName) === id
        ? { ...r, status: checked ? "checked_in" : "checked_out" }
        : r
    ));
    try {
      const userId = localStorage.getItem("userId");
      if (!userId) {
        setResourceError("User not logged in. Please log in again.");
        setResourceLoading(false);
        setResources(prevResources);
        return;
      }
      const res = resources.find(r => (r.fileId || r.id || r.fileName) === id);
      if (!res) return;
      if (checked) {
        await checkinResource(courseId, res.fileId || res.id || res.fileName);
      } else {
        await checkoutResource(courseId, res.fileId || res.id || res.fileName);
      }
      updateFileChecked(res.fileName, checked);
      // No forced refresh here
    } catch (err) {
      setResourceError("Failed to update resource status");
      setResources(prevResources); // Revert on error
    } finally {
      setResourceLoading(false);
    }
  };

  // Handler for select all
  const handleSelectAll = async (checked) => {
    setResourceLoading(true);
    // Optimistically update UI
    const prevResources = [...resources];
    setResources(resources.map(r => ({ ...r, status: checked ? "checked_in" : "checked_out" })));
    try {
      await Promise.all(
        resources.map(async (r) => {
          const id = r.fileId || r.id || r.fileName;
          if (checked && r.status !== "checked_in") {
            await checkinResource(courseId, id);
          } else if (!checked && r.status !== "checked_out") {
            await checkoutResource(courseId, id);
          }
        })
      );
      setAllChecked(checked);
      // No forced refresh here
    } catch (err) {
      setResourceError("Failed to update all resource statuses");
      setResources(prevResources); // Revert on error
    } finally {
      setResourceLoading(false);
    }
  };

  // Fetch resources from backend on mount and after upload
  useEffect(() => {
    if (!courseId) return;
    setResourceLoading(true);
    getCourseResources(courseId)
      .then(data => setResources(data.resources || []))
      .catch(() => setResourceError("Failed to fetch resources"))
      .finally(() => setResourceLoading(false));
  }, [courseId]);

  // Fetch or create thread and load messages on mount or when option changes
//   useEffect(() => {
//     if (!courseId) return;
//     setChatLoading(true);
//     setChatError("");
//     setMessages([]);
    
//     async function initThread() {
//       try {
//         let thread_id;
//         // Always create thread through backend to ensure consistency
//         if (option === 'brainstorm') {
//           const thread = await createBrainstormThread(courseId);
//           thread_id = thread.thread_id || thread.id || thread.threadId;
//         } else if (option === 'course-outcomes') {
//           const thread = await courseOutcomesService.createThread(courseId);
//           thread_id = thread.thread_id || thread.id || thread.threadId;
//         }
//         setThreadId(thread_id);
//         // Ensure all files are linked to the thread (production ready)
//         if (thread_id) {
//           try {
//             await addAllFilesToAssistant(courseId, thread_id);
//           } catch (e) {
//             console.warn('Failed to link all files to thread:', e);
//           }
//         }
//         // Load messages for the thread
//         let data;
//         if (option === 'brainstorm') {
//           data = await getBrainstormMessages(courseId, thread_id);
//         } else if (option === 'course-outcomes') {
//           data = await courseOutcomesService.getMessages(courseId, thread_id);
//         }
//         setMessages(data.messages || []);
//       } catch (err) {
//         setChatError(err.message || 'Failed to load thread/messages');
//       } finally {
//         setChatLoading(false);
//       }
//     }
//     initThread();
//     // eslint-disable-next-line
//   }, [courseId, option]);

  // Handle file upload to backend in the modal
  const handleModalFileUpload = async (files) => {
    if (!courseId) return;
    setResourceLoading(true);
    setResourceError("");
    try {
      // Always upload to course-level (assistant), not thread-level
      await uploadCourseResources(courseId, Array.from(files));
      addFiles(Array.from(files).map(f => ({ name: f.name, type: f.type, checked: false })));
      const updated = await getCourseResources(courseId);
      setResources(updated.resources || []);
    } catch (err) {
      setResourceError("Failed to upload files");
    } finally {
      setResourceLoading(false);
    }
  };

  // Handle file input change from sidebar
  const handleFileChange = async (e) => {
    const files = e.target.files;
    if (!files || files.length === 0) return;
    if (!courseId) return;
    setResourceLoading(true);
    setResourceError("");
    try {
      // Always upload to course-level (assistant), not thread-level
      await uploadCourseResources(courseId, Array.from(files));
      const updated = await getCourseResources(courseId);
      setResources(updated.resources || []);
    } catch (err) {
      setResourceError("Failed to upload files");
    } finally {
      setResourceLoading(false);
    }
    // Reset the file input so the same file can be uploaded again if needed
    if (fileInputRef.current) fileInputRef.current.value = null;
  };

  const handleAddContentClick = () => {
    setAddRefStep(0);
    setShowAddContentModal(true);
  };

  const handleAddContentModalClose = () => {
    setShowAddContentModal(false);
  };

  const handleAddContentModalAdd = () => {
    setShowAddContentModal(false);
    // backend integration: add uploaded/selected references to backend knowledge base
    // You can handle the selected option here
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

  // Download chat response as PDF
  const handleDownload = (content, index) => {
    const courseName = localStorage.getItem("currentCourseTitle") || "Unknown Course";
    const assetType = optionTitles[option] || option || "Chat";
    const timestampStr = new Date().toISOString().slice(0, 19).replace(/:/g, '-');
    const filename = `${assetType.toLowerCase()}-${courseName.toLowerCase().replace(/\s+/g, '-')}-${timestampStr}-msg${index+1}.pdf`;
    createPDFBlob(content, filename, `${assetType} Response`, courseName, assetType);
  };

  // Save chat response to resources
  const handleSaveToResources = async (content, index) => {
    setSavingMessageId(index);
    try {
      const courseName = localStorage.getItem("currentCourseTitle") || "Unknown Course";
      const assetType = optionTitles[option] || option || "Chat";
      const timestampStr = new Date().toISOString().slice(0, 19).replace(/:/g, '-');
      const filename = `${assetType.toLowerCase()}-${courseName.toLowerCase().replace(/\s+/g, '-')}-${timestampStr}-msg${index+1}.pdf`;
      const blob = createPDFBlobForUpload(content, filename, `${assetType} Response`, courseName, assetType);
      const file = new File([blob], filename, { type: 'application/pdf' });
      await uploadCourseResources(courseId, [file]);
      // Optionally show a success message
    } catch (error) {
      // Optionally show an error message
      console.error("Error saving to resources:", error);
    } finally {
      setSavingMessageId(null);
    }
  };

  return (
    <>
      <style>{blinkingDotStyle}</style>
    <div style={{ minHeight: "100vh", background: "#cbe0f7", padding: 0 }}>
      {/* Header */}
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", padding: "18px 32px 0 18px" }}>
        <div style={{ fontWeight: 700, fontSize: 22, display: "flex", alignItems: "center", gap: 8 }}>
          <span style={{ fontSize: 22 }}>✨</span> AI Studio
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: 14 }}>
          
          <button style={btnStyle} onClick={() => setShowSettingsModal(true)}>Settings</button>
          <button style={btnStyle} onClick={() => navigate(-1)}>Close</button>
          <button style={{ ...btnStyle, background: "#222", color: "#fff", border: "none" }}>Save</button>
        </div>
      </div>
      {/* Main Content */}
      <div style={{ display: "flex", maxWidth: 1200, margin: "24px auto 0 auto", gap: 18, alignItems: "flex-start" }}>
        {/* Chat Area */}
        <div style={{ flex: 3, background: "#fff", borderRadius: 14, minHeight: 520, display: "flex", flexDirection: "column", boxShadow: "0 1px 4px #0001", maxHeight: '80vh' }}>
          <div style={{ fontWeight: 600, fontSize: 18, padding: "18px 18px 8px 18px", borderBottom: "1px solid #e0e0e0" }}>{title}</div>
          <div style={{ flex: 1, padding: 18, overflowY: "auto", maxHeight: '60vh' }}>
              {chatLoading ? (
                <div>Loading...</div>
              ) : chatError ? (
                <div style={{ color: 'red' }}>{chatError}</div>
              ) : (
                messages.map((msg, i) => (
                  <div key={i} style={{ marginBottom: 12, textAlign: msg.role === 'user' ? 'right' : 'left' }}>
                    <div style={{ display: 'inline-block', background: msg.role === 'user' ? '#e3f0ff' : '#f5f7fa', borderRadius: 8, padding: '8px 14px', fontSize: 15, maxWidth: 400, wordBreak: 'break-word', position: 'relative' }}>
                      {msg.role === 'assistant' ? (
                        <>
                          <ReactMarkdown
                            children={msg.content}
                            components={{
                              strong: ({node, ...props}) => <strong style={{fontWeight:700}} {...props} />,
                              b: ({node, ...props}) => <b style={{fontWeight:700}} {...props} />,
                              p: ({node, ...props}) => <p style={{margin:0, padding:0}} {...props} />,
                            }}
                          />
                          {!(i === messages.length - 1 && streaming) && (
                            <div style={{ display: 'flex', gap: 12, marginTop: 8 }}>
                            <RxDownload
                              style={{ cursor: "pointer", fontSize: 20 }}
                              title="Download"
                              onClick={() => handleDownload(msg.content, i)}
                            />
                            <RxPlusCircled
                              style={{ cursor: "pointer", fontSize: 20 }}
                              title="Add to Resources"
                              onClick={() => handleSaveToResources(msg.content, i)}
                            />
                            <RxBookmark
                              style={{ cursor: "pointer", fontSize: 20 }}
                              title="Save"
                              onClick={() => alert('Save action')}
                            />
                            <RxPencil2
                              style={{ cursor: "pointer", fontSize: 20 }}
                              title="Edit"
                              onClick={() => alert('Edit action')}
                            />
                          </div>
                          )}
                        </>
                      ) : (
                        msg.content
                      )}
                      {msg.role === 'assistant' && i === messages.length - 1 && streaming && (
                        <span className="blinking-dot"></span>
                      )}
                    </div>
                  </div>
                ))
              )}
          </div>
          <div style={{ borderTop: "1px solid #e0e0e0", padding: 10, display: "flex", alignItems: "center", gap: 8 }}>
            <input
              type="text"
              placeholder="Type a prompt to generate a lesson, quiz, or outcome..."
              style={{ flex: 1, border: "none", outline: "none", fontSize: 15, padding: "10px 14px", borderRadius: 8, background: "#f5f7fa" }}
                value={inputValue}
                onChange={e => setInputValue(e.target.value)}
                disabled={streaming}
            />
              <button style={{ background: "#1976d2", color: "#fff", border: "none", borderRadius: 8, padding: "10px 18px", fontWeight: 600, fontSize: 16, cursor: streaming ? 'not-allowed' : 'pointer' }} onClick={handleSendMessage} disabled={streaming || !inputValue.trim()}>&#9658;</button>
          </div>
        </div>
        {/* Sidebar */}
        <div style={{ flex: 1, minWidth: 280 }}>
          <div style={{ background: "#fff", borderRadius: 12, boxShadow: "0 1px 4px #0001", padding: 18, maxHeight: '80vh', overflowY: 'auto' }}>
            <div style={{ fontWeight: 600, fontSize: 16, marginBottom: 4 }}>Knowledge base</div>
            <div style={{ color: "#888", fontSize: 13, marginBottom: 10 }}>Guides AI for content generation.</div>
            <input
              type="file"
              ref={fileInputRef}
              style={{ display: "none" }}
              multiple
              onChange={handleFileChange}
            />
            <button style={{ width: "100%", marginBottom: 12, padding: "8px 0", borderRadius: 6, border: "1px solid #bbb", background: "#fff", fontWeight: 500, fontSize: 15, cursor: "pointer" }} onClick={handleAddContentClick}>Add Resources</button>
            <div style={{ marginBottom: 8 }}>
              <label style={{ display: "flex", alignItems: "center", gap: 8, fontWeight: 500, fontSize: 14 }}>
                  <input type="checkbox" checked={resources.length > 0 && resources.every(r => r.status === "checked_in")} onChange={e => handleSelectAll(e.target.checked)} /> Select All References
              </label>
            </div>
            <ul style={{ listStyle: "none", padding: 0, margin: 0 }}>
                {resourceLoading ? (
                  <li>Loading resources...</li>
                ) : resourceError ? (
                  <li style={{ color: 'red' }}>{resourceError}</li>
                ) : resources.length === 0 ? (
                  <li style={{ color: '#888' }}>No resources uploaded yet.</li>
                ) : (
                  resources.map((res, i) => {
                    const id = res.fileId || res.id || res.fileName;
                    return (
                      <li key={id} style={{ display: "flex", alignItems: "center", justifyContent: "space-between", padding: "7px 0", borderBottom: i < resources.length - 1 ? "1px solid #f0f0f0" : "none" }}>
                  <label style={{ display: "flex", alignItems: "center", gap: 8, fontSize: 15, flex: 1 }}>
                    <input
                      type="checkbox"
                            checked={res.status === "checked_in"}
                            onChange={e => handleResourceCheck(id, e.target.checked)}
                            disabled={resourceLoading}
                    />
                          <span>{getFileIcon(res)}</span>
                          <span style={{ flex: 1 }}>{res.fileName || res.title}</span>
                  </label>
                        {res.url && (
                          <a href={res.url} target="_blank" rel="noopener noreferrer" style={{ color: '#2563eb', fontSize: 14, marginLeft: 8 }}>Download</a>
                        )}
                </li>
                    );
                  })
                )}
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
                  onClick={async () => {
                  if (selectedRefOption === 0 && sessionUploadedFiles.length > 0) {
                      // Upload files to backend and refresh resource list
                      await handleModalFileUpload(sessionUploadedFiles);
                    setSessionUploadedFiles([]);
                    setSessionUploadedCount(0);
                  }
                  handleAddContentModalAdd();
                }}
                style={{ padding: "8px 18px", borderRadius: 6, border: "none", background: "#222", color: "#fff", fontWeight: 500, fontSize: 15, cursor: "pointer" }}
              >
                Add
              </button>
            </div>
          </>
        )}
        {addRefStep === 1 && (
          <UploadReferencesStep
            onBack={() => setAddRefStep(0)}
            onCancel={handleAddContentModalClose}
            setSessionUploadedFiles={setSessionUploadedFiles}
            setSessionUploadedCount={setSessionUploadedCount}
              handleModalFileUpload={handleModalFileUpload}
          />
        )}
      </AddReferencesModal>
      <SettingsModal open={showSettingsModal} onClose={() => setShowSettingsModal(false)} onSave={() => setShowSettingsModal(false)} />
    </div>
    </>
  );
}

function getFileIcon(file) {
  const name = file.name || file.fileName || file.title || "";
  const type = file.type || "";
  if (type && type.startsWith("image/")) return "🖼️";
  if (type === "application/pdf") return "📄";
  if (name.endsWith(".doc") || name.endsWith(".docx")) return "📄";
  if (name.endsWith(".ppt") || name.endsWith(".pptx")) return "📊";
  if (name.endsWith(".xls") || name.endsWith(".xlsx")) return "📊";
  if (name.endsWith(".txt")) return "📄";
  if (name.endsWith(".zip") || name.endsWith(".rar")) return "🗜️";
  if (name.endsWith(".csv")) return "📑";
  if (name.endsWith(".mp4") || name.endsWith(".mov")) return "🎞️";
  if (name.endsWith(".mp3") || name.endsWith(".wav")) return "🎵";
  if (name.endsWith(".html") || name.endsWith(".htm")) return "🌐";
  if (name.endsWith(".json")) return "🗂️";
  if (name.endsWith(".js")) return "📜";
  if (name.endsWith(".py")) return "🐍";
  if (name.endsWith(".java")) return "☕";
  if (name.endsWith(".c") || name.endsWith(".cpp")) return "💻";
  if (name.endsWith(".md")) return "📝";
  if (name.endsWith(".svg")) return "🖼️";
  if (name.endsWith(".xml")) return "🗂️";
  if (name.endsWith(".yml") || name.endsWith(".yaml")) return "🗂️";
  return "📁";
}

function UploadReferencesStep({ onBack, onCancel, setSessionUploadedFiles, setSessionUploadedCount, handleModalFileUpload }) {
  const [uploading, setUploading] = useState([]); // [{file, progress, done}]
  const [uploaded, setUploaded] = useState([]); // [{file}]
  const fileInputRef = useRef();

  const handleFiles = files => {
    const filesArr = Array.from(files);
    const newUploads = filesArr.map(file => ({ file, progress: 0, done: false }));
    setUploading(prev => [...prev, ...newUploads]);
    filesArr.forEach((file, idx) => simulateUpload(file, idx + uploading.length));
  };

  const simulateUpload = (file, idx) => {
    let progress = 0;
    const interval = setInterval(() => {
      progress += Math.random() * 25 + 10;
      setUploading(prev => prev.map((u, i) => i === idx ? { ...u, progress: Math.min(progress, 100), done: progress >= 100 } : u));
      if (progress >= 100) {
        clearInterval(interval);
        setUploaded(prev => {
          const updated = [...prev, { file }];
          // Only update session state, do not add to global references
          setSessionUploadedFiles(updated.map(u => ({ name: u.file.name, type: u.file.type, checked: false })));
          setSessionUploadedCount(updated.length);
          return updated;
        });
      }
    }, 300);
  };

  const handleDrop = e => {
    e.preventDefault();
    handleFiles(e.dataTransfer.files);
  };
  const handleBrowse = e => {
    handleFiles(e.target.files);
    e.target.value = null;
  };
  const handleDelete = idx => {
    setUploaded(prev => prev.filter((_, i) => i !== idx));
  };

  const handleCancel = () => {
    setUploaded([]);
    setSessionUploadedFiles([]);
    setSessionUploadedCount(0);
    onCancel();
  };
  const handleBack = () => {
    setUploaded([]);
    onBack();
  };

  return (
    <div>
      <div style={{ fontWeight: 700, fontSize: 20, marginBottom: 6 }}>Upload References</div>
      <div style={{ color: "#444", fontSize: 15, marginBottom: 12 }}>Accepted formats: PDF, DOCX, PPTX, TXT, CSV, Images</div>
      <div
        onDrop={handleDrop}
        onDragOver={e => e.preventDefault()}
        style={{ border: "2px dashed #1976d2", borderRadius: 10, padding: 32, textAlign: "center", marginBottom: 18, background: "#f5f7fa", cursor: "pointer" }}
        onClick={() => fileInputRef.current.click()}
      >
        <div style={{ fontSize: 32, marginBottom: 8 }}>📂</div>
        <div style={{ fontWeight: 500, fontSize: 16 }}>Drag & drop files here or <span style={{ color: "#1976d2", textDecoration: "underline" }}>Browse</span></div>
        <input
          type="file"
          multiple
          ref={fileInputRef}
          style={{ display: "none" }}
          onChange={handleBrowse}
          accept=".pdf,.doc,.docx,.ppt,.pptx,.txt,.csv,image/*"
        />
      </div>
      <div style={{ marginBottom: 12 }}>
        {uploading.map((u, i) => (
          <div key={i} style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 6 }}>
            <span>{u.file.name}</span>
            <div style={{ flex: 1, height: 8, background: "#eee", borderRadius: 4, overflow: "hidden" }}>
              <div style={{ width: `${u.progress}%`, height: 8, background: u.done ? "#4caf50" : "#1976d2" }} />
            </div>
            <span style={{ fontSize: 13 }}>{Math.round(u.progress)}%</span>
          </div>
        ))}
      </div>
      <div style={{ marginBottom: 12 }}>
        {uploaded.map((u, i) => (
          <div key={i} style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 6 }}>
            <span>{u.file.name}</span>
            <span style={{ cursor: "pointer", color: "#d32f2f" }} onClick={() => handleDelete(i)}>🗑️</span>
          </div>
        ))}
      </div>
      <div style={{ display: "flex", justifyContent: "flex-end", gap: 12 }}>
        <button onClick={handleCancel} style={{ padding: "8px 18px", borderRadius: 6, border: "1px solid #bbb", background: "#fff", fontWeight: 500, fontSize: 15, cursor: "pointer" }}>Cancel</button>
        <button onClick={handleBack} style={{ padding: "8px 18px", borderRadius: 6, border: "1px solid #1976d2", background: "#f0f7ff", color: "#1976d2", fontWeight: 500, fontSize: 15, cursor: "pointer" }}>Back to Add References</button>
        <button
          onClick={async () => {
            if (uploaded.length > 0) {
              await handleModalFileUpload(uploaded.map(u => u.file));
              setUploaded([]);
              setSessionUploadedFiles([]);
              setSessionUploadedCount(0);
              onCancel();
            }
          }}
          style={{ padding: "8px 18px", borderRadius: 6, border: "none", background: uploaded.length > 0 ? "#222" : "#ccc", color: "#fff", fontWeight: 500, fontSize: 15, cursor: uploaded.length > 0 ? "pointer" : "not-allowed" }}
          disabled={uploaded.length === 0}
        >
          Add
        </button>
      </div>
    </div>
  );
} 

  // ... (rest of the UI and handlers remain unchanged, just use config.title for the title) ...
