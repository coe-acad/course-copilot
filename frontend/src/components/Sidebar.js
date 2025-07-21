import React, { useState, useImperativeHandle, forwardRef } from "react";
import { getCourseResources, deleteResource } from "../services/resources";

const Sidebar = forwardRef(function Sidebar({ onAddContentClick }, ref) {
  const [resources, setResources] = useState([]);
  const [resourceLoading, setResourceLoading] = useState(false);
  const [resourceError, setResourceError] = useState("");
  const [menuIndex, setMenuIndex] = useState(null);
  const courseId = localStorage.getItem("currentCourseId");

  const fetchResources = React.useCallback(() => {
    if (!courseId) return;
    console.log("Fetching resources for courseId:", courseId);
    setResourceLoading(true);
    setResourceError("");
    getCourseResources(courseId)
      .then(data => {
        console.log("Fetched resources:", data);
        setResources(data.resources || []);
      })
      .catch((error) => {
        console.error("Failed to fetch resources:", error);
        setResourceError("Failed to fetch resources: " + (error.message || error));
      })
      .finally(() => setResourceLoading(false));
  }, [courseId]);

  React.useEffect(() => {
    fetchResources();
  }, [fetchResources]);

  // Expose refresh function to parent components
  useImperativeHandle(ref, () => ({
    refreshResources: () => {
      console.log("refreshResources called from parent");
      fetchResources();
    }
  }));

  const handleMenuClick = (idx) => {
    setMenuIndex(idx === menuIndex ? null : idx);
  };

  const handleMenuClose = () => {
    setMenuIndex(null);
  };

  const handleDelete = async (fileId) => {
    if (!window.confirm('Are you sure you want to delete this file?')) return;
    if (!courseId) return;
    setResourceLoading(true);
    setResourceError("");
    try {
      await deleteResource(courseId, fileId);
      fetchResources(); // Refresh the list after deletion
      handleMenuClose();
    } catch (err) {
      console.error("Delete error:", err);
      setResourceError("Failed to delete file: " + (err.message || err));
    } finally {
      setResourceLoading(false);
    }
  };

  // Add this function to handle programmatic download
  const handleDownload = async (file) => {
    try {
      // Try to fetch the file as a blob and trigger download
      const response = await fetch(file.url, { credentials: 'include' });
      if (!response.ok) throw new Error('Network response was not ok');
      const blob = await response.blob();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = file.fileName || file.title || 'download';
      document.body.appendChild(a);
      a.click();
      setTimeout(() => {
        window.URL.revokeObjectURL(url);
        document.body.removeChild(a);
      }, 100);
    } catch (err) {
      // Fallback: open in new tab if download fails
      window.open(file.url, '_blank');
    }
    handleMenuClose();
  };

  const sidebarBoxHeight = '60vh';

  return (
    <div>
      <div style={{
        background: "#fff",
        borderRadius: 16,
        border: "1px solid #e5e7eb",
        boxShadow: "none",
        padding: 24,
        height: sidebarBoxHeight,
        maxHeight: sidebarBoxHeight,
        display: "flex",
        flexDirection: "column",
        gap: 0
      }}>
        <div style={{ fontWeight: 700, fontSize: 22, marginBottom: 2, color: "#1a2533" }}>Knowledge Base</div>
        <div style={{ color: "#6b7280", fontSize: 14, marginBottom: 18, fontWeight: 500 }}>
        Add resources from the web or course documents you've already created — this helps AI give relevant results.
        </div>
        <button
          style={{
            padding: "12px 0",
            borderRadius: 8,
            border: "1px solid #bbb",
            background: "#fff",
            cursor: "pointer",
            fontSize: 16,
            fontWeight: 600,
            marginBottom: 18,
            width: "100%"
          }}
          onClick={onAddContentClick}
        >
          Add Resource
        </button>
        <div style={{ flex: 1, minHeight: 0, overflowY: "auto" }}>
          <ul style={{ listStyle: "none", padding: 0, margin: 0 }}>
            {resourceLoading ? (
              <li style={{ padding: "10px 0", color: "#666", textAlign: "center" }}>Loading resources...</li>
            ) : resourceError ? (
              <li style={{ color: 'red', padding: "10px 0", fontSize: 14 }}>{resourceError}</li>
            ) : resources.length === 0 ? (
              <li style={{ color: '#888', padding: "10px 0", textAlign: "center", fontSize: 14 }}>No resources uploaded yet.</li>
            ) : (
              resources.map((file, i) => (
                <li key={file.fileId || i} style={{ position: 'relative', display: "flex", alignItems: "center", justifyContent: "space-between", padding: "7px 0", borderBottom: i < resources.length - 1 ? "1px solid #f0f0f0" : "none" }}>
                  <span style={{ fontSize: 15 }}>{getFileIcon(file)} {file.fileName || file.title}</span>
                  <span style={{ cursor: "pointer", fontSize: 18 }} onClick={e => { e.stopPropagation(); handleMenuClick(i); }}>⋮</span>
                  {menuIndex === i && (
                    <div style={{ position: 'absolute', right: 0, top: 28, background: '#fff', border: '1px solid #ddd', borderRadius: 8, boxShadow: '0 2px 8px #0002', zIndex: 10, minWidth: 120 }}>
                      <div style={{ padding: '10px 16px', cursor: 'pointer', borderBottom: '1px solid #eee' }} onClick={() => { window.open(file.url, '_blank'); handleMenuClose(); }}>View</div>
                      <div style={{ padding: '10px 16px', cursor: 'pointer', borderBottom: '1px solid #eee' }} onClick={() => handleDownload(file)}>Download</div>
                      <div style={{ padding: '10px 16px', cursor: 'pointer', color: '#d32f2f' }} onClick={() => handleDelete(file.fileId)}>Delete</div>
                    </div>
                  )}
                </li>
              ))
            )}
          </ul>
          {menuIndex !== null && <div onClick={handleMenuClose} style={{ position: 'fixed', left: 0, top: 0, width: '100vw', height: '100vh', zIndex: 5 }} />}
        </div>
      </div>
    </div>
  );
});

function getFileIcon(file) {
  if (file.type && file.type.startsWith("image/")) return "🖼️";
  if (file.type === "application/pdf") return "📄";
  if (file.fileName && (file.fileName.endsWith(".doc") || file.fileName.endsWith(".docx"))) return "📄";
  if (file.fileName && (file.fileName.endsWith(".ppt") || file.fileName.endsWith(".pptx"))) return "📊";
  if (file.fileName && (file.fileName.endsWith(".xls") || file.fileName.endsWith(".xlsx"))) return "📊";
  if (file.fileName && file.fileName.endsWith(".txt")) return "📄";
  if (file.fileName && (file.fileName.endsWith(".zip") || file.fileName.endsWith(".rar"))) return "🗜️";
  if (file.fileName && file.fileName.endsWith(".csv")) return "📑";
  if (file.fileName && (file.fileName.endsWith(".mp4") || file.fileName.endsWith(".mov"))) return "🎞️";
  if (file.fileName && (file.fileName.endsWith(".mp3") || file.fileName.endsWith(".wav"))) return "🎵";
  if (file.fileName && (file.fileName.endsWith(".html") || file.fileName.endsWith(".htm"))) return "🌐";
  if (file.fileName && file.fileName.endsWith(".json")) return "🗂️";
  if (file.fileName && file.fileName.endsWith(".js")) return "📜";
  if (file.fileName && file.fileName.endsWith(".py")) return "🐍";
  if (file.fileName && file.fileName.endsWith(".java")) return "☕";
  if (file.fileName && (file.fileName.endsWith(".c") || file.fileName.endsWith(".cpp"))) return "💻";
  if (file.fileName && file.fileName.endsWith(".md")) return "📝";
  if (file.fileName && file.fileName.endsWith(".svg")) return "🖼️";
  if (file.fileName && file.fileName.endsWith(".xml")) return "🗂️";
  if (file.fileName && (file.fileName.endsWith(".yml") || file.fileName.endsWith(".yaml"))) return "🗂️";
  return "📁";
}

export default Sidebar; 