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
  const [markSchemeFile, setMarkSchemeFile] = useState(null);
  const [answerSheetFiles, setAnswerSheetFiles] = useState([]);
  const [isUploadingMarkScheme, setIsUploadingMarkScheme] = useState(false);
  const [isUploadingAnswerSheets, setIsUploadingAnswerSheets] = useState(false);
  const [isEvaluating, setIsEvaluating] = useState(false);
  const [markSchemeUploaded, setMarkSchemeUploaded] = useState(false);
  const [answerSheetsUploaded, setAnswerSheetsUploaded] = useState(false);
  const [evaluationId, setEvaluationId] = useState(null);
  const [evaluationResult, setEvaluationResult] = useState(null);
  const [selectedStudent, setSelectedStudent] = useState(null);
  const [showResults, setShowResults] = useState(false);
  const [evaluationProgress, setEvaluationProgress] = useState(0);
  const [evaluationStatus, setEvaluationStatus] = useState('');
  const [showReview, setShowReview] = useState(false);
  const [selectedStudentIndex, setSelectedStudentIndex] = useState(null);
  const [selectedQuestionIndex, setSelectedQuestionIndex] = useState(0);
  const [isEditing, setIsEditing] = useState(false);
  const [editedQuestionScores, setEditedQuestionScores] = useState([]);
  const [editedFeedback, setEditedFeedback] = useState('');

  const courseId = localStorage.getItem('currentCourseId');
  const courseTitle = localStorage.getItem("currentCourseTitle") || "Course";

  // Simulate evaluation progress
  useEffect(() => {
    let progressInterval;
    if (isEvaluating && showResults) {
      setEvaluationProgress(0);
      setEvaluationStatus('Starting evaluation...');
      
      progressInterval = setInterval(() => {
        setEvaluationProgress(prev => {
          if (prev >= 90) {
            clearInterval(progressInterval);
            return 90;
          }
          return prev + Math.random() * 15;
        });
      }, 1000);

      // Update status messages based on progress
      const statusInterval = setInterval(() => {
        setEvaluationProgress(prev => {
          if (prev < 20) {
            setEvaluationStatus('Analyzing mark scheme...');
          } else if (prev < 40) {
            setEvaluationStatus('Processing answer sheets...');
          } else if (prev < 60) {
            setEvaluationStatus('Evaluating student responses...');
          } else if (prev < 80) {
            setEvaluationStatus('Calculating scores...');
          } else if (prev < 90) {
            setEvaluationStatus('Finalizing results...');
          }
          return prev;
        });
      }, 2000);
    }

    return () => {
      if (progressInterval) clearInterval(progressInterval);
    };
  }, [isEvaluating, showResults]);

  const handleLogout = () => {
    localStorage.removeItem("token");
    navigate("/login");
  };

  const handleUploadMarkScheme = async () => {
    if (!markSchemeFile) {
      alert("Please select a mark scheme file.");
      return;
    }
    try {
      setIsUploadingMarkScheme(true);
      const res = await evaluationService.uploadMarkScheme({
        courseId,
        markSchemeFile
      });
      
      setEvaluationId(res.evaluation_id);
      setMarkSchemeUploaded(true);
      alert("Mark scheme uploaded successfully! You can now upload answer sheets.");
    } catch (error) {
      alert(error.message || "Failed to upload mark scheme");
    } finally {
      setIsUploadingMarkScheme(false);
      setIsUploadingMarkScheme(false);
    }
  };

  const handleUploadAnswerSheets = async () => {
    if (!markSchemeUploaded || !evaluationId) {
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
      
      setAnswerSheetsUploaded(true);
      alert(`Answer sheets uploaded successfully! Ready to start evaluation.`);
    } catch (err) {
      alert(err?.message || 'Answer sheets upload failed');
    } finally {
      setIsUploadingAnswerSheets(false);
    }
  };

  const handleEvaluate = async () => {
    if (!markSchemeUploaded || !answerSheetsUploaded || !evaluationId) {
      alert('Please upload both mark scheme and answer sheets first.');
      return;
    }
    
    try {
      setIsEvaluating(true);
      setShowResults(true); // Show results page immediately
      setEvaluationProgress(0);
      setEvaluationStatus('Starting evaluation...');
      
      // Start the evaluation in background
      const result = await evaluationService.evaluateFiles(evaluationId);
      setEvaluationResult(result);
      setEvaluationProgress(100);
      setEvaluationStatus('Evaluation completed!');
      setIsEvaluating(false);
      
      alert(`Evaluation completed successfully!\n\nStudents evaluated: ${result?.evaluation_result?.students?.length || 0}`);
      
    } catch (err) {
      console.error('Evaluation error:', err);
      setEvaluationStatus('Evaluation failed');
      setIsEvaluating(false);
      alert(err?.message || 'Evaluation failed');
    }
  };

  const handleStudentClick = (studentIndex) => {
    console.log('Student clicked:', {
      studentIndex,
      evaluationResult,
      answerSheetFiles: answerSheetFiles.length,
      hasEvaluationData: !!evaluationResult?.evaluation_result?.students
    });
    
    // Validate that we have the required data
    if (!evaluationResult || !evaluationResult.evaluation_result || !evaluationResult.evaluation_result.students) {
      alert('Evaluation data is not yet available. Please wait for the evaluation to complete.');
      return;
    }
    
    if (studentIndex >= evaluationResult.evaluation_result.students.length) {
      alert('Student data not found. Please try again.');
      return;
    }
    
    // Add additional validation
    try {
      const student = evaluationResult.evaluation_result.students[studentIndex];
      console.log('Student data structure:', student);
      console.log('Available student properties:', Object.keys(student));
      
      if (!student) {
        alert('Student data is missing. Please try again.');
        return;
      }
      
      // Check if we have the required data structure for the review page
      const hasRequiredData = student.question_scores && student.questions && student.answers && student.ai_feedback;
      console.log('Has required data for review page:', hasRequiredData);
      
      if (!hasRequiredData) {
        console.log('Missing required data structure for review page');
        alert('The evaluation data structure is incomplete. Please contact support.');
        return;
      }
      
      // Update status to "opened" if it's currently "unopened"
      if (student.status === "unopened") {
        updateStudentStatusToOpened(evaluationId, studentIndex);
      }
      
      console.log('Student data found:', student);
      setSelectedStudentIndex(studentIndex);
      setShowReview(true);
      setSelectedQuestionIndex(0);
      setIsEditing(false);
      setEditedQuestionScores([]);
      setEditedFeedback('');
    } catch (error) {
      console.error('Error accessing student data:', error);
      alert('Error accessing student data. Please try again.');
    }
  };

  const updateStudentStatusToOpened = async (evaluationId, studentIndex) => {
    try {
      const result = await evaluationService.updateStudentStatus({
        evaluationId,
        studentIndex,
        status: "opened"
      });
      
      console.log('Status updated to opened:', result);
      
      // Update local state to reflect the status change
      const updatedEvaluationResult = { ...evaluationResult };
      updatedEvaluationResult.evaluation_result.students[studentIndex].status = "opened";
      setEvaluationResult(updatedEvaluationResult);
      
    } catch (error) {
      console.error('Failed to update status to opened:', error);
      // Don't block the user from opening the review page if status update fails
    }
  };

  const handleBackToResults = () => {
    setShowReview(false);
    setSelectedStudentIndex(null);
    setSelectedQuestionIndex(0);
    setIsEditing(false);
    setEditedQuestionScores([]);
    setEditedFeedback('');
  };

  const handleEdit = () => {
    console.log('Edit button clicked');
    if (evaluationResult && selectedStudentIndex !== null) {
      const student = evaluationResult.evaluation_result.students[selectedStudentIndex];
      console.log('Setting up edit mode for student:', student);
      
      // Initialize with current values
      setEditedQuestionScores([...student.question_scores]);
      
      // Get general feedback for the student
      const currentFeedback = student.feedback || '';
      setEditedFeedback(currentFeedback);
      
      setIsEditing(true);
      console.log('Edit mode activated with:', {
        questionScores: student.question_scores,
        feedback: currentFeedback
      });
    } else {
      console.log('Cannot edit - missing data:', { evaluationResult, selectedStudentIndex });
    }
  };

  const handleSave = async () => {
    console.log('Save button clicked');
    if (!evaluationId || selectedStudentIndex === null) {
      console.log('Cannot save - missing data:', { evaluationId, selectedStudentIndex });
      return;
    }
    
    try {
      // Validate question scores
      if (!Array.isArray(editedQuestionScores) || editedQuestionScores.length === 0) {
        alert('Question scores are required and must be an array');
        return;
      }
      
      // Ensure all scores are valid numbers
      const validScores = editedQuestionScores.map((score, index) => {
        const numScore = parseInt(score);
        if (isNaN(numScore) || numScore < 0) {
          throw new Error(`Invalid score at question ${index + 1}: ${score}`);
        }
        return numScore;
      });
      
      const totalScore = validScores.reduce((sum, score) => sum + score, 0);
      console.log('Calculated total score:', totalScore);
      
      // Validate and clean the feedback
      const cleanFeedback = typeof editedFeedback === 'string' ? editedFeedback.trim() : '';
      console.log('Data being sent:', {
        evaluationId,
        studentIndex: selectedStudentIndex,
        questionScores: validScores,
        feedback: cleanFeedback
      });
      
      // Call the backend to update the student result
      const result = await evaluationService.updateStudentResult({
        evaluationId,
        studentIndex: selectedStudentIndex,
        questionScores: validScores,
        feedback: cleanFeedback
      });
      
      console.log('Backend update result:', result);
      
      // Update local state for immediate feedback
      const updatedEvaluationResult = { ...evaluationResult };
      updatedEvaluationResult.evaluation_result.students[selectedStudentIndex] = {
        ...updatedEvaluationResult.evaluation_result.students[selectedStudentIndex],
        question_scores: validScores,
        feedback: cleanFeedback,
        total_score: totalScore,
        status: "modified"  // Update status to modified
      };
      
      setEvaluationResult(updatedEvaluationResult);
      setIsEditing(false);
      
      console.log('Local state updated successfully');
      
      alert('Changes saved successfully!');
      
    } catch (error) {
      console.error('Error saving changes:', error);
      console.error('Error details:', {
        message: error.message,
        response: error.response?.data,
        status: error.response?.status
      });
      alert('Failed to save changes: ' + error.message);
    }
  };

  const handleCancelEdit = () => {
    setIsEditing(false);
    setEditedQuestionScores([]);
    setEditedFeedback('');
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

  const getStatusColor = (status) => {
    switch (status) {
      case 'unopened':
        return '#6c757d'; // Gray
      case 'opened':
        return '#2563eb'; // Blue
      case 'modified':
        return '#dc3545'; // Red
      default:
        return '#6c757d'; // Gray
    }
  };

  const getStatusText = (status) => {
    switch (status) {
      case 'unopened':
        return 'unopened';
      case 'opened':
        return 'opened';
      case 'modified':
        return 'modified';
      default:
        return 'unopened';
    }
  };

  // If showing review page, display the review interface
  if (showReview && selectedStudentIndex !== null && evaluationResult) {
    // Add safety checks for evaluation data
    if (!evaluationResult.evaluation_result || !evaluationResult.evaluation_result.students) {
      console.error('Missing evaluation data:', evaluationResult);
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
          <div style={{ flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
            <div style={{ textAlign: 'center', padding: '40px' }}>
              <h2 style={{ color: '#dc3545', marginBottom: '16px' }}>No Evaluation Data Available</h2>
              <p style={{ color: '#666', marginBottom: '24px' }}>
                The evaluation data is not yet available or has an unexpected format.
              </p>
              <button
                onClick={handleBackToResults}
                style={{
                  padding: '12px 24px',
                  borderRadius: '8px',
                  border: '1px solid #dee2e6',
                  background: '#fff',
                  color: '#495057',
                  fontWeight: 600,
                  cursor: 'pointer',
                  fontSize: '14px'
                }}
              >
                ← Back to Results
              </button>
            </div>
          </div>
        </div>
      );
    }
    
    const student = evaluationResult.evaluation_result.students[selectedStudentIndex];
    console.log('Review page - Student data:', student);
    console.log('Review page - Student properties:', Object.keys(student));
    console.log('Review page - Question scores:', student?.question_scores);
    console.log('Review page - Questions:', student?.questions);
    console.log('Review page - Answers:', student?.answers);
    console.log('Review page - AI feedback:', student?.ai_feedback);
    
    if (!student) {
      console.error('Student data not found for index:', selectedStudentIndex);
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
          <div style={{ flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
            <div style={{ textAlign: 'center', padding: '40px' }}>
              <h2 style={{ color: '#dc3545', marginBottom: '16px' }}>Student Data Not Found</h2>
              <p style={{ color: '#666', marginBottom: '24px' }}>
                The selected student's evaluation data could not be found.
              </p>
              <button
                onClick={handleBackToResults}
                style={{
                  padding: '12px 24px',
                  borderRadius: '8px',
                  border: '1px solid #dee2e6',
                  background: '#fff',
                  color: '#495057',
                  fontWeight: 600,
                  cursor: 'pointer',
                  fontSize: '14px'
                }}
              >
                ← Back to Results
              </button>
            </div>
          </div>
        </div>
      );
    }
    
    const fileName = answerSheetFiles[selectedStudentIndex]?.name || `Student ${selectedStudentIndex + 1}`;

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
          <span style={{ color: '#2563eb', cursor: 'pointer', fontWeight: 600 }} onClick={handleBackToResults}>Evaluation</span>
          <span style={{ color: '#888' }}>{'>'}</span>
          <span style={{ fontWeight: 700 }}>Review - {fileName}</span>
          <span style={{ 
            color: getStatusColor(student?.status || 'unopened'),
            fontSize: '14px',
            fontWeight: 600,
            padding: '4px 12px',
            borderRadius: '12px',
            background: getStatusColor(student?.status || 'unopened') === '#6c757d' ? '#f8f9fa' : 
                       getStatusColor(student?.status || 'unopened') === '#2563eb' ? '#eff6ff' : '#fef2f2',
            border: `1px solid ${getStatusColor(student?.status || 'unopened')}`
          }}>
            {getStatusText(student?.status || 'unopened')}
          </span>
        </div>

        {/* Review Content */}
        <div style={{ flex: 1, display: 'flex', gap: 24, padding: '0 5vw', overflow: 'hidden' }}>
          {/* Left Panel: Question Navigation */}
          <div style={{ flex: 1, maxWidth: 300, overflowY: 'auto', padding: '24px 0' }}>
            <div style={{ background: '#fff', borderRadius: 18, padding: '24px', boxShadow: '0 2px 7px #0002' }}>
              <h3 style={{ margin: '0 0 20px 0', fontSize: 20, fontWeight: 600, color: '#1e40af' }}>Questions</h3>
              {student?.question_scores?.map((score, index) => (
                <div
                  key={index}
                  style={{
                    padding: '12px 16px',
                    marginBottom: '8px',
                    borderRadius: '8px',
                    background: selectedQuestionIndex === index ? '#e0f2fe' : '#f8f9fa',
                    border: selectedQuestionIndex === index ? '2px solid #0288d1' : '1px solid #e9ecef',
                    cursor: 'pointer',
                    transition: 'all 0.2s'
                  }}
                  onClick={() => setSelectedQuestionIndex(index)}
                >
                  <div style={{ fontWeight: 600, marginBottom: '4px' }}>Question {index + 1}</div>
                  <div style={{ fontSize: '14px', color: '#666' }}>{score}/{student?.max_scores?.[index] || '?'}</div>
                </div>
              )) || (
                <div style={{ padding: '16px', textAlign: 'center', color: '#666' }}>
                  No question scores available
                </div>
              )}
            </div>
          </div>

          {/* Center Panel: Question Details */}
          <div style={{ flex: 2, maxWidth: 600, overflowY: 'auto', padding: '24px 0' }}>
            <div style={{ background: '#fff', borderRadius: 18, padding: '32px', boxShadow: '0 2px 7px #0002' }}>
              <h3 style={{ margin: '0 0 20px 0', fontSize: 22, fontWeight: 600, color: '#1e40af' }}>
                Question {selectedQuestionIndex + 1}
              </h3>
              
              <div style={{ marginBottom: '24px' }}>
                <h4 style={{ margin: '0 0 12px 0', fontSize: 16, fontWeight: 600, color: '#374151' }}>Question</h4>
                <div style={{ padding: '16px', background: '#f8f9fa', borderRadius: '8px', border: '1px solid #e9ecef' }}>
                  {student?.questions?.[selectedQuestionIndex] || 'Question text not available'}
                </div>
              </div>

              <div style={{ marginBottom: '24px' }}>
                <h4 style={{ margin: '0 0 12px 0', fontSize: 16, fontWeight: 600, color: '#374151' }}>Student Answer</h4>
                <div style={{ padding: '16px', background: '#f0f9ff', borderRadius: '8px', border: '1px solid #bfdbfe' }}>
                  {student?.answers?.[selectedQuestionIndex] || 'Student answer not available'}
                </div>
              </div>

              <div style={{ marginBottom: '24px' }}>
                <h4 style={{ margin: '0 0 12px 0', fontSize: 16, fontWeight: 600, color: '#374151' }}>AI Evaluation</h4>
                <div style={{ padding: '16px', background: '#fef3c7', borderRadius: '8px', border: '1px solid #fbbf24' }}>
                  {student?.ai_feedback?.[selectedQuestionIndex] || 'AI feedback not available'}
                </div>
              </div>
            </div>
          </div>

          {/* Right Panel: Marks & Feedback Editor */}
          <div style={{ flex: 1, maxWidth: 400, overflowY: 'auto', padding: '24px 0' }}>
            <div style={{ background: '#fff', borderRadius: 18, padding: '32px', boxShadow: '0 2px 7px #0002' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '20px' }}>
                <h3 style={{ margin: 0, fontSize: 20, fontWeight: 600, color: '#1e40af' }}>Marks & Feedback</h3>
                {!isEditing ? (
                  <button
                    style={{
                      padding: '8px 16px',
                      borderRadius: '6px',
                      border: '1px solid #2563eb',
                      background: '#fff',
                      color: '#2563eb',
                      fontWeight: 600,
                      cursor: 'pointer',
                      fontSize: '14px'
                    }}
                    onClick={handleEdit}
                  >
                    Edit
                  </button>
                ) : (
                  <div style={{ display: 'flex', gap: '8px' }}>
                    <button
                      style={{
                        padding: '8px 16px',
                        borderRadius: '6px',
                        border: '1px solid #28a745',
                        background: '#28a745',
                        color: '#fff',
                        fontWeight: 600,
                        cursor: 'pointer',
                        fontSize: '14px'
                      }}
                      onClick={handleSave}
                    >
                      Save
                    </button>
                    <button
                      style={{
                        padding: '8px 16px',
                        borderRadius: '6px',
                        border: '1px solid #dc3545',
                        background: '#fff',
                        color: '#dc3545',
                        fontWeight: 600,
                        cursor: 'pointer',
                        fontSize: '14px'
                      }}
                      onClick={handleCancelEdit}
                    >
                      Cancel
                    </button>
                  </div>
                )}
              </div>

              <div style={{ marginBottom: '24px' }}>
                <h4 style={{ margin: '0 0 12px 0', fontSize: 16, fontWeight: 600, color: '#374151' }}>Marks obtained</h4>
                {isEditing ? (
                  <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                    <input
                      type="number"
                      min="0"
                      max={student?.max_scores?.[selectedQuestionIndex] || 10}
                      value={editedQuestionScores[selectedQuestionIndex] || 0}
                      onChange={(e) => {
                        const newScores = [...editedQuestionScores];
                        newScores[selectedQuestionIndex] = parseInt(e.target.value) || 0;
                        setEditedQuestionScores(newScores);
                      }}
                      style={{
                        width: '80px',
                        padding: '8px',
                        border: '1px solid #ddd',
                        borderRadius: '4px',
                        fontSize: '16px',
                        fontWeight: 'bold',
                        textAlign: 'center'
                      }}
                    />
                    <span style={{ fontSize: '14px', color: '#666' }}>
                      of {student?.max_scores?.[selectedQuestionIndex] || '?'}
                    </span>
                  </div>
                ) : (
                  <>
                    <div style={{ fontSize: '32px', fontWeight: 'bold', color: '#2563eb' }}>
                      {student?.question_scores?.[selectedQuestionIndex] || 0}
                    </div>
                    <div style={{ fontSize: '14px', color: '#666' }}>
                      of {student?.max_scores?.[selectedQuestionIndex] || '?'}
                    </div>
                  </>
                )}
              </div>

              <div style={{ marginBottom: '24px' }}>
                <h4 style={{ margin: '0 0 12px 0', fontSize: 16, fontWeight: 600, color: '#374151' }}>Feedback</h4>
                {isEditing ? (
                  <textarea
                    value={editedFeedback}
                    onChange={(e) => setEditedFeedback(e.target.value)}
                    placeholder="Enter feedback for this question..."
                    style={{
                      width: '100%',
                      minHeight: '100px',
                      padding: '12px',
                      border: '1px solid #ddd',
                      borderRadius: '6px',
                      fontSize: '14px',
                      lineHeight: '1.5',
                      resize: 'vertical'
                    }}
                  />
                ) : (
                  <div style={{ padding: '16px', background: '#f8f9fa', borderRadius: '8px', border: '1px solid #e9ecef', fontSize: '14px', lineHeight: '1.5' }}>
                    {student?.feedback || 'No feedback available'}
                  </div>
                )}
              </div>

              <div style={{ textAlign: 'center', marginTop: '32px' }}>
                <button 
                  onClick={handleBackToResults}
                  style={{
                    padding: '12px 24px',
                    borderRadius: '8px',
                    border: '1px solid #dee2e6',
                    background: '#fff',
                    color: '#495057',
                    fontWeight: 600,
                    cursor: 'pointer',
                    fontSize: '14px'
                  }}
                >
                  Close
                </button>
              </div>
            </div>
          </div>
        </div>

        <SettingsModal open={showSettingsModal} onClose={() => setShowSettingsModal(false)} />
      </div>
    );
  }

  // If showing results, display the results page
  if (showResults) {
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

        {/* Progress Bar */}
        <div style={{ 
          maxWidth: 1200, 
          margin: "0 auto 2rem auto", 
          width: '100%', 
          padding: '20px',
          background: '#fff',
          borderRadius: '12px',
          boxShadow: '0 2px 8px rgba(0,0,0,0.1)',
          border: '1px solid #e9ecef'
        }}>
          <div style={{ marginBottom: '16px' }}>
            <div style={{ 
              display: 'flex', 
              justifyContent: 'space-between', 
              alignItems: 'center',
              marginBottom: '8px'
            }}>
              <span style={{ fontSize: '16px', fontWeight: 600, color: '#495057' }}>
                {isEvaluating ? 'Evaluation in Progress...' : 'Evaluation Complete'}
              </span>
              <span style={{ fontSize: '14px', fontWeight: 600, color: '#2563eb' }}>
                {Math.round(evaluationProgress)}%
              </span>
            </div>
            <div style={{ fontSize: '14px', color: '#6c757d', marginBottom: '12px' }}>
              {evaluationStatus}
            </div>
          </div>
          
          {/* Progress Bar */}
          <div style={{ 
            width: '100%', 
            height: '12px', 
            background: '#e9ecef', 
            borderRadius: '6px',
            overflow: 'hidden'
          }}>
            <div style={{
              width: `${evaluationProgress}%`,
              height: '100%',
              background: isEvaluating 
                ? 'linear-gradient(90deg, #2563eb, #3b82f6)' 
                : evaluationProgress === 100 
                  ? '#28a745' 
                  : '#dc3545',
              borderRadius: '6px',
              transition: 'width 0.5s ease-in-out',
              boxShadow: '0 2px 4px rgba(0,0,0,0.1)'
            }} />
          </div>
        </div>

        {/* Total Submissions Summary */}
        <div style={{ maxWidth: 1200, margin: "0 auto 2rem auto", width: '100%' }}>
          <div style={{ 
            display: 'inline-block',
            background: '#e3f2fd', 
            borderRadius: '12px', 
            padding: '20px 32px',
            border: '1px solid #bbdefb'
          }}>
            <div style={{ fontSize: '14px', color: '#1976d2', marginBottom: '8px' }}>Total Submissions</div>
            <div style={{ fontSize: '32px', fontWeight: 'bold', color: '#1565c0' }}>
              {answerSheetFiles.length || 0}
            </div>
          </div>
        </div>

        {/* Evaluation Results Table */}
        <div style={{ maxWidth: 1200, margin: "0 auto 2rem auto", width: '100%', flex: 1, overflow: 'auto' }}>
          <div style={{ background: '#fff', borderRadius: '12px', boxShadow: '0 2px 8px rgba(0,0,0,0.1)', overflow: 'hidden' }}>
            {/* Table Header */}
            <div style={{ 
              display: 'grid', 
              gridTemplateColumns: '2fr 1fr 1fr 1fr',
              background: '#f8f9fa',
              borderBottom: '1px solid #dee2e6',
              padding: '16px 20px',
              fontWeight: 600,
              color: '#495057',
              fontSize: '14px'
            }}>
              <div>filename (roll no. + student name)</div>
              <div>Marks</div>
              <div>Result</div>
              <div>Status</div>
            </div>

            {/* Table Rows */}
            {answerSheetFiles.map((file, index) => (
              <div
                key={index}
                style={{
                  display: 'grid',
                  gridTemplateColumns: '2fr 1fr 1fr 1fr',
                  padding: '16px 20px',
                  borderBottom: '1px solid #f1f3f4',
                  alignItems: 'center',
                  background: index % 2 === 0 ? '#fff' : '#fafbfc',
                  transition: 'background-color 0.2s'
                }}
                onMouseEnter={(e) => e.target.parentElement.style.background = '#f8f9fa'}
                onMouseLeave={(e) => e.target.parentElement.style.background = index % 2 === 0 ? '#fff' : '#fafbfc'}
              >
                {/* Filename - Now Clickable */}
                <div 
                  style={{ 
                    color: evaluationResult ? '#2563eb' : '#6c757d', 
                    textDecoration: evaluationResult ? 'underline' : 'none', 
                    cursor: evaluationResult ? 'pointer' : 'default',
                    fontWeight: 500,
                    padding: '4px 8px',
                    borderRadius: '4px',
                    transition: 'all 0.2s ease',
                    background: evaluationResult ? 'transparent' : 'transparent',
                    ':hover': evaluationResult ? {
                      background: '#f0f8ff',
                      color: '#1e40af'
                    } : {}
                  }}
                  onMouseEnter={(e) => {
                    if (evaluationResult) {
                      e.target.style.background = '#f0f8ff';
                      e.target.style.color = '#1e40af';
                    }
                  }}
                  onMouseLeave={(e) => {
                    if (evaluationResult) {
                      e.target.style.background = 'transparent';
                      e.target.style.color = '#2563eb';
                    }
                  }}
                  onClick={() => {
                    console.log('Filename clicked:', file.name, 'Index:', index);
                    console.log('Evaluation result available:', !!evaluationResult);
                    if (evaluationResult) {
                      handleStudentClick(index);
                    }
                  }}
                >
                  {file.name}
                  {!evaluationResult && (
                    <div style={{ fontSize: '12px', color: '#dc3545', marginTop: '4px' }}>
                      (Complete evaluation first)
                    </div>
                  )}
                  {evaluationResult && (
                    <div style={{ fontSize: '12px', color: '#2563eb', marginTop: '4px' }}>
                      (Click to review)
                    </div>
                  )}
                </div>
                
                {/* Marks */}
                <div style={{ 
                  fontWeight: 600,
                  color: isEvaluating ? '#6c757d' : '#28a745'
                }}>
                  {isEvaluating ? 'Processing...' : evaluationResult?.evaluation_result?.students?.[index] ? 
                    formatScore(evaluationResult.evaluation_result.students[index].total_score, evaluationResult.evaluation_result.students[index].max_total_score) : 
                    'Pending'
                  }
                </div>
                
                {/* Result */}
                <div style={{ 
                  fontWeight: 600,
                  color: isEvaluating ? '#6c757d' : '#28a745'
                }}>
                  {isEvaluating ? 'Processing...' : evaluationResult?.evaluation_result?.students?.[index] ? 
                    ((evaluationResult.evaluation_result.students[index].total_score / evaluationResult.evaluation_result.students[index].max_total_score) >= 0.6 ? 'Passed' : 'Failed') : 
                    'Pending'
                  }
                </div>
                
                {/* Status */}
                <div style={{ 
                  fontSize: '13px', 
                  color: getStatusColor(evaluationResult?.evaluation_result?.students?.[index]?.status || 'unopened'),
                  fontWeight: 500
                }}>
                  {isEvaluating ? 'evaluating...' : getStatusText(evaluationResult?.evaluation_result?.students?.[index]?.status || 'unopened')}
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Back to Upload Button */}
        <div style={{ maxWidth: 1200, margin: "0 auto 2rem auto", width: '100%', textAlign: 'center' }}>
          <button
            onClick={() => setShowResults(false)}
            style={{
              padding: '12px 24px',
              borderRadius: '8px',
              border: '1px solid #dee2e6',
              background: '#fff',
              color: '#495057',
              fontWeight: 600,
              cursor: 'pointer',
              fontSize: '14px',
              marginRight: '12px'
            }}
          >
            ← Back to Upload
          </button>
          
          {/* Test button for debugging */}
          {evaluationResult && (
            <button
              onClick={() => {
                console.log('Test button clicked - opening review page for first student');
                handleStudentClick(0);
              }}
              style={{
                padding: '12px 24px',
                borderRadius: '8px',
                border: '1px solid #28a745',
                background: '#28a745',
                color: '#fff',
                fontWeight: 600,
                cursor: 'pointer',
                fontSize: '14px'
              }}
            >
              🧪 Test Review Page
            </button>
          )}
        </div>

        <SettingsModal open={showSettingsModal} onClose={() => setShowSettingsModal(false)} />
      </div>
    );
  }

  // Original upload interface
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
        {/* Left Section: Mark Scheme Upload */}
        <div style={{ flex: 1, maxWidth: 500, overflowY: 'auto', padding: '24px 0' }}>
          <div style={{ background: '#fff', borderRadius: 18, padding: '32px', boxShadow: '0 2px 7px #0002' }}>
            <h2 style={{ margin: 0, fontSize: 24, fontWeight: 600, color: '#1e40af' }}>Mark Scheme</h2>
            <p style={{ marginTop: 8, color: '#444', marginBottom: 20 }}>Upload your evaluation mark scheme first</p>
            
            <div style={{ marginBottom: '20px' }}>
              <label style={{ display: 'block', fontWeight: 600, marginBottom: '8px' }}>Mark Scheme File</label>
              <input
                type="file"
                accept=".pdf,.doc,.docx,.txt"
                onChange={(e) => setMarkSchemeFile(e.target.files?.[0] || null)}
                style={{
                  width: '100%',
                  padding: '8px',
                  border: '1px solid #ddd',
                  borderRadius: '4px'
                }}
              />
              {markSchemeFile && (
                <div style={{ marginTop: '8px', fontSize: '14px', color: '#555' }}>
                  Selected: {markSchemeFile.name}
                </div>
              )}
            </div>

            <button
              onClick={handleUploadMarkScheme}
              disabled={isUploadingMarkScheme || !markSchemeFile}
              style={{
                width: '100%',
                padding: '12px',
                borderRadius: '8px',
                border: 'none',
                background: '#2563eb',
                color: '#fff',
                fontWeight: 600,
                cursor: 'pointer',
                opacity: isUploadingMarkScheme || !markSchemeFile ? 0.5 : 1,
                marginBottom: '16px'
              }}
            >
              {isUploadingMarkScheme ? 'Uploading...' : 'Upload Mark Scheme'}
            </button>

            {markSchemeUploaded && (
              <div style={{ padding: '16px', background: '#f0f9ff', borderRadius: '8px', border: '1px solid #7dd3fc', marginBottom: '20px' }}>
                <div style={{ fontWeight: 600, color: '#0369a1', marginBottom: '4px' }}>✓ Mark Scheme Uploaded</div>
                <div style={{ fontSize: '14px', color: '#666' }}>Evaluation ID: {evaluationId}</div>
                <div style={{ fontSize: '14px', color: '#666' }}>Ready to upload answer sheets</div>
              </div>
            )}

            <div style={{ padding: '16px', background: '#f8f9fa', borderRadius: '8px', border: '1px solid #e9ecef' }}>
              <div style={{ fontWeight: 600, marginBottom: 8 }}>Tips</div>
              <div style={{ color: '#555', fontSize: 14 }}>
                <ul style={{ margin: 0, paddingLeft: '20px' }}>
                  <li>Mark scheme should contain questions, correct answers, and scoring criteria</li>
                  <li>Supported formats: PDF, DOC, DOCX, TXT</li>
                  <li>Upload mark scheme first, then answer sheets</li>
                  <li>AI evaluation may take several minutes depending on file size and number of students</li>
                </ul>
              </div>
            </div>
          </div>
        </div>

        {/* Right Section: Answer Sheets Upload */}
        <div style={{ flex: 1, maxWidth: 500, overflowY: 'auto', padding: '24px 0' }}>
          <div style={{ background: '#fff', borderRadius: 18, padding: '32px', boxShadow: '0 2px 7px #0002' }}>
            <h2 style={{ margin: 0, fontSize: 24, fontWeight: 600, color: '#1e40af' }}>Answer Sheets</h2>
            
            {markSchemeUploaded ? (
              <div style={{ marginTop: 20 }}>
                <div style={{ padding: '16px', background: '#f0f8ff', borderRadius: '8px', border: '1px solid #bfdbfe', marginBottom: '20px' }}>
                  <div style={{ fontWeight: 600, color: '#1e40af', marginBottom: '4px' }}>✓ Mark Scheme Ready</div>
                  <div style={{ fontSize: '14px', color: '#666' }}>You can now upload answer sheets</div>
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
                  disabled={isUploadingAnswerSheets || !answerSheetFiles || answerSheetFiles.length === 0}
                  style={{
                    width: '100%',
                    padding: '12px',
                    borderRadius: '8px',
                    border: 'none',
                    background: '#2563eb',
                    color: '#fff',
                    fontWeight: 600,
                    cursor: 'pointer',
                    opacity: isUploadingAnswerSheets || !answerSheetFiles || answerSheetFiles.length === 0 ? 0.5 : 1,
                    marginBottom: '16px'
                  }}
                >
                  {isUploadingAnswerSheets ? 'Uploading...' : 'Upload Answer Sheets'}
                </button>

            {answerSheetsUploaded && (
              <div style={{ padding: '16px', background: '#f0f9ff', borderRadius: '8px', border: '1px solid #7dd3fc', marginBottom: '20px' }}>
                <div style={{ fontWeight: 600, color: '#0369a1', marginBottom: '4px' }}>✓ Answer Sheets Uploaded</div>
                <div style={{ fontSize: '14px', color: '#666' }}>Ready to start evaluation</div>
              </div>
            )}

            <button
              onClick={handleEvaluate}
              disabled={isEvaluating || !answerSheetsUploaded}
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
                opacity: isEvaluating || !answerSheetsUploaded ? 0.5 : 1
              }}
            >
              {isEvaluating ? 'Evaluating...' : 'Evaluate →'}
            </button>
          </div>
        ) : (
          <div style={{ textAlign: 'center', padding: '40px 20px', color: '#666' }}>
            <div style={{ fontSize: '18px', marginBottom: '8px' }}>Upload mark scheme first</div>
            <div style={{ fontSize: '14px' }}>Complete the left side to upload answer sheets</div>
          </div>
        )}
      </div>
    </div>
  </div>

  <SettingsModal open={showSettingsModal} onClose={() => setShowSettingsModal(false)} />
</div>
  );
} 