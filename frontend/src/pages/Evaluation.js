import React, { useState, useEffect } from "react";
import { useNavigate, useLocation } from "react-router-dom";
import Header from "../components/header/Header";
import SettingsModal from "../components/SettingsModal";
import Modal from "../components/Modal";
import { evaluationService } from "../services/evaluation";
import { trackPendingEvaluation } from "../components/EvaluationCompletionWatcher";
import { buildStudentReportPdf, studentReportFileName, PASS_MARK } from "../utils/studentReportPdf";
import { FiEye, FiEdit2, FiMail, FiX, FiChevronLeft, FiChevronRight, FiDownload, FiAlertTriangle, FiUploadCloud, FiFileText, FiCheck, FiCheckCircle, FiLock, FiInfo, FiArrowRight } from "react-icons/fi";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import remarkBreaks from "remark-breaks";
import { latexToText } from "../utils/latexToText";
import { jsPDF } from "jspdf";

export default function Evaluation() {
  const navigate = useNavigate();
  const location = useLocation();
  const [isGridView] = useState(true);
  const [showSettingsModal, setShowSettingsModal] = useState(false);
  const [markSchemeFile, setMarkSchemeFile] = useState(null);
  const [answerSheetFiles, setAnswerSheetFiles] = useState([]);
  const [isUploadingMarkScheme, setIsUploadingMarkScheme] = useState(false);
  const [isUploadingAnswerSheets, setIsUploadingAnswerSheets] = useState(false);
  const [isEvaluating, setIsEvaluating] = useState(false);
  const [markSchemeUploaded, setMarkSchemeUploaded] = useState(false);
  const [answerSheetsUploaded, setAnswerSheetsUploaded] = useState(false);
  const [evaluationId, setEvaluationId] = useState(null);
  const [evaluationResult, setEvaluationResult] = useState(null);
  const [evaluationError, setEvaluationError] = useState(null); // Set when the backend reports the evaluation failed
  const [showResults, setShowResults] = useState(false);
  const [showReview, setShowReview] = useState(false);
  const [selectedStudentIndex, setSelectedStudentIndex] = useState(null);
  const [selectedQuestionIndex, setSelectedQuestionIndex] = useState(0);
  const [isEditing, setIsEditing] = useState(false);
  const [editedQuestionScores, setEditedQuestionScores] = useState([]);
  const [editedFeedback, setEditedFeedback] = useState([]); // Array for per-question feedback
  const [isSaving, setIsSaving] = useState(false); // Loading state for save operation
  const [forceUpdate, setForceUpdate] = useState(0); // Force re-render when status changes
  const [showFormatError, setShowFormatError] = useState(false); // Show format error modal
  const [formatErrorMessage, setFormatErrorMessage] = useState(''); // Format error message
  const [showSaveModal, setShowSaveModal] = useState(false); // Show save modal
  const [assetName, setAssetName] = useState(''); // Asset name for saving
  const [showNameInputScreen, setShowNameInputScreen] = useState(false); // Show name input screen
  const [showProcessStartedPopup, setShowProcessStartedPopup] = useState(false); // Show process started popup
  const [showReportModal, setShowReportModal] = useState(false); // Show report modal
  const [isLoadingReport, setIsLoadingReport] = useState(false); // Loading report
  const [reportStudentIndex, setReportStudentIndex] = useState(null); // Student shown in the report modal
  const [showDownloadSuccessModal, setShowDownloadSuccessModal] = useState(false); // Show download success popup
  const pendingSavePromiseRef = React.useRef(null);

  const evaluationInProgressRef = React.useRef(false);

  const courseId = localStorage.getItem('currentCourseId');
  const courseTitle = localStorage.getItem("currentCourseTitle") || "Course";
  const openedFromCardRef = React.useRef(false);



  const handleClose = () => {
    const maybeWaitForSave = async () => {
      try {
        if (pendingSavePromiseRef.current) {
          // Wait up to 1.5s to let the asset persist so the card shows on Dashboard
          await Promise.race([
            pendingSavePromiseRef.current,
            new Promise((resolve) => setTimeout(resolve, 1500))
          ]);
        }
      } catch { }
      navigate('/dashboard');
    };
    maybeWaitForSave();
  };
  // If opened with evaluation_id in query, load that evaluation and show results UI
  useEffect(() => {
    const params = new URLSearchParams(location.search);
    const evalId = params.get('evaluation_id');
    let cancelled = false;
    let pollTimer = null;
    if (evalId) {
      openedFromCardRef.current = true;
      setEvaluationId(evalId);
      setShowResults(true);
      // Fetch status and populate results; while still processing, check again so the
      // results appear without reopening the card
      const loadStatus = async () => {
        try {
          const status = await evaluationService.checkEvaluationStatus(evalId);
          if (cancelled) return;
          // If filenames are available, populate the table's file list to render rows
          if (Array.isArray(status.answer_sheet_filenames) && status.answer_sheet_filenames.length > 0) {
            const files = status.answer_sheet_filenames.map(name => ({ name }));
            setAnswerSheetFiles(files);
            setAnswerSheetsUploaded(true);
          }
          if (status.status === 'completed' && status.evaluation_result) {
            setEvaluationResult({ evaluation_id: evalId, evaluation_result: status.evaluation_result });
            setIsEvaluating(false);
          } else if (status.status === 'failed') {
            setEvaluationError(status.error || status.message || 'The evaluation process failed.');
            setIsEvaluating(false);
          } else {
            setIsEvaluating(true);
            pollTimer = setTimeout(loadStatus, 10000);
          }
        } catch (e) {
          if (cancelled) return;
          console.warn('Failed to load saved evaluation:', e.message);
          setIsEvaluating(false);
        }
      };
      loadStatus();
    }
    return () => {
      cancelled = true;
      clearTimeout(pollTimer);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [location.search]);



  // Force re-render when status changes
  useEffect(() => {
    // This effect will run whenever forceUpdate changes, forcing a re-render
  }, [forceUpdate]);

  const handleLogout = () => {
    localStorage.removeItem("token");
    navigate("/login");
  };

  const handleUploadMarkScheme = async (file = null) => {
    const fileToUpload = file || markSchemeFile;
    if (!fileToUpload) {
      return; // No need to show alert for auto-upload
    }

    // Prevent duplicate uploads of the same file
    if (isUploadingMarkScheme) {
      return;
    }

    try {
      setIsUploadingMarkScheme(true);
      const res = await evaluationService.uploadMarkScheme({
        courseId,
        markSchemeFile: fileToUpload
      });

      // Backend now returns the format check result
      setEvaluationId(res.evaluation_id);
      setMarkSchemeUploaded(true);

      // No popup for successful format - just proceed silently
      // The UI will show "✓ Mark Scheme Uploaded" status
    } catch (error) {
      // Check if it's a format error
      if (error.response?.data?.detail && error.response.data.detail.includes("not in the correct format")) {
        setFormatErrorMessage(error.response.data.detail);
        setShowFormatError(true);
      } else if (error.message && error.message.includes("not in the correct format")) {
        setFormatErrorMessage("Mark scheme is not in the correct format.");
        setShowFormatError(true);
      } else {
        alert(error.message || "Failed to upload mark scheme");
      }
    } finally {
      setIsUploadingMarkScheme(false);
    }
  };

  const handleReuploadMarkScheme = () => {
    setShowFormatError(false);
    setFormatErrorMessage('');
    // Reset the file input to allow re-selection
    const fileInput = document.querySelector('input[type="file"][accept=".pdf,.doc,.docx,.txt"]');
    if (fileInput) {
      fileInput.value = '';
    }
    setMarkSchemeFile(null);
  };

  const handleUploadAnswerSheets = async (files = null) => {
    if (!markSchemeUploaded || !evaluationId) {
      alert("Please upload mark scheme first.");
      return;
    }
    const filesToUpload = files || answerSheetFiles;
    if (!filesToUpload || filesToUpload.length === 0) {
      return; // No need to show alert for auto-upload
    }

    // Prevent duplicate uploads
    if (isUploadingAnswerSheets) {
      return;
    }

    try {
      setIsUploadingAnswerSheets(true);

      await evaluationService.uploadAnswerSheets({
        evaluationId,
        answerSheetFiles: filesToUpload
      });

      setAnswerSheetsUploaded(true);
      // No success popup - just proceed silently
      // The UI will show "✓ Answer Sheets Uploaded" status
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

    // Prevent duplicate evaluation calls
    if (evaluationInProgressRef.current || isEvaluating) {
      return;
    }

    // Show name input screen
    setShowNameInputScreen(true);
  };

  const handleStartEvaluation = async () => {
    if (!assetName.trim()) {
      alert('Please enter a name for the evaluation');
      return;
    }

    // Prevent duplicate evaluation calls
    if (evaluationInProgressRef.current || isEvaluating) {
      return;
    }

    // Show process started popup on the name screen
    setShowProcessStartedPopup(true);

    // Save the evaluation with the provided name
    const fileName = answerSheetFiles.length > 0
      ? `${answerSheetFiles.length}_students_evaluation_report`
      : 'evaluation_report';

    // Fire-and-forget save call
    try { localStorage.setItem('pendingEvaluationAssetName', assetName.trim()); } catch { }

    const savePromise = evaluationService.saveEvaluation(evaluationId, assetName.trim(), fileName)
      .then(() => {
        try {
          const el = document.createElement('div');
          el.textContent = 'Saved. You can access this in the Evaluation cards on the creation page.';
          el.style.position = 'fixed';
          el.style.bottom = '24px';
          el.style.right = '24px';
          el.style.background = '#10b981';
          el.style.color = '#fff';
          el.style.padding = '12px 16px';
          el.style.borderRadius = '8px';
          el.style.boxShadow = '0 4px 12px rgba(0,0,0,0.15)';
          el.style.zIndex = '2000';
          document.body.appendChild(el);
          setTimeout(() => { try { document.body.removeChild(el); } catch { } }, 2200);
        } catch { }
      })
      .catch((error) => {
        console.error('Error saving evaluation:', error);
        alert('Failed to save evaluation: ' + (error?.message || 'Unknown error'));
      })
      .finally(() => {
        try { localStorage.removeItem('pendingEvaluationAssetName'); } catch { }
      });
    pendingSavePromiseRef.current = savePromise;

    // Clear any previous evaluation tracking state
    evaluationService.clearCompletedEvaluations();

    evaluationInProgressRef.current = true;

    try {
      setEvaluationError(null);
      setIsEvaluating(true);

      // Start the evaluation in the background
      await evaluationService.evaluateFiles(evaluationId);

      // Evaluation started successfully
      evaluationInProgressRef.current = false;
      trackPendingEvaluation({ evaluationId, name: assetName.trim(), courseId, courseTitle });

    } catch (err) {
      console.error('Evaluation error:', err);
      evaluationInProgressRef.current = false;
      // A request timeout still means the evaluation is running in the background
      if ((err?.message || '').includes('Evaluation started successfully')) {
        trackPendingEvaluation({ evaluationId, name: assetName.trim(), courseId, courseTitle });
      }
      setIsEvaluating(false);
      setShowProcessStartedPopup(false);
      alert(err?.message || 'Failed to start evaluation');
    }
  };



  const handleStudentClick = async (studentIndex) => {


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

      if (!student) {
        alert('Student data is missing. Please try again.');
        return;
      }

      // Check if we have the required data structure for the review page
      // Backend provides 'answers' array with scores, not 'question_scores'
      // We need either question_scores OR answers array with scores
      const hasRequiredData = (
        (student.question_scores && Array.isArray(student.question_scores) && student.question_scores.length > 0) ||
        (student.answers && Array.isArray(student.answers) && student.answers.length > 0)
      );

      if (!hasRequiredData) {
        alert('The evaluation data structure is incomplete. Please contact support.');
        return;
      }

      // Update status to "opened" if it's currently "unopened"
      if (student.status === "unopened") {

        // Update status locally
        setEvaluationResult(prevState => {
          const updatedState = JSON.parse(JSON.stringify(prevState));
          updatedState.evaluation_result.students[studentIndex].status = "opened";
          return updatedState;
        });

        // Force a re-render by updating a separate state variable
        setForceUpdate(prev => prev + 1);
      }

      setSelectedStudentIndex(studentIndex);
      setShowReview(true);
      setSelectedQuestionIndex(0);
      setIsEditing(false);
      setEditedQuestionScores([]);
      setEditedFeedback([]);
    } catch (error) {
      console.error('Error accessing student data:', error);
      alert('Error accessing student data. Please try again.');
    }
  };



  const handleBackToResults = () => {
    setShowReview(false);
    setSelectedStudentIndex(null);
    setSelectedQuestionIndex(0);
    setIsEditing(false);
    setEditedQuestionScores([]);
    setEditedFeedback([]); // Reset feedback array
  };

  const handleEdit = () => {
    if (evaluationResult && selectedStudentIndex !== null) {
      const student = evaluationResult.evaluation_result.students[selectedStudentIndex];

      // Initialize with current values - use helper function to extract scores
      const currentScores = extractQuestionScores(student);
      if (currentScores.length > 0) {
        // Ensure 0 values are properly handled by converting to strings
        const scoresForEditing = currentScores.map(score => {
          if (score === 0) return '0';
          if (score === null || score === undefined) return '';
          return score.toString();
        });
        setEditedQuestionScores(scoresForEditing);
      } else {
        console.warn('No question scores available, initializing with empty array');
        setEditedQuestionScores([]);
      }

      // Get feedback for each question individually
      const currentFeedbackArray = [];
      if (student.answers && Array.isArray(student.answers)) {
        student.answers.forEach(answer => {
          currentFeedbackArray.push(answer.feedback || '');
        });
      }
      setEditedFeedback(currentFeedbackArray);

      setIsEditing(true);
    } else {
    }
  };

  const handleSave = async () => {
    if (!evaluationId || selectedStudentIndex === null) {
      return;
    }

    setIsSaving(true); // Start loading state

    try {
      // Validate question scores
      if (!Array.isArray(editedQuestionScores) || editedQuestionScores.length === 0) {
        alert('Question scores are required and must be an array');
        return;
      }


      // Ensure all scores are valid numbers and don't exceed max scores
      const validScores = editedQuestionScores.map((score, index) => {
        // Handle empty string or undefined values
        if (score === '' || score === undefined || score === null) {
          throw new Error(`Score at question ${index + 1} is required`);
        }

        const numScore = parseFloat(score);
        if (isNaN(numScore) || numScore < 0) {
          throw new Error(`Invalid score at question ${index + 1}: ${score}`);
        }

        // Check if score exceeds max score for this question
        const student = evaluationResult.evaluation_result.students[selectedStudentIndex];
        const maxScore = extractMaxScores(student)[index] || 10;
        if (numScore > maxScore) {
          throw new Error(`Score at question ${index + 1} (${numScore}) exceeds maximum score (${maxScore})`);
        }

        return numScore;
      });

      const totalScore = validScores.reduce((sum, score) => sum + score, 0);

      // Validate and clean the feedback for each question
      const cleanFeedbackArray = [];
      if (Array.isArray(editedFeedback)) {
        editedFeedback.forEach((feedback, index) => {
          const cleanFeedback = typeof feedback === 'string' ? feedback.trim() : '';
          cleanFeedbackArray.push(cleanFeedback);
        });
      }

      // Call the backend to update each question result individually
      // Backend expects individual question updates, not bulk updates
      const student = evaluationResult.evaluation_result.students[selectedStudentIndex];
      const fileId = student.file_id;


      if (!fileId) {
        throw new Error('Student file ID not found. Cannot update results.');
      }

      // Update each question score and feedback
      for (let i = 0; i < validScores.length; i++) {
        const questionFeedback = cleanFeedbackArray[i] || '';

        try {
          // Ensure feedback is not undefined or null
          const feedbackToSend = questionFeedback || '';

          await evaluationService.editQuestionResult({
            evaluationId,
            fileId,
            questionNumber: (i + 1).toString(),
            score: parseFloat(validScores[i]), // Convert to float as backend expects
            feedback: feedbackToSend
          });
        } catch (error) {
          console.error(`Failed to update question ${i + 1}:`, error);
          throw error; // Re-throw to stop the process
        }
      }


      // Update local state for immediate feedback
      const updatedEvaluationResult = { ...evaluationResult };
      const studentIndex = selectedStudentIndex;

      // Update the answers array with new scores and feedback
      updatedEvaluationResult.evaluation_result.students[studentIndex].answers =
        updatedEvaluationResult.evaluation_result.students[studentIndex].answers.map((answer, index) => ({
          ...answer,
          score: validScores[index], // Use the validated scores directly
          feedback: cleanFeedbackArray[index] || answer.feedback
        }));

      // Also update question_scores if it exists for backward compatibility
      if (updatedEvaluationResult.evaluation_result.students[studentIndex].question_scores) {
        updatedEvaluationResult.evaluation_result.students[studentIndex].question_scores = [...validScores];
      }

      // Update the student object
      updatedEvaluationResult.evaluation_result.students[studentIndex] = {
        ...updatedEvaluationResult.evaluation_result.students[studentIndex],
        total_score: totalScore,
        status: "modified"
      };

      // Force a re-render by creating a new object reference
      setEvaluationResult({ ...updatedEvaluationResult });
      setIsEditing(false);


      // Changes saved successfully - no popup needed

    } catch (error) {
      console.error('Error saving changes:', {
        message: error.message,
        detail: error.response?.data?.detail,
        status: error.response?.status
      });
      alert('Failed to save changes: ' + error.message);
    } finally {
      setIsSaving(false); // Reset loading state regardless of success/failure
    }
  };

  const handleCancelEdit = () => {
    setIsEditing(false);
    setEditedQuestionScores([]);
    setEditedFeedback([]); // Reset feedback array
  };

  const handleSaveEvaluation = async () => {
    if (!assetName.trim()) {
      alert('Please enter a name for the evaluation');
      return;
    }

    // Create a combined filename for the evaluation report
    const fileName = answerSheetFiles.length > 0
      ? `${answerSheetFiles.length}_students_evaluation_report`
      : 'evaluation_report';

    setIsSaving(true);
    // Optimistic, non-blocking save: close modal immediately and show toast
    setShowSaveModal(false);
    const nameToSave = assetName.trim();
    setAssetName('');
    try {
      const el = document.createElement('div');
      el.textContent = 'Saving... Your evaluation card will appear shortly.';
      el.style.position = 'fixed';
      el.style.bottom = '24px';
      el.style.right = '24px';
      el.style.background = '#2563eb';
      el.style.color = '#fff';
      el.style.padding = '12px 16px';
      el.style.borderRadius = '8px';
      el.style.boxShadow = '0 4px 12px rgba(0,0,0,0.15)';
      el.style.zIndex = '2000';
      document.body.appendChild(el);
      setTimeout(() => { try { document.body.removeChild(el); } catch { } }, 1800);
    } catch { }

    // Fire-and-forget save call; do not block UI
    // Mark a pending indicator for Dashboard to aggressively refresh assets
    try { localStorage.setItem('pendingEvaluationAssetName', nameToSave); } catch { }

    const savePromise = evaluationService.saveEvaluation(evaluationId, nameToSave, fileName)
      .then(() => {
        try {
          const el = document.createElement('div');
          el.textContent = 'Saved. You can access this in the Evaluation cards on the creation page.';
          el.style.position = 'fixed';
          el.style.bottom = '24px';
          el.style.right = '24px';
          el.style.background = '#10b981';
          el.style.color = '#fff';
          el.style.padding = '12px 16px';
          el.style.borderRadius = '8px';
          el.style.boxShadow = '0 4px 12px rgba(0,0,0,0.15)';
          el.style.zIndex = '2000';
          document.body.appendChild(el);
          setTimeout(() => { try { document.body.removeChild(el); } catch { } }, 2200);
        } catch { }
      })
      .catch((error) => {
        console.error('Error saving evaluation:', error);
        alert('Failed to save evaluation: ' + (error?.message || 'Unknown error'));
      })
      .finally(() => {
        setIsSaving(false);
        try { localStorage.removeItem('pendingEvaluationAssetName'); } catch { }
      });
    pendingSavePromiseRef.current = savePromise;
  };





  // Helper function to extract question scores from backend data structure
  const extractQuestionScores = (student) => {
    if (student.question_scores && Array.isArray(student.question_scores)) {
      return student.question_scores;
    }

    if (student.answers && Array.isArray(student.answers)) {
      // Backend provides answers array with scores, extract them
      return student.answers.map(answer => answer.score || 0);
    }

    return [];
  };

  // Helper function to get max scores from backend data structure
  // Section-wise numbering (Mettl answer sheets); old sheets have no section and use the list position
  const getQuestionSection = (answer) => (
    answer && answer.section != null && answer.section_question_number != null
      ? { section: answer.section, number: answer.section_question_number }
      : null
  );

  const extractMaxScores = (student) => {
    if (student.max_scores && Array.isArray(student.max_scores)) {
      return student.max_scores;
    }

    if (student.answers && Array.isArray(student.answers)) {
      // Backend provides max_score in each answer
      return student.answers.map(answer => answer.max_score || 0);
    }

    return [];
  };

  const handleViewStudentReport = async (studentIndex) => {
    if (!evaluationId) {
      alert('Evaluation ID not found');
      return;
    }

    // The modal and its PDF are built from the loaded results
    setReportStudentIndex(studentIndex);
    setShowReportModal(true);
  };

  const handleDownloadReport = () => {
    const student = evaluationResult?.evaluation_result?.students?.[reportStudentIndex];
    if (!student) {
      alert('No report to download');
      return;
    }

    try {
      const name = answerSheetFiles[reportStudentIndex]?.name || `Student ${reportStudentIndex + 1}`;
      const doc = buildStudentReportPdf(jsPDF, { student, name });
      doc.save(studentReportFileName(name));
    } catch (error) {
      console.error('Error generating PDF:', error);
      alert('Failed to generate PDF. Please try again.');
    }
  };

  const handleDownloadCSV = async () => {
    if (!evaluationId) {
      alert('No evaluation available to download');
      return;
    }

    try {
      setIsLoadingReport(true);
      await evaluationService.downloadReportCSV(evaluationId);
      setShowDownloadSuccessModal(true);
      // Auto-hide popup after 3 seconds
      setTimeout(() => {
        setShowDownloadSuccessModal(false);
      }, 3000);
    } catch (error) {
      console.error('Error downloading CSV:', error);
      alert(error.message || 'Failed to download CSV report. Please try again.');
    } finally {
      setIsLoadingReport(false);
    }
  };

  // Shared styles for the upload and results views, matching the Dashboard card theme
  const evalCardStyle = { background: '#fff', borderRadius: 14, padding: '24px 26px', border: '1px solid #e8ecf2', boxShadow: '0 1px 3px rgba(15, 23, 42, 0.06)', boxSizing: 'border-box', display: 'flex', flexDirection: 'column', gap: 18, minHeight: 420 };
  const stepBadgeStyle = (done, muted = false) => ({ width: 32, height: 32, borderRadius: '50%', flexShrink: 0, display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 14, fontWeight: 700, background: done ? '#ecfdf5' : muted ? '#f1f5f9' : '#eff4ff', color: done ? '#059669' : muted ? '#94a3b8' : '#2563eb' });
  const dropzoneStyle = (busy) => ({ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 6, padding: '26px 16px', border: '1.5px dashed #c7d2fe', borderRadius: 12, background: '#f8faff', cursor: busy ? 'not-allowed' : 'pointer', opacity: busy ? 0.6 : 1, textAlign: 'center', transition: 'background 0.15s ease' });
  const fileRowStyle = { display: 'flex', alignItems: 'center', gap: 8, padding: '8px 12px', border: '1px solid #e8ecf2', borderRadius: 8, background: '#fff', fontSize: 13, color: '#374151' };
  const statusStyle = (kind) => ({ display: 'flex', alignItems: 'flex-start', gap: 10, padding: '12px 14px', borderRadius: 10, fontSize: 14, ...(kind === 'success' ? { background: '#ecfdf5', border: '1px solid #a7f3d0', color: '#047857' } : { background: '#eff4ff', border: '1px solid #c7d2fe', color: '#1d4ed8', alignItems: 'center', fontWeight: 600 }) });
  const evalSpinnerStyle = { width: 14, height: 14, border: '2px solid #bfdbfe', borderTopColor: '#2563eb', borderRadius: '50%', animation: 'cc-spin 0.8s linear infinite', flexShrink: 0 };

  const statTileStyle = { background: '#fff', borderRadius: 14, padding: '16px 20px', border: '1px solid #e8ecf2', boxShadow: '0 1px 3px rgba(15, 23, 42, 0.06)' };
  const statLabelStyle = { fontSize: 13, fontWeight: 500, color: '#6b7280' };
  const statValueStyle = { fontSize: 26, fontWeight: 700, color: '#111827', marginTop: 4 };
  const resultsGridColumns = 'minmax(0, 2.4fr) 1.2fr 1fr 1fr 72px';
  const pillStyle = (kind) => {
    const palette = {
      success: { background: '#ecfdf5', color: '#047857' },
      danger: { background: '#fef2f2', color: '#b91c1c' },
      warning: { background: '#fff7ed', color: '#c2410c' },
      neutral: { background: '#f1f5f9', color: '#64748b' }
    };
    return { display: 'inline-block', padding: '3px 10px', borderRadius: 999, fontSize: 12, fontWeight: 600, ...palette[kind] };
  };
  // Colour a question's score: full marks green, partial amber, zero red
  const scoreToneStyle = (score, max) => {
    if (!max) return { background: '#f1f5f9', color: '#64748b' };
    if (score >= max) return { background: '#ecfdf5', color: '#047857' };
    if (score > 0) return { background: '#fff7ed', color: '#c2410c' };
    return { background: '#fef2f2', color: '#b91c1c' };
  };
  // Structured answers (tables/images) are stored as a JSON array string; render them as Markdown
  const formatStudentAnswer = (raw) => {
    if (typeof raw !== 'string' || !raw.trim()) return '';
    if (!raw.trim().startsWith('[')) return raw;
    try {
      const items = JSON.parse(raw);
      if (!Array.isArray(items)) return raw;
      return items.map(item => {
        if (item?.type === 'text') return item.content || '';
        if (item?.type === 'table' && Array.isArray(item.content) && item.content.length) {
          const rows = item.content.map(r => (Array.isArray(r) ? r : []).map(c => String(c ?? '').replace(/\|/g, '\\|').replace(/\n/g, ' ')));
          const width = Math.max(...rows.map(r => r.length));
          const pad = r => [...r, ...Array(width - r.length).fill('')];
          const [head, ...body] = rows.map(pad);
          return [`| ${head.join(' | ')} |`, `| ${head.map(() => '---').join(' | ')} |`, ...body.map(r => `| ${r.join(' | ')} |`)].join('\n');
        }
        if (item?.type === 'image') return '_[Image attached to this answer]_';
        return '';
      }).filter(Boolean).join('\n\n');
    } catch {
      return raw;
    }
  };
  // Question text from the answer sheet, noting any question images that were sent to the model
  const formatQuestionText = (answer) => {
    const text = answer?.question_text || '';
    const imageCount = Array.isArray(answer?.question_images) ? answer.question_images.length : 0;
    if (!imageCount) return text;
    const note = `_[${imageCount === 1 ? 'Image' : `${imageCount} images`} attached to this question]_`;
    return text ? `${text}\n\n${note}` : note;
  };
  const reportMdComponents = (codeBg = '#1f2937') => ({
    p: ({ node, ...props }) => <p style={{ margin: '0 0 8px 0', lineHeight: 1.65 }} {...props} />,
    strong: ({ node, ...props }) => <strong style={{ fontWeight: 600, color: '#1f2937' }} {...props} />,
    ul: ({ node, ...props }) => <ul style={{ margin: '0 0 8px 0', paddingLeft: 20 }} {...props} />,
    ol: ({ node, ...props }) => <ol style={{ margin: '0 0 8px 0', paddingLeft: 20 }} {...props} />,
    li: ({ node, ...props }) => <li style={{ marginBottom: 4 }} {...props} />,
    pre: ({ node, ...props }) => <pre style={{ margin: '4px 0 8px 0', background: codeBg, borderRadius: 8, overflow: 'auto' }} {...props} />,
    code: ({ node, inline, ...props }) =>
      inline ?
        <code style={{ background: '#eef2f7', padding: '1px 5px', borderRadius: 4, fontSize: 13, fontFamily: 'monospace' }} {...props} /> :
        <code style={{ display: 'block', color: '#f3f4f6', padding: 12, fontSize: 13, fontFamily: 'monospace', whiteSpace: 'pre' }} {...props} />,
    table: ({ node, ...props }) => <table style={{ borderCollapse: 'collapse', margin: '4px 0 8px 0', fontSize: 13 }} {...props} />,
    th: ({ node, ...props }) => <th style={{ border: '1px solid #e2e8f0', padding: '6px 10px', background: '#f8fafc', textAlign: 'left', fontWeight: 600 }} {...props} />,
    td: ({ node, ...props }) => <td style={{ border: '1px solid #e2e8f0', padding: '6px 10px' }} {...props} />
  });
  // Summary numbers for the results tiles (only once grading has finished)
  const resultStats = (() => {
    const students = (evaluationResult?.evaluation_result?.students || []).filter(s => !s?.skipped);
    if (students.length === 0) return null;
    const pcts = students.map(s => (s.max_total_score ? s.total_score / s.max_total_score : 0));
    return {
      total: students.length,
      passed: pcts.filter(p => p >= PASS_MARK).length,
      avgPct: Math.round((pcts.reduce((a, b) => a + b, 0) / pcts.length) * 100)
    };
  })();

  // If showing review page, display the review interface
  if (showReview && selectedStudentIndex !== null && evaluationResult) {
    // Add safety checks for evaluation data
    if (!evaluationResult.evaluation_result || !evaluationResult.evaluation_result.students) {
      console.error('Missing evaluation data:', evaluationResult);
      return (
        <div style={{ height: '100vh', display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
          {/* Header removed for review page - cleaner interface */}
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

    if (!student) {
      console.error('Student data not found for index:', selectedStudentIndex);
      return (
        <div style={{ height: '100vh', display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
          {/* Header removed for review page - cleaner interface */}
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
    const questionScores = extractQuestionScores(student);
    const maxScores = extractMaxScores(student);
    const questionCount = questionScores.length;
    const currentScore = questionScores[selectedQuestionIndex] || 0;
    const currentMax = maxScores[selectedQuestionIndex];
    const currentSectionInfo = getQuestionSection(student?.answers?.[selectedQuestionIndex]);
    const totalPct = student.max_total_score ? student.total_score / student.max_total_score : null;
    // Colour a question's score: full marks green, partial amber, zero red
    const scoreTone = (score, max) => {
      if (!max) return { background: '#f1f5f9', color: '#64748b' };
      if (score >= max) return { background: '#ecfdf5', color: '#047857' };
      if (score > 0) return { background: '#fff7ed', color: '#c2410c' };
      return { background: '#fef2f2', color: '#b91c1c' };
    };
    // Group consecutive questions by section for the left nav, with per-section subtotals
    const questionGroups = [];
    questionScores.forEach((score, index) => {
      const sectionInfo = getQuestionSection(student?.answers?.[index]);
      const section = sectionInfo ? sectionInfo.section : null;
      let group = questionGroups[questionGroups.length - 1];
      if (!group || group.section !== section) {
        group = { section, score: 0, max: 0, items: [] };
        questionGroups.push(group);
      }
      const max = maxScores[index];
      group.score += Number(score) || 0;
      group.max += Number(max) || 0;
      group.items.push({ index, score, max, number: sectionInfo ? sectionInfo.number : index + 1 });
    });
    questionGroups.forEach(group => {
      group.score = Math.round(group.score * 100) / 100;
      group.max = Math.round(group.max * 100) / 100;
    });
    const reviewMdComponents = (inlineCodeBg) => ({
      p: ({ node, ...props }) => <p style={{ margin: '0 0 10px 0', lineHeight: '1.65' }} {...props} />,
      strong: ({ node, ...props }) => <strong style={{ fontWeight: 600, color: '#1f2937' }} {...props} />,
      ul: ({ node, ...props }) => <ul style={{ marginBottom: 10, paddingLeft: 20 }} {...props} />,
      ol: ({ node, ...props }) => <ol style={{ marginBottom: 10, paddingLeft: 20 }} {...props} />,
      li: ({ node, ...props }) => <li style={{ marginBottom: 6 }} {...props} />,
      code: ({ node, inline, ...props }) =>
        inline ?
          <code style={{ background: inlineCodeBg, padding: '2px 4px', borderRadius: 3, fontSize: 13, fontFamily: 'monospace' }} {...props} /> :
          <code style={{ display: 'block', background: '#1f2937', color: '#f3f4f6', padding: 8, borderRadius: 4, overflow: 'auto', fontSize: 13, fontFamily: 'monospace' }} {...props} />
    });
    const reviewPanelStyle = { background: '#fff', borderRadius: 14, border: '1px solid #e8ecf2', boxShadow: '0 1px 3px rgba(15, 23, 42, 0.06)', boxSizing: 'border-box' };
    const sectionLabelStyle = { margin: '0 0 8px 0', fontSize: 12, fontWeight: 600, color: '#6b7280', textTransform: 'uppercase', letterSpacing: '0.04em' };
    const navBtnStyle = (disabled) => ({ width: 34, height: 34, borderRadius: 8, border: '1px solid #e8ecf2', background: '#fff', color: disabled ? '#cbd5e1' : '#374151', cursor: disabled ? 'not-allowed' : 'pointer', display: 'inline-flex', alignItems: 'center', justifyContent: 'center' });

    return (
      <div style={{ height: '100vh', display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
        <Header
          title={"Review - " + (answerSheetFiles[selectedStudentIndex]?.name || `Student ${selectedStudentIndex + 1}`)}
          onLogout={handleLogout}
          onSettings={null}
          onExport={null}
          onGridView={null}
          onListView={null}
          isGridView={isGridView}
          onBack={handleBackToResults}
          backLabel="Close"
        />

        {/* Breadcrumb */}
        <div style={{ maxWidth: 1680, padding: '0 32px', boxSizing: 'border-box', margin: '20px auto 4px auto', width: '100%' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 14, fontWeight: 500, minWidth: 0 }}>
            <span style={{ color: '#2563eb', cursor: 'pointer', flexShrink: 0 }} onClick={() => navigate('/courses')}>Courses</span>
            <span style={{ color: '#9ca3af' }}>/</span>
            <span style={{ color: '#2563eb', cursor: 'pointer', flexShrink: 0 }} onClick={() => navigate('/dashboard')}>{courseTitle}</span>
            <span style={{ color: '#9ca3af' }}>/</span>
            <span style={{ color: '#2563eb', cursor: 'pointer', flexShrink: 0 }} onClick={handleBackToResults}>Evaluation</span>
            <span style={{ color: '#9ca3af' }}>/</span>
            <span style={{ color: '#6b7280', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>Review</span>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 12, flexWrap: 'wrap', marginTop: 6 }}>
            <h1 style={{ margin: 0, fontSize: 24, fontWeight: 700, color: '#111827', minWidth: 0, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }} title={fileName}>{fileName}</h1>
            {totalPct !== null && (
              <span style={{ fontSize: 14, fontWeight: 600, color: '#374151' }}>
                {student.total_score}<span style={{ color: '#94a3b8', fontWeight: 500 }}>/{student.max_total_score}</span>
                <span style={{ marginLeft: 4, fontSize: 13, fontWeight: 500, color: '#6b7280' }}>({Math.round(totalPct * 100)}%)</span>
              </span>
            )}
            {totalPct !== null && (
              <span style={pillStyle(totalPct >= PASS_MARK ? 'success' : 'danger')}>{totalPct >= PASS_MARK ? 'Passed' : 'Failed'}</span>
            )}
            {student.status === 'modified' && <span style={pillStyle('warning')}>Modified</span>}
          </div>
        </div>

        {/* Review Content */}
        <div style={{ flex: 1, minHeight: 0, display: 'flex', gap: 20, width: '100%', maxWidth: 1680, margin: '0 auto', padding: '16px 32px 24px', boxSizing: 'border-box' }}>
          {/* Left Panel: Question Navigation */}
          <div style={{ ...reviewPanelStyle, width: 280, flexShrink: 0, display: 'flex', flexDirection: 'column', minHeight: 0 }}>
            <div style={{ padding: '16px 18px 10px', display: 'flex', alignItems: 'center', gap: 8 }}>
              <h3 style={{ margin: 0, fontSize: 16, fontWeight: 700, color: '#111827' }}>Questions</h3>
              {questionCount > 0 && (
                <span style={{ fontSize: 12, fontWeight: 600, color: '#2563eb', background: '#eff4ff', borderRadius: 999, padding: '2px 8px' }}>{questionCount}</span>
              )}
            </div>
            <div className="cc-scroll" style={{ flex: 1, minHeight: 0, overflowY: 'auto', padding: '0 10px 12px' }}>
              {questionCount > 0 ? (
                questionGroups.map((group, groupIndex) => {
                  const groupHasActive = group.items.some(item => item.index === selectedQuestionIndex);
                  const groupPct = group.max > 0 ? Math.min(1, group.score / group.max) : 0;
                  const groupBarColor = group.max > 0 && group.score >= group.max ? '#10b981' : group.score > 0 ? '#f59e0b' : '#ef4444';
                  return (
                    <div
                      key={group.section ?? `ungrouped-${groupIndex}`}
                      style={{
                        marginBottom: 10,
                        borderRadius: 10,
                        border: `1px solid ${groupHasActive ? '#c7d7fe' : '#eef1f6'}`,
                        background: '#fff'
                      }}
                    >
                      {group.section != null && (
                        <div
                          style={{
                            position: 'sticky',
                            top: 0,
                            zIndex: 1,
                            padding: '10px 12px 8px',
                            background: groupHasActive ? '#f5f8ff' : '#f8fafc',
                            borderBottom: '1px solid #eef1f6',
                            borderRadius: '10px 10px 0 0'
                          }}
                        >
                          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 8 }}>
                            <span style={{ fontSize: 12, fontWeight: 700, color: groupHasActive ? '#1d4ed8' : '#334155', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
                              Section {group.section}
                              <span style={{ marginLeft: 6, fontWeight: 500, color: '#94a3b8', textTransform: 'none', letterSpacing: 0 }}>
                                · {group.items.length} {group.items.length === 1 ? 'question' : 'questions'}
                              </span>
                            </span>
                            {group.max > 0 && (
                              <span style={{ fontSize: 12, fontWeight: 700, color: '#334155', whiteSpace: 'nowrap' }}>
                                {group.score}<span style={{ color: '#94a3b8', fontWeight: 500 }}>/{group.max}</span>
                              </span>
                            )}
                          </div>
                          {group.max > 0 && (
                            <div style={{ marginTop: 6, height: 4, borderRadius: 999, background: '#e2e8f0', overflow: 'hidden' }}>
                              <div style={{ width: `${groupPct * 100}%`, height: '100%', borderRadius: 999, background: groupBarColor, transition: 'width 0.2s ease' }} />
                            </div>
                          )}
                        </div>
                      )}
                      <div style={{ padding: 4 }}>
                        {group.items.map(({ index, score, max, number }) => {
                          const isActive = selectedQuestionIndex === index;
                          const tone = scoreTone(score, max);
                          return (
                            <div
                              key={index}
                              className={isActive ? undefined : 'cc-kb-row'}
                              style={{
                                display: 'flex',
                                alignItems: 'center',
                                gap: 10,
                                padding: '8px 10px',
                                borderRadius: 7,
                                background: isActive ? '#eff4ff' : 'transparent',
                                boxShadow: isActive ? 'inset 3px 0 0 #2563eb' : 'none',
                                cursor: 'pointer'
                              }}
                              onClick={() => setSelectedQuestionIndex(index)}
                            >
                              <span style={{ width: 8, height: 8, borderRadius: '50%', flexShrink: 0, background: tone.color, opacity: 0.85 }} />
                              <span style={{ flex: 1, minWidth: 0, fontSize: 14, fontWeight: isActive ? 600 : 500, color: isActive ? '#1d4ed8' : '#374151' }}>
                                Question {number}
                              </span>
                              <span style={{ fontSize: 12, fontWeight: 600, borderRadius: 999, padding: '2px 8px', ...tone }}>
                                {score}/{max || (score > 0 ? score : '?')}
                              </span>
                            </div>
                          );
                        })}
                      </div>
                    </div>
                  );
                })
              ) : (
                <div style={{ padding: '16px', textAlign: 'center', fontSize: 14, color: '#94a3b8' }}>
                  No question scores available
                </div>
              )}
            </div>
          </div>

          {/* Center Panel: Question Details */}
          <div className="cc-scroll" style={{ ...reviewPanelStyle, flex: 1, minWidth: 0, overflowY: 'auto', padding: '22px 26px' }}>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 12, marginBottom: 20 }}>
              <h3 style={{ margin: 0, fontSize: 19, fontWeight: 700, color: '#111827' }}>
                {currentSectionInfo
                  ? `Section ${currentSectionInfo.section} · Question ${currentSectionInfo.number}`
                  : `Question ${selectedQuestionIndex + 1}`}
                {questionCount > 0 && (
                  <span style={{ fontSize: 14, fontWeight: 500, color: '#94a3b8' }}>
                    {currentSectionInfo ? ` (${selectedQuestionIndex + 1} of ${questionCount})` : ` of ${questionCount}`}
                  </span>
                )}
              </h3>
              <div style={{ display: 'flex', gap: 6 }}>
                <button
                  title="Previous question"
                  disabled={selectedQuestionIndex <= 0}
                  onClick={() => setSelectedQuestionIndex(i => Math.max(0, i - 1))}
                  style={navBtnStyle(selectedQuestionIndex <= 0)}
                >
                  <FiChevronLeft />
                </button>
                <button
                  title="Next question"
                  disabled={selectedQuestionIndex >= questionCount - 1}
                  onClick={() => setSelectedQuestionIndex(i => Math.min(questionCount - 1, i + 1))}
                  style={navBtnStyle(selectedQuestionIndex >= questionCount - 1)}
                >
                  <FiChevronRight />
                </button>
              </div>
            </div>

            <div style={{ marginBottom: 22 }}>
              <h4 style={sectionLabelStyle}>Question</h4>
              <div style={{ padding: '14px 16px', background: '#f8fafc', borderRadius: 10, border: '1px solid #e8ecf2', fontSize: 15, color: '#1f2937' }}>
                <ReactMarkdown remarkPlugins={[remarkGfm, remarkBreaks]} components={reviewMdComponents('#e5e7eb')}>
                  {latexToText(formatQuestionText(student?.answers?.[selectedQuestionIndex]) || 'Question text not available')}
                </ReactMarkdown>
              </div>
            </div>

            <div>
              <h4 style={sectionLabelStyle}>Student Answer</h4>
              <div style={{ padding: '14px 16px', background: '#f5f8ff', borderRadius: 10, border: '1px solid #dbe5fb', fontSize: 15, color: '#1f2937' }}>
                <ReactMarkdown remarkPlugins={[remarkGfm, remarkBreaks]} components={reviewMdComponents('#dbeafe')}>
                  {latexToText(formatStudentAnswer(student?.answers?.[selectedQuestionIndex]?.student_answer) || 'Student answer not available')}
                </ReactMarkdown>
              </div>
            </div>
          </div>

          {/* Right Panel: Marks & Feedback Editor */}
          <div className="cc-scroll" style={{ ...reviewPanelStyle, width: 400, flexShrink: 0, overflowY: 'auto', padding: '22px 24px' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 8, marginBottom: 20 }}>
              <h3 style={{ margin: 0, fontSize: 17, fontWeight: 700, color: '#111827' }}>Marks & Feedback</h3>
              {!isEditing ? (
                <button
                  className="cc-section-btn"
                  style={{ padding: '6px 12px', borderRadius: 8, border: '1px solid #d6dde8', background: '#fff', color: '#374151', fontWeight: 600, cursor: 'pointer', fontSize: 13, display: 'inline-flex', alignItems: 'center', gap: 6 }}
                  onClick={handleEdit}
                >
                  <FiEdit2 size={13} /> Edit
                </button>
              ) : (
                <div style={{ display: 'flex', gap: 6 }}>
                  <button
                    style={{ padding: '6px 12px', borderRadius: 8, border: '1px solid #d6dde8', background: '#fff', color: '#4b5563', fontWeight: 600, cursor: 'pointer', fontSize: 13 }}
                    onClick={handleCancelEdit}
                  >
                    Cancel
                  </button>
                  <button
                    disabled={isSaving}
                    style={{ padding: '6px 14px', borderRadius: 8, border: 'none', background: '#2563eb', color: '#fff', fontWeight: 600, cursor: isSaving ? 'not-allowed' : 'pointer', fontSize: 13, opacity: isSaving ? 0.6 : 1 }}
                    onClick={handleSave}
                  >
                    {isSaving ? 'Saving...' : 'Save'}
                  </button>
                </div>
              )}
            </div>

            <div style={{ marginBottom: 22 }}>
              <h4 style={sectionLabelStyle}>Marks obtained</h4>
              {isEditing ? (
                <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                  <input
                    type="number"
                    min="0"
                    max={currentMax || 10}
                    step="0.1"
                    value={editedQuestionScores[selectedQuestionIndex] ?? ''}
                    onChange={(e) => {
                      const inputValue = e.target.value;
                      const maxScore = currentMax || 10;

                      // Always allow the input to be updated first
                      const newScores = [...editedQuestionScores];
                      newScores[selectedQuestionIndex] = inputValue;
                      setEditedQuestionScores(newScores);

                      // Then validate and show any errors (but don't block the input)
                      if (inputValue === '') {
                        return; // Allow empty input
                      }

                      // Check for more than one decimal place
                      if (inputValue.includes('.') && inputValue.split('.')[1]?.length > 1) {
                        return; // Don't allow more than one decimal place
                      }

                      // Validate the number
                      const numValue = parseFloat(inputValue);
                      if (isNaN(numValue) || numValue < 0) {
                        return; // Don't allow negative numbers or invalid input
                      }

                      if (numValue > maxScore) {
                        return; // Don't allow score higher than max
                      }
                    }}
                    style={{
                      width: 90,
                      padding: '8px 10px',
                      border: '1px solid #c7d2fe',
                      borderRadius: 8,
                      fontSize: 18,
                      fontWeight: 700,
                      textAlign: 'center',
                      color: '#111827',
                      outline: 'none',
                      boxSizing: 'border-box'
                    }}
                  />
                  <span style={{ fontSize: 15, color: '#6b7280' }}>
                    of {currentMax || '?'}
                  </span>
                </div>
              ) : (
                <>
                  <div style={{ display: 'flex', alignItems: 'baseline', gap: 6 }}>
                    <span style={{ fontSize: 34, fontWeight: 700, color: '#111827', lineHeight: 1 }}>{currentScore}</span>
                    <span style={{ fontSize: 16, fontWeight: 500, color: '#94a3b8' }}>/ {currentMax || '?'}</span>
                  </div>
                  {currentMax > 0 && (
                    <div style={{ marginTop: 10, height: 6, background: '#f1f5f9', borderRadius: 999, overflow: 'hidden' }}>
                      <div style={{ height: '100%', width: `${Math.min(100, Math.round((currentScore / currentMax) * 100))}%`, background: scoreTone(currentScore, currentMax).color, borderRadius: 999, transition: 'width 0.2s ease' }} />
                    </div>
                  )}
                </>
              )}
            </div>

            <div>
              <h4 style={sectionLabelStyle}>Feedback</h4>
              {isEditing ? (
                <textarea
                  value={editedFeedback[selectedQuestionIndex] || ''}
                  onChange={(e) => {
                    const newFeedbackArray = [...editedFeedback];
                    newFeedbackArray[selectedQuestionIndex] = e.target.value;
                    setEditedFeedback(newFeedbackArray);
                  }}
                  placeholder="Enter feedback for this question..."
                  style={{
                    width: '100%',
                    minHeight: 140,
                    padding: '12px',
                    border: '1px solid #c7d2fe',
                    borderRadius: 10,
                    fontSize: 14,
                    lineHeight: '1.55',
                    resize: 'vertical',
                    fontFamily: 'inherit',
                    outline: 'none',
                    boxSizing: 'border-box'
                  }}
                />
              ) : (
                <div style={{ padding: '14px 16px', background: '#f8fafc', borderRadius: 10, border: '1px solid #e8ecf2', fontSize: 14, color: '#374151' }}>
                  <ReactMarkdown remarkPlugins={[remarkGfm, remarkBreaks]} components={reviewMdComponents('#e5e7eb')}>
                    {latexToText(student?.answers?.[selectedQuestionIndex]?.feedback || 'No feedback available')}
                  </ReactMarkdown>
                </div>
              )}
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
          title="Evaluation Results"
          onLogout={handleLogout}
          onSettings={null}
          onExport={null}
          onGridView={null}
          onListView={null}
          isGridView={isGridView}
          onBack={handleClose}
          onSave={showResults && evaluationId && !openedFromCardRef.current ? () => setShowSaveModal(true) : null}
          saveLabel="Save Evaluation"
          backLabel="Close"
        />

        {/* Breadcrumb */}
        <div style={{ maxWidth: 1680, padding: '0 32px', boxSizing: 'border-box', margin: '20px auto 4px auto', width: '100%' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 14, fontWeight: 500 }}>
            <span style={{ color: '#2563eb', cursor: 'pointer' }} onClick={() => navigate('/courses')}>Courses</span>
            <span style={{ color: '#9ca3af' }}>/</span>
            <span style={{ color: '#2563eb', cursor: 'pointer' }} onClick={() => navigate('/dashboard')}>{courseTitle}</span>
            <span style={{ color: '#9ca3af' }}>/</span>
            <span style={{ color: '#6b7280' }}>Evaluation</span>
          </div>
          <div style={{ display: 'flex', alignItems: 'flex-end', justifyContent: 'space-between', gap: 16, flexWrap: 'wrap' }}>
            <div>
              <h1 style={{ margin: '6px 0 0 0', fontSize: 26, fontWeight: 700, color: '#111827' }}>Evaluation Results</h1>
              <div style={{ fontSize: 14, color: '#6b7280', marginTop: 2 }}>
                {isEvaluating ? "AI is grading the answer sheets. You'll get an email once it's complete." : 'Click an answer sheet to review and adjust marks.'}
              </div>
            </div>

            {/* Action Buttons */}
            {evaluationResult && (
              <button
                className="cc-section-btn"
                onClick={handleDownloadCSV}
                disabled={isLoadingReport}
                style={{
                  padding: '9px 16px',
                  borderRadius: 10,
                  border: '1px solid #d6dde8',
                  background: '#fff',
                  color: '#374151',
                  fontWeight: 600,
                  fontSize: 14,
                  cursor: isLoadingReport ? 'not-allowed' : 'pointer',
                  opacity: isLoadingReport ? 0.6 : 1,
                  display: 'flex',
                  alignItems: 'center',
                  gap: 8,
                  transition: 'all 0.15s ease'
                }}
              >
                <FiDownload />
                {isLoadingReport ? 'Downloading...' : 'Download CSV'}
              </button>
            )}
          </div>
        </div>

        <div className="cc-scroll" style={{ flex: 1, minHeight: 0, overflowY: 'auto', width: '100%', maxWidth: 1680, margin: '0 auto', padding: '20px 32px 32px', boxSizing: 'border-box' }}>
          {/* Evaluation failed banner */}
          {evaluationError && (
            <div style={{ background: '#fef2f2', border: '1px solid #fecaca', borderRadius: 12, padding: '14px 18px', display: 'flex', alignItems: 'flex-start', gap: 12, marginBottom: 20 }}>
              <FiAlertTriangle style={{ fontSize: 20, color: '#dc2626', flexShrink: 0, marginTop: 2 }} />
              <div>
                <div style={{ fontWeight: 700, color: '#b91c1c', fontSize: 15, marginBottom: 4 }}>
                  Evaluation failed — the process has stopped
                </div>
                <div style={{ color: '#7f1d1d', fontSize: 14, lineHeight: 1.6 }}>
                  {evaluationError}
                </div>
                <div style={{ color: '#991b1b', fontSize: 13, marginTop: 6 }}>
                  No answer sheets were evaluated. Please fix the issue above and start a new evaluation.
                </div>
              </div>
            </div>
          )}

          {/* Sheets that could not be read or graded, and graded sheets that may be incomplete */}
          {(evaluationResult?.evaluation_result?.skipped_sheets?.length > 0 || evaluationResult?.evaluation_result?.warnings?.length > 0) && (
            <div style={{ marginBottom: 20, padding: '14px 18px', borderRadius: 12, background: '#fffbeb', border: '1px solid #fde68a' }}>
              {evaluationResult.evaluation_result.skipped_sheets?.length > 0 && (
                <>
                  <div style={{ fontWeight: 700, color: '#92400e', fontSize: 14, marginBottom: 6 }}>
                    {evaluationResult.evaluation_result.skipped_sheets.length} answer sheet(s) were not evaluated
                  </div>
                  {evaluationResult.evaluation_result.skipped_sheets.map(s => (
                    <div key={s.file_id} style={{ color: '#78350f', fontSize: 13, lineHeight: 1.6 }}>
                      <strong>{s.filename || s.file_id}</strong>: {s.error}
                    </div>
                  ))}
                </>
              )}
              {evaluationResult.evaluation_result.warnings?.length > 0 && (
                <>
                  <div style={{ fontWeight: 700, color: '#92400e', fontSize: 14, marginBottom: 6, marginTop: evaluationResult.evaluation_result.skipped_sheets?.length > 0 ? 12 : 0 }}>
                    {new Set(evaluationResult.evaluation_result.warnings.map(w => w.file_id)).size} answer sheet(s) were graded but may be incomplete
                  </div>
                  {evaluationResult.evaluation_result.warnings.map((w, i) => (
                    <div key={`${w.file_id}-${i}`} style={{ color: '#78350f', fontSize: 13, lineHeight: 1.6 }}>
                      <strong>{w.filename || w.file_id}</strong>: {w.message}
                    </div>
                  ))}
                </>
              )}
            </div>
          )}

          {/* Summary tiles */}
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: 16, marginBottom: 20 }}>
            <div style={statTileStyle}>
              <div style={statLabelStyle}>Total submissions</div>
              <div style={statValueStyle}>{answerSheetFiles.length || 0}</div>
            </div>
            <div style={statTileStyle}>
              <div style={statLabelStyle}>Average score</div>
              <div style={statValueStyle}>{resultStats ? `${resultStats.avgPct}%` : '—'}</div>
            </div>
            <div style={statTileStyle}>
              <div style={statLabelStyle}>Passed</div>
              <div style={statValueStyle}>
                {resultStats ? <>{resultStats.passed}<span style={{ fontSize: 15, fontWeight: 500, color: '#94a3b8' }}> / {resultStats.total}</span></> : '—'}
              </div>
            </div>
          </div>

          {/* Evaluation Results Table */}
          <div style={{ background: '#fff', borderRadius: 14, border: '1px solid #e8ecf2', boxShadow: '0 1px 3px rgba(15, 23, 42, 0.06)', overflow: 'hidden' }}>
            {/* Table Header */}
            <div style={{
              display: 'grid',
              gridTemplateColumns: resultsGridColumns,
              gap: 16,
              background: '#f8fafc',
              borderBottom: '1px solid #e8ecf2',
              padding: '12px 20px',
              fontWeight: 600,
              color: '#6b7280',
              fontSize: 12,
              textTransform: 'uppercase',
              letterSpacing: '0.04em'
            }}>
              <div>Answer Sheet</div>
              <div>Marks</div>
              <div>Result</div>
              <div>Status</div>
              <div style={{ textAlign: 'center' }}>Report</div>
            </div>

            {/* Table Rows */}
            {answerSheetFiles.map((file, index) => {
              const student = evaluationResult?.evaluation_result?.students?.[index];
              const isSkipped = !!student?.skipped;
              const pct = student && student.max_total_score ? student.total_score / student.max_total_score : null;
              const passed = pct !== null && pct >= PASS_MARK;
              const isModified = student?.status === 'modified';
              const warning = !isSkipped && student?.warnings?.length ? student.warnings.join('; ') : null;
              return (
                <div
                  key={index}
                  className="cc-kb-row"
                  style={{
                    display: 'grid',
                    gridTemplateColumns: resultsGridColumns,
                    gap: 16,
                    padding: '14px 20px',
                    borderBottom: index === answerSheetFiles.length - 1 ? 'none' : '1px solid #f1f5f9',
                    alignItems: 'center',
                    background: '#fff',
                    cursor: evaluationResult && !isSkipped ? 'pointer' : 'default'
                  }}
                  onClick={() => {
                    if (evaluationResult && !isSkipped) {
                      handleStudentClick(index);
                    }
                  }}
                >
                  {/* Filename - clickable row opens the review */}
                  <div style={{ display: 'flex', alignItems: 'center', gap: 12, minWidth: 0 }}>
                    <span style={{ width: 36, height: 36, borderRadius: 8, background: '#eff4ff', color: '#2563eb', display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0 }}>
                      <FiFileText size={17} />
                    </span>
                    <div style={{ minWidth: 0 }}>
                      <div style={{ fontWeight: 600, fontSize: 14, color: '#111827', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }} title={file.name}>
                        {file.name}
                      </div>
                      <div
                        style={{ fontSize: 12, marginTop: 2, color: evaluationError || isSkipped ? '#dc2626' : warning ? '#b45309' : evaluationResult ? '#2563eb' : '#94a3b8', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}
                        title={isSkipped ? student.error : warning || undefined}
                      >
                        {evaluationError ? 'Not evaluated' : isSkipped ? `Not evaluated: ${student.error || 'could not be read'}` : warning ? `⚠ ${warning} · Click to review` : evaluationResult ? 'Click to review' : 'Evaluating...'}
                      </div>
                    </div>
                  </div>

                  {/* Marks */}
                  <div>
                    {evaluationError || isSkipped ? (
                      <span style={{ fontSize: 14, color: '#94a3b8' }}>—</span>
                    ) : isEvaluating ? (
                      <span style={{ display: 'inline-flex', alignItems: 'center', gap: 8, fontSize: 13, color: '#6b7280' }}>
                        <span style={evalSpinnerStyle} /> Processing
                      </span>
                    ) : student ? (
                      <div>
                        <div style={{ fontSize: 14, fontWeight: 600, color: '#111827' }}>
                          {student.total_score}<span style={{ color: '#94a3b8', fontWeight: 500 }}>/{student.max_total_score}</span>
                          <span style={{ marginLeft: 6, fontSize: 12, fontWeight: 500, color: '#6b7280' }}>({Math.round((pct || 0) * 100)}%)</span>
                        </div>
                        <div style={{ marginTop: 6, height: 4, width: '100%', maxWidth: 120, background: '#f1f5f9', borderRadius: 999, overflow: 'hidden' }}>
                          <div style={{ height: '100%', width: `${Math.min(100, Math.round((pct || 0) * 100))}%`, background: passed ? '#10b981' : '#f87171', borderRadius: 999 }} />
                        </div>
                      </div>
                    ) : (
                      <span style={{ fontSize: 13, color: '#94a3b8' }}>Pending</span>
                    )}
                  </div>

                  {/* Result */}
                  <div>
                    {evaluationError ? (
                      <span style={pillStyle('danger')}>Stopped</span>
                    ) : isSkipped ? (
                      <span style={pillStyle('warning')}>Skipped</span>
                    ) : isEvaluating ? (
                      <span style={pillStyle('neutral')}>Processing</span>
                    ) : student ? (
                      <span style={pillStyle(passed ? 'success' : 'danger')}>{passed ? 'Passed' : 'Failed'}</span>
                    ) : (
                      <span style={pillStyle('neutral')}>Pending</span>
                    )}
                  </div>

                  {/* Status - Show modified or unmodified */}
                  <div>
                    <span style={pillStyle(isModified ? 'warning' : 'neutral')}>
                      {isModified ? 'Modified' : 'Unmodified'}
                    </span>
                  </div>

                  {/* Eye Button - View Individual Report */}
                  <div style={{ textAlign: 'center' }}>
                    {evaluationResult && !isSkipped ? (
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          handleViewStudentReport(index);
                        }}
                        style={{
                          borderRadius: 8,
                          border: '1px solid #e8ecf2',
                          background: '#fff',
                          color: '#2563eb',
                          cursor: 'pointer',
                          display: 'inline-flex',
                          alignItems: 'center',
                          justifyContent: 'center',
                          transition: 'all 0.15s ease',
                          width: 36,
                          height: 36
                        }}
                        onMouseEnter={(e) => {
                          e.currentTarget.style.background = '#eff4ff';
                          e.currentTarget.style.borderColor = '#2563eb';
                        }}
                        onMouseLeave={(e) => {
                          e.currentTarget.style.background = '#fff';
                          e.currentTarget.style.borderColor = '#e8ecf2';
                        }}
                        title="View Report"
                      >
                        <FiEye size={17} />
                      </button>
                    ) : (
                      <span style={{ color: '#cbd5e1', fontSize: 16 }}>—</span>
                    )}
                  </div>
                </div>
              );
            })}

            {answerSheetFiles.length === 0 && (
              <div style={{ padding: '32px 16px', textAlign: 'center', fontSize: 14, color: '#94a3b8' }}>
                No answer sheets yet
              </div>
            )}
          </div>
        </div>



        <SettingsModal open={showSettingsModal} onClose={() => setShowSettingsModal(false)} />

        {/* Save Modal */}
        {showSaveModal && (
          <div style={{
            position: 'fixed',
            top: 0,
            left: 0,
            right: 0,
            bottom: 0,
            background: 'rgba(0, 0, 0, 0.5)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            zIndex: 1000
          }}>
            <div style={{
              background: '#fff',
              borderRadius: 12,
              padding: 24,
              width: '400px',
              maxWidth: '90vw',
              boxShadow: '0 4px 20px rgba(0, 0, 0, 0.15)'
            }}>
              <h3 style={{ margin: '0 0 16px 0', fontSize: 18, fontWeight: 600 }}>
                Save Evaluation
              </h3>

              <div style={{ marginBottom: 16 }}>
                <label style={{ display: 'block', marginBottom: 8, fontWeight: 500 }}>
                  Evaluation Name:
                </label>
                <input
                  type="text"
                  value={assetName}
                  onChange={(e) => setAssetName(e.target.value)}
                  style={{
                    width: '100%',
                    padding: '10px 12px',
                    borderRadius: 6,
                    border: '1px solid #ccc',
                    fontSize: 14,
                    boxSizing: 'border-box'
                  }}
                  placeholder="Enter evaluation name..."
                  autoFocus
                />
              </div>

              <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 12 }}>
                <button
                  onClick={() => {
                    setShowSaveModal(false);
                    setAssetName('');
                  }}
                  style={{
                    padding: '8px 16px',
                    borderRadius: 6,
                    border: '1px solid #ccc',
                    background: '#fff',
                    color: '#666',
                    cursor: 'pointer',
                    fontSize: 14
                  }}
                >
                  Cancel
                </button>
                <button
                  onClick={handleSaveEvaluation}
                  disabled={isSaving || !assetName.trim()}
                  style={{
                    padding: '8px 16px',
                    borderRadius: 6,
                    border: 'none',
                    background: isSaving || !assetName.trim() ? '#ccc' : '#2563eb',
                    color: '#fff',
                    cursor: isSaving || !assetName.trim() ? 'not-allowed' : 'pointer',
                    fontSize: 14
                  }}
                >
                  {isSaving ? 'Saving...' : 'Save'}
                </button>
              </div>
            </div>
          </div>
        )}

        {/* Report Modal */}
        {showReportModal && (() => {
          const reportStudent = evaluationResult?.evaluation_result?.students?.[reportStudentIndex];
          const reportAnswers = reportStudent?.answers || [];
          const reportName = answerSheetFiles[reportStudentIndex]?.name || `Student ${(reportStudentIndex ?? 0) + 1}`;
          const reportPct = reportStudent?.max_total_score ? reportStudent.total_score / reportStudent.max_total_score : null;
          const reportPassed = reportPct !== null && reportPct >= PASS_MARK;
          const answeredCount = reportAnswers.filter(a => typeof a.student_answer === 'string' && a.student_answer.trim()).length;
          const closeReport = () => setShowReportModal(false);
          const reportLabelStyle = { margin: '0 0 6px 0', fontSize: 11, fontWeight: 600, color: '#6b7280', textTransform: 'uppercase', letterSpacing: '0.04em' };
          const reportTile = { flex: '1 1 150px', background: '#f8fafc', border: '1px solid #e8ecf2', borderRadius: 12, padding: '12px 16px' };
          return (
            <div
              onClick={closeReport}
              style={{ position: 'fixed', inset: 0, background: 'rgba(15, 23, 42, 0.45)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 1000, padding: 16 }}
            >
              <div
                role="dialog"
                aria-modal="true"
                onClick={(e) => e.stopPropagation()}
                style={{ background: '#fff', borderRadius: 16, width: 960, maxWidth: '100%', maxHeight: '92vh', display: 'flex', flexDirection: 'column', boxShadow: '0 20px 50px rgba(15, 23, 42, 0.18)', overflow: 'hidden' }}
              >
                {/* Header */}
                <div style={{ display: 'flex', alignItems: 'center', gap: 12, padding: '18px 24px', borderBottom: '1px solid #e8ecf2' }}>
                  <span style={{ width: 40, height: 40, borderRadius: 10, background: '#eff4ff', color: '#2563eb', display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0 }}>
                    <FiFileText size={19} />
                  </span>
                  <div style={{ minWidth: 0, flex: 1 }}>
                    <div style={{ fontSize: 12, fontWeight: 600, color: '#6b7280', textTransform: 'uppercase', letterSpacing: '0.04em' }}>Student report</div>
                    <h2 style={{ margin: '2px 0 0 0', fontSize: 19, fontWeight: 700, color: '#111827', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }} title={reportName}>{reportName}</h2>
                  </div>
                  <button
                    title="Close"
                    onClick={closeReport}
                    style={{ width: 34, height: 34, borderRadius: 8, border: '1px solid #e8ecf2', background: '#fff', color: '#6b7280', cursor: 'pointer', display: 'inline-flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0 }}
                  >
                    <FiX size={17} />
                  </button>
                </div>

                {/* Body */}
                <div className="cc-scroll" style={{ flex: 1, minHeight: 0, overflowY: 'auto', padding: '20px 24px', background: '#fafbfc' }}>
                  {!reportStudent ? (
                    <div style={{ padding: '40px 16px', textAlign: 'center', fontSize: 14, color: '#94a3b8' }}>No results available for this answer sheet.</div>
                  ) : (
                    <>
                      {/* Summary */}
                      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 12, marginBottom: 20 }}>
                        <div style={reportTile}>
                          <div style={reportLabelStyle}>Total marks</div>
                          <div style={{ fontSize: 20, fontWeight: 700, color: '#111827' }}>
                            {reportStudent.total_score}<span style={{ color: '#94a3b8', fontWeight: 500 }}>/{reportStudent.max_total_score}</span>
                            {reportPct !== null && <span style={{ marginLeft: 6, fontSize: 13, fontWeight: 500, color: '#6b7280' }}>({Math.round(reportPct * 100)}%)</span>}
                          </div>
                          {reportPct !== null && (
                            <div style={{ marginTop: 8, height: 4, background: '#e8ecf2', borderRadius: 999, overflow: 'hidden' }}>
                              <div style={{ height: '100%', width: `${Math.min(100, Math.round(reportPct * 100))}%`, background: reportPassed ? '#10b981' : '#f87171', borderRadius: 999 }} />
                            </div>
                          )}
                        </div>
                        <div style={reportTile}>
                          <div style={reportLabelStyle}>Result</div>
                          {reportPct !== null ? <span style={pillStyle(reportPassed ? 'success' : 'danger')}>{reportPassed ? 'Passed' : 'Failed'}</span> : <span style={pillStyle('neutral')}>—</span>}
                        </div>
                        <div style={reportTile}>
                          <div style={reportLabelStyle}>Status</div>
                          <span style={pillStyle(reportStudent.status === 'modified' ? 'warning' : 'neutral')}>{reportStudent.status === 'modified' ? 'Modified' : 'Unmodified'}</span>
                        </div>
                        <div style={reportTile}>
                          <div style={reportLabelStyle}>Answered</div>
                          <div style={{ fontSize: 20, fontWeight: 700, color: '#111827' }}>
                            {answeredCount}<span style={{ color: '#94a3b8', fontWeight: 500 }}>/{reportAnswers.length}</span>
                          </div>
                        </div>
                      </div>

                      {/* Questions */}
                      {reportAnswers.map((answer, index) => {
                        const hasSection = answer.section != null && answer.section_question_number != null;
                        const prev = reportAnswers[index - 1];
                        const startsSection = hasSection && (!prev || prev.section !== answer.section);
                        const score = answer.score ?? 0;
                        const studentAnswer = formatStudentAnswer(answer.student_answer);
                        return (
                          <React.Fragment key={index}>
                            {startsSection && (
                              <div style={{ margin: index === 0 ? '0 0 10px 2px' : '22px 0 10px 2px', fontSize: 12, fontWeight: 700, color: '#2563eb', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
                                Section {answer.section}
                              </div>
                            )}
                            <div style={{ background: '#fff', border: '1px solid #e8ecf2', borderRadius: 14, boxShadow: '0 1px 3px rgba(15, 23, 42, 0.06)', marginBottom: 12, overflow: 'hidden' }}>
                              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 12, padding: '12px 18px', borderBottom: '1px solid #f1f5f9' }}>
                                <span style={{ fontSize: 15, fontWeight: 700, color: '#111827' }}>
                                  Question {hasSection ? answer.section_question_number : index + 1}
                                </span>
                                <span style={{ fontSize: 12, fontWeight: 600, borderRadius: 999, padding: '3px 10px', ...scoreToneStyle(score, answer.max_score) }}>
                                  {score}/{answer.max_score ?? '?'}
                                </span>
                              </div>
                              <div style={{ padding: '14px 18px', display: 'grid', gap: 14 }}>
                                <div>
                                  <h4 style={reportLabelStyle}>Question</h4>
                                  <div style={{ padding: '10px 14px', background: '#f8fafc', borderRadius: 10, border: '1px solid #e8ecf2', fontSize: 14, color: '#1f2937' }}>
                                    <ReactMarkdown remarkPlugins={[remarkGfm, remarkBreaks]} components={reportMdComponents()}>
                                      {latexToText(formatQuestionText(answer) || 'Question text not available')}
                                    </ReactMarkdown>
                                  </div>
                                </div>
                                <div>
                                  <h4 style={reportLabelStyle}>Student answer</h4>
                                  <div style={{ padding: '10px 14px', background: '#f5f8ff', borderRadius: 10, border: '1px solid #dbe5fb', fontSize: 14, color: '#1f2937' }}>
                                    {studentAnswer ? (
                                      <ReactMarkdown remarkPlugins={[remarkGfm, remarkBreaks]} components={reportMdComponents()}>
                                        {latexToText(studentAnswer)}
                                      </ReactMarkdown>
                                    ) : (
                                      <span style={{ color: '#94a3b8', fontStyle: 'italic' }}>Not attempted</span>
                                    )}
                                  </div>
                                </div>
                                {answer.feedback && (
                                  <div>
                                    <h4 style={reportLabelStyle}>Feedback</h4>
                                    <div style={{ fontSize: 14, color: '#374151' }}>
                                      <ReactMarkdown remarkPlugins={[remarkGfm, remarkBreaks]} components={reportMdComponents()}>
                                        {latexToText(answer.feedback)}
                                      </ReactMarkdown>
                                    </div>
                                  </div>
                                )}
                              </div>
                            </div>
                          </React.Fragment>
                        );
                      })}
                    </>
                  )}
                </div>

                {/* Footer */}
                <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 10, padding: '14px 24px', borderTop: '1px solid #e8ecf2', background: '#fff' }}>
                  <button
                    className="cc-section-btn"
                    onClick={closeReport}
                    style={{ padding: '9px 18px', borderRadius: 10, border: '1px solid #d6dde8', background: '#fff', color: '#374151', fontWeight: 600, fontSize: 14, cursor: 'pointer' }}
                  >
                    Close
                  </button>
                  <button
                    onClick={handleDownloadReport}
                    disabled={!reportStudent}
                    style={{
                      padding: '9px 18px', borderRadius: 10, border: 'none', fontWeight: 600, fontSize: 14,
                      background: reportStudent ? '#2563eb' : '#93c5fd', color: '#fff',
                      cursor: reportStudent ? 'pointer' : 'not-allowed',
                      display: 'inline-flex', alignItems: 'center', gap: 8
                    }}
                  >
                    <FiDownload />
                    Download PDF
                  </button>
                </div>
              </div>
            </div>
          );
        })()}
      </div>
    );
  }

  // Original upload interface
  return (
    <div style={{ height: '100vh', display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
      <Header
        title="Evaluation"
        onLogout={handleLogout}
        onSettings={null}
        onExport={null}
        onGridView={null}
        onListView={null}
        isGridView={isGridView}
        onBack={() => navigate('/dashboard')}
        backLabel="Close"
      />

      {/* Breadcrumb */}
      <div style={{ maxWidth: 1680, padding: '0 32px', boxSizing: 'border-box', margin: '20px auto 4px auto', width: '100%' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 14, fontWeight: 500 }}>
          <span style={{ color: '#2563eb', cursor: 'pointer' }} onClick={() => navigate('/courses')}>Courses</span>
          <span style={{ color: '#9ca3af' }}>/</span>
          <span style={{ color: '#2563eb', cursor: 'pointer' }} onClick={() => navigate('/dashboard')}>{courseTitle}</span>
          <span style={{ color: '#9ca3af' }}>/</span>
          <span style={{ color: '#6b7280' }}>Evaluation</span>
        </div>
        <h1 style={{ margin: '6px 0 0 0', fontSize: 26, fontWeight: 700, color: '#111827' }}>Evaluation</h1>
        <div style={{ fontSize: 14, color: '#6b7280', marginTop: 2 }}>Upload a mark scheme, then the student's answer sheets, and let AI grade them.</div>
      </div>

      <div className="cc-scroll" style={{ flex: 1, minHeight: 0, overflowY: 'auto', width: '100%', maxWidth: 1680, margin: '0 auto', padding: '20px 32px 32px', boxSizing: 'border-box' }}>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(340px, 1fr))', gap: 24, alignItems: 'stretch' }}>
          {/* Left Section: Mark Scheme Upload */}
          <div style={evalCardStyle}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
              <span style={stepBadgeStyle(markSchemeUploaded)}>{markSchemeUploaded ? <FiCheck /> : '1'}</span>
              <div>
                <h2 style={{ margin: 0, fontSize: 19, fontWeight: 700, color: '#111827' }}>Mark Scheme</h2>
                <div style={{ fontSize: 14, color: '#6b7280', marginTop: 2 }}>Upload your evaluation mark scheme first</div>
              </div>
            </div>

            <label style={dropzoneStyle(isUploadingMarkScheme)}>
              <input
                type="file"
                accept=".pdf,.doc,.docx,.txt"
                disabled={isUploadingMarkScheme}
                onChange={(e) => {
                  const file = e.target.files?.[0] || null;
                  setMarkSchemeFile(file);
                  // Auto-upload when file is selected
                  if (file) {
                    handleUploadMarkScheme(file);
                  }
                }}
                style={{ display: 'none' }}
              />
              <FiUploadCloud style={{ fontSize: 28, color: '#2563eb' }} />
              <div style={{ fontSize: 14, fontWeight: 600, color: '#111827' }}>
                {markSchemeFile ? 'Choose a different file' : 'Click to choose a mark scheme'}
              </div>
              <div style={{ fontSize: 13, color: '#94a3b8' }}>PDF · uploads automatically</div>
            </label>

            {markSchemeFile && (
              <div style={fileRowStyle}>
                <FiFileText style={{ color: '#64748b', flexShrink: 0 }} />
                <span style={{ flex: 1, minWidth: 0, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{markSchemeFile.name}</span>
              </div>
            )}

            {isUploadingMarkScheme && (
              <div style={statusStyle('info')}>
                <span style={evalSpinnerStyle} />
                Uploading mark scheme...
              </div>
            )}

            {markSchemeUploaded && !isUploadingMarkScheme && (
              <div style={statusStyle('success')}>
                <FiCheckCircle style={{ flexShrink: 0 }} />
                <div>
                  <div style={{ fontWeight: 600 }}>Mark scheme uploaded</div>
                  <div style={{ fontSize: 13, color: '#4b5563', marginTop: 2 }}>Ready to upload answer sheets</div>
                </div>
              </div>
            )}
          </div>

          {/* Right Section: Answer Sheets Upload */}
          <div style={evalCardStyle}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
              <span style={stepBadgeStyle(answerSheetsUploaded, !markSchemeUploaded)}>{answerSheetsUploaded ? <FiCheck /> : '2'}</span>
              <div>
                <h2 style={{ margin: 0, fontSize: 19, fontWeight: 700, color: markSchemeUploaded ? '#111827' : '#9ca3af' }}>Answer Sheets</h2>
                <div style={{ fontSize: 14, color: '#6b7280', marginTop: 2 }}>Upload one file per student</div>
              </div>
            </div>

            {markSchemeUploaded ? (
              <>
                <label style={dropzoneStyle(isUploadingAnswerSheets)}>
                  <input
                    type="file"
                    multiple
                    accept=".pdf,.doc,.docx,.txt"
                    disabled={isUploadingAnswerSheets}
                    onChange={(e) => {
                      const files = Array.from(e.target.files || []);
                      setAnswerSheetFiles(files);
                      // Auto-upload when files are selected
                      if (files.length > 0) {
                        handleUploadAnswerSheets(files);
                      }
                    }}
                    style={{ display: 'none' }}
                  />
                  <FiUploadCloud style={{ fontSize: 28, color: '#2563eb' }} />
                  <div style={{ fontSize: 14, fontWeight: 600, color: '#111827' }}>
                    {answerSheetFiles.length > 0 ? 'Choose different files' : 'Click to choose answer sheets'}
                  </div>
                  <div style={{ fontSize: 13, color: '#94a3b8' }}>Select multiple files · uploads automatically</div>
                </label>

                {answerSheetFiles && answerSheetFiles.length > 0 && (
                  <div>
                    <div style={{ fontSize: 13, fontWeight: 600, color: '#6b7280', marginBottom: 8 }}>
                      {answerSheetFiles.length} {answerSheetFiles.length === 1 ? 'file' : 'files'}
                    </div>
                    <div className="cc-scroll" style={{ display: 'flex', flexDirection: 'column', gap: 6, maxHeight: 180, overflowY: 'auto' }}>
                      {answerSheetFiles.map((f, i) => (
                        <div key={i} style={fileRowStyle}>
                          <FiFileText style={{ color: '#64748b', flexShrink: 0 }} />
                          <span style={{ flex: 1, minWidth: 0, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{f.name}</span>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {isUploadingAnswerSheets && (
                  <div style={statusStyle('info')}>
                    <span style={evalSpinnerStyle} />
                    Uploading answer sheets...
                  </div>
                )}

                {answerSheetsUploaded && !isUploadingAnswerSheets && (
                  <div style={statusStyle('success')}>
                    <FiCheckCircle style={{ flexShrink: 0 }} />
                    <div>
                      <div style={{ fontWeight: 600 }}>Answer sheets uploaded</div>
                      <div style={{ fontSize: 13, color: '#4b5563', marginTop: 2 }}>Ready to start evaluation</div>
                    </div>
                  </div>
                )}

                <button
                  onClick={handleEvaluate}
                  disabled={isEvaluating || !answerSheetsUploaded || evaluationInProgressRef.current}
                  style={{
                    marginTop: 'auto',
                    width: '100%',
                    padding: '12px 16px',
                    borderRadius: 10,
                    border: 'none',
                    background: '#2563eb',
                    color: '#fff',
                    fontWeight: 600,
                    fontSize: 15,
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    gap: 8,
                    boxShadow: '0 1px 3px rgba(37, 99, 235, 0.3)',
                    transition: 'background 0.15s ease',
                    cursor: isEvaluating || !answerSheetsUploaded || evaluationInProgressRef.current ? 'not-allowed' : 'pointer',
                    opacity: isEvaluating || !answerSheetsUploaded || evaluationInProgressRef.current ? 0.5 : 1
                  }}
                  onMouseEnter={(e) => { if (!e.currentTarget.disabled) e.currentTarget.style.background = '#1d4ed8'; }}
                  onMouseLeave={(e) => { e.currentTarget.style.background = '#2563eb'; }}
                >
                  {isEvaluating ? 'Evaluating...' : <>Next <FiArrowRight /></>}
                </button>
              </>
            ) : (
              <div style={{ flex: 1, minHeight: 200, padding: '28px 16px', border: '1px dashed #d6dde8', borderRadius: 10, background: '#fafbfd', display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', gap: 8, textAlign: 'center' }}>
                <FiLock style={{ fontSize: 22, color: '#94a3b8' }} />
                <div style={{ fontSize: 15, fontWeight: 600, color: '#64748b' }}>Upload mark scheme first</div>
                <div style={{ fontSize: 13, color: '#94a3b8' }}>Complete step 1 to unlock answer sheet upload</div>
              </div>
            )}
          </div>
        </div>

        {/* Tips */}
        <div style={{ marginTop: 24, padding: '16px 20px', background: '#f8fafc', borderRadius: 12, border: '1px solid #e8ecf2', display: 'flex', gap: 12 }}>
          <FiInfo style={{ fontSize: 18, color: '#2563eb', flexShrink: 0, marginTop: 1 }} />
          <div>
            <div style={{ fontWeight: 600, fontSize: 14, color: '#111827', marginBottom: 6 }}>Tips</div>
            <ul style={{ margin: 0, paddingLeft: 18, color: '#4b5563', fontSize: 13, lineHeight: 1.7 }}>
              <li>Mark scheme should contain questions, correct answers, and scoring criteria</li>
              <li>Supported formats: PDF</li>
              <li>Mark scheme and answer sheets upload automatically when files are selected</li>
              <li>AI evaluation may take several minutes depending on file size and number of students. You'll get an email once it's complete</li>
            </ul>
          </div>
        </div>
      </div>

      <SettingsModal open={showSettingsModal} onClose={() => setShowSettingsModal(false)} />

      {/* Name + start dialog: floats over the upload screen without darkening it */}
      {(showNameInputScreen || showProcessStartedPopup) && (
        <div style={{
          position: 'fixed',
          inset: 0,
          background: 'rgba(248, 250, 252, 0.55)',
          backdropFilter: 'blur(2px)',
          WebkitBackdropFilter: 'blur(2px)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          zIndex: 3000,
          padding: 16
        }}>
          <div style={{
            position: 'relative',
            background: '#fff',
            borderRadius: 16,
            border: '1px solid #e8ecf2',
            padding: '28px 32px',
            width: 600,
            maxWidth: '100%',
            boxSizing: 'border-box',
            boxShadow: '0 20px 50px rgba(15, 23, 42, 0.18)'
          }}>
            {showProcessStartedPopup ? (
              <div style={{ textAlign: 'center' }}>
                <div style={{
                  width: 56,
                  height: 56,
                  background: evaluationError ? '#fef2f2' : '#eff4ff',
                  color: evaluationError ? '#dc2626' : '#2563eb',
                  borderRadius: '50%',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  margin: '0 auto 14px auto'
                }}>
                  {evaluationError ? <FiAlertTriangle size={24} /> : <FiMail size={24} />}
                </div>
                <h3 style={{ margin: '0 0 8px 0', fontSize: 20, fontWeight: 700, color: evaluationError ? '#b91c1c' : '#111827' }}>
                  {evaluationError ? 'Evaluation failed' : 'Evaluation started'}
                </h3>
                <p style={{ margin: '0 auto 22px auto', maxWidth: 460, fontSize: 14, color: '#4b5563', lineHeight: 1.6 }}>
                  {evaluationError
                    ? <>The evaluation process has stopped due to an error:<br />
                      <span style={{ fontSize: 13, color: '#7f1d1d' }}>{evaluationError}</span></>
                    : <>We're grading the answer sheets now. <strong style={{ color: '#111827' }}>You'll receive an email and a notification here once it's complete</strong>, and the results will be available on the Evaluation card.</>}
                </p>
                <button
                  onClick={() => {
                    setShowProcessStartedPopup(false);
                    navigate('/dashboard');
                  }}
                  style={{ padding: '11px 28px', borderRadius: 10, border: 'none', background: '#2563eb', color: '#fff', fontWeight: 600, cursor: 'pointer', fontSize: 15 }}
                >
                  Go to Course Page
                </button>
              </div>
            ) : (
              <>
                <button
                  title="Close"
                  onClick={() => setShowNameInputScreen(false)}
                  style={{ position: 'absolute', top: 14, right: 14, width: 32, height: 32, borderRadius: 8, border: 'none', background: 'transparent', color: '#6b7280', cursor: 'pointer', display: 'flex', alignItems: 'center', justifyContent: 'center' }}
                  onMouseEnter={(e) => { e.currentTarget.style.background = '#f1f5f9'; }}
                  onMouseLeave={(e) => { e.currentTarget.style.background = 'transparent'; }}
                >
                  <FiX size={18} />
                </button>

                <h2 style={{ margin: 0, fontSize: 20, fontWeight: 700, color: '#111827' }}>
                  Name your evaluation
                </h2>
                <p style={{ margin: '4px 0 0 0', color: '#6b7280', fontSize: 14, lineHeight: 1.55 }}>
                  This name is used to save the evaluation under Assets on the Evaluation card.
                </p>

                <label htmlFor="evaluation-name" style={{ display: 'block', margin: '20px 0 8px', fontWeight: 600, fontSize: 14, color: '#374151' }}>
                  Evaluation name
                </label>
                <input
                  id="evaluation-name"
                  type="text"
                  value={assetName}
                  onChange={(e) => setAssetName(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter' && assetName.trim()) handleStartEvaluation();
                    if (e.key === 'Escape') setShowNameInputScreen(false);
                  }}
                  style={{
                    width: '100%',
                    padding: '11px 14px',
                    borderRadius: 10,
                    border: '1px solid #d6dde8',
                    fontSize: 15,
                    boxSizing: 'border-box',
                    outline: 'none',
                    transition: 'border-color 0.15s, box-shadow 0.15s'
                  }}
                  placeholder="e.g. Mid-term exam – Section A"
                  autoFocus
                  onFocus={(e) => { e.target.style.borderColor = '#2563eb'; e.target.style.boxShadow = '0 0 0 3px rgba(37, 99, 235, 0.12)'; }}
                  onBlur={(e) => { e.target.style.borderColor = '#d6dde8'; e.target.style.boxShadow = 'none'; }}
                />

                {/* Email notice */}
                <div style={{ display: 'flex', alignItems: 'flex-start', gap: 10, marginTop: 16, padding: '12px 14px', background: '#f5f8ff', border: '1px solid #dbe5fb', borderRadius: 10 }}>
                  <FiMail style={{ fontSize: 17, color: '#2563eb', flexShrink: 0, marginTop: 1 }} />
                  <div style={{ fontSize: 13, color: '#374151', lineHeight: 1.55 }}>
                    <span style={{ fontWeight: 600, color: '#1e3a8a' }}>You'll get an email when results are ready.</span>{' '}
                    Grading can take several minutes. You can leave this page; results will also appear on the Evaluation card.
                  </div>
                </div>

                <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 10, marginTop: 22 }}>
                  <button
                    onClick={() => setShowNameInputScreen(false)}
                    style={{ padding: '10px 18px', borderRadius: 10, border: '1px solid #d6dde8', background: '#fff', color: '#374151', fontWeight: 600, fontSize: 14, cursor: 'pointer' }}
                  >
                    Cancel
                  </button>
                  <button
                    onClick={handleStartEvaluation}
                    disabled={!assetName.trim()}
                    style={{
                      padding: '10px 20px',
                      borderRadius: 10,
                      border: 'none',
                      background: '#2563eb',
                      color: '#fff',
                      fontWeight: 600,
                      fontSize: 14,
                      display: 'flex',
                      alignItems: 'center',
                      gap: 8,
                      boxShadow: '0 1px 3px rgba(37, 99, 235, 0.3)',
                      cursor: !assetName.trim() ? 'not-allowed' : 'pointer',
                      opacity: !assetName.trim() ? 0.5 : 1
                    }}
                  >
                    Start Evaluation <FiArrowRight />
                  </button>
                </div>
              </>
            )}
          </div>
        </div>
      )}

      {/* Format Error Modal */}
      {showFormatError && (
        <div style={{
          position: 'fixed',
          top: 0,
          left: 0,
          right: 0,
          bottom: 0,
          background: 'rgba(0, 0, 0, 0.5)',
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
            boxShadow: '0 10px 25px rgba(0, 0, 0, 0.2)'
          }}>
            <div style={{ textAlign: 'center', marginBottom: '24px' }}>
              <div style={{
                width: '64px',
                height: '64px',
                background: '#fef2f2',
                borderRadius: '50%',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                margin: '0 auto 16px auto'
              }}>
                <span style={{ fontSize: '32px', color: '#ef4444' }}>⚠️</span>
              </div>
              <h3 style={{ fontSize: '20px', fontWeight: '600', color: '#1f2937', margin: '0 0 8px 0' }}>
                Format Issue
              </h3>
              <p style={{ fontSize: '14px', color: '#6b7280', margin: 0 }}>
                {formatErrorMessage}
              </p>
            </div>

            <div style={{ display: 'flex', justifyContent: 'center', gap: '12px' }}>
              <button
                onClick={handleReuploadMarkScheme}
                style={{
                  padding: '12px 24px',
                  fontSize: '15px',
                  borderRadius: '8px',
                  border: 'none',
                  background: '#3b82f6',
                  color: '#fff',
                  fontWeight: '600',
                  cursor: 'pointer',
                  transition: 'background 0.2s ease'
                }}
                onMouseOver={e => e.target.style.background = '#2563eb'}
                onMouseOut={e => e.target.style.background = '#3b82f6'}
              >
                Upload New File
              </button>
              <button
                onClick={() => setShowFormatError(false)}
                style={{
                  padding: '12px 24px',
                  fontSize: '15px',
                  borderRadius: '8px',
                  border: '1px solid #d1d5db',
                  background: '#fff',
                  color: '#6b7280',
                  fontWeight: '500',
                  cursor: 'pointer',
                  transition: 'border 0.2s ease'
                }}
                onMouseOver={e => e.target.style.border = '1px solid #9ca3af'}
                onMouseOut={e => e.target.style.border = '1px solid #d1d5db'}
              >
                Cancel
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Download Success Modal */}
      <Modal
        open={showDownloadSuccessModal}
        onClose={() => setShowDownloadSuccessModal(false)}
        modalStyle={{
          minWidth: 400,
          maxWidth: 500,
          padding: '32px',
          textAlign: 'center'
        }}
      >
        <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '20px' }}>
          <div style={{
            width: '60px',
            height: '60px',
            borderRadius: '50%',
            background: '#10b981',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            fontSize: '24px',
            color: 'white'
          }}>
            ✓
          </div>
          <div>
            <h3 style={{ margin: '0 0 8px 0', fontSize: '18px', fontWeight: '600', color: '#374151' }}>
              CSV Report Downloaded Successfully!
            </h3>
            <p style={{ margin: '0', fontSize: '14px', color: '#6b7280' }}>
              Your evaluation report has been saved to your downloads folder.
            </p>
          </div>
        </div>
      </Modal>
    </div>
  );
} 