import React from "react";
import AppHeader from "./AppHeader";
import SectionCard from "./SectionCard";
import Sidebar from "./Sidebar";
import Modal from "./Modal";
import SettingsModal from "./SettingsModal";
import KnowledgeBaseSelectModal from "./KnowledgeBaseSelectModal";

export default function DashboardLayout({
  state,
  curriculumOptions,
  onFilesUpload,
  onCreate,
  onLogout,
  navigate,
  allFiles
}) {
  const courseTitle = localStorage.getItem("currentCourseTitle") || "Untitled Course";

  return (
    <div style={{ minHeight: "100vh", height: "100vh", background: "#fafbfc", display: "flex", flexDirection: "column" }}>
      <AppHeader onLogout={onLogout} title="Creators Copilot" />

      {/* Breadcrumb */}
      <div style={{
        maxWidth: 1200,
        margin: "1rem auto 0.5rem auto",
        width: "100%",
        display: 'flex',
        alignItems: 'center',
        gap: 10,
        fontSize: 18,
        fontWeight: 500,
        color: '#222'
      }}>
        <span
          style={{ color: '#2563eb', cursor: 'pointer', fontWeight: 600 }}
          onClick={() => navigate('/courses')}
        >
          Courses
        </span>
        <span style={{ color: '#888', fontSize: 18, margin: '0 6px' }}>{'>'}</span>
        <span style={{ fontWeight: 700, color: '#111', fontSize: 22 }}>
          {courseTitle}
        </span>
      </div>

      {/* Main layout */}
      <div style={{ display: "flex", gap: 24, alignItems: "stretch", flex: 1, minHeight: 0, height: "100%", padding: "0 5vw" }}>
        {/* Left: Sections */}
        <div style={{ flex: 2, display: "flex", flexDirection: "column", minHeight: 0, height: "100%" }}>
          <div style={{ background: "#fafbfc", borderRadius: 16, padding: 0, height: "100%", display: "flex", flexDirection: "column", overflow: "hidden" }}>
            <div style={{ flex: 1, minHeight: 0, overflowY: "auto", display: "flex", flexDirection: "column", gap: 28, padding: "24px 24px 32px 24px" }}>
              <SectionCard title="Curriculum" buttonLabel="Create" onButtonClick={state.handleCurriculumCreate} />
              <SectionCard title="Assessments" buttonLabel="Create" />
              <SectionCard title="Evaluation" buttonLabel="Start Evaluation" />
              <div style={{ background: "#fff", borderRadius: 18, padding: "28px 32px" }}>
                <h2 style={{ fontSize: 24, fontWeight: 600 }}>
                  Sprint Plan
                  <span style={{ fontSize: 13, fontWeight: 400, color: '#444', marginLeft: 8 }}>
                    (Based on the Academics term...)
                  </span>
                </h2>
                <div style={{ marginTop: 12 }}>
                  <button
                    onClick={onCreate}
                    style={{
                      padding: "8px 22px",
                      borderRadius: 6,
                      border: "1px solid #bbb",
                      background: "#fff",
                      fontWeight: 500,
                      fontSize: 15,
                      cursor: "pointer",
                      marginLeft: 12
                    }}
                  >
                    Create Documentation
                  </button>
                </div>
              </div>
            </div>
          </div>
        </div>

        {/* Right: Sidebar */}
        <div style={{ flex: 1, minWidth: 280, height: "100%", display: 'flex', flexDirection: 'column', justifyContent: 'flex-start', marginTop: 24 }}>
          <Sidebar ref={state.sidebarRef} onAddContentClick={() => state.setShowAddResourceModal(true)} />
        </div>
      </div>

      {/* Curriculum Component Modal */}
      <Modal open={state.showCurriculumModal} onClose={() => state.setShowCurriculumModal(false)}>
        <div style={{ fontWeight: 700, fontSize: 22, marginBottom: 8, display: "flex", alignItems: "center", gap: 8 }}>
          <span style={{ fontSize: 24 }}>✨</span> Curriculum
        </div>
        <div style={{ fontWeight: 500, fontSize: 16, marginBottom: 18 }}>Select Curriculum component</div>
        <div style={{ display: "flex", flexWrap: "wrap", gap: 10, marginBottom: 18 }}>
          {curriculumOptions.map((opt, i) => (
            <label key={opt.label} style={{
              border: state.selectedOption === i ? "2px solid #1976d2" : "1px solid #ddd",
              borderRadius: 8,
              padding: 10,
              minWidth: 150,
              flex: "1 1 38%",
              background: state.selectedOption === i ? "#f0f7ff" : "#fafbfc",
              cursor: "pointer",
              display: "flex",
              flexDirection: "column",
              gap: 10,
              boxShadow: state.selectedOption === i ? "0 2px 8px #1976d222" : "none"
            }}>
              <input
                type="radio"
                name="curriculum-option"
                checked={state.selectedOption === i}
                onChange={() => {
                  state.setSelectedOption(i);
                  state.setSelectedComponent(opt.url);
                }}
                style={{ marginBottom: 6 }}
              />
              <span style={{ fontWeight: 600, fontSize: 15 }}>{opt.label}</span>
              <span style={{ color: "#444", fontSize: 13 }}>{opt.desc}</span>
            </label>
          ))}
        </div>
        <div style={{ display: "flex", justifyContent: "flex-end", gap: 12 }}>
          <button
            onClick={() => state.setShowCurriculumModal(false)}
            style={{ padding: "8px 18px", borderRadius: 6, border: "1px solid #bbb", background: "#fff", fontWeight: 500, fontSize: 15 }}
          >
            Cancel
          </button>
          <button
            onClick={onCreate}
            style={{ padding: "8px 18px", borderRadius: 6, background: "#222", color: "#fff", fontWeight: 500, fontSize: 15 }}
          >
            Create
          </button>
        </div>
      </Modal>

      {/* Knowledge Base Modal */}
      <KnowledgeBaseSelectModal
        open={state.showKBModal}
        onClose={() => state.setShowKBModal(false)}
        onGenerate={(selectedFiles) => {
          state.setShowKBModal(false);
          navigate(`/studio/${state.selectedComponent}`, { state: { selectedFiles } });
        }}
        files={allFiles}
      />

      {/* Settings Modal */}
      <SettingsModal
        open={state.showSettingsModal}
        onClose={() => state.setShowSettingsModal(false)}
        onSave={() => state.setShowSettingsModal(false)}
      />
    </div>
  );
}
