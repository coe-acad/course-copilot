import React from "react";
import { useNavigate } from "react-router-dom";
import DashboardLayout from "../components/DashboardLayout";
import { useDashboardState } from "../hooks/useDashboardState";
import { useUploadHandler } from "../hooks/useUploadHandler";
import { useCourseResources } from "../hooks/useCourseResources";
import curriculumOptions from "../config/curriculumOptions";

export default function Dashboard() {
  const navigate = useNavigate();
  const courseId = localStorage.getItem("currentCourseId");

  // ✅ Safeguard: Ensure course title exists for breadcrumb
  if (!localStorage.getItem("currentCourseTitle")) {
    localStorage.setItem("currentCourseTitle", "Untitled Course");
  }

  // All UI/State
  const state = useDashboardState();

  // File fetcher
  const allFiles = useCourseResources(courseId, state.showKBModal);

  // Upload handler
  const handleFilesUpload = useUploadHandler(courseId, state.sidebarRef, state.setResourceError);

  const handleCreate = () => {
    const assetName = curriculumOptions[state.selectedOption]?.url;
    if (!assetName) return alert("Please select a valid component.");
    state.setShowCurriculumModal(false);
    navigate(`/studio/${assetName}`);
  };

  const handleLogout = () => {
    localStorage.removeItem("token");
    navigate("/login");
  };

  return (
    <DashboardLayout
      state={state}
      curriculumOptions={curriculumOptions}
      onFilesUpload={handleFilesUpload}
      onCreate={handleCreate}
      onLogout={handleLogout}
      navigate={navigate}
      allFiles={allFiles}
    />
  );
}
