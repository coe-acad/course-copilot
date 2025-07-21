import React, { useRef, useState, useEffect } from "react";
// import { useFilesContext } from "../context/FilesContext";
import { useResources } from "../context/ResourcesContext";

export default function Sidebar({ onAddContentClick }) {
  // const { files, addFiles } = useFilesContext();
  const { getAllResources, loadResources, removeResource, updateResource } = useResources();
  const fileInputRef = useRef();
  const [menuIndex, setMenuIndex] = useState(null);
  const [courseId, setCourseId] = useState(null);

  // Local state for checked-in and checked-out file names, persisted per course
  const [checkedInList, setCheckedInList] = useState(() => {
    const courseId = localStorage.getItem('currentCourseId');
    const saved = localStorage.getItem(`checkedInList_${courseId}`);
    return saved ? JSON.parse(saved) : [];
  });
  const [checkedOutList, setCheckedOutList] = useState(() => {
    const courseId = localStorage.getItem('currentCourseId');
    const saved = localStorage.getItem(`checkedOutList_${courseId}`);
    return saved ? JSON.parse(saved) : [];
  });

  // Persist checkedInList and checkedOutList in localStorage per courseId
  useEffect(() => {
    const courseId = localStorage.getItem('currentCourseId');
    if (courseId) {
      localStorage.setItem(`checkedInList_${courseId}`, JSON.stringify(checkedInList));
      localStorage.setItem(`checkedOutList_${courseId}`, JSON.stringify(checkedOutList));
    }
  }, [checkedInList, checkedOutList]);

  // Only update courseId when it changes
  useEffect(() => {
    const id = localStorage.getItem("currentCourseId");
    setCourseId(id);
  }, []);

  // Only call loadResources when courseId changes
  useEffect(() => {
    if (courseId) {
      loadResources(courseId);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [courseId, loadResources]);

  const resources = getAllResources(courseId) || [];

  // When resources change, ensure any new files are added to checkedOutList by default
  useEffect(() => {
    if (!resources || resources.length === 0) return;
    const allFileNames = resources.map(f => f.fileName || f.name);
    setCheckedOutList(prev => {
      // Add any new files to checkedOutList if not already in either list
      const newCheckedOut = allFileNames.filter(
        name => !prev.includes(name) && !checkedInList.includes(name)
      );
      if (newCheckedOut.length === 0) return prev;
      const updated = [...prev, ...newCheckedOut];
      // Print for debug
      console.log('Checked-out files (after add):', updated);
      return updated;
    });
  }, [resources, checkedInList]);

  // Remove handleFileChange and addFiles logic, as upload is handled elsewhere

  const handleAddContentClick = () => {
    if (onAddContentClick) {
      onAddContentClick();
    } else {
      fileInputRef.current && fileInputRef.current.click();
    }
  };

  const handleMenuClick = (idx) => {
    setMenuIndex(idx === menuIndex ? null : idx);
  };

  const handleMenuClose = () => {
    setMenuIndex(null);
  };

  // Adjust this value if your header/top row height changes
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
        Add resources from the web or course documents you’ve already created — this helps AI give relevant results.
        </div>
        <input
          type="file"
          ref={fileInputRef}
          style={{ display: "none" }}
          multiple
          // onChange={handleFileChange} // Remove, handled in modal
        />
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
          onClick={handleAddContentClick}
        >
          Add Resource
        </button>
        <ul style={{ listStyle: "none", padding: 0, margin: 0 }}>
          {resources.map((file, i) => {
            // Use local state for checked-in/checked-out
            const fileName = file.fileName || file.name;
            const isCheckedIn = checkedInList.includes(fileName);
            return (
              <li key={file.fileId || file.fileName || i} style={{ position: 'relative', display: "flex", alignItems: "center", justifyContent: "space-between", padding: "7px 0", borderBottom: i < resources.length - 1 ? "1px solid #f0f0f0" : "none" }}>
                <label style={{ display: "flex", alignItems: "center", gap: 8, fontSize: 15, flex: 1 }}>
                  <input
                    type="checkbox"
                    checked={isCheckedIn}
                    onChange={async (e) => {
                      // Toggle checked-in/checked-out lists
                      if (e.target.checked) {
                        setCheckedInList(prev => {
                          const updated = [...prev, fileName].filter((v, i, a) => a.indexOf(v) === i);
                          setTimeout(() => {
                            console.log('Checked-in files:', updated);
                            console.log('Checked-out files:', checkedOutList.filter(name => name !== fileName));
                          }, 0);
                          return updated;
                        });
                        setCheckedOutList(prev => {
                          const updated = prev.filter(name => name !== fileName);
                          return updated;
                        });
                      } else {
                        setCheckedOutList(prev => {
                          const updated = [...prev, fileName].filter((v, i, a) => a.indexOf(v) === i);
                          setTimeout(() => {
                            console.log('Checked-in files:', checkedInList.filter(name => name !== fileName));
                            console.log('Checked-out files:', updated);
                          }, 0);
                          return updated;
                        });
                        setCheckedInList(prev => {
                          const updated = prev.filter(name => name !== fileName);
                          return updated;
                        });
                      }
                    }}
                    style={{ width: 18, height: 18, accentColor: isCheckedIn ? '#43a047' : '#fb8c00', cursor: 'pointer' }}
                    id={`checkinout-${file.fileId}`}
                  />
                  {getFileIcon(file)} {file.fileName || file.name}
                </label>
                <span style={{ cursor: "pointer", fontSize: 18 }} onClick={e => { e.stopPropagation(); handleMenuClick(i); }}>⋮</span>
                {menuIndex === i && (
                  <div style={{ position: 'absolute', right: 0, top: 28, background: '#fff', border: '1px solid #ddd', borderRadius: 8, boxShadow: '0 2px 8px #0002', zIndex: 10, minWidth: 120 }}>
                    <div style={{ padding: '10px 16px', cursor: 'pointer', borderBottom: '1px solid #eee' }} onClick={() => { alert('View: ' + (file.fileName || file.name)); handleMenuClose(); }}>View</div>
                    <div style={{ padding: '10px 16px', cursor: 'pointer', borderBottom: '1px solid #eee' }} onClick={() => { alert('Download: ' + (file.fileName || file.name)); handleMenuClose(); }}>Download</div>
                    <div style={{ padding: '10px 16px', cursor: 'pointer', color: '#d32f2f' }} onClick={async () => { if (file.fileId && courseId) { await removeResource(courseId, file.fileId); await loadResources(courseId); } handleMenuClose(); }}>Delete</div>
                  </div>
                )}
              </li>
            );
          })}
        </ul>
        {/* Display checked-in and checked-out lists */}
        <div style={{ marginTop: 16, fontSize: 14 }}>
          <div><b>Checked-in files:</b> {checkedInList.length > 0 ? checkedInList.join(', ') : <span style={{ color: '#888' }}>None</span>}</div>
          <div><b>Checked-out files:</b> {checkedOutList.length > 0 ? checkedOutList.join(', ') : <span style={{ color: '#888' }}>None</span>}</div>
        </div>
        {menuIndex !== null && <div onClick={handleMenuClose} style={{ position: 'fixed', left: 0, top: 0, width: '100vw', height: '100vh', zIndex: 5 }} />}
      </div>
    </div>
  );
}

function getFileIcon(file) {
  if (file.type && file.type.startsWith("image/")) return "🖼️";
  if (file.type === "application/pdf") return "📄";
  if ((file.fileName || file.name || "").endsWith(".doc") || (file.fileName || file.name || "").endsWith(".docx")) return "📄";
  if ((file.fileName || file.name || "").endsWith(".ppt") || (file.fileName || file.name || "").endsWith(".pptx")) return "📊";
  if ((file.fileName || file.name || "").endsWith(".xls") || (file.fileName || file.name || "").endsWith(".xlsx")) return "📊";
  if ((file.fileName || file.name || "").endsWith(".txt")) return "📄";
  if ((file.fileName || file.name || "").endsWith(".zip") || (file.fileName || file.name || "").endsWith(".rar")) return "🗜️";
  if ((file.fileName || file.name || "").endsWith(".csv")) return "📑";
  if ((file.fileName || file.name || "").endsWith(".mp4") || (file.fileName || file.name || "").endsWith(".mov")) return "🎞️";
  if ((file.fileName || file.name || "").endsWith(".mp3") || (file.fileName || file.name || "").endsWith(".wav")) return "🎵";
  if ((file.fileName || file.name || "").endsWith(".html") || (file.fileName || file.name || "").endsWith(".htm")) return "🌐";
  if ((file.fileName || file.name || "").endsWith(".json")) return "🗂️";
  if ((file.fileName || file.name || "").endsWith(".js")) return "📜";
  if ((file.fileName || file.name || "").endsWith(".py")) return "🐍";
  if ((file.fileName || file.name || "").endsWith(".java")) return "☕";
  if ((file.fileName || file.name || "").endsWith(".c") || (file.fileName || file.name || "").endsWith(".cpp")) return "💻";
  if ((file.fileName || file.name || "").endsWith(".md")) return "📝";
  if ((file.fileName || file.name || "").endsWith(".svg")) return "🖼️";
  if ((file.fileName || file.name || "").endsWith(".xml")) return "🗂️";
  if ((file.fileName || file.name || "").endsWith(".yml") || (file.fileName || file.name || "").endsWith(".yaml")) return "🗂️";
  return "📁";
} 