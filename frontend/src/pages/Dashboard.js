import React, { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import Header from "../components/header/Header";
import AssetViewModal from "../components/AssetViewModal";
import SectionCard from "../components/SectionCard";
import KnowledgeBase from "../components/KnowledgBase";
import SettingsModal from "../components/SettingsModal";
import KnowledgeBaseSelectModal from "../components/KnowledgeBaseSelectModal";
import SelectionModal from "../components/SelectionModal";
import { getAllResources, uploadCourseResources, deleteResource as deleteResourceApi } from "../services/resources";
import { getCourseSettings } from "../services/course";
import { assetService } from "../services/asset";
import curriculumOptions from "../config/curriculumOptions";
import assessmentOptions from "../config/assessmentsOptions";
import AddResourceModal from '../components/AddReferencesModal';
import SettingsPromptModal from '../components/SettingsPromptModal';

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
  const [assets, setAssets] = useState({ curriculum: [], assessments: [], evaluation: [] });
  const [, setLoadingAssets] = useState(true);
  const [showAddResourceModal, setShowAddResourceModal] = useState(false);
  const [isUploadingResources, setIsUploadingResources] = useState(false);
  const [showSettingsPrompt, setShowSettingsPrompt] = useState(false);
  const [pendingContentType, setPendingContentType] = useState('');
  const [showAssetModal, setShowAssetModal] = useState(false);
  const [selectedAsset, setSelectedAsset] = useState(null);
  const [assetModalLoading, setAssetModalLoading] = useState(false);
  const [categoryFilter, setCategoryFilter] = useState('All');
  const navigate = useNavigate();
  // Helper to view asset
  const handleViewAsset = async (category, asset) => {
    const courseId = localStorage.getItem('currentCourseId');
    if (!courseId || !asset.name) return;
    setAssetModalLoading(true);
    try {
      // Use assetService to fetch asset details
      const assetData = await assetService.viewAsset(courseId, asset.name);
      setSelectedAsset(assetData);
      setShowAssetModal(true);
    } catch (error) {
      alert('Failed to view asset.');
    } finally {
      setAssetModalLoading(false);
    }
  };

  // Helper to download asset
  const handleDownloadAsset = async (asset) => {
    const courseId = localStorage.getItem('currentCourseId');
    if (!courseId || !asset.name) return;
    try {
      await assetService.downloadAsset(courseId, asset.name);
    } catch (error) {
      alert('Failed to download asset.');
    }
  };

  // Fetch resources on component mount
  useEffect(() => {
    const fetchResources = async () => {
      try {
        setLoadingResources(true);
        const courseId = localStorage.getItem('currentCourseId');
        if (!courseId) {
          console.error('No current course ID found');
          setResources([]);
          return;
        }
        
        const data = await getAllResources(courseId);
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

  // Fetch assets on component mount and when returning after a pending save
  useEffect(() => {
    const fetchAssets = async () => {
      try {
        setLoadingAssets(true);
        const courseId = localStorage.getItem('currentCourseId');
        if (!courseId) {
          console.error('No current course ID found');
          return;
        }
        
        const data = await assetService.getAssets(courseId);
        const assetsList = data.assets || [];
        
        // Group assets by category
        const groupedAssets = {
          curriculum: [],
          assessments: [],
          evaluation: []
        };
        
        assetsList.forEach(asset => {
          const category = asset.asset_category;
          if (groupedAssets.hasOwnProperty(category)) {
            groupedAssets[category].push({
              name: asset.asset_name,
              type: asset.asset_type,
              timestamp: asset.asset_last_updated_at,
              updatedBy: asset.asset_last_updated_by
            });
          }
        });
        
        setAssets(groupedAssets);
      } catch (error) {
        console.error('Error fetching assets:', error);
        setAssets({ curriculum: [], assessments: [], evaluation: [] });
      } finally {
        setLoadingAssets(false);
      }
    };

    fetchAssets();

    // If we just saved an evaluation, retry fetch a couple of times for eventual consistency
    const pendingName = localStorage.getItem('pendingEvaluationAssetName');
    if (pendingName) {
      const retries = [800, 1600, 3000];
      retries.forEach((delay) => {
        setTimeout(() => { fetchAssets(); }, delay);
      });
      // Clear the hint to avoid repeated retries on future visits
      localStorage.removeItem('pendingEvaluationAssetName');
    }
  }, []);

  const handleCurriculumCreate = () => {
    handleContentCreation('curriculum', () => {
      setSelectedOption(0);
      setShowCurriculumModal(true);
    });
  };

  const handleAssessmentCreate = () => {
    handleContentCreation('assessments', () => {
      setSelectedAssessmentOption(0);
      setShowAssessmentModal(true);
    });
  };

  const handleEvaluationCreate = () => {
    handleContentCreation('evaluation', () => {
      navigate('/evaluation');
    });
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

  // Check if settings are configured (any setting is enough)
  const checkSettings = async () => {
    try {
      const courseId = localStorage.getItem('currentCourseId');
      if (!courseId) return false;
      
      const settings = await getCourseSettings(courseId);
      return settings && (
        (settings.course_level && settings.course_level.length > 0) ||
        (settings.study_area && settings.study_area.length > 0) ||
        (settings.pedagogical_components && settings.pedagogical_components.length > 0) ||
        settings.ask_clarifying_questions !== undefined
      );
    } catch (error) {
      console.error('Error checking settings:', error);
      return false;
    }
  };

  // Handle content creation with settings check
  const handleContentCreation = async (contentType, createFunction) => {
    const hasSettings = await checkSettings();
    if (!hasSettings) {
      setPendingContentType(contentType);
      setShowSettingsPrompt(true);
    } else {
      createFunction();
    }
  };

  // Handle settings prompt actions
  const handleSettingsPromptClose = () => {
    setShowSettingsPrompt(false);
    // Continue with the pending content creation
    if (pendingContentType === 'curriculum') {
      setSelectedOption(0);
      setShowCurriculumModal(true);
    } else if (pendingContentType === 'assessments') {
      setSelectedAssessmentOption(0);
      setShowAssessmentModal(true);
    } else if (pendingContentType === 'evaluation') {
      navigate('/evaluation');
    }
  };

  // Add this handler to refresh resources after adding
  const handleAddResources = async (files) => {
    setShowAddResourceModal(false);
    const courseId = localStorage.getItem('currentCourseId');
    if (!courseId || !files.length) return;
    
    setIsUploadingResources(true);
    try {
      await uploadCourseResources(courseId, files); // upload to backend
      // Refresh resources
      const data = await getAllResources(courseId);
      const transformedResources = (data.resources || []).map(resource => ({
        id: resource.resourceName,
        fileName: resource.resourceName,
        title: resource.resourceName,
        url: `#${resource.resourceName}`
      }));
      setResources(transformedResources);
    } catch (error) {
      console.error('Error uploading resources:', error);
      alert('Failed to upload resources. Please try again.');
    } finally {
      setIsUploadingResources(false);
    }
  };

  const handleDeleteResource = async (resourceId) => {
    const courseId = localStorage.getItem('currentCourseId');
    if (!courseId) return;
    try {
      await deleteResourceApi(courseId, resourceId);
      // Refresh resources
      const data = await getAllResources(courseId);
      const transformedResources = (data.resources || []).map(resource => ({
        id: resource.resourceName,
        fileName: resource.resourceName,
        title: resource.resourceName,
        url: `#${resource.resourceName}`
      }));
      setResources(transformedResources);
    } catch (err) {
      alert('Failed to delete resource.');
    }
  };

  return (
    <>
      <style>{`
        .dashboard-scroll-area::-webkit-scrollbar {
          width: 8px;
          background: transparent;
        }
        .dashboard-scroll-area::-webkit-scrollbar-thumb {
          background: #e0e7ef;
          border-radius: 6px;
        }
        .dashboard-scroll-area::-webkit-scrollbar-thumb:hover {
          background: #cbd5e1;
        }
        .dashboard-scroll-area {
          scrollbar-width: thin;
          scrollbar-color: #e0e7ef transparent;
        }
        .assets-table {
          width: 100%;
          border-collapse: collapse;
          background: #fff;
          border-radius: 18px;
          box-shadow: 0 4px 24px #0002;
          margin: 32px auto;
          overflow: hidden;
        }
        .assets-table th, .assets-table td {
          padding: 14px 18px;
          text-align: left;
        }
        .assets-table th {
          background: #f5f8ff;
          font-weight: 700;
          font-size: 16px;
          color: #2563eb;
          border-bottom: 1px solid #e5eaf2;
        }
        .assets-table tr:not(:last-child) td {
          border-bottom: 1px solid #f3f4f6;
        }
      `}</style>
      <div style={{ height: '100vh', display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
        <Header
          title="Course Copilot"
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

        {/* Conditional main content: grid or list view */}
        {isGridView ? (
          <div style={{ flex: 1, display: 'flex', gap: 24, padding: '0 5vw', overflow: 'hidden' }}>
            {/* ...existing grid view code... */}
            <div className="dashboard-scroll-area" style={{ flex: 2, maxWidth: 900, width: '100%', margin: '0 auto', overflowY: 'auto', padding: '24px 0', display: 'flex', flexDirection: 'column', gap: 28 }}>
              <SectionCard 
                title="Curriculum" 
                buttonLabel="Create" 
                onButtonClick={handleCurriculumCreate}
                assets={assets.curriculum}
                courseId={localStorage.getItem('currentCourseId')}
              />
              <SectionCard 
                title="Assessments" 
                buttonLabel="Create" 
                onButtonClick={handleAssessmentCreate}
                assets={assets.assessments}
                courseId={localStorage.getItem('currentCourseId')}
              />
              <SectionCard 
                title="Evaluation" 
                buttonLabel="Start Evaluation"
                onButtonClick={handleEvaluationCreate}
                assets={assets.evaluation}
                courseId={localStorage.getItem('currentCourseId')}
              />
            </div>
            {/* Right panel: Knowledge Base */}
            <div style={{ flex: 1, marginTop: 24, minWidth: 340, maxWidth: 420 }}>
              <KnowledgeBase
                resources={loadingResources ? [] : resources}
                fileInputRef={{ current: null }}
                onFileChange={() => {}}
                showCheckboxes={false}
                selected={[]}
                onSelect={() => {}}
                onAddResource={() => setShowAddResourceModal(true)}
                onDelete={handleDeleteResource}
                isUploading={isUploadingResources}
              />
            </div>
          </div>
        ) : (
          <div style={{ flex: 1, width: '100%', padding: '0 8vw', display: 'flex', flexDirection: 'column', alignItems: 'center', boxSizing: 'border-box', height: 'calc(100vh - 120px)' }}>
            <h2 style={{ fontWeight: 700, fontSize: 28, color: '#2563eb', margin: '32px 0 18px 0' }}>Course Assets</h2>
            <div style={{ flex: 1, width: '100%', overflowY: 'auto', boxSizing: 'border-box', marginBottom: 24 }}>
              <table className="assets-table" style={{ width: '100%' }}>
                <thead style={{ position: 'sticky', top: 0, zIndex: 2, background: '#fff' }}>
                  <tr>
                    <th>Name</th>
                    <th>Type</th>
                    <th style={{ minWidth: 180 }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: 8, position: 'relative', minHeight: 40 }}>
                        <span style={{ fontWeight: 600, color: '#2563eb', fontSize: 15, marginRight: 6 }}>Category</span>
                        <select
                          id="categoryFilter"
                          value={categoryFilter}
                          onChange={e => setCategoryFilter(e.target.value)}
                          style={{
                            padding: '6px 18px 6px 10px',
                            borderRadius: 10,
                            border: '1.5px solid #d1d5db',
                            fontSize: 15,
                            fontWeight: 500,
                            color: '#2563eb',
                            background: '#f5f8ff',
                            cursor: 'pointer',
                            boxShadow: '0 2px 8px #0001',
                            transition: 'border 0.2s',
                            outline: 'none',
                            marginLeft: 0,
                            minWidth: 120
                          }}
                        >
                          <option value="All">All</option>
                          <option value="Curriculum">Curriculum</option>
                          <option value="Assessments">Assessments</option>
                          <option value="Evaluation">Evaluation</option>
                        </select>
                      </div>
                    </th>
                    <th>Last Updated</th>
                    <th>Updated By</th>
                    <th>Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {['curriculum', 'assessments', 'evaluation']
                    .filter(category => categoryFilter === 'All' || category.toLowerCase() === categoryFilter.toLowerCase())
                    .flatMap(category =>
                      assets[category].map(asset => (
                        <tr key={asset.name + asset.type + category}>
                          <td>
                            <button
                              style={{ background: 'none', border: 'none', color: '#2563eb', fontWeight: 600, cursor: 'pointer', textDecoration: 'underline', fontSize: 16 }}
                              onClick={() => handleViewAsset(category, asset)}
                              disabled={assetModalLoading}
                            >
                              {asset.name}
                            </button>
                          </td>
                          <td>{asset.type}</td>
                          <td style={{ textTransform: 'capitalize' }}>{category}</td>
                          <td>{asset.timestamp}</td>
                          <td>{asset.updatedBy}</td>
                          <td>
                            <button
                              style={{ background: 'none', border: 'none', color: '#2563eb', cursor: 'pointer', fontSize: 18, marginRight: 8 }}
                              title="Download"
                              onClick={() => handleDownloadAsset(asset)}
                            >
                              ⬇️
                            </button>
                          </td>
                        </tr>
                      ))
                    )}
                </tbody>
              </table>
            </div>
            {/* Asset view modal */}
            <AssetViewModal
              open={showAssetModal}
              onClose={() => { setShowAssetModal(false); setSelectedAsset(null); }}
              assetData={selectedAsset}
              courseId={localStorage.getItem('currentCourseId')}
            />
          </div>
        )}

        {/* ...existing modals and overlays... */}
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
        <AddResourceModal
          open={showAddResourceModal}
          onClose={() => setShowAddResourceModal(false)}
          onAdd={handleAddResources}
        />
        <SettingsPromptModal
          open={showSettingsPrompt}
          onClose={handleSettingsPromptClose}
          onOpenSettings={() => {
            setShowSettingsPrompt(false);
            setShowSettingsModal(true);
          }}
          contentType={pendingContentType}
        />
      </div>
    </>
  );
}
