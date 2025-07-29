import React, { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import Header from "../components/header/Header";
import SectionCard from "../components/SectionCard";
import KnowledgeBase from "../components/KnowledgBase";
import SettingsModal from "../components/SettingsModal";
import KnowledgeBaseSelectModal from "../components/KnowledgeBaseSelectModal";
import SelectionModal from "../components/SelectionModal";
import { getAllResources } from "../services/resources";
import curriculumOptions from "../config/curriculumOptions";
import assessmentOptions from "../config/assessmentsOptions";

export default function Dashboard() {
  const [showKBModal, setShowKBModal] = useState(false);
  const [selectedComponent, setSelectedComponent] = useState(null);
  const [showCurriculumModal, setShowCurriculumModal] = useState(false);
  const [showAssessmentModal, setShowAssessmentModal] = useState(false);
  const [selectedOption, setSelectedOption] = useState(0);
  const [selectedAssessmentOption, setSelectedAssessmentOption] = useState(0);
  const [showSettingsModal, setShowSettingsModal] = useState(false);
  const [isGridView, setIsGridView] = useState(true);
  const [resources, setResources] = useState([]);
  const [loadingResources, setLoadingResources] = useState(true);
  const navigate = useNavigate();

  // Fetch resources on component mount
  useEffect(() => {
    const fetchResources = async () => {
      try {
        setLoadingResources(true);
        const data = await getAllResources();
        // Transform the resources to match the expected format
        const transformedResources = (data.resources || []).map(resource => ({
          id: resource.resourceName,
          fileName: resource.resourceName,
          title: resource.resourceName,
          url: `#${resource.resourceName}` // Placeholder URL
        }));
        setResources(transformedResources);
      } catch (error) {
        console.error('Error fetching resources:', error);
        setResources([]);
      } finally {
        setLoadingResources(false);
      }
    };

    fetchResources();
  }, []);

  const handleCurriculumCreate = () => {
    setSelectedOption(0);
    setShowCurriculumModal(true);
  };

  const handleAssessmentCreate = () => {
    setSelectedAssessmentOption(0);
    setShowAssessmentModal(true);
  };

  const handleCurriculumSubmit = (selected) => {
    setShowCurriculumModal(false);
    setSelectedComponent(selected.url);
    setShowKBModal(true);
  };

  const handleAssessmentSubmit = (selected) => {
    setShowAssessmentModal(false);
    setSelectedComponent(selected.url);
    setShowKBModal(true);
  };

  const handleLogout = () => {
    localStorage.removeItem("token");
    navigate("/login");
  };

  return (
    <div style={{ minHeight: "100vh", background: "#fafbfc", display: "flex", flexDirection: "column" }}>
      <Header
        title="Creators Copilot"
        onLogout={handleLogout}
        onSettings={() => setShowSettingsModal(true)}
        onExport={() => alert("Export to LMS coming soon!")}
        onGridView={() => setIsGridView(true)}
        onListView={() => setIsGridView(false)}
        isGridView={isGridView}
      />

      {/* Breadcrumb */}
      <div style={{ maxWidth: 1200, margin: "1rem auto 0.5rem auto", width: "100%", display: 'flex', alignItems: 'center', gap: 10, fontSize: 18, fontWeight: 500 }}>
        <span style={{ color: '#2563eb', cursor: 'pointer', fontWeight: 600 }} onClick={() => navigate('/courses')}>Courses</span>
        <span style={{ color: '#888' }}>{'>'}</span>
        <span style={{ fontWeight: 700 }}>{localStorage.getItem("currentCourseTitle") || "Course Title"}</span>
      </div>

      <div style={{ display: "flex", gap: 24, flex: 1, padding: "0 5vw" }}>
        {/* Main Section */}
        <div style={{ flex: 2, display: "flex", flexDirection: "column", gap: 28, padding: "24px 0" }}>
          <SectionCard title="Curriculum" buttonLabel="Create" onButtonClick={handleCurriculumCreate} />
          <SectionCard title="Assessments" buttonLabel="Create" onButtonClick={handleAssessmentCreate} />
          <SectionCard title="Evaluation" buttonLabel="Start Evaluation" />
          <div style={{ background: "#fff", borderRadius: 18, padding: 28, boxShadow: "0 4px 24px #0002" }}>
            <h2 style={{ margin: 0 }}>Sprint Plan <span style={{ fontSize: 13, fontWeight: 400, color: '#444' }}>(Based on the Academic term...)</span></h2>
            <button
              onClick={() => navigate("/studio/sprint-plan")}
              style={{ marginTop: 12, padding: "8px 22px", borderRadius: 6, border: "1px solid #bbb", background: "#fff", cursor: "pointer" }}
            >
              Create Documentation
            </button>
          </div>
        </div>

        {/* Right Knowledge Base Panel */}
        <div style={{ flex: 1, marginTop: 24 }}>
          <KnowledgeBase
            resources={loadingResources ? [] : resources}
            fileInputRef={{ current: null }}
            onFileChange={() => {}}
            showCheckboxes={false}
            selected={[]}
            onSelect={() => {}}
          />
        </div>
      </div>

      {/* Selection Modals */}
      <SelectionModal
        open={showCurriculumModal}
        title="Curriculum"
        options={curriculumOptions}
        selectedOption={selectedOption}
        onSelect={setSelectedOption}
        onClose={() => setShowCurriculumModal(false)}
        onCreate={handleCurriculumSubmit}
      />

      <SelectionModal
        open={showAssessmentModal}
        title="Assessments"
        options={assessmentOptions}
        selectedOption={selectedAssessmentOption}
        onSelect={setSelectedAssessmentOption}
        onClose={() => setShowAssessmentModal(false)}
        onCreate={handleAssessmentSubmit}
      />

      {/* KB Selection Modal → AI Studio */}
      <KnowledgeBaseSelectModal
        open={showKBModal}
        onClose={() => setShowKBModal(false)}
        onGenerate={(selectedFiles) => {
          setShowKBModal(false);
          navigate(`/studio/${selectedComponent}`, {
            state: { selectedFiles }
          });
        }}
        files={loadingResources ? [] : resources}
      />

      <SettingsModal open={showSettingsModal} onClose={() => setShowSettingsModal(false)} />
    </div>
  );
}
