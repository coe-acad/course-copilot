import React, { useState, useEffect, useRef } from "react";
import { useNavigate } from "react-router-dom";
import Header from "../components/header/Header";
import SectionCard from "../components/SectionCard";
import Modal from "../components/Modal";
import SettingsModal from "../components/SettingsModal";
import KnowledgeBaseSelectModal from "../components/KnowledgeBaseSelectModal";
import KnowledgeBase from "../components/KnowledgBase";

const curriculumOptions = [
  {
    label: "Brainstorm",
    desc: "Generate and organize initial ideas for your course curriculum.",
    url: "brainstorm"
  },
  {
    label: "Course Outcomes",
    desc: "Set clear learning goals students are expected to achieve by the end of the course.",
    url: "course-outcomes"
  },
  {
    label: "Modules & Topics",
    desc: "Organize content into structured modules and focused topics for easy navigation.",
    url: "modules-topics"
  },
  {
    label: "Lesson Plans",
    desc: "Plan each session with defined objectives, activities, and resources.",
    url: "lesson-plans"
  },
  {
    label: "Concept Map",
    desc: "Visualize relationships between key ideas and topics in the course.",
    url: "concept-map"
  },
  {
    label: "Course Notes",
    desc: "Add notes to support student understanding and revision.",
    url: "course-notes"
  },
];

export default function Dashboard() {
  const [showKBModal, setShowKBModal] = useState(false);
  const [selectedComponent, setSelectedComponent] = useState(null);
  const [allFiles, setAllFiles] = useState([]); // Fetch this from your backend or context
  
  const [showCurriculumModal, setShowCurriculumModal] = useState(false);
  const [selectedOption, setSelectedOption] = useState(0);
  const [showSettingsModal, setShowSettingsModal] = useState(false);
  const [isGridView, setIsGridView] = useState(true);
  const navigate = useNavigate();
  const [resourceError, setResourceError] = useState("");
  const courseId = localStorage.getItem("currentCourseId");
  const sidebarRef = useRef();
  
  useEffect(() => {
    // TODO: Integrate backend to fetch resources
    setAllFiles([]); // Set to [] or dummy data for now
    // setResourceError(""); // No backend, so no error
  }, [showKBModal, courseId]);

  // Handle real file upload to backend
  const handleFilesUpload = async files => {
    // TODO: Integrate backend to upload resources
    // Simulate upload success
    setResourceError(""); // No error since no backend
    // Optionally update local state or show a message
  };

  // When opening the curriculum modal, always select the first option by default
  const handleCurriculumCreate = () => {
    setSelectedOption(0); // Always select the first option by default
    setShowCurriculumModal(true);
  };
  const handleModalClose = () => setShowCurriculumModal(false);

  const handleCreate = async () => {
    const assetName = curriculumOptions[selectedOption]?.url;
    console.log('handleCreate: selectedOption:', selectedOption, 'assetName:', assetName);
    if (!assetName) {
      alert("Please select a valid curriculum component.");
      return;
    }    
    setShowCurriculumModal(false);
    // Navigate immediately to AssetStudio for the selected asset
    navigate(`/studio/${assetName}`);
    // Start backend thread creation in the background
    // setTimeout(async () => {
    //   try {
    //     await courseOutcomesService.createThread(courseId, assetName);
    //     // Optionally, trigger a refresh or update state in AssetStudio
    //   } catch (error) {
    //     // Optionally show an error or toast
    //     console.error('Failed to create thread:', error);
    //   }
    // }, 0);
  };

  // Add Resource modal with Upload/Discover toggle
  const [showAddResourceModal, setShowAddResourceModal] = useState(false);
  const [resourceTab, setResourceTab] = useState(null); // null, 'upload', or 'discover'
  const [pendingFiles, setPendingFiles] = useState([]); // For modal upload step
  const [uploadProgress, setUploadProgress] = useState([]); // Progress for each file
  const [isUploading, setIsUploading] = useState(false);

  const handleResourceBack = () => {
    setResourceTab(null);
  };
  const handleResourceModalClose = () => {
    setShowAddResourceModal(false);
  };
  const handleDrop = e => {
    e.preventDefault();
    handleFilesUpload(e.dataTransfer.files);
  };
  // const handleResourceAdd = () => { // This function is removed
  //   if (resourceTab === 'upload') {
  //     const newFiles = uploadingFiles.filter(f => f.done).map(f => ({ name: f.name, type: f.file?.type || '', checked: true }));
  //     addFiles(newFiles);
  //   }
  //   setShowAddResourceModal(false);
  //   setUploadingFiles([]);
  // };

  // Handler functions
  const handleLogout = () => {
    localStorage.removeItem("token");
    navigate("/login");
  };
  const handleSettings = () => setShowSettingsModal(true);
  const handleExport = () => alert("Export to LMS coming soon!");
  const handleGridView = () => setIsGridView(true);
  const handleListView = () => setIsGridView(false);

  return (
    <div style={{ minHeight: "100vh", height: "100vh", background: "#fafbfc", display: "flex", flexDirection: "column" }}>
      <Header
        title="Creators Copilot"
        onLogout={handleLogout}
        onSettings={handleSettings}
        onExport={handleExport}
        onGridView={handleGridView}
        onListView={handleListView}
        isGridView={isGridView}
      />
      {/* Breadcrumb Navigation */}
      <div style={{ maxWidth: 1200, margin: "1rem auto 0.5rem auto", width: "100%", display: 'flex', alignItems: 'center', gap: 10, fontSize: 18, fontWeight: 500, color: '#222' }}>
        <span
          style={{ color: '#2563eb', cursor: 'pointer', fontWeight: 600 }}
          onClick={() => navigate('/courses')}
        >
          Courses
        </span>
        <span style={{ color: '#888', fontSize: 18, margin: '0 6px' }}>{'>'}</span>
        <span style={{ fontWeight: 700, color: '#111', fontSize: 22 }}>
          {localStorage.getItem("currentCourseTitle") || "Course Title"}
        </span>
      </div>
      <div className="main-layout" style={{ display: "flex", gap: 24, alignItems: "stretch", flex: 1, minHeight: 0, height: "100%", padding: "0 5vw" }}>
        {/* Main Content: 4 cards inside a scrollable card container */}
        <div style={{ flex: 2, display: "flex", flexDirection: "column", minHeight: 0, height: "100%" }}>
          <div style={{ background: "rgb(250, 251, 252)", borderRadius: 16, boxShadow: "none", padding: 0, height: "100%", minHeight: 0, display: "flex", flexDirection: "column", overflow: "hidden" }}>
            <div style={{ flex: 1, minHeight: 0, overflowY: "auto", display: "flex", flexDirection: "column", gap: 28, padding: "24px 24px 32px 24px" }}>
          <SectionCard
            title="Curriculum"
            buttonLabel="Create"
                style={{
                  boxShadow: "0 4px 24px #0002",
                  borderRadius: 18,
                  padding: "28px 32px",
                  marginBottom: 0,
                  background: "#fff"
                }}
            onButtonClick={handleCurriculumCreate}
          />
          <SectionCard
                title="Assessments"
            buttonLabel="Create"
                style={{
                  boxShadow: "0 4px 24px #0002",
                  borderRadius: 18,
                  padding: "28px 32px",
                  marginBottom: 0,
                  background: "#fff"
                }}
          />
          <SectionCard
                title="Evaluation"
            buttonLabel="Start Evaluation"
                style={{
                  boxShadow: "0 4px 24px #0002",
                  borderRadius: 18,
                  padding: "28px 32px",
                  marginBottom: 0,
                  background: "#fff"
                }}
              />
              <div style={{ background: "#fff", borderRadius: 18, boxShadow: "0 4px 24px #0002", padding: "28px 32px", minHeight: 140, display: "flex", flexDirection: "column", justifyContent: "center" }}>
                <div style={{ display: "flex", alignItems: "center", gap: 16 }}>
                  <h2 style={{ margin: 0, fontSize: 24, fontWeight: 600, flex: 1 }}>Sprint Plan <span style={{ fontSize: 13, fontWeight: 400, color: '#444', marginLeft: 8 }}>(Based on the Academics term...)</span></h2>
                </div>
                <div style={{ display: "flex", alignItems: "center", marginTop: 12 }}>
                  <button onClick={handleCreate} style={{ padding: "8px 22px", borderRadius: 6, border: "1px solid #bbb", background: "#fff", fontWeight: 500, fontSize: 15, cursor: "pointer", marginLeft: 12, boxShadow: "0 1px 2px #0001", transition: "background 0.2s" }}>Create Documentation</button>
                </div>
              </div>
            </div>
          </div>
        </div>
        {/* Knowledge Base Panel (instead of Sidebar) */}
        <div className="knowledge-base" style={{ flex: 1, minWidth: 280, height: "100%", display: 'flex', flexDirection: 'column', marginTop: 24 }}>
          <KnowledgeBase
            resources={allFiles}
            fileInputRef={{ current: null }} // You can make this a real ref if needed
            onFileChange={() => {}} // Optional, hook it to your upload
            showCheckboxes={false}
            selected={[]}
            onSelect={() => {}}
          />
        </div>
      </div>
      <Modal open={showCurriculumModal} onClose={handleModalClose}>
        <div style={{ fontWeight: 700, fontSize: 22, marginBottom: 8, display: "flex", alignItems: "center", gap: 8 }}>
          <span style={{ fontSize: 24 }}>✨</span> Curriculum
        </div>
        <div style={{ fontWeight: 500, fontSize: 16, marginBottom: 18 }}>Select Curriculum component</div>
        <div style={{ display: "flex", flexWrap: "wrap", gap: 10, marginBottom: 18 }}>
          {curriculumOptions.map((opt, i) => (
            <label key={opt.label} style={{
              border: selectedOption === i ? "2px solid #1976d2" : "1px solid #ddd",
              borderRadius: 8,
              padding: 10,
              minWidth: 150,
              flex: "1 1 38%",
              background: selectedOption === i ? "#f0f7ff" : "#fafbfc",
              cursor: "pointer",
              display: "flex",
              flexWrap: "wrap",
              flexDirection: "column",
              gap: 10,
              boxShadow: selectedOption === i ? "0 2px 8px #1976d222" : "none"
            }}>
              <input
                type="radio"
                name="curriculum-option"
                checked={selectedOption === i}
                onChange={() => {setSelectedOption(i); setSelectedComponent(opt.url);}}
                style={{ marginBottom: 6 }}
              />
              <span style={{ fontWeight: 600, fontSize: 15 }}>{opt.label}</span>
              <span style={{ color: "#444", fontSize: 13 }}>{opt.desc}</span>
            </label>
          ))}
        </div>
        <div style={{ display: "flex", justifyContent: "flex-end", gap: 12 }}>
          <button onClick={handleModalClose} style={{ padding: "8px 18px", borderRadius: 6, border: "1px solid #bbb", background: "#fff", fontWeight: 500, fontSize: 15, cursor: "pointer" }}>Cancel</button>
          <button onClick={handleCreate} style={{ padding: "8px 18px", borderRadius: 6, border: "none", background: "#222", color: "#fff", fontWeight: 500, fontSize: 15, cursor: "pointer" }}>Create</button>
        </div>
      </Modal>
      <KnowledgeBaseSelectModal
      open={showKBModal}
      onClose={() => setShowKBModal(false)}
      onGenerate={(selectedFiles) => {
        setShowKBModal(false);
        // Navigate to AI Studio with selected component and files
        navigate(`/studio/${selectedComponent}`, {
          state: { selectedFiles }
        });
      }}
      files={allFiles}
    />
      {showAddResourceModal && (
        <Modal open={showAddResourceModal} onClose={handleResourceModalClose} modalStyle={{ minWidth: 600, maxWidth: 700, borderRadius: 16, padding: 0 }}>
          <div style={{ padding: "32px 36px 24px 36px", background: "#fff", borderRadius: 16, minWidth: 500 }}>
            <div style={{ fontWeight: 700, fontSize: 24, marginBottom: 6, color: "#1a2533" }}>Add Resources</div>
            <div style={{ color: "#6b7280", fontSize: 15, marginBottom: 28, fontWeight: 500 }}>
              Add resources from the web or course documents you’ve already created — this helps AI give relevant results.
            </div>
            {resourceError && <div style={{ color: 'red', marginBottom: 12 }}>{resourceError}</div>}
            {resourceTab === null && (
              <div style={{ display: "flex", gap: 24, marginBottom: 32 }}>
                <button
                  onClick={() => setResourceTab('upload')}
                  style={{
                    flex: 1,
                    background: '#f5f8ff',
                    border: '2px solid #2563eb',
                    borderRadius: 12,
                    padding: '36px 0',
                    display: 'flex',
                    flexDirection: 'column',
                    alignItems: 'center',
                    cursor: 'pointer',
                    fontWeight: 600,
                    fontSize: 18,
                    color: '#2563eb',
                    outline: 'none',
                    boxShadow: '0 2px 8px #2563eb22',
                    transition: 'border 0.2s, background 0.2s',
                  }}
                >
                  <span style={{ fontSize: 38, marginBottom: 16 }}>&#8682;</span>
                  Upload
                </button>
                <button
                  onClick={() => setResourceTab('discover')}
                  style={{
                    flex: 1,
                    background: '#fff',
                    border: '1px solid #e5e7eb',
                    borderRadius: 12,
                    padding: '36px 0',
                    display: 'flex',
                    flexDirection: 'column',
                    alignItems: 'center',
                    cursor: 'pointer',
                    fontWeight: 600,
                    fontSize: 18,
                    color: '#222',
                    outline: 'none',
                    transition: 'border 0.2s, background 0.2s',
                  }}
                >
                  <span style={{ fontSize: 38, marginBottom: 16 }}>&#128269;</span>
                  Discover
                </button>
              </div>
            )}
            {resourceTab === 'upload' && (
              <>
                <button onClick={handleResourceBack} style={{ background: 'none', border: 'none', color: '#2563eb', fontWeight: 500, fontSize: 16, cursor: 'pointer', padding: 0, marginBottom: 12, display: 'flex', alignItems: 'center' }}>
                  <span style={{ fontSize: 20, marginRight: 6 }}>&larr;</span> Back
                </button>
                <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 8 }}>
                  <span style={{ fontSize: 22, color: "#2563eb" }}>⭳</span>
                  <span style={{ fontWeight: 700, fontSize: 22, color: "#1a2533" }}>Upload</span>
                </div>
                <div
                  onDrop={handleDrop}
                  onDragOver={e => e.preventDefault()}
                  style={{ border: "2px dashed #d1d5db", borderRadius: 12, padding: 32, textAlign: "center", marginBottom: 24, background: "#fafbfc", cursor: "pointer", position: "relative" }}
                  onClick={() => document.getElementById('upload-input-modal').click()}
                >
                  <span style={{ fontSize: 36, color: "#2563eb", display: "block", marginBottom: 10 }}>⭳</span>
                  <div style={{ fontSize: 16, color: "#222", marginBottom: 6 }}>
                    Drag and drop or <span style={{ color: "#2563eb", textDecoration: "underline", cursor: "pointer" }}>browse files</span> to upload
                  </div>
                  <div style={{ color: "#6b7280", fontSize: 15, marginBottom: 0 }}>
                    Accepted formats: <span style={{ color: "#2563eb", textDecoration: "underline", margin: "0 2px" }}>.pdf</span>
                    <span style={{ color: "#2563eb", textDecoration: "underline", margin: "0 2px" }}>.docx</span>
                    <span style={{ color: "#2563eb", textDecoration: "underline", margin: "0 2px" }}>.jpg</span>
                    <span style={{ color: "#2563eb", textDecoration: "underline", margin: "0 2px" }}>.png</span>
                    <span style={{ color: "#2563eb", textDecoration: "underline", margin: "0 2px" }}>.xlsx</span>
                    <span style={{ color: "#2563eb", textDecoration: "underline", margin: "0 2px" }}>.pptx</span>
                  </div>
                  <input
                    id="upload-input-modal"
                    type="file"
                    multiple
                    style={{ display: "none" }}
                    onChange={e => {
                      setPendingFiles(Array.from(e.target.files || []));
                      setUploadProgress([]);
                    }}
                    accept=".pdf,.docx,.jpg,.png,.xlsx,.pptx"
                  />
                </div>
                {/* Pending files UI with progress bars */}
                {pendingFiles.length > 0 && (
                  <div style={{ background: '#f5f7fa', borderRadius: 8, padding: 12, marginBottom: 12, border: '1px solid #ddd' }}>
                    <div style={{ fontWeight: 600, fontSize: 15, marginBottom: 8 }}>Files to Add:</div>
                    <ul style={{ listStyle: 'none', padding: 0, margin: 0 }}>
                      {pendingFiles.map((file, idx) => (
                        <li key={idx} style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 8 }}>
                          <span>{file.name}</span>
                          {isUploading ? (
                            <div style={{ flex: 1, height: 8, background: '#eee', borderRadius: 4, overflow: 'hidden', marginLeft: 8, marginRight: 8 }}>
                              <div style={{ width: `${uploadProgress[idx] || 0}%`, height: 8, background: uploadProgress[idx] === 100 ? '#4caf50' : '#1976d2', transition: 'width 0.2s' }} />
                            </div>
                          ) : (
                            <span style={{ cursor: 'pointer', color: '#d32f2f', fontSize: 16 }} onClick={() => setPendingFiles(prev => prev.filter((_, i) => i !== idx))}>🗑️</span>
                          )}
                          {isUploading && <span style={{ fontSize: 13 }}>{Math.round(uploadProgress[idx] || 0)}%</span>}
                        </li>
                      ))}
                    </ul>
                  </div>
                )}
                {/* Single set of action buttons at the bottom */}
                <div style={{ display: "flex", justifyContent: "flex-end", gap: 12, marginTop: 8 }}>
                  <button onClick={handleResourceModalClose} style={{ padding: "10px 28px", borderRadius: 8, border: "1px solid #bbb", background: "#fff", fontWeight: 500, fontSize: 16, cursor: isUploading ? "not-allowed" : "pointer" }} disabled={isUploading}>Cancel</button>
                  <button
                    onClick={async () => {
                      if (pendingFiles.length > 0) {
                        console.log('Starting upload of', pendingFiles.length, 'files');
                        setIsUploading(true);
                        setUploadProgress(Array(pendingFiles.length).fill(0));
                        setResourceError("");
                        try {
                          // Upload each file with progress
                          for (let i = 0; i < pendingFiles.length; i++) {
                            await new Promise((resolve, reject) => {
                              const formData = new FormData();
                              formData.append('files', pendingFiles[i]);
                              const xhr = new XMLHttpRequest();
                              const API_BASE = process.env.REACT_APP_API_BASE_URL || 'http://localhost:8000/api';
                              xhr.open('POST', `${API_BASE}/courses/${courseId}/resources`);
                              xhr.setRequestHeader('Authorization', `Bearer ${localStorage.getItem('token')}`);
                              xhr.upload.onprogress = (event) => {
                                if (event.lengthComputable) {
                                  setUploadProgress(prev => {
                                    const copy = [...prev];
                                    copy[i] = (event.loaded / event.total) * 100;
                                    return copy;
                                  });
                                }
                              };
                              xhr.onload = () => {
                                setUploadProgress(prev => {
                                  const copy = [...prev];
                                  copy[i] = 100;
                                  return copy;
                                });
                                resolve();
                              };
                              xhr.onerror = () => reject(new Error('Upload failed'));
                              xhr.send(formData);
                            });
                          }
                          console.log('Upload completed successfully');
                          // Refresh the sidebar resources list
                          if (sidebarRef.current && sidebarRef.current.refreshResources) {
                            console.log('Refreshing sidebar resources');
                            sidebarRef.current.refreshResources();
                          }
                          setPendingFiles([]);
                          setResourceTab(null);
                          setShowAddResourceModal(false);
                        } catch (err) {
                          setResourceError("Failed to upload files");
                        } finally {
                          setIsUploading(false);
                        }
                      }
                    }}
                    style={{ padding: "10px 28px", borderRadius: 8, border: "none", background: pendingFiles.length > 0 && !isUploading ? "#2563eb" : "#ccc", color: "#fff", fontWeight: 600, fontSize: 16, cursor: pendingFiles.length > 0 && !isUploading ? "pointer" : "not-allowed" }}
                    disabled={pendingFiles.length === 0 || isUploading}
                  >
                    Add
                  </button>
                </div>
              </>
            )}
            {resourceTab === 'discover' && (
              <>
                <button onClick={handleResourceBack} style={{ background: 'none', border: 'none', color: '#2563eb', fontWeight: 500, fontSize: 16, cursor: 'pointer', padding: 0, marginBottom: 12, display: 'flex', alignItems: 'center' }}>
                  <span style={{ fontSize: 20, marginRight: 6 }}>&larr;</span> Back
                </button>
                <div style={{ minHeight: 200, display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#888', fontSize: 18, fontWeight: 500 }}>
                  Discover resources (coming soon)
                </div>
              </>
            )}
          </div>
        </Modal>
      )}
      <SettingsModal open={showSettingsModal} onClose={() => setShowSettingsModal(false)} onSave={() => setShowSettingsModal(false)} />
    </div>
  );
}