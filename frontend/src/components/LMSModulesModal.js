import React, { useState, useEffect } from "react";
import Modal from "./Modal";

export default function LMSModulesModal({
  open,
  onClose,
  selectedCourse,
  onModuleSelected
}) {
  const [modules, setModules] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [isGridView, setIsGridView] = useState(true);
  const [searchQuery, setSearchQuery] = useState("");
  const [selectedModuleId, setSelectedModuleId] = useState(null);

  useEffect(() => {
    if (open && selectedCourse) {
      fetchLMSModules();
      setSelectedModuleId(null);
    }
  }, [open, selectedCourse]);

  const fetchLMSModules = async () => {
    try {
      setLoading(true);
      setError("");
      
      const token = localStorage.getItem("token");
      const lmsCookies = localStorage.getItem("lms_cookies");

      if (!lmsCookies) {
        throw new Error("LMS cookies not found. Please login to LMS first.");
      }

      // ========================================
      // LMS MODULES FETCH - NEW ENDPOINT NEEDED
      // ========================================
      // 
      // ENDPOINT: POST /api/courses-lms/{course_id}/modules
      // 
      // REQUEST HEADERS:
      // - Authorization: Bearer <user_auth_token>
      // - Content-Type: application/json
      // 
      // REQUEST BODY:
      // {
      //   "lms_cookies": "session=abc123; Path=/; HttpOnly"
      // }
      // 
      // EXPECTED SUCCESS RESPONSE (200):
      // {
      //   "message": "Successfully fetched modules from LMS course",
      //   "data": [
      //     {
      //       "id": "module_id_123",
      //       "name": "Introduction to Machine Learning",
      //       "description": "Module description here...",
      //       "position": 1,
      //       "visible": true,
      //       "completion_tracking": true,
      //       "created_at": "2024-01-01T00:00:00Z",
      //       "updated_at": "2024-01-10T00:00:00Z"
      //     }
      //   ]
      // }
      
      const response = await fetch(
        `${process.env.REACT_APP_API_BASE_URL || 'http://localhost:8000'}/api/courses-lms/${selectedCourse.id}/modules`,
        {
          method: 'POST',
          headers: {
            'Authorization': `Bearer ${token}`,
            'Content-Type': 'application/json'
          },
          body: JSON.stringify({
            lms_cookies: lmsCookies
          })
        }
      );

      if (!response.ok) {
        if (response.status === 401) {
          throw new Error("LMS session expired. Please login again.");
        }
        const errorData = await response.json().catch(() => ({}));
        throw new Error(errorData.detail || 'Failed to fetch modules');
      }

      const data = await response.json();
      const normalized = Array.isArray(data) ? data : (data.data || data.modules || data.results || []);
      console.log('LMS Modules fetched:', normalized);
      setModules(normalized);
      
    } catch (err) {
      console.error('Error fetching LMS modules:', err);
      setError(err.message || 'Failed to load modules from LMS');
    } finally {
      setLoading(false);
    }
  };

  const handleModuleSelect = (moduleId) => {
    console.log('Module selected:', moduleId);
    setSelectedModuleId(moduleId);
  };

  const handleProceedWithActivities = () => {
    if (!selectedModuleId) return;
    
    const selectedModule = modules.find(m => m.id === selectedModuleId);
    onModuleSelected(selectedModule);
  };

  // Filter modules based on search query
  const filteredModules = modules.filter(module => 
    module.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
    (module.description || "").toLowerCase().includes(searchQuery.toLowerCase())
  );

  if (!open) return null;

  return (
    <Modal open={open} onClose={onClose}>
      <div style={{ display: "flex", flexDirection: "column", gap: 16, position: "relative", minHeight: 400 }}>
        
        {/* Header */}
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
          <div style={{ fontWeight: 700, fontSize: 22 }}>Select Module</div>
          {!loading && !error && (
            <div style={{ display: "flex", gap: 8 }}>
              <button
                onClick={() => setIsGridView(true)}
                style={{
                  padding: "6px 12px",
                  borderRadius: 6,
                  border: "1px solid #d1d5db",
                  background: isGridView ? "#2563eb" : "#fff",
                  color: isGridView ? "#fff" : "#222",
                  cursor: "pointer",
                  fontSize: 16
                }}
              >
                ▦
              </button>
              <button
                onClick={() => setIsGridView(false)}
                style={{
                  padding: "6px 12px",
                  borderRadius: 6,
                  border: "1px solid #d1d5db",
                  background: !isGridView ? "#2563eb" : "#fff",
                  color: !isGridView ? "#fff" : "#222",
                  cursor: "pointer",
                  fontSize: 16
                }}
              >
                ≡
              </button>
            </div>
          )}
        </div>

        {/* Course Info */}
        {selectedCourse && (
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
                Course: {selectedCourse.name}
              </div>
              <div style={{ fontSize: 13, color: '#6b7280' }}>
                {selectedCourse.code && `Code: ${selectedCourse.code}`}
              </div>
            </div>
          </div>
        )}

        <p style={{ margin: 0, color: "#6b7280", fontSize: 14 }}>
          Choose a module to add activities and quizzes to
        </p>

        {/* Search Bar */}
        {!loading && !error && modules.length > 0 && (
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="Search by module name or description..."
            style={{
              width: '100%',
              padding: '10px 12px',
              borderRadius: 8,
              border: '1px solid #d1d5db',
              fontSize: 14,
              boxSizing: 'border-box'
            }}
          />
        )}

        {/* Loading State */}
        {loading && (
          <div style={{ 
            textAlign: 'center',
            padding: '60px 20px'
          }}>
            <div style={{
              width: 48,
              height: 48,
              border: "4px solid #e5e7eb",
              borderTop: "4px solid #2563eb",
              borderRadius: "50%",
              animation: "spin 1s linear infinite",
              margin: '0 auto 16px auto'
            }}></div>
            <div style={{
              fontSize: 15,
              fontWeight: 600,
              color: "#2563eb"
            }}>
              Loading modules from LMS...
            </div>
            <style>{`
              @keyframes spin {
                0% { transform: rotate(0deg); }
                100% { transform: rotate(360deg); }
              }
            `}</style>
          </div>
        )}

        {/* Error State */}
        {error && !loading && (
          <div style={{ 
            padding: '16px',
            background: '#fee2e2',
            borderRadius: 8,
            border: '1px solid #fecaca',
            textAlign: 'center'
          }}>
            <div style={{ fontSize: 16, fontWeight: 600, color: '#b91c1c', marginBottom: 8 }}>
              ❌ Error Loading Modules
            </div>
            <div style={{ fontSize: 14, color: '#991b1b', marginBottom: 12 }}>
              {error}
            </div>
            <button
              onClick={fetchLMSModules}
              style={{
                padding: "8px 16px",
                borderRadius: 6,
                border: "none",
                background: "#b91c1c",
                color: "#fff",
                fontWeight: 600,
                fontSize: 14,
                cursor: "pointer"
              }}
            >
              Try Again
            </button>
          </div>
        )}

        {/* Modules List */}
        {!loading && !error && (
          <div style={{
            maxHeight: '400px',
            overflowY: 'auto',
            border: '1px solid #e5e7eb',
            borderRadius: 10,
            background: '#fafbfc',
            padding: 8
          }}>
            {filteredModules.length === 0 ? (
              <div style={{ 
                padding: '40px 20px',
                textAlign: 'center',
                color: '#6b7280',
                fontSize: 14
              }}>
                {searchQuery ? `No modules found matching "${searchQuery}"` : "No modules available"}
              </div>
            ) : isGridView ? (
              /* Grid View */
              <div style={{ display: 'grid', gap: 12 }}>
                {filteredModules.map(module => (
                  <div
                    key={module.id}
                    onClick={() => handleModuleSelect(module.id)}
                    style={{
                      background: '#fff',
                      borderRadius: 10,
                      padding: 16,
                      border: selectedModuleId === module.id ? '3px solid #2563eb' : '1px solid #e5e7eb',
                      cursor: 'pointer',
                      position: 'relative',
                      transition: 'all 0.2s'
                    }}
                    onMouseEnter={(e) => {
                      if (selectedModuleId !== module.id) {
                        e.currentTarget.style.borderColor = '#cbd5e1';
                      }
                    }}
                    onMouseLeave={(e) => {
                      if (selectedModuleId !== module.id) {
                        e.currentTarget.style.borderColor = '#e5e7eb';
                      }
                    }}
                  >
                    {/* Selection indicator */}
                    {selectedModuleId === module.id && (
                      <div style={{
                        position: 'absolute',
                        top: 12,
                        right: 12,
                        width: 28,
                        height: 28,
                        borderRadius: '50%',
                        background: '#2563eb',
                        color: '#fff',
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        fontSize: 16,
                        fontWeight: 'bold'
                      }}>
                        ✓
                      </div>
                    )}

                    {/* Module Header */}
                    <div style={{ display: 'flex', alignItems: 'flex-start', gap: 10, marginBottom: 8 }}>
                      <div style={{ flex: 1 }}>
                        <h3 style={{ 
                          fontSize: 16, 
                          fontWeight: 700, 
                          color: '#2563eb',
                          margin: '0 0 4px 0'
                        }}>
                          {module.name}
                        </h3>
                        {module.position && (
                          <div style={{ fontSize: 12, color: '#6b7280', fontWeight: 600 }}>
                            Position: {module.position}
                          </div>
                        )}
                      </div>
                      {module.visible !== undefined && (
                        <span style={{
                          padding: '4px 10px',
                          borderRadius: 10,
                          fontSize: 11,
                          fontWeight: 600,
                          textTransform: 'uppercase',
                          background: module.visible ? '#dcfce7' : '#f3f4f6',
                          color: module.visible ? '#16a34a' : '#6b7280'
                        }}>
                          {module.visible ? 'visible' : 'hidden'}
                        </span>
                      )}
                    </div>

                    {/* Module Description */}
                    {module.description && (
                      <div style={{ fontSize: 13, color: '#374151', lineHeight: 1.4 }}>
                        {module.description}
                      </div>
                    )}
                  </div>
                ))}
              </div>
            ) : (
              /* List View */
              <table style={{ width: '100%', borderCollapse: 'collapse' }}>
                <thead>
                  <tr style={{ background: '#f5f8ff', borderBottom: '1px solid #e5e7eb' }}>
                    <th style={{ padding: '10px 12px', textAlign: 'center', fontSize: 13, fontWeight: 700, color: '#2563eb', width: 50 }}>
                      Select
                    </th>
                    <th style={{ padding: '10px 12px', textAlign: 'left', fontSize: 13, fontWeight: 700, color: '#2563eb' }}>
                      Module
                    </th>
                    <th style={{ padding: '10px 12px', textAlign: 'center', fontSize: 13, fontWeight: 700, color: '#2563eb' }}>
                      Position
                    </th>
                    <th style={{ padding: '10px 12px', textAlign: 'center', fontSize: 13, fontWeight: 700, color: '#2563eb' }}>
                      Status
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {filteredModules.map((module, index) => (
                    <tr 
                      key={module.id}
                      onClick={() => handleModuleSelect(module.id)}
                      style={{ 
                        borderBottom: index < filteredModules.length - 1 ? '1px solid #f3f4f6' : 'none',
                        cursor: 'pointer',
                        background: selectedModuleId === module.id ? '#eff6ff' : 'transparent'
                      }}
                    >
                      <td style={{ padding: '12px', textAlign: 'center' }}>
                        <input
                          type="radio"
                          checked={selectedModuleId === module.id}
                          onChange={() => handleModuleSelect(module.id)}
                          style={{ width: 18, height: 18, cursor: 'pointer' }}
                        />
                      </td>
                      <td style={{ padding: '12px', fontSize: 14, fontWeight: 600, color: '#2563eb' }}>
                        {module.name}
                      </td>
                      <td style={{ padding: '12px', fontSize: 13, color: '#6b7280', textAlign: 'center' }}>
                        {module.position || '-'}
                      </td>
                      <td style={{ padding: '12px', textAlign: 'center' }}>
                        <span style={{
                          padding: '4px 10px',
                          borderRadius: 10,
                          fontSize: 11,
                          fontWeight: 600,
                          textTransform: 'uppercase',
                          background: module.visible ? '#dcfce7' : '#f3f4f6',
                          color: module.visible ? '#16a34a' : '#6b7280'
                        }}>
                          {module.visible ? 'visible' : 'hidden'}
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        )}

        {/* Action Buttons */}
        {!loading && !error && (
          <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 12, marginTop: 8 }}>
            <button
              onClick={onClose}
              style={{
                padding: "10px 20px",
                borderRadius: 8,
                border: "1px solid #d1d5db",
                background: "#fff",
                color: "#374151",
                fontWeight: 600,
                fontSize: 15,
                cursor: "pointer"
              }}
            >
              Cancel
            </button>
            <button
              onClick={handleProceedWithActivities}
              disabled={!selectedModuleId}
              style={{
                padding: "10px 24px",
                borderRadius: 8,
                border: "none",
                background: selectedModuleId ? "#2563eb" : "#94a3b8",
                color: "#fff",
                fontWeight: 600,
                fontSize: 15,
                cursor: selectedModuleId ? "pointer" : "not-allowed",
                display: 'flex',
                alignItems: 'center',
                gap: 8
              }}
            >
              Select Activities
              <span style={{ fontSize: 16 }}>→</span>
            </button>
          </div>
        )}
      </div>
    </Modal>
  );
}
