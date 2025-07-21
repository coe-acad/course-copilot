import React, { useState, useRef, useEffect } from 'react';
import { 
  uploadCourseResources, 
  uploadAssetResources, 
  deleteResource
} from '../services/resources';
import { useResources } from '../context/ResourcesContext';
import { FiMoreVertical, FiDownload, FiTrash2 } from 'react-icons/fi';

const FileUpload = ({ 
  courseId, 
  threadId = null, 
  onUploadComplete, 
  onResourcesLoaded,
  showCheckoutControls = true,
  title = "Upload Files"
}) => {
  const [files, setFiles] = useState([]);
  const [uploading, setUploading] = useState(false);
  const [uploadProgress, setUploadProgress] = useState(0);
  const [error, setError] = useState(null);
  const [selectedResource, setSelectedResource] = useState(null);
  const [showMenu, setShowMenu] = useState(false);
  const fileInputRef = useRef(null);
  
  // Use global resources context
  const { 
    getResources, 
    loadResources: loadGlobalResources, 
    addResource,
    removeResource,
    updateResource,
    isLoading 
  } = useResources();
  
  const resources = getResources(courseId);
  const loading = isLoading(courseId);

  // Load resources on component mount
  React.useEffect(() => {
    if (courseId) {
      loadGlobalResources(courseId);
    }
  }, [courseId]); // eslint-disable-line react-hooks/exhaustive-deps

  // Close menu when clicking outside
  useEffect(() => {
    const handleClickOutside = (event) => {
      if (showMenu) {
        handleMenuClose();
      }
    };

    document.addEventListener('click', handleClickOutside);
    return () => {
      document.removeEventListener('click', handleClickOutside);
    };
  }, [showMenu]);

  // Define compatible file types/extensions
  const COMPATIBLE_EXTENSIONS = [
    '.pdf', '.doc', '.docx', '.txt', '.md', '.csv', '.png', '.jpg', '.jpeg', '.xlsx', '.xls', '.ppt', '.pptx', '.gif'
  ];

  // Helper to check file compatibility
  const isCompatible = (file) => {
    const name = file.name.toLowerCase();
    return COMPATIBLE_EXTENSIONS.some(ext => name.endsWith(ext));
  };

  const handleFileSelect = (event) => {
    const selectedFiles = Array.from(event.target.files);
    const compatible = [];
    const incompatible = [];

    selectedFiles.forEach(file => {
      if (isCompatible(file)) {
        compatible.push(file);
      } else {
        incompatible.push(file);
      }
    });

    setFiles(compatible);
    if (incompatible.length > 0) {
      setError(
        `The following files are not compatible and will not be uploaded:` +
        '\n' +
        incompatible.map(f => `- ${f.name} (unsupported file type)`).join('\n')
      );
    } else {
      setError(null);
      if (compatible.length > 0) {
        // Auto-upload compatible files
        handleUploadAuto(compatible);
      }
    }
  };

  // Auto-upload function (no button)
  const handleUploadAuto = async (autoFiles) => {
    if (!autoFiles.length || !courseId) return;
    
    console.log('Starting upload with courseId:', courseId, 'files:', autoFiles.map(f => f.name));
    
    try {
      setUploading(true);
      setUploadProgress(0);
      setError(null);
      
      let response;
      if (threadId) {
        console.log('Uploading to asset thread:', threadId);
        response = await uploadAssetResources(courseId, threadId, autoFiles);
      } else {
        console.log('Uploading to course level');
        response = await uploadCourseResources(courseId, autoFiles);
      }
      
      console.log('Upload response:', response);
      
      if (response && response.resources) {
        response.resources.forEach(resource => {
          addResource(courseId, resource);
        });
      }
      
      setFiles([]);
      setUploadProgress(0);
      if (fileInputRef.current) {
        fileInputRef.current.value = '';
      }
      if (onUploadComplete) {
        onUploadComplete(response);
      }
    } catch (err) {
      console.error('Upload error:', err);
      setError(err.message || 'Upload failed');
    } finally {
      setUploading(false);
    }
  };



  const handleDelete = async (fileId) => {
    if (!window.confirm('Are you sure you want to delete this file?')) return;
    
    try {
      await deleteResource(courseId, fileId);
      
      // Remove from context immediately for instant UI update
      removeResource(courseId, fileId);
      
      console.log('Resource deleted successfully');
    } catch (err) {
      console.error('Delete error:', err);
      setError(err.message || 'Delete failed');
    }
  };

  const handleMenuClick = (resource, event) => {
    event.stopPropagation();
    setSelectedResource(resource);
    setShowMenu(true);
  };

  const handleMenuClose = () => {
    setShowMenu(false);
    setSelectedResource(null);
  };

  const getFileIcon = (resource) => {
    const fileName = resource.fileName || resource.name || '';
    if (fileName.endsWith(".pdf")) return "📄";
    if (fileName.endsWith(".doc") || fileName.endsWith(".docx")) return "📄";
    if (fileName.endsWith(".ppt") || fileName.endsWith(".pptx")) return "📊";
    if (fileName.endsWith(".xls") || fileName.endsWith(".xlsx")) return "📊";
    if (fileName.endsWith(".txt")) return "📄";
    if (fileName.endsWith(".zip") || fileName.endsWith(".rar")) return "🗜️";
    if (fileName.endsWith(".csv")) return "📑";
    if (fileName.endsWith(".mp4") || fileName.endsWith(".mov")) return "🎞️";
    if (fileName.endsWith(".mp3") || fileName.endsWith(".wav")) return "🎵";
    if (fileName.endsWith(".html") || fileName.endsWith(".htm")) return "🌐";
    if (fileName.endsWith(".json")) return "🗂️";
    if (fileName.endsWith(".js")) return "📜";
    if (fileName.endsWith(".py")) return "🐍";
    if (fileName.endsWith(".java")) return "☕";
    if (fileName.endsWith(".c") || fileName.endsWith(".cpp")) return "💻";
    if (fileName.endsWith(".md")) return "📝";
    if (fileName.endsWith(".svg")) return "🖼️";
    if (fileName.endsWith(".xml")) return "🗂️";
    if (fileName.endsWith(".yml") || fileName.endsWith(".yaml")) return "🗂️";
    if (fileName.endsWith(".jpg") || fileName.endsWith(".jpeg") || fileName.endsWith(".png") || fileName.endsWith(".gif")) return "🖼️";
    return "📁";
  };

  return (
    <div style={{
      background: '#fff',
      borderRadius: 20,
      boxShadow: '0 2px 12px #0001',
      padding: 20,
      maxWidth: 540,
      margin: '32px auto',
      minHeight: 320,
      display: 'flex',
      flexDirection: 'column',
      gap: 16
    }}>
      <div style={{ fontWeight: 700, fontSize: 20, marginBottom: 4 }}>{title}</div>
      {/* File Upload Section */}
      <div style={{
        border: '2px dashed #ddd',
        borderRadius: 10,
        padding: 14,
        textAlign: 'center',
        background: '#fafafa',
        marginBottom: 6
      }}>
        <input
          ref={fileInputRef}
          type="file"
          multiple
          onChange={handleFileSelect}
          style={{ display: "none" }}
          accept=".pdf,.doc,.docx,.txt,.md,.csv,.png,.jpg,.jpeg,.xlsx,.xls,.ppt,.pptx,.gif"
        />
        <button
          onClick={() => fileInputRef.current?.click()}
          style={{
            padding: "6px 12px",
            background: "#1976d2",
            color: "#fff",
            border: "none",
            borderRadius: 5,
            cursor: "pointer",
            fontSize: 13,
            fontWeight: 500
          }}
          disabled={uploading}
        >
          Select Files
        </button>
        {files.length > 0 && (
          <div style={{ marginTop: 10 }}>
            <p style={{ fontSize: 13, color: "#666", marginBottom: 6 }}>Selected files:</p>
            <ul style={{ fontSize: 13, marginBottom: 10 }}>
              {files.map((file, index) => (
                <li key={index} style={{ color: "#333", marginBottom: 2 }}>
                  {file.name} ({(file.size / 1024 / 1024).toFixed(2)} MB)
                </li>
              ))}
            </ul>
            {/* Upload button removed for auto-upload */}
            {uploading && (
              <div style={{ marginTop: 6 }}>
                <div style={{
                  width: "100%",
                  background: "#e0e0e0",
                  borderRadius: 3,
                  height: 7,
                  overflow: "hidden"
                }}>
                  <div
                    style={{
                      background: "#1976d2",
                      height: "100%",
                      width: `${uploadProgress}%`,
                      transition: "width 0.3s ease"
                    }}
                  ></div>
                </div>
                <p style={{ fontSize: 11, color: "#666", marginTop: 2 }}>{uploadProgress.toFixed(1)}%</p>
              </div>
            )}
          </div>
        )}
      </div>
      {/* Error Display */}
      {error && (
        <div style={{
          background: "#ffebee",
          border: "1px solid #f44336",
          color: "#c62828",
          padding: "10px",
          borderRadius: 5,
          fontSize: 13,
          marginBottom: 6
        }}>
          {error}
        </div>
      )}
      {/* Resources List - Only show if showCheckoutControls is true */}
      {showCheckoutControls && (
        <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
          <div style={{ fontWeight: 600, fontSize: 15, marginBottom: 2 }}>Resources</div>
          {loading ? (
            <div style={{ textAlign: "center", padding: 10 }}>
              <p style={{ color: "#666" }}>Loading resources...</p>
            </div>
          ) : resources.length === 0 ? (
            <div style={{ textAlign: "center", padding: 10 }}>
              <p style={{ color: "#666" }}>No resources uploaded yet</p>
            </div>
          ) : (
            <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
              {resources.map((resource, index) => {
                // Default to checked_out if status is missing
                const isCheckedIn = resource.status === 'checked_in';
                return (
                  <div
                    key={resource.fileId || resource.fileName || index}
                    style={{
                      display: "flex",
                      alignItems: "center",
                      background: isCheckedIn ? "#f5f7fa" : "#fbe9e7",
                      borderRadius: 10,
                      boxShadow: "0 1px 3px #0001",
                      padding: '8px 12px',
                      opacity: isCheckedIn ? 1 : 0.7,
                      position: "relative",
                      minHeight: 44
                    }}
                  >
                    {/* Check in/out checkbox at the start */}
                    <div style={{ display: 'flex', alignItems: 'center', marginRight: 10, minWidth: 24 }}>
                      <input
                        type="checkbox"
                        checked={isCheckedIn}
                        onChange={async (e) => {
                          // Optimistic UI update
                          updateResource(courseId, resource.fileId, { status: e.target.checked ? 'checked_in' : 'checked_out' });
                          try {
                            if (e.target.checked) {
                              // No checkinResource call here
                            } else {
                              // No checkoutResource call here
                            }
                          } catch (err) {
                            // Revert UI if backend call failed
                            updateResource(courseId, resource.fileId, { status: !e.target.checked ? 'checked_in' : 'checked_out' });
                            alert('Failed to update file status: ' + (err.message || err));
                          }
                        }}
                        style={{ width: 18, height: 18, accentColor: isCheckedIn ? '#43a047' : '#fb8c00', cursor: 'pointer' }}
                        id={`checkinout-${resource.fileId}`}
                      />
                    </div>
                    {/* File icon */}
                    <span style={{ fontSize: 18, marginRight: 10 }}>{getFileIcon(resource)}</span>
                    {/* File info */}
                    <div style={{ flex: 1, minWidth: 0, display: 'flex', flexDirection: 'column', justifyContent: 'center' }}>
                      <div style={{ fontWeight: 600, fontSize: 13, color: isCheckedIn ? '#222' : '#b71c1c', marginBottom: 0, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                        {resource.fileName}
                      </div>
                      <div style={{ fontSize: 11, color: isCheckedIn ? '#388e3c' : '#b71c1c', fontWeight: 500, display: 'flex', alignItems: 'center', gap: 5 }}>
                        {isCheckedIn ? (
                          <>
                            <span style={{ fontSize: 13 }}>✔️</span> Available
                          </>
                        ) : (
                          <>
                            <span style={{ fontSize: 13 }}>❌</span> Checked Out
                          </>
                        )}
                      </div>
                    </div>
                    {/* 3-dots menu */}
                    <span style={{ cursor: "pointer", fontSize: 18 }} onClick={e => { e.stopPropagation(); handleMenuClick(resource, e); }}>⋮</span>
                    {showMenu && selectedResource === resource && (
                      <div style={{ position: 'absolute', right: 0, top: 28, background: '#fff', border: '1px solid #ddd', borderRadius: 8, boxShadow: '0 2px 8px #0002', zIndex: 10, minWidth: 120 }}>
                        <div style={{ padding: '10px 16px', cursor: 'pointer', borderBottom: '1px solid #eee' }} onClick={() => { alert('View: ' + (resource.fileName || resource.name)); handleMenuClose(); }}>View</div>
                        <div style={{ padding: '10px 16px', cursor: 'pointer', borderBottom: '1px solid #eee' }} onClick={() => { alert('Download: ' + (resource.fileName || resource.name)); handleMenuClose(); }}>Download</div>
                        <div style={{ padding: '10px 16px', cursor: 'pointer', color: '#d32f2f' }} onClick={async () => { if (resource.fileId && courseId) { await handleDelete(resource.fileId); } handleMenuClose(); }}>Delete</div>
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          )}
        </div>
      )}
    </div>
  );
};

export default FileUpload; 