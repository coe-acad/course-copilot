import React, { useState, useEffect, useMemo } from "react";
import Modal from "./Modal";
import { assetService } from "../services/asset";

export default function ActivitiesSelectionModal({
  open,
  onClose,
  selectedCourse,
  selectedModule,
  onActivitiesSelected
}) {
  const [loading, setLoading] = useState(false);
  const [exporting, setExporting] = useState(false);
  const [error, setError] = useState("");
  const [assets, setAssets] = useState([]);
  const [selected, setSelected] = useState({});
  const [search, setSearch] = useState("");

  useEffect(() => {
    if (!open) return;
    setError("");
    setSelected({});
    
    // Filter to only show activities and quizzes
    const activityTypes = ['quiz', 'question-paper', 'mock-interview', 'test'];
    
    const load = async () => {
      try {
        setLoading(true);
        const courseId = localStorage.getItem("currentCourseId");
        if (!courseId) {
          setAssets([]);
          return;
        }
        const data = await assetService.getAssets(courseId);
        const list = (data?.assets || []).map((a, idx) => ({
          id: `${a.asset_category || ""}|${a.asset_type || ""}|${a.asset_name || ""}|${a.asset_last_updated_at || idx}`,
          name: a.asset_name,
          type: a.asset_type,
          category: a.asset_category,
          updatedAt: a.asset_last_updated_at,
          updatedBy: a.asset_last_updated_by
        })).filter(asset => activityTypes.includes(asset.type));
        
        setAssets(list);
      } catch (e) {
        setError(e?.message || "Failed to load activities");
      } finally {
        setLoading(false);
      }
    };
    load();
  }, [open]);

  const filteredAssets = useMemo(() => {
    const q = search.trim().toLowerCase();
    if (!q) return assets;
    return assets.filter(a =>
      a.name.toLowerCase().includes(q) ||
      (a.type || "").toLowerCase().includes(q) ||
      (a.category || "").toLowerCase().includes(q)
    );
  }, [assets, search]);

  const grouped = useMemo(() => {
    const groups = {};
    filteredAssets.forEach(a => {
      const key = (a.category || "Other");
      if (!groups[key]) groups[key] = [];
      groups[key].push(a);
    });
    return groups;
  }, [filteredAssets]);

  const totalCount = filteredAssets.length;
  const selectedIds = Object.keys(selected).filter(k => selected[k]);
  const selectedCount = selectedIds.length;
  const allChecked = totalCount > 0 && selectedCount === totalCount;
  const someChecked = selectedCount > 0 && selectedCount < totalCount;

  const toggleAll = () => {
    if (allChecked) {
      setSelected({});
    } else {
      const next = {};
      filteredAssets.forEach(a => { next[a.id] = true; });
      setSelected(next);
    }
  };

  const toggleOne = (id) => {
    setSelected(prev => ({ ...prev, [id]: !prev[id] }));
  };

  const handleExport = async () => {
    try {
      setExporting(true);
      setError("");
      const chosen = assets.filter(a => selected[a.id]);
      
      if (chosen.length === 0) {
        setError("Please select at least one activity to export");
        return;
      }
      
      // Call the export API
      const courseId = localStorage.getItem("currentCourseId");
      if (courseId) {
        const assetNames = chosen.map(a => a.name);
        const assetTypes = [...new Set(chosen.map(a => a.type))];
        const token = localStorage.getItem("token");
        
        // ========================================
        // BACKEND INTEGRATION REQUIRED
        // ========================================
        // 
        // NEW ENDPOINT NEEDED: POST /api/courses/{course_id}/export-to-lms-module
        // 
        // REQUEST HEADERS:
        // - Authorization: Bearer <user_auth_token>
        // - Content-Type: application/json
        // 
        // REQUEST BODY:
        // {
        //   "asset_names": ["asset1", "asset2", ...],
        //   "asset_type": ["quiz", "question-paper", ...],
        //   "lms_course_id": "course_id",
        //   "lms_module_id": "module_id",
        //   "lms_cookies": "session=abc123; Path=/; HttpOnly"
        // }
        // 
        // EXPECTED SUCCESS RESPONSE (200):
        // {
        //   "success": true,
        //   "message": "Successfully exported activities to LMS module",
        //   "data": {
        //     "lms_module_id": "module_id",
        //     "lms_activity_ids": ["activity1", "activity2", ...],
        //     "exported_assets": [
        //       {
        //         "asset_name": "quiz1",
        //         "lms_activity_id": "lms_quiz_id",
        //         "status": "success"
        //       }
        //     ]
        //   }
        // }
        
        const response = await fetch(`${process.env.REACT_APP_API_BASE_URL || 'http://localhost:8000'}/api/courses/${courseId}/export-to-lms-module`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'Authorization': `Bearer ${token}`
          },
          body: JSON.stringify({ 
            asset_names: assetNames,
            asset_type: assetTypes,
            lms_course_id: selectedCourse?.id,
            lms_module_id: selectedModule?.id,
            lms_cookies: localStorage.getItem("lms_cookies")
          })
        });
        
        if (!response.ok) {
          const errorData = await response.json().catch(() => ({}));
          throw new Error(errorData.detail || 'Export failed');
        }
        
        const data = await response.json();
        console.log('Export data:', data);
        
        // Show success message
        alert(`Successfully exported ${chosen.length} activities to module "${selectedModule?.name}"`);
      }
      
      if (onActivitiesSelected) onActivitiesSelected(chosen);
      onClose?.();
    } catch (error) {
      console.error('Export error:', error);
      setError(error.message || 'Export failed');
    } finally {
      setExporting(false);
    }
  };

  if (!open) return null;

  return (
    <Modal open={open} onClose={onClose}>
      <div style={{ display: "flex", flexDirection: "column", gap: 16, position: "relative" }}>
        
        {/* Selected Course and Module Info */}
        <div style={{
          padding: '12px 16px',
          background: '#eff6ff',
          borderRadius: 8,
          border: '1px solid #2563eb',
          display: 'flex',
          alignItems: 'center',
          gap: 12
        }}>
          <div style={{
            width: 40,
            height: 40,
            borderRadius: '50%',
            background: '#2563eb',
            color: '#fff',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            fontSize: 18,
            fontWeight: 'bold',
            flexShrink: 0
          }}>
            📚
          </div>
          <div style={{ flex: 1 }}>
            <div style={{ fontSize: 14, fontWeight: 700, color: '#2563eb', marginBottom: 2 }}>
              Exporting to: {selectedCourse?.name} → {selectedModule?.name}
            </div>
            <div style={{ fontSize: 13, color: '#6b7280' }}>
              Select activities and quizzes to add to this module
            </div>
          </div>
        </div>
        
        {/* Loading Overlay */}
        {exporting && (
          <div style={{
            position: "absolute",
            top: 0,
            left: 0,
            right: 0,
            bottom: 0,
            background: "rgba(255, 255, 255, 0.95)",
            display: "flex",
            flexDirection: "column",
            alignItems: "center",
            justifyContent: "center",
            gap: 16,
            zIndex: 1000,
            borderRadius: 12
          }}>
            <div style={{
              width: 48,
              height: 48,
              border: "4px solid #e5e7eb",
              borderTop: "4px solid #2563eb",
              borderRadius: "50%",
              animation: "spin 1s linear infinite"
            }}></div>
            <div style={{
              fontSize: 16,
              fontWeight: 600,
              color: "#2563eb"
            }}>
              Adding activities to module, please wait...
            </div>
            <style>{`
              @keyframes spin {
                0% { transform: rotate(0deg); }
                100% { transform: rotate(360deg); }
              }
            `}</style>
          </div>
        )}
        
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
          <div style={{ fontWeight: 700, fontSize: 22 }}>Select Activities & Quizzes</div>
          <div style={{ color: "#6b7280", fontSize: 14 }}>
            {selectedCount} selected{totalCount ? ` / ${totalCount}` : ""}
          </div>
        </div>

        <div style={{ display: "flex", gap: 10, alignItems: "center" }}>
          <input
            value={search}
            onChange={e => setSearch(e.target.value)}
            placeholder="Search by name, type, or category"
            style={{ flex: 1, padding: "10px 12px", border: "1px solid #d1d5db", borderRadius: 8 }}
          />
          <label style={{ display: "flex", alignItems: "center", gap: 8, userSelect: "none", cursor: "pointer" }}>
            <input
              type="checkbox"
              checked={allChecked}
              ref={el => { if (el) el.indeterminate = someChecked; }}
              onChange={toggleAll}
            />
            <span style={{ fontWeight: 600 }}>Select all</span>
          </label>
        </div>

        {error && (
          <div style={{ color: "#b91c1c", background: "#fee2e2", padding: 10, borderRadius: 8 }}>{error}</div>
        )}

        <div style={{
          maxHeight: "50vh",
          overflowY: "auto",
          border: "1px solid #e5e7eb",
          borderRadius: 10,
          background: "#fafbfc",
          padding: 8
        }}>
          {loading ? (
            <div style={{ padding: 16 }}>Loading activities…</div>
          ) : (
            Object.keys(grouped).sort().map(group => (
              <div key={group} style={{ marginBottom: 10 }}>
                <div style={{
                  position: "sticky",
                  top: 0,
                  background: "#f5f8ff",
                  padding: "8px 10px",
                  borderRadius: 8,
                  fontWeight: 700,
                  color: "#2563eb",
                  border: "1px solid #e5e7eb"
                }}>{group.charAt(0).toUpperCase() + group.slice(1)}</div>
                <div style={{ display: "flex", flexDirection: "column", marginTop: 6 }}>
                  {grouped[group].map(item => (
                    <label key={item.id} style={{
                      display: "grid",
                      gridTemplateColumns: "24px 1fr auto",
                      alignItems: "center",
                      gap: 10,
                      padding: "8px 10px",
                      borderBottom: "1px solid #eef2f7",
                      background: selected[item.id] ? "#eef6ff" : "transparent",
                      cursor: "pointer",
                      borderRadius: 6
                    }}>
                      <input type="checkbox" checked={!!selected[item.id]} onChange={() => toggleOne(item.id)} />
                      <div style={{ display: "flex", flexDirection: "column" }}>
                        <span style={{ fontWeight: 600 }}>{item.name}</span>
                        <span style={{ fontSize: 12, color: "#6b7280" }}>{item.type}</span>
                      </div>
                      <div style={{ fontSize: 12, color: "#6b7280" }}>
                        {item.updatedAt ? new Date(item.updatedAt).toLocaleString() : ""}
                      </div>
                    </label>
                  ))}
                </div>
              </div>
            ))
          )}
          {!loading && totalCount === 0 && (
            <div style={{ padding: 16, color: "#6b7280" }}>No activities or quizzes found.</div>
          )}
        </div>

        <div style={{ display: "flex", justifyContent: "flex-end", gap: 12 }}>
          <button 
            onClick={onClose} 
            disabled={exporting}
            style={{ 
              padding: "10px 16px", 
              borderRadius: 8, 
              border: "1px solid #d1d5db", 
              background: "#fff",
              cursor: exporting ? "not-allowed" : "pointer",
              opacity: exporting ? 0.5 : 1
            }}
          >
            Cancel
          </button>
          <button
            onClick={handleExport}
            disabled={selectedCount === 0 || exporting}
            style={{
              padding: "10px 16px",
              borderRadius: 8,
              border: "none",
              background: (selectedCount === 0 || exporting) ? "#94a3b8" : "#2563eb",
              color: "#fff",
              fontWeight: 600,
              cursor: (selectedCount === 0 || exporting) ? "not-allowed" : "pointer"
            }}
          >
            {exporting ? "Adding to Module..." : `Add ${selectedCount > 0 ? `(${selectedCount})` : ""} to Module`}
          </button>
        </div>
      </div>
    </Modal>
  );
}
