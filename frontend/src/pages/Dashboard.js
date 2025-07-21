import React, { useState } from "react";
import { useNavigate } from "react-router-dom";
import Header from "../components/Header";
import SectionCard from "../components/SectionCard";
import Sidebar from "../components/Sidebar";
import Modal from "../components/Modal";
import SettingsModal from "../components/SettingsModal";
import { useFilesContext } from "../context/FilesContext";
import { useResources } from "../context/ResourcesContext";

function TopRow({ onAddContentClick, onSettingsClick }) {
  const courseTitle = localStorage.getItem("currentCourseTitle") || "Course Title";
  const navigate = useNavigate();
  return (
    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", maxWidth: 1200, margin: "1rem auto 0.5rem auto", width: "100%" }}>
      <div>
        <button
          style={{
            background: "#fff",
            border: "1px solid #ddd",
            borderRadius: 8,
            padding: "7px 18px",
            fontWeight: 500,
            fontSize: 15,
            color: "#222",
            cursor: "pointer",
            marginBottom: 18,
            boxShadow: "0 1px 2px #0001"
          }}
          onClick={() => navigate("/courses")}
        >
          Back to Courses
        </button>
        <div style={{ fontWeight: 700, fontSize: 32, marginTop: 0 }}>{courseTitle}</div>
      </div>
      <div style={{ display: "flex", alignItems: "center", gap: 14, marginTop: 8, justifyContent: "flex-end" }}>
        {/* Toggle button group */}
        <div style={{ display: "flex", alignItems: "center", gap: 0, background: "#f5f8ff", borderRadius: 8, border: "1px solid #e0e7ef", overflow: "hidden", height: 38, marginRight: 10 }}>
          <button
            style={{
              background: "#2563eb",
              color: "#fff",
              border: "none",
              padding: "0 14px",
              fontWeight: 600,
              fontSize: 18,
              height: 38,
              cursor: "pointer",
              outline: "none",
              display: "flex",
              alignItems: "center",
              borderRadius: 0
            }}
          >
            <span style={{ fontSize: 18, verticalAlign: "middle" }}>▦</span>
          </button>
          <button
            style={{
              background: "#fff",
              color: "#222",
              border: "none",
              padding: "0 14px",
              fontWeight: 600,
              fontSize: 18,
              height: 38,
              cursor: "pointer",
              outline: "none",
              borderLeft: "1px solid #e0e7ef",
              display: "flex",
              alignItems: "center",
              borderRadius: 0
            }}
          >
            <span style={{ fontSize: 18, verticalAlign: "middle" }}>≡</span>
          </button>
        </div>
        <button
          style={{
            height: 38,
            padding: "0 22px",
            borderRadius: 8,
            border: "1px solid #ddd",
            background: "#fff",
            fontWeight: 500,
            fontSize: 16,
            color: "#222",
            cursor: "pointer",
            marginRight: 2
          }}
          onClick={onSettingsClick}
        >
          Settings
        </button>
        <button
          style={{
            height: 38,
            padding: "0 22px",
            borderRadius: 8,
            border: "none",
            background: "#2563eb",
            fontWeight: 500,
            fontSize: 16,
            color: "#fff",
            cursor: "pointer"
          }}
        >
          Export to LMS
        </button>
      </div>
    </div>
  );
}


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
  const [showCurriculumModal, setShowCurriculumModal] = useState(false);
  const [selectedOption, setSelectedOption] = useState(0);
  // Remove Add Resources modal, go directly to upload modal
  // const [showAddResourceModal, setShowAddResourceModal] = useState(false);
  // const [selectedResourceOption, setSelectedResourceOption] = useState(0); // 0: Upload, 1: Discover
  const [showSettingsModal, setShowSettingsModal] = useState(false);
  const navigate = useNavigate();
  const { addFiles } = useFilesContext();
  const { addPendingFiles, commitPendingFiles, resetCommit, loadResources } = useResources();

  const handleCurriculumCreate = () => setShowCurriculumModal(true);
  const handleModalClose = () => setShowCurriculumModal(false);
  const handleModalCreate = () => {
    const url = curriculumOptions[selectedOption].url;
    setShowCurriculumModal(false);
    navigate(`/studio/${url}`);
  };

  // Add Resource modal with Upload/Discover toggle
  const [showAddResourceModal, setShowAddResourceModal] = useState(false);
  const [resourceTab, setResourceTab] = useState(null); // null, 'upload', or 'discover'
  const [uploadingFiles, setUploadingFiles] = useState([]); // [{name, progress, done, file}]
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState("");

  const handleAddResourceClick = () => {
    setShowAddResourceModal(true);
    setResourceTab(null);
    setUploadingFiles([]);
  };
  const handleResourceBack = () => {
    setResourceTab(null);
    setUploadingFiles([]);
  };
  const handleResourceModalClose = () => {
    setShowAddResourceModal(false);
    setUploadingFiles([]);
  };
  const handleFilesUpload = files => {
    const filesArr = Array.from(files).map(file => ({ name: file.name, progress: 0, done: false, file }));
    setUploadingFiles(prev => [...prev, ...filesArr]);
    filesArr.forEach((file, idx) => simulateUpload(file, uploadingFiles.length + idx));
  };
  const simulateUpload = (file, idx) => {
    let progress = 0;
    const interval = setInterval(() => {
      progress += Math.random() * 25 + 10;
      setUploadingFiles(prev => prev.map((u, i) => i === idx ? { ...u, progress: Math.min(progress, 100), done: progress >= 100 } : u));
      if (progress >= 100) clearInterval(interval);
    }, 300);
  };
  const handleDrop = e => {
    e.preventDefault();
    handleFilesUpload(e.dataTransfer.files);
  };
  const handleBrowse = e => {
    handleFilesUpload(e.target.files);
    e.target.value = null;
  };
  const handleRemoveFile = idx => {
    setUploadingFiles(prev => prev.filter((_, i) => i !== idx));
  };
  const handleResourceAdd = async () => {
    if (resourceTab === 'upload') {
      setUploading(true);
      setError("");
      try {
        const courseId = localStorage.getItem("currentCourseId");
        const files = uploadingFiles.filter(f => f.done).map(f => f.file);
        await addPendingFiles(files);
        await commitPendingFiles(courseId);
        await loadResources(courseId); // <-- Refresh resources after upload
        resetCommit();
      } catch (err) {
        setError(err.message || "Failed to upload files");
      } finally {
        setUploading(false);
      }
    }
    setShowAddResourceModal(false);
    setUploadingFiles([]);
  };

  return (
    <div style={{ minHeight: "100vh", height: "100vh", background: "#fafbfc", display: "flex", flexDirection: "column" }}>
      <Header />
      <TopRow onSettingsClick={() => setShowSettingsModal(true)} />
      <div className="main-layout" style={{ display: "flex", gap: 24, alignItems: "flex-start", flex: 1, minHeight: 0, height: "100%", padding: "0 5vw" }}>
        {/* Main Content: 4 cards inside a scrollable card container */}
        <div style={{ flex: 2, display: "flex", flexDirection: "column", minHeight: 0, height: "100%" }}>
          <div style={{ background: "rgb(250, 251, 252)", borderRadius: 16, boxShadow: "none", padding: 0, height: "100%", minHeight: 0, display: "flex", flexDirection: "column", overflow: "hidden" }}>
            <div style={{ flex: 1, minHeight: 0, overflowY: "auto", display: "flex", flexDirection: "column", gap: 28, padding: "32px 24px 32px 24px" }}>
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
                  <button style={{ padding: "8px 22px", borderRadius: 6, border: "1px solid #bbb", background: "#fff", fontWeight: 500, fontSize: 15, cursor: "pointer", marginLeft: 12, boxShadow: "0 1px 2px #0001", transition: "background 0.2s" }}>Create Documentation</button>
                </div>
              </div>
            </div>
          </div>
        </div>
        {/* Sidebar */}
        <div className="sidebar" style={{ flex: 1, minWidth: 280, height: "100%" }}>
          <Sidebar onAddContentClick={handleAddResourceClick} />
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
              flexDirection: "column",
              gap: 4,
              boxShadow: selectedOption === i ? "0 2px 8px #1976d222" : "none"
            }}>
              <input
                type="radio"
                name="curriculum-option"
                checked={selectedOption === i}
                onChange={() => setSelectedOption(i)}
                style={{ marginBottom: 6 }}
              />
              <span style={{ fontWeight: 600, fontSize: 15 }}>{opt.label}</span>
              <span style={{ color: "#444", fontSize: 13 }}>{opt.desc}</span>
            </label>
          ))}
        </div>
        <div style={{ display: "flex", justifyContent: "flex-end", gap: 12 }}>
          <button onClick={handleModalClose} style={{ padding: "8px 18px", borderRadius: 6, border: "1px solid #bbb", background: "#fff", fontWeight: 500, fontSize: 15, cursor: "pointer" }}>Cancel</button>
          <button onClick={handleModalCreate} style={{ padding: "8px 18px", borderRadius: 6, border: "none", background: "#222", color: "#fff", fontWeight: 500, fontSize: 15, cursor: "pointer" }}>Create</button>
        </div>
      </Modal>
      <Modal open={showAddResourceModal} onClose={handleResourceModalClose} modalStyle={{ minWidth: 600, maxWidth: 700, borderRadius: 16, padding: 0 }}>
        <div style={{ padding: "32px 36px 24px 36px", background: "#fff", borderRadius: 16, minWidth: 500 }}>
          <div style={{ fontWeight: 700, fontSize: 24, marginBottom: 6, color: "#1a2533" }}>Add Resources</div>
          <div style={{ color: "#6b7280", fontSize: 15, marginBottom: 28, fontWeight: 500 }}>
            Add resources from the web or course documents you’ve already created — this helps AI give relevant results.
          </div>
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
                onClick={() => document.getElementById('upload-input').click()}
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
                  id="upload-input"
                  type="file"
                  multiple
                  style={{ display: "none" }}
                  onChange={handleBrowse}
                  accept=".pdf,.docx,.jpg,.png,.xlsx,.pptx"
                />
              </div>
              {uploadingFiles.length > 0 && (
                <div style={{ marginBottom: 24 }}>
                  <div style={{ fontWeight: 600, fontSize: 16, marginBottom: 10 }}>Uploading files</div>
                  {uploadingFiles.map((file, idx) => (
                    <div key={file.name + idx} style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 10, background: file.done ? "#f0fdf4" : "#fff", borderRadius: 6, padding: "8px 12px", border: file.done ? "1px solid #34d399" : "1px solid #e5e7eb" }}>
                      <span style={{ flex: 1, fontSize: 15 }}>{file.name}</span>
                      <div style={{ flex: 2, height: 6, background: "#e5e7eb", borderRadius: 3, overflow: "hidden", marginRight: 8 }}>
                        <div style={{ width: `${file.progress}%`, height: 6, background: file.done ? "#34d399" : "#2563eb" }} />
                      </div>
                      {file.done ? (
                        <span style={{ color: "#34d399", fontSize: 18 }}>✔</span>
                      ) : (
                        <span style={{ color: "#2563eb", fontSize: 18 }}>&#8635;</span>
                      )}
                      <button onClick={() => handleRemoveFile(idx)} style={{ background: "none", border: "none", color: "#d32f2f", fontSize: 18, cursor: "pointer" }} title="Remove">&#128465;</button>
                    </div>
                  ))}
                </div>
              )}
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
          <div style={{ display: "flex", justifyContent: "flex-end", gap: 12 }}>
            <button onClick={handleResourceModalClose} style={{ padding: "10px 28px", borderRadius: 8, border: "1px solid #bbb", background: "#fff", fontWeight: 500, fontSize: 16, cursor: "pointer" }}>Cancel</button>
            <button onClick={handleResourceAdd} style={{ padding: "10px 28px", borderRadius: 8, border: "none", background: "#2563eb", color: "#fff", fontWeight: 600, fontSize: 16, cursor: "pointer" }}>Add</button>
          </div>
        </div>
      </Modal>
      <SettingsModal open={showSettingsModal} onClose={() => setShowSettingsModal(false)} onSave={() => setShowSettingsModal(false)} />
    </div>
  );
}