import React, { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import Header from "../components/header/Header";
import SettingsModal from "../components/SettingsModal";
import { evaluationService } from "../services/evaluation";

export default function Evaluation() {
  const navigate = useNavigate();
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
  const [showResults, setShowResults] = useState(false);
  const [evaluationProgress, setEvaluationProgress] = useState(0);
  const [evaluationStatus, setEvaluationStatus] = useState('');
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
  const manualProgressRef = React.useRef(false);
  const evaluationCompletedRef = React.useRef(false);

  const evaluationInProgressRef = React.useRef(false);

  const courseId = localStorage.getItem('currentCourseId');
  const courseTitle = localStorage.getItem("currentCourseTitle") || "Course";
  


  // Force re-render when status changes
  useEffect(() => {
    // This effect will run whenever forceUpdate changes, forcing a re-render
  }, [forceUpdate]);

  // Simulate evaluation progress
  useEffect(() => {
    let progressInterval;
    
    if (isEvaluating && showResults && !manualProgressRef.current) {
      setEvaluationProgress(0);
      setEvaluationStatus('Starting evaluation...');
      
      // More conservative timing for production - slower progress that gives backend more time
      let currentProgress = 0;
      
      progressInterval = setInterval(() => {
        setEvaluationProgress(prev => {
          currentProgress = prev;
          
          // Adaptive progress speed - slower as we approach 95%
          let progressIncrement;
          if (currentProgress < 50) {
            progressIncrement = 2; // Fast initially (2% per second)
          } else if (currentProgress < 80) {
            progressIncrement = 1; // Medium speed (1% per second)
          } else if (currentProgress < 90) {
            progressIncrement = 0.5; // Slow down (0.5% per second)
          } else if (currentProgress < 95) {
            progressIncrement = 0.2; // Very slow approach to 95% (0.2% per second)
          } else {
            // Stop at 95% and wait for backend
            setEvaluationStatus('Backend processing files... Please wait...');
            return 95;
          }
          
          const newProgress = currentProgress + progressIncrement;
          
          // Update status based on progress
          if (newProgress < 20) {
            setEvaluationStatus('Analyzing mark scheme...');
          } else if (newProgress < 40) {
            setEvaluationStatus('Processing answer sheets...');
          } else if (newProgress < 60) {
            setEvaluationStatus('Evaluating student responses...');
          } else if (newProgress < 80) {
            setEvaluationStatus('Calculating scores...');
          } else if (newProgress < 90) {
            setEvaluationStatus('Finalizing evaluation...');
          } else if (newProgress < 95) {
            setEvaluationStatus(`Processing ${answerSheetFiles.length} files...`);
          }
          
          return Math.min(newProgress, 95);
        });
      }, 1000); // Update every second
    }

    return () => {
      if (progressInterval) clearInterval(progressInterval);
    };
  }, [isEvaluating, showResults, answerSheetFiles.length]);

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
    
    // Clear any previous evaluation tracking state
    evaluationService.clearCompletedEvaluations();
    
    evaluationInProgressRef.current = true;
    
    try {
      setIsEvaluating(true);
      setShowResults(true); // Show results page immediately
      setEvaluationProgress(0);
      setEvaluationStatus('Starting evaluation...');

      // Start precise progress simulation up to 95%: 90 seconds per file
      manualProgressRef.current = true;
      evaluationCompletedRef.current = false;
      const totalSecondsTo95 = Math.max(1, (answerSheetFiles?.length || 1) * 90);
      let elapsedSeconds = 0;
      const progressTimer = setInterval(() => {
        if (evaluationCompletedRef.current) {
          clearInterval(progressTimer);
          return;
        }
        elapsedSeconds += 1;
        const target = Math.min(95, (elapsedSeconds / totalSecondsTo95) * 95);
        setEvaluationProgress(prev => (target > prev ? target : prev));
        // Update status bands
        if (target < 20) setEvaluationStatus('Analyzing mark scheme...');
        else if (target < 40) setEvaluationStatus('Processing answer sheets...');
        else if (target < 60) setEvaluationStatus('Evaluating student responses...');
        else if (target < 80) setEvaluationStatus('Calculating scores...');
        else if (target < 95) setEvaluationStatus('Finalizing evaluation...');
        else setEvaluationStatus('Waiting for backend to complete...');

        if (target >= 95) {
          clearInterval(progressTimer); // Stop at exactly 95% and wait for backend
          // Start polling for completion after reaching 95%
          startPollingForCompletion();
        }
      }, 1000);

      // Trigger backend evaluation; whenever it finishes, jump to 100%
      const finishWithResult = (result) => {
        evaluationCompletedRef.current = true;
        evaluationInProgressRef.current = false; // Reset the flag
        setEvaluationResult(result);
        setEvaluationProgress(100);
        setEvaluationStatus('Evaluation completed!');
        setIsEvaluating(false);
        manualProgressRef.current = false;
        
        // Clear any ongoing polling to prevent duplicate requests
      };

      // Start polling function that monitors status after 95%
      const startPollingForCompletion = async () => {
        if (evaluationCompletedRef.current) {
          return;
        }
        
        setEvaluationStatus('Backend processing complete files... Please wait...');
        
        let consecutiveFailures = 0;
        const maxConsecutiveFailures = 3;
        let pollInterval;
        
        try {
          // Poll every 15 seconds until completion
          pollInterval = setInterval(async () => {
            if (evaluationCompletedRef.current) {
              clearInterval(pollInterval);
              return;
            }
            
            try {
              const statusResponse = await evaluationService.checkEvaluationStatus(evaluationId);
              
              // Reset failure counter on successful response
              consecutiveFailures = 0;
              
              if (statusResponse.status === 'completed' && statusResponse.evaluation_result) {
                clearInterval(pollInterval);
                finishWithResult({
                  evaluation_id: evaluationId,
                  evaluation_result: statusResponse.evaluation_result
                });
                return; // Exit immediately after completion
              } else {
                setEvaluationStatus('Backend still processing... Please wait...');
              }
            } catch (pollError) {
              consecutiveFailures++;
              console.warn(`Polling error (attempt ${consecutiveFailures}/${maxConsecutiveFailures}):`, pollError.message);
              
              // If it's a 404 error and we've had consecutive failures, try fallback
              if (pollError.message.includes('Evaluation not found') && consecutiveFailures >= maxConsecutiveFailures) {
                try {
                  const fallbackResponse = await evaluationService.checkCompletedEvaluation(evaluationId);
                  if (fallbackResponse.status === 'completed' && fallbackResponse.evaluation_result) {
                    clearInterval(pollInterval);
                    finishWithResult({
                      evaluation_id: evaluationId,
                      evaluation_result: fallbackResponse.evaluation_result
                    });
                    return; // Exit immediately after completion
                  }
                  // Reset failure counter if fallback works
                  consecutiveFailures = 0;
                  setEvaluationStatus('Using fallback monitoring... Please wait...');
                } catch (fallbackError) {
                  console.error('Fallback check also failed:', fallbackError.message);
                  // If fallback also fails, stop polling
                  clearInterval(pollInterval);
                  evaluationInProgressRef.current = false;
                  setIsEvaluating(false);
                  setEvaluationStatus('Evaluation session lost - please try again');
                  setEvaluationProgress(0);
                  manualProgressRef.current = false;
                  alert('The evaluation session was lost and could not be recovered. This might be due to a server restart or timeout. Please try restarting the evaluation process.');
                  return;
                }
              } else {
                // For other errors or first few 404s, just log and continue
                setEvaluationStatus(`Checking status... (${consecutiveFailures} retries)`);
              }
            }
          }, 15000); // Poll every 15 seconds
          
          // Safety timeout after 1 hour of polling
          setTimeout(() => {
            if (!evaluationCompletedRef.current) {
              clearInterval(pollInterval);
              evaluationInProgressRef.current = false;
              setIsEvaluating(false);
              setEvaluationStatus('Evaluation timed out - please try again');
              setEvaluationProgress(0);
              manualProgressRef.current = false;
              alert('Evaluation timed out after 1 hour. Please try refreshing and checking again, or contact support.');
            }
          }, 60 * 60 * 1000); // 1 hour
          
        } catch (error) {
          console.error('Error starting polling:', error);
          if (pollInterval) clearInterval(pollInterval);
          evaluationInProgressRef.current = false;
          setIsEvaluating(false);
          setEvaluationStatus('Polling failed - please try again');
          alert('Failed to monitor evaluation status: ' + error.message);
        }
      };

      // Also try the original evaluation service call (for single files or immediate completion)
      evaluationService.evaluateFiles(evaluationId)
        .then((result) => {
          finishWithResult(result);
        })
        .catch(err => {
          console.warn('Evaluation service call failed, relying on polling:', err?.message || err);
          // Don't fail here - let polling handle the completion
          // Only fail if it's a clear authentication or setup error
          if (err?.message?.includes('Authentication failed') || err?.message?.includes('not found')) {
            evaluationInProgressRef.current = false;
            setIsEvaluating(false);
            setEvaluationStatus('Evaluation failed - please try again');
            setEvaluationProgress(0);
            manualProgressRef.current = false;
            alert('Evaluation failed: ' + (err?.message || 'Unknown error'));
          }
        });
       
    } catch (err) {
      console.error('Evaluation error:', err);
      evaluationInProgressRef.current = false; // Reset the flag
      setIsEvaluating(false); // Stop the progress simulation
      setEvaluationStatus('Evaluation failed');
      setEvaluationProgress(0);
      alert(err?.message || 'Evaluation failed');
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
     setEvaluationResult({...updatedEvaluationResult});
     setIsEditing(false);
     
     
     // Changes saved successfully - no popup needed
      
    } catch (error) {
      console.error('Error saving changes:', error);
      console.error('Error details:', {
        message: error.message,
        response: error.response?.data,
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
        />

        {/* Breadcrumb */}
        <div style={{ maxWidth: 1200, margin: "1rem auto 0.5rem auto", width: '100%', display: 'flex', alignItems: 'center', gap: 10, fontSize: 18, fontWeight: 500 }}>
          <span style={{ color: '#2563eb', cursor: 'pointer', fontWeight: 600 }} onClick={() => navigate('/courses')}>Courses</span>
          <span style={{ color: '#888' }}>{'>'}</span>
          <span style={{ color: '#2563eb', cursor: 'pointer', fontWeight: 600 }} onClick={() => navigate('/dashboard')}>{courseTitle}</span>
          <span style={{ color: '#888' }}>{'>'}</span>
          <span style={{ color: '#2563eb', cursor: 'pointer', fontWeight: 600 }} onClick={handleBackToResults}>Evaluation</span>
          <span style={{ color: '#888' }}>{'>'}</span>
          <span style={{ fontWeight: 700 }}>Review - {fileName}</span>
        </div>

        {/* Review Content */}
        <div style={{ flex: 1, display: 'flex', gap: 24, padding: '0 5vw', overflow: 'hidden' }}>
          {/* Left Panel: Question Navigation */}
          <div style={{ flex: 1, maxWidth: 300, overflowY: 'auto', padding: '24px 0' }}>
            <div style={{ background: '#fff', borderRadius: 18, padding: '24px', boxShadow: '0 2px 7px #0002' }}>
              <h3 style={{ margin: '0 0 20px 0', fontSize: 20, fontWeight: 600, color: '#1e40af' }}>Questions</h3>
                             {(() => {
                 const questionScores = extractQuestionScores(student);
                 const maxScores = extractMaxScores(student);
                 
                 if (questionScores.length > 0) {
                   return questionScores.map((score, index) => (
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
                       <div style={{ fontSize: '14px', color: '#666' }}>{score}/{maxScores[index] || (score > 0 ? score : '?')}</div>
                     </div>
                   ));
                 } else {
                   return (
                     <div style={{ padding: '16px', textAlign: 'center', color: '#666' }}>
                       No question scores available
                     </div>
                   );
                 }
               })()}
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
                   {student?.answers?.[selectedQuestionIndex]?.question_text || 'Question text not available'}
                 </div>
               </div>

               <div style={{ marginBottom: '24px' }}>
                 <h4 style={{ margin: '0 0 12px 0', fontSize: 16, fontWeight: 600, color: '#374151' }}>Student Answer</h4>
                 <div style={{ padding: '16px', background: '#f0f9ff', borderRadius: '8px', border: '1px solid #bfdbfe' }}>
                   {student?.answers?.[selectedQuestionIndex]?.student_answer || 'Student answer not available'}
                 </div>
               </div>

               <div style={{ marginBottom: '24px' }}>
                 <h4 style={{ margin: '0 0 12px 0', fontSize: 16, fontWeight: 600, color: '#374151' }}>AI Evaluation</h4>
                 <div style={{ padding: '16px', background: '#fef3c7', borderRadius: '8px', border: '1px solid #fbbf24' }}>
                   {student?.answers?.[selectedQuestionIndex]?.feedback || 'AI feedback not available'}
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
                      disabled={isSaving}
                      style={{
                        padding: '8px 16px',
                        borderRadius: '6px',
                        border: '1px solid #28a745',
                        background: isSaving ? '#6c757d' : '#28a745',
                        color: '#fff',
                        fontWeight: 600,
                        cursor: isSaving ? 'not-allowed' : 'pointer',
                        fontSize: '14px',
                        opacity: isSaving ? 0.6 : 1
                      }}
                      onClick={handleSave}
                    >
                      {isSaving ? 'Saving...' : 'Save'}
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
                      max={extractMaxScores(student)[selectedQuestionIndex] || 10}
                      step="0.1"
                      value={editedQuestionScores[selectedQuestionIndex] ?? ''}
                      onChange={(e) => {
                        const inputValue = e.target.value;
                        const maxScore = extractMaxScores(student)[selectedQuestionIndex] || 10;
                        
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
                      of {extractMaxScores(student)[selectedQuestionIndex] || '?'}
                    </span>
                  </div>
                ) : (
                  <>
                    <div style={{ fontSize: '32px', fontWeight: 'bold', color: '#2563eb' }}>
                      {extractQuestionScores(student)[selectedQuestionIndex] || 0}
                    </div>
                    <div style={{ fontSize: '14px', color: '#666' }}>
                      of {extractMaxScores(student)[selectedQuestionIndex] || '?'}
                    </div>
                  </>
                )}
              </div>

              <div style={{ marginBottom: '24px' }}>
                <h4 style={{ margin: '0 0 12px 0', fontSize: 16, fontWeight: 600, color: '#374151' }}>Feedback</h4>
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
                    {student?.answers?.[selectedQuestionIndex]?.feedback || 'No feedback available'}
                  </div>
                )}
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
          title="Evaluation Results"
          onLogout={handleLogout}
          onSettings={null}
          onExport={null}
          onGridView={null}
          onListView={null}
          isGridView={isGridView}
          onBack={() => navigate('/dashboard')}
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
                {isEvaluating ? 'Evaluation in Progress' : 'Evaluation Complete'}
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
                    if (evaluationResult) {
                      handleStudentClick(index);
                    }
                  }}
                >
                  {file.name}
                  {!evaluationResult && (
                    <div style={{ fontSize: '12px', color: '#dc3545', marginTop: '4px' }}>
                      (evaluating....)
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
                
                {/* Status - Show modified or unmodified */}
                <div style={{ 
                  fontSize: '13px', 
                  color: getStatusColor(evaluationResult?.evaluation_result?.students?.[index]?.status || 'unopened'),
                  fontWeight: 500
                }}>
                  {evaluationResult?.evaluation_result?.students?.[index]?.status === 'modified' ? 'modified' : 'unmodified'}
                </div>
              </div>
            ))}
          </div>
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
        onSettings={null}
        onExport={null}
        onGridView={null}
        onListView={null}
        isGridView={isGridView}
        onBack={() => navigate('/dashboard')}
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
                onChange={(e) => {
                  const file = e.target.files?.[0] || null;
                  setMarkSchemeFile(file);
                  // Auto-upload when file is selected
                  if (file) {
                    handleUploadMarkScheme(file);
                  }
                }}
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

            {isUploadingMarkScheme && (
              <div style={{
                width: '100%',
                padding: '12px',
                borderRadius: '8px',
                border: 'none',
                background: '#2563eb',
                color: '#fff',
                fontWeight: 600,
                textAlign: 'center',
                marginBottom: '16px'
              }}>
                Uploading Mark Scheme...
              </div>
            )}

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
                  <li>Mark scheme uploads automatically when file is selected</li>
                  <li>Answer sheets upload automatically when files are selected</li>
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
                    onChange={(e) => {
                      const files = Array.from(e.target.files || []);
                      setAnswerSheetFiles(files);
                      // Auto-upload when files are selected
                      if (files.length > 0) {
                        handleUploadAnswerSheets(files);
                      }
                    }}
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

                {isUploadingAnswerSheets && (
                  <div style={{
                    width: '100%',
                    padding: '12px',
                    borderRadius: '8px',
                    border: 'none',
                    background: '#2563eb',
                    color: '#fff',
                    fontWeight: 600,
                    textAlign: 'center',
                    marginBottom: '16px'
                  }}>
                    Uploading Answer Sheets...
                  </div>
                )}

                {answerSheetsUploaded && (
                  <div style={{ padding: '16px', background: '#f0f9ff', borderRadius: '8px', border: '1px solid #7dd3fc', marginBottom: '20px' }}>
                    <div style={{ fontWeight: 600, color: '#0369a1', marginBottom: '4px' }}>✓ Answer Sheets Uploaded</div>
                    <div style={{ fontSize: '14px', color: '#666' }}>Ready to start evaluation</div>
                  </div>
                )}

                <button
                  onClick={handleEvaluate}
                  disabled={isEvaluating || !answerSheetsUploaded || evaluationInProgressRef.current}
                  style={{
                    width: '100%',
                    padding: '16px',
                    borderRadius: '8px',
                    border: 'none',
                    background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
                    color: '#fff',
                    fontWeight: 600,
                    fontSize: '16px',
                    cursor: isEvaluating || !answerSheetsUploaded || evaluationInProgressRef.current ? 'not-allowed' : 'pointer',
                    opacity: isEvaluating || !answerSheetsUploaded || evaluationInProgressRef.current ? 0.5 : 1
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
    </div>
  );
} 