import { useState, useRef } from "react";

export function useDashboardState() {
  const [showKBModal, setShowKBModal] = useState(false);
  const [selectedComponent, setSelectedComponent] = useState(null);
  const [showCurriculumModal, setShowCurriculumModal] = useState(false);
  const [selectedOption, setSelectedOption] = useState(0);
  const [showSettingsModal, setShowSettingsModal] = useState(false);
  const [isGridView, setIsGridView] = useState(true);
  const [resourceError, setResourceError] = useState("");
  const [showAddResourceModal, setShowAddResourceModal] = useState(false);
  const [resourceTab, setResourceTab] = useState(null);
  const [pendingFiles, setPendingFiles] = useState([]);
  const [uploadProgress, setUploadProgress] = useState([]);
  const [isUploading, setIsUploading] = useState(false);

  const sidebarRef = useRef();

  return {
    showKBModal, setShowKBModal,
    selectedComponent, setSelectedComponent,
    showCurriculumModal, setShowCurriculumModal,
    selectedOption, setSelectedOption,
    showSettingsModal, setShowSettingsModal,
    isGridView, setIsGridView,
    resourceError, setResourceError,
    showAddResourceModal, setShowAddResourceModal,
    resourceTab, setResourceTab,
    pendingFiles, setPendingFiles,
    uploadProgress, setUploadProgress,
    isUploading, setIsUploading,
    sidebarRef
  };
}
