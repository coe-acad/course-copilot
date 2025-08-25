import React, { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import Header from "../components/header/Header";
import SettingsModal from "../components/SettingsModal";
import { evaluationService } from "../services/evaluation";
import { getCurrentUser } from "../services/auth";

export default function Evaluation() {
  const navigate = useNavigate();
  const [isGridView, setIsGridView] = useState(true);
  const [showSettingsModal, setShowSettingsModal] = useState(false);
  const [evaluationSchemes, setEvaluationSchemes] = useState([]);
  const [selectedScheme, setSelectedScheme] = useState(null);
  const [searchQuery, setSearchQuery] = useState("");
  const [answerSheetFiles, setAnswerSheetFiles] = useState([]);
  const [isUploadingMarkScheme, setIsUploadingMarkScheme] = useState(false);
  const [isUploadingAnswerSheets, setIsUploadingAnswerSheets] = useState(false);
  const [isEvaluating, setIsEvaluating] = useState(false);
  const [hasUploaded, setHasUploaded] = useState(false);
  const [evaluationId, setEvaluationId] = useState(null);
  const [evaluationResult, setEvaluationResult] = useState(null);
  const [selectedStudent, setSelectedStudent] = useState(null);
  const [showUploadSchemeModal, setShowUploadSchemeModal] = useState(false);
  const [newSchemeName, setNewSchemeName] = useState("");
  const [newSchemeDescription, setNewSchemeDescription] = useState("");
  const [newSchemeFile, setNewSchemeFile] = useState(null);
  const [isUploadingScheme, setIsUploadingScheme] = useState(false);

  const courseId = localStorage.getItem('currentCourseId');
  const courseTitle = localStorage.getItem("currentCourseTitle") || "Course";

  useEffect(() => {
    if (courseId) {
      loadEvaluationSchemes();
    }
  }, [courseId]);

  const loadEvaluationSchemes = async () => {
    try {
      const schemes = await evaluationService.getEvaluationSchemes(courseId);
      setEvaluationSchemes(schemes);
    } catch (error) {
      console.error('Failed to load evaluation schemes:', error);
    }
  };

  const handleLogout = () => {
    localStorage.removeItem("token");
    navigate("/login");
  };

  const handleUploadScheme = async () => {
    if (!newSchemeName || !newSchemeDescription || !newSchemeFile) {
      alert("Please fill in all fields and select a file.");
      return;
    }

    try {
      setIsUploadingScheme(true);
      await evaluationService.uploadEvaluationScheme({
        courseId,
        schemeName: newSchemeName,
        schemeDescription: newSchemeDescription,
        markSchemeFile: newSchemeFile
      });
      
      alert("Evaluation scheme uploaded successfully!");
      setShowUploadSchemeModal(false);
      setNewSchemeName("");
      setNewSchemeDescription("");
      setNewSchemeFile(null);
      loadEvaluationSchemes(); // Reload the list
    } catch (error) {
      alert(error.message || "Failed to upload evaluation scheme");
    } finally {
      setIsUploadingScheme(false);
    }
  };

  const handleUploadAnswerSheets = async () => {
    if (!selectedScheme) {
      alert("Please select an evaluation scheme first.");
      return;
    }
    if (!answerSheetFiles || answerSheetFiles.length === 0) {
      alert("Please select at least one answer sheet.");
      return;
    }

    try {
      setIsUploading(true);
      const user = getCurrentUser();
      
      if (!user?.id) {
        alert('User not found. Please log in again.');
        return;
      }

      const res = await evaluationService.uploadMarkScheme({
        courseId,
        schemeId: selectedScheme.scheme_id,
        answerSheetFiles
      });
      
      setEvaluationId(res?.evaluation_id);
      setHasUploaded(true);
      alert(`Answer sheets uploaded successfully! Evaluation ID: ${res?.evaluation_id}`);
    } catch (err) {
      console.error('Upload error:', err);
      alert(err?.message || 'Upload failed');
    } finally {
      setIsUploadingAnswerSheets(false);
    }
  };

  const handleEvaluate = async () => {
    if (!hasUploaded || !evaluationId) {
      alert('Please upload answer sheets first.');
      return;
    }
    try {
      setIsEvaluating(true);
      alert('Starting AI evaluation... This may take several minutes.');
      
      const result = await evaluationService.evaluateFiles(evaluationId);
      setEvaluationResult(result);
      alert(`Evaluation completed successfully!\n\nStudents evaluated: ${result?.evaluation_result?.students?.length || 0}`);
      
    } catch (err) {
      console.error('Evaluation error:', err);
      alert(err?.message || 'Evaluation failed');
    } finally {
      setIsEvaluating(false);
    }
  };

  const getScoreColor = (score, maxScore) => {
    const percentage = (score / maxScore) * 100;
    if (percentage >= 80) return '#28a745';
    if (percentage >= 60) return '#ffc107';
    return '#dc3545';
  };

  const formatScore = (score, maxScore) => {
    const percentage = Math.round((score / maxScore) * 100);
    return `${score}/${maxScore} (${percentage}%)`;
  };

  const filteredSchemes = evaluationSchemes.filter(scheme =>
    scheme.scheme_name.toLowerCase().includes(searchQuery.toLowerCase()) ||
    scheme.scheme_description.toLowerCase().includes(searchQuery.toLowerCase())
  );

  return (
    <div style={{ height: '100vh', display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
      <Header
        title="Evaluation"
        onLogout={handleLogout}
        onSettings={() => setShowSettingsModal(true)}
        onExport={() => alert("Export to LMS coming soon!")}
        onGridView={() => setIsGridView(true)}
        onListView={() => setIsGridView(false)}
        isGridView={isGridView}
      />

      {/* Breadcrumb */}
      <div style={{ maxWidth: 1200, margin: "1rem auto 0.5rem auto", width: '100%', display: 'flex', alignItems: 'center', gap: 10, fontSize: 18, fontWeight: 500 }}>
        <span style={{ color: '#2563eb', cursor: 'pointer', fontWeight: 600 }} onClick={() => navigate('/courses')}>Courses</span>
        <span style={{ color: '#888' }}>{'>'}</span>
        <span style={{ color: '#2563eb', cursor: 'pointer', fontWeight: 600 }} onClick={() => navigate('/dashboard')}>{courseTitle}</span>
        <span style={{ color: '#888' }}>{'>'}</span>
        <span style={{ fontWeight: 700 }}>Evaluation</span>
      </div>

      <div style={{ flex: 1, display: 'flex', gap: 24, padding: '0 5vw', overflow: 'hidden' }}>
        {/* Left Section: Evaluation Schemes */}
        <div style={{ flex: 1, maxWidth: 500, overflowY: 'auto', padding: '24px 0' }}>
          <div style={{ background: '#fff', borderRadius: 18, padding: '32px', boxShadow: '0 2px 7px #0002' }}>
            <h2 style={{ margin: 0, fontSize: 24, fontWeight: 600, color: '#1e40af' }}>Evaluation Scheme</h2>
            <p style={{ marginTop: 8, color: '#444', marginBottom: 20 }}>Select Evaluation Scheme or Upload</p>
            
            {/* Search Bar */}
            <div style={{ marginBottom: 20 }}>
              <input
                type="text"
                placeholder="Search evaluation scheme"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                style={{
                  width: '100%',
                  padding: '12px 16px',
                  borderRadius: '8px',
                  border: '1px solid #ddd',
                  fontSize: '14px',
                  outline: 'none'
                }}
              />
            </div>

            {/* Upload New Scheme Button */}
            <button
              onClick={() => setShowUploadSchemeModal(true)}
              style={{
                width: '100%',
                padding: '12px',
                borderRadius: '8px',
                border: '2px dashed #ddd',
                background: '#f8f9fa',
                color: '#666',
                cursor: 'pointer',
                marginBottom: 20,
                fontSize: '14px'
              }}
            >
              + Upload New Evaluation Scheme
            </button>

            {/* Schemes List */}
            <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
              {filteredSchemes.map((scheme) => (
                <div
                  key={scheme.scheme_id}
                  style={{
                    padding: '16px',
                    border: selectedScheme?.scheme_id === scheme.scheme_id ? '2px solid #2563eb' : '1px solid #e9ecef',
                    borderRadius: '8px',
                    cursor: 'pointer',
                    background: selectedScheme?.scheme_id === scheme.scheme_id ? '#f0f8ff' : '#fff',
                    transition: 'all 0.2s'
                  }}
                  onClick={() => setSelectedScheme(scheme)}
                >
                  <input
                    type="radio"
                    checked={selectedScheme?.scheme_id === scheme.scheme_id}
                    onChange={() => setSelectedScheme(scheme)}
                    style={{ marginRight: '12px' }}
                  />
                  <div>
                    <div style={{ fontWeight: 600, fontSize: '16px', marginBottom: '4px' }}>
                      {scheme.scheme_name}
                    </div>
                    <div style={{ fontSize: '14px', color: '#666' }}>
                      {scheme.scheme_description}
                    </div>
                    <div style={{ fontSize: '12px', color: '#999', marginTop: '4px' }}>
                      Created: {new Date(scheme.created_at).toLocaleDateString()}
                    </div>
                  </div>
                </div>
              ))}
            </div>

            {filteredSchemes.length === 0 && (
              <div style={{ textAlign: 'center', padding: '20px', color: '#666' }}>
                No evaluation schemes found. Upload one to get started.
              </div>
            )}
          </div>
        </div>

        {/* Right Section: Upload Answer Sheets */}
        <div style={{ flex: 1, maxWidth: 500, overflowY: 'auto', padding: '24px 0' }}>
          <div style={{ background: '#fff', borderRadius: 18, padding: '32px', boxShadow: '0 2px 7px #0002' }}>
            <h2 style={{ margin: 0, fontSize: 24, fontWeight: 600, color: '#1e40af' }}>Upload Answer Sheets</h2>
            
            {selectedScheme ? (
              <div style={{ marginTop: 20 }}>
                <div style={{ padding: '16px', background: '#f0f8ff', borderRadius: '8px', border: '1px solid #bfdbfe', marginBottom: '20px' }}>
                  <div style={{ fontWeight: 600, color: '#1e40af', marginBottom: '4px' }}>
                    Selected Scheme: {selectedScheme.scheme_name}
                  </div>
                  <div style={{ fontSize: '14px', color: '#666' }}>
                    {selectedScheme.scheme_description}
                  </div>
                </div>

                <div style={{ marginBottom: '20px' }}>
                  <label style={{ display: 'block', fontWeight: 600, marginBottom: '8px' }}>Answer Sheets</label>
                  <input
                    type="file"
                    multiple
                    accept=".pdf,.doc,.docx,.txt"
                    onChange={(e) => setAnswerSheetFiles(Array.from(e.target.files || []))}
                    style={{
                      width: '100%',
                      padding: '8px',
                      border: '1px solid #ddd',
                      borderRadius: '4px'
                    }}
                  />
                  {answerSheetFiles && answerSheetFiles.length > 0 && (
                    <div style={{ marginTop: '8px', fontSize: '14px', color: '#555' }}>
                      Selected ({answerSheetFiles.length}): {answerSheetFiles.map(f => f.name).join(', ')}
                    </div>
                  )}
                </div>

                <button
                  onClick={handleUploadAnswerSheets}
                  disabled={isUploading || !answerSheetFiles || answerSheetFiles.length === 0}
                  style={{
                    width: '100%',
                    padding: '12px',
                    borderRadius: '8px',
                    border: 'none',
                    background: '#2563eb',
                    color: '#fff',
                    fontWeight: 600,
                    cursor: 'pointer',
                    opacity: isUploading || !answerSheetFiles || answerSheetFiles.length === 0 ? 0.5 : 1,
                    marginBottom: '16px'
                  }}
                >
                  {isUploading ? 'Uploading...' : 'Upload Answer Sheets'}
                </button>

                {hasUploaded && evaluationId && (
                  <div style={{ padding: '16px', background: '#f0f9ff', borderRadius: '8px', border: '1px solid #7dd3fc', marginBottom: '20px' }}>
                    <div style={{ fontWeight: 600, color: '#0369a1', marginBottom: '4px' }}>✓ Answer Sheets Uploaded</div>
                    <div style={{ fontSize: '14px', color: '#666' }}>Ready to start evaluation</div>
                  </div>
                )}

                <button
                  onClick={handleEvaluate}
                  disabled={isEvaluating || !hasUploaded || !evaluationId}
                  style={{
                    width: '100%',
                    padding: '16px',
                    borderRadius: '8px',
                    border: 'none',
                    background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
                    color: '#fff',
                    fontWeight: 600,
                    fontSize: '16px',
                    cursor: 'pointer',
                    opacity: isEvaluating || !hasUploaded || !evaluationId ? 0.5 : 1
                  }}
                >
                  {isEvaluating ? 'Evaluating...' : 'Evaluate →'}
                </button>
              </div>
            ) : (
              <div style={{ textAlign: 'center', padding: '40px 20px', color: '#666' }}>
                <div style={{ fontSize: '18px', marginBottom: '8px' }}>Select an evaluation scheme</div>
                <div style={{ fontSize: '14px' }}>Choose a scheme from the left to upload answer sheets</div>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Upload Scheme Modal */}
      {showUploadSchemeModal && (
        <div style={{
          position: 'fixed',
          top: 0,
          left: 0,
          right: 0,
          bottom: 0,
          background: 'rgba(0,0,0,0.5)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          zIndex: 1000
        }}>
          <div style={{
            background: '#fff',
            borderRadius: '12px',
            padding: '32px',
            maxWidth: '500px',
            width: '90%',
            maxHeight: '90vh',
            overflowY: 'auto'
          }}>
            <h3 style={{ margin: '0 0 20px 0', fontSize: '20px', fontWeight: 600 }}>Upload Evaluation Scheme</h3>
            
            <div style={{ marginBottom: '16px' }}>
              <label style={{ display: 'block', fontWeight: 600, marginBottom: '6px' }}>Scheme Name</label>
              <input
                type="text"
                value={newSchemeName}
                onChange={(e) => setNewSchemeName(e.target.value)}
                placeholder="e.g., Midterm Exam Scheme"
                style={{
                  width: '100%',
                  padding: '8px 12px',
                  border: '1px solid #ddd',
                  borderRadius: '4px',
                  fontSize: '14px'
                }}
              />
            </div>

            <div style={{ marginBottom: '16px' }}>
              <label style={{ display: 'block', fontWeight: 600, marginBottom: '6px' }}>Description</label>
              <textarea
                value={newSchemeDescription}
                onChange={(e) => setNewSchemeDescription(e.target.value)}
                placeholder="Brief description of the evaluation scheme"
                rows={3}
                style={{
                  width: '100%',
                  padding: '8px 12px',
                  border: '1px solid #ddd',
                  borderRadius: '4px',
                  fontSize: '14px',
                  resize: 'vertical'
                }}
              />
            </div>

            <div style={{ marginBottom: '20px' }}>
              <label style={{ display: 'block', fontWeight: 600, marginBottom: '6px' }}>Mark Scheme File</label>
              <input
                type="file"
                accept=".pdf,.doc,.docx,.txt"
                onChange={(e) => setNewSchemeFile(e.target.files?.[0] || null)}
                style={{
                  width: '100%',
                  padding: '8px',
                  border: '1px solid #ddd',
                  borderRadius: '4px'
                }}
              />
              {newSchemeFile && (
                <div style={{ marginTop: '6px', fontSize: '14px', color: '#555' }}>
                  Selected: {newSchemeFile.name}
                </div>
              )}
            </div>

            <div style={{ display: 'flex', gap: '12px', justifyContent: 'flex-end' }}>
              <button
                onClick={() => setShowUploadSchemeModal(false)}
                style={{
                  padding: '8px 16px',
                  borderRadius: '6px',
                  border: '1px solid #bbb',
                  background: '#fff',
                  cursor: 'pointer'
                }}
              >
                Cancel
              </button>
              <button
                onClick={handleUploadScheme}
                disabled={isUploadingScheme || !newSchemeName || !newSchemeDescription || !newSchemeFile}
                style={{
                  padding: '8px 16px',
                  borderRadius: '6px',
                  border: 'none',
                  background: '#2563eb',
                  color: '#fff',
                  cursor: 'pointer',
                  opacity: isUploadingScheme || !newSchemeName || !newSchemeDescription || !newSchemeFile ? 0.5 : 1
                }}
              >
                {isUploadingScheme ? 'Uploading...' : 'Upload Scheme'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Evaluation Results Section */}
      {evaluationResult && (
        <div style={{
          position: 'fixed',
          top: 0,
          left: 0,
          right: 0,
          bottom: 0,
          background: 'rgba(0,0,0,0.5)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          zIndex: 1000
        }}>
          <div style={{
            background: '#fff',
            borderRadius: '12px',
            padding: '32px',
            maxWidth: '800px',
            width: '90%',
            maxHeight: '90vh',
            overflowY: 'auto'
          }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '20px' }}>
              <h3 style={{ margin: 0, fontSize: '20px', fontWeight: 600 }}>Evaluation Results</h3>
              <button
                onClick={() => setEvaluationResult(null)}
                style={{
                  padding: '8px 16px',
                  borderRadius: '6px',
                  border: '1px solid #ddd',
                  background: '#fff',
                  cursor: 'pointer'
                }}
              >
                Close
              </button>
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '16px', marginBottom: '20px' }}>
              <div style={{ textAlign: 'center', padding: '16px', background: '#f8f9fa', borderRadius: '8px' }}>
                <div style={{ fontSize: '24px', fontWeight: 'bold', color: '#2563eb' }}>
                  {evaluationResult?.evaluation_result?.students?.length || 0}
                </div>
                <div style={{ fontSize: '14px', color: '#666' }}>Students Evaluated</div>
              </div>
              <div style={{ textAlign: 'center', padding: '16px', background: '#f8f9fa', borderRadius: '8px' }}>
                <div style={{ fontSize: '24px', fontWeight: 'bold', color: '#28a745' }}>
                  {evaluationResult?.evaluation_id || 'N/A'}
                </div>
                <div style={{ fontSize: '14px', color: '#666' }}>Evaluation ID</div>
              </div>
            </div>

            <div style={{ maxHeight: '400px', overflowY: 'auto' }}>
              {evaluationResult?.evaluation_result?.students?.map((student, index) => (
                <div
                  key={index}
                  style={{
                    padding: '16px',
                    border: '1px solid #e9ecef',
                    borderRadius: '8px',
                    marginBottom: '12px',
                    background: selectedStudent === student ? '#f8f9fa' : '#fff'
                  }}
                >
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <div>
                      <div style={{ fontWeight: 600, fontSize: '16px' }}>
                        {student.student_name || `Student ${index + 1}`}
                      </div>
                      <div style={{ fontSize: '14px', color: '#666' }}>
                        Score: {formatScore(student.total_score, student.max_total_score)}
                      </div>
                    </div>
                    <div style={{
                      fontSize: '20px',
                      fontWeight: 'bold',
                      color: getScoreColor(student.total_score, student.max_total_score)
                    }}>
                      {formatScore(student.total_score, student.max_total_score)}
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}

      <SettingsModal open={showSettingsModal} onClose={() => setShowSettingsModal(false)} />
    </div>
  );
} 