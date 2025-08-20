import React, { useState } from "react";
import { useNavigate } from "react-router-dom";
import Header from "../components/header/Header";
import SettingsModal from "../components/SettingsModal";
import { evaluationService } from "../services/evaluation";
import { getCurrentUser } from "../services/auth";

export default function Evaluation() {
  const navigate = useNavigate();
  const [isGridView, setIsGridView] = useState(true);
  const [showSettingsModal, setShowSettingsModal] = useState(false);
  const [markSchemeFile, setMarkSchemeFile] = useState(null);
  const [answerSheetFiles, setAnswerSheetFiles] = useState([]);
  const [isUploadingMarkScheme, setIsUploadingMarkScheme] = useState(false);
  const [isUploadingAnswerSheets, setIsUploadingAnswerSheets] = useState(false);
  const [isEvaluating, setIsEvaluating] = useState(false);
  const [evaluationId, setEvaluationId] = useState(null);
  const [markSchemeFileId, setMarkSchemeFileId] = useState(null);
  const [answerSheetFileIds, setAnswerSheetFileIds] = useState([]);

  const handleLogout = () => {
    localStorage.removeItem("token");
    navigate("/login");
  };

  const handleUploadMarkScheme = async () => {
    if (!markSchemeFile) {
      alert("Please select a Mark Scheme file.");
      return;
    }
    try {
      setIsUploadingMarkScheme(true);
      const courseId = localStorage.getItem('currentCourseId');
      if (!courseId) {
        alert('No active course found. Please select a course.');
        return;
      }

      const res = await evaluationService.uploadMarkScheme({
        courseId,
        markSchemeFile
      });
      setEvaluationId(res?.evaluation_id);
      setMarkSchemeFileId(res?.mark_scheme_file_id);
      alert('Mark scheme uploaded successfully!');
    } catch (err) {
      alert(err?.message || 'Mark scheme upload failed');
    } finally {
      setIsUploadingMarkScheme(false);
    }
  };

  const handleUploadAnswerSheets = async () => {
    if (!evaluationId) {
      alert("Please upload mark scheme first.");
      return;
    }
    if (!answerSheetFiles || answerSheetFiles.length === 0) {
      alert("Please select at least one Answer Sheet.");
      return;
    }
    try {
      setIsUploadingAnswerSheets(true);
      const res = await evaluationService.uploadAnswerSheets({
        evaluationId,
        answerSheetFiles
      });
      setAnswerSheetFileIds(res?.answer_sheet_file_ids || []);
      alert(`Uploaded ${res?.answer_sheet_file_ids?.length || 0} answer sheet(s) successfully!`);
    } catch (err) {
      alert(err?.message || 'Answer sheets upload failed');
    } finally {
      setIsUploadingAnswerSheets(false);
    }
  };

  const handleEvaluate = async () => {
    if (!evaluationId || !markSchemeFileId || answerSheetFileIds.length === 0) {
      alert('Please upload both mark scheme and answer sheets first.');
      return;
    }
    try {
      setIsEvaluating(true);
      const res = await evaluationService.evaluateFiles({ evaluationId });
      alert(`Evaluation completed! Evaluated ${res?.evaluation_result?.students?.length || 0} students.`);
    } catch (err) {
      alert(err?.message || 'Evaluation failed');
    } finally {
      setIsEvaluating(false);
    }
  };

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
      <div style={{ maxWidth: 1200, margin: "1rem auto 0.5rem auto", width: "100%", display: 'flex', alignItems: 'center', gap: 10, fontSize: 18, fontWeight: 500 }}>
        <span style={{ color: '#2563eb', cursor: 'pointer', fontWeight: 600 }} onClick={() => navigate('/courses')}>Courses</span>
        <span style={{ color: '#888' }}>{'>'}</span>
        <span style={{ color: '#2563eb', cursor: 'pointer', fontWeight: 600 }} onClick={() => navigate('/dashboard')}>{localStorage.getItem("currentCourseTitle") || "Course"}</span>
        <span style={{ color: '#888' }}>{'>'}</span>
        <span style={{ fontWeight: 700 }}>Evaluation</span>
      </div>

      <div style={{ flex: 1, display: 'flex', gap: 24, padding: '0 5vw', overflow: 'hidden' }}>
        {/* Main content */}
        <div style={{ flex: 2, maxWidth: 900, width: '100%', margin: '0 auto', overflowY: 'auto', padding: '24px 0', display: 'flex', flexDirection: 'column', gap: 28 }}>
          <div style={{ background: '#fff', borderRadius: 18, padding: '32px', boxShadow: '0 2px 7px #0002' }}>
            <h2 style={{ margin: 0, fontSize: 24, fontWeight: 600 }}>Start Evaluation</h2>
            <p style={{ marginTop: 8, color: '#444' }}>Upload one Mark Scheme and multiple Answer Sheets, then run evaluation.</p>

            <form onSubmit={(e) => e.preventDefault()} style={{ marginTop: 16, display: 'flex', flexDirection: 'column', gap: 16 }}>
              <div>
                <label style={{ display: 'block', fontWeight: 600, marginBottom: 6 }}>Mark Scheme</label>
                <input type="file" accept=".pdf,.doc,.docx,.txt" onChange={(e) => setMarkSchemeFile(e.target.files?.[0] || null)} />
                {markSchemeFile && (
                  <div style={{ marginTop: 6, fontSize: 14, color: '#555' }}>Selected: {markSchemeFile.name}</div>
                )}
                {markSchemeFileId && (
                  <div style={{ marginTop: 4, fontSize: 12, color: '#2563eb' }}>Uploaded ID: {markSchemeFileId}</div>
                )}
              </div>
              <div>
                <label style={{ display: 'block', fontWeight: 600, marginBottom: 6 }}>Answer Sheets</label>
                <input type="file" multiple accept=".pdf,.doc,.docx,.txt" onChange={(e) => setAnswerSheetFiles(Array.from(e.target.files || []))} />
                {answerSheetFiles && answerSheetFiles.length > 0 && (
                  <div style={{ marginTop: 6, fontSize: 14, color: '#555' }}>
                    Selected ({answerSheetFiles.length}): {answerSheetFiles.map(f => f.name).join(', ')}
                  </div>
                )}
                {answerSheetFileIds && answerSheetFileIds.length > 0 && (
                  <div style={{ marginTop: 6, fontSize: 12, color: '#2563eb' }}>
                    Uploaded IDs: {answerSheetFileIds.join(', ')}
                  </div>
                )}
              </div>

              <div style={{ display: 'flex', gap: 12, marginTop: 8 }}>
                <button type="button" onClick={() => navigate('/dashboard')} style={{ padding: '8px 22px', borderRadius: 6, border: '1px solid #bbb', background: '#fff', fontWeight: 500, fontSize: 15, cursor: 'pointer' }}>Cancel</button>
                <button type="button" onClick={handleUploadMarkScheme} disabled={isUploadingMarkScheme || !markSchemeFile} style={{ padding: '8px 22px', borderRadius: 6, border: 'none', background: '#2563eb', color: '#fff', fontWeight: 600, fontSize: 15, cursor: 'pointer', opacity: isUploadingMarkScheme ? 0.7 : 1 }}>{isUploadingMarkScheme ? 'Uploading...' : 'Upload Mark Scheme'}</button>
                <button type="button" onClick={handleUploadAnswerSheets} disabled={isUploadingAnswerSheets || !evaluationId || !answerSheetFiles || answerSheetFiles.length === 0} style={{ padding: '8px 22px', borderRadius: 6, border: 'none', background: '#16a34a', color: '#fff', fontWeight: 600, fontSize: 15, cursor: 'pointer', opacity: isUploadingAnswerSheets ? 0.7 : 1 }}>{isUploadingAnswerSheets ? 'Uploading...' : 'Upload Answer Sheets'}</button>
                <button type="button" onClick={handleEvaluate} disabled={isEvaluating || !evaluationId || !markSchemeFileId || answerSheetFileIds.length === 0} style={{ padding: '8px 22px', borderRadius: 6, border: '1px solid #bbb', background: '#fff', color: '#222', fontWeight: 600, fontSize: 15, cursor: 'pointer', opacity: isEvaluating ? 0.7 : 1 }}>{isEvaluating ? 'Evaluating...' : 'Evaluate'}</button>
              </div>
            </form>
          </div>
        </div>

        {/* Right panel placeholder to match UI spacing; optional: show KB */}
        <div style={{ flex: 1, marginTop: 24, minWidth: 340, maxWidth: 420 }}>
          <div style={{ background: '#fff', borderRadius: 12, padding: 16, boxShadow: '0 2px 12px #0001' }}>
            <div style={{ fontWeight: 600, marginBottom: 8 }}>Tips</div>
            <div style={{ color: '#555', fontSize: 14 }}>
              Keep file names clear, e.g., <em>mark-scheme.pdf</em> and <em>answers-student-a.pdf</em>.
            </div>
          </div>
        </div>
      </div>

      <SettingsModal open={showSettingsModal} onClose={() => setShowSettingsModal(false)} />
    </div>
  );
} 