import axios from 'axios';
import { getCurrentUser } from './auth';

const baseUrl = process.env.REACT_APP_API_BASE_URL || 'http://localhost:8000';
const API_BASE = new URL('/api', baseUrl).toString();

// Track ongoing evaluation requests to prevent duplicates
const ongoingEvaluations = new Set();
// Track last evaluation request timestamps to prevent rapid duplicates
const lastEvaluationTime = new Map();

function getToken() {
  const user = getCurrentUser();
  if (!user || !user.token) {
    throw new Error('User not authenticated. Please log in.');
  }
  return user.token;
}

export const evaluationService = {
  async uploadMarkScheme({ courseId, markSchemeFile }) {
    const formData = new FormData();
    formData.append('course_id', courseId);
    formData.append('mark_scheme', markSchemeFile);
    
    try {
      const res = await axios.post(`${API_BASE}/evaluation/upload-mark-scheme`, formData, {
        headers: { 
          'Authorization': `Bearer ${getToken()}`,
          'Content-Type': 'multipart/form-data'
        }
      });
      return res.data; // { evaluation_id: "uuid", mark_scheme_file_id: "uuid" }
    } catch (error) {
      console.error('Upload mark scheme error:', error);
      if (error.response?.status === 401) {
        throw new Error('Authentication failed. Please try again.');
      }
      throw new Error(error.response?.data?.detail || 'Failed to upload mark scheme');
    }
  },

  async uploadAnswerSheets({ evaluationId, answerSheetFiles }) {
    const formData = new FormData();
    formData.append('evaluation_id', evaluationId);
    if (Array.isArray(answerSheetFiles)) {
      answerSheetFiles.forEach(f => formData.append('answer_sheets', f));
    } else if (answerSheetFiles) {
      formData.append('answer_sheets', answerSheetFiles);
    }
    
    try {
      const res = await axios.post(`${API_BASE}/evaluation/upload-answer-sheets`, formData, {
        headers: { 
          'Authorization': `Bearer ${getToken()}`,
          'Content-Type': 'multipart/form-data'
        }
      });
      return res.data; // { evaluation_id: "uuid", answer_sheet_file_ids: ["uuid1", "uuid2"] }
    } catch (error) {
      console.error('Upload answer sheets error:', error);
      if (error.response?.status === 401) {
        throw new Error('Authentication failed. Please try again.');
      }
      throw new Error(error.response?.data?.detail || 'Failed to upload answer sheets');
    }
  },

  async evaluateFiles(evaluationId) {
    const now = Date.now();
    const lastRequestTime = lastEvaluationTime.get(evaluationId) || 0;
    
    // Prevent duplicate requests for the same evaluation
    if (ongoingEvaluations.has(evaluationId)) {
      console.log(`Evaluation for ${evaluationId} already in progress, ignoring duplicate request`);
      throw new Error('Evaluation already in progress for this ID');
    }
    
    // NUCLEAR PROTECTION: Prevent rapid successive requests (within 3 seconds)
    if (now - lastRequestTime < 3000) {
      console.log(`🚫 SERVICE BLOCKED: Evaluation request for ${evaluationId} made too soon (${now - lastRequestTime}ms ago)`);
      throw new Error('Duplicate request blocked - please wait');
    }
    
    ongoingEvaluations.add(evaluationId);
    lastEvaluationTime.set(evaluationId, now);
    
    try {
      const user = getCurrentUser();
      if (!user?.id) {
        ongoingEvaluations.delete(evaluationId);
        throw new Error('User not authenticated');
      }

      console.log(`Starting evaluation for ID: ${evaluationId}`);

      const res = await axios.get(`${API_BASE}/evaluation/evaluate-files`, {
        headers: { 'Authorization': `Bearer ${getToken()}` },
        params: {
          evaluation_id: evaluationId,
          user_id: user.id
        },
        timeout: 30000 // 30 seconds - backend returns immediately for multiple files
      });
      
            console.log('Evaluation response received:', res.data);
      
      // If backend is processing in background, poll for completion
      if (res.data.evaluation_result?.status === 'processing') {
        ongoingEvaluations.delete(evaluationId);
        return await this.waitForCompletion(evaluationId);
      }
      
      ongoingEvaluations.delete(evaluationId); // Clean up tracking
      return res.data; // { evaluation_id: "uuid", evaluation_result: {...} }
    } catch (error) {
      console.error('Evaluation error details:', {
        message: error.message,
        status: error.response?.status,
        statusText: error.response?.statusText,
        data: error.response?.data,
        evaluationId: evaluationId,
        code: error.code
      });
      
      if (error.response?.status === 401) {
        throw new Error('Authentication failed. Please try again.');
      }
      
      if (error.response?.status === 504 || error.code === 'ECONNABORTED') {
        throw new Error('Processing is taking longer than expected. The evaluation may still be running in the background. Please check back in a few minutes or contact support.');
      }
      
      if (error.response?.status >= 500) {
        const errorDetail = error.response?.data?.detail || 'Server error during evaluation';
        throw new Error(`Server error: ${errorDetail}. The backend may still be processing. Please try again in a few minutes.`);
      }
      
      if (error.response?.status === 404) {
        throw new Error('Evaluation session not found. Please restart the evaluation process.');
      }
      
      // Always clean up tracking in catch block
      ongoingEvaluations.delete(evaluationId);
      throw new Error(error.response?.data?.detail || `Evaluation failed: ${error.message}`);
        }
  },

  async waitForCompletion(evaluationId) {
    // Simple polling - check every 10 seconds for up to 15 minutes
    for (let i = 0; i < 90; i++) {
      await new Promise(resolve => setTimeout(resolve, 10000)); // Wait 10 seconds
      
      const res = await axios.get(`${API_BASE}/evaluation/check/${evaluationId}`, {
        headers: { 'Authorization': `Bearer ${getToken()}` },
        timeout: 10000
      });
      
      if (res.data.status === 'completed') {
        return { evaluation_id: evaluationId, evaluation_result: res.data.evaluation_result };
      }
    }
    
    throw new Error('Evaluation timed out after 15 minutes');
  },

  async editQuestionResult({ evaluationId, fileId, questionNumber, score, feedback }) {
    try {
      const user = getCurrentUser();
      if (!user?.id) {
        throw new Error('User not authenticated');
      }

      console.log('Sending data to backend:', {
        evaluation_id: evaluationId,
        file_id: fileId,
        question_number: questionNumber,
        score: score,
        feedback: feedback
      });
      
      const res = await axios.put(`${API_BASE}/evaluation/edit-results`, {
        evaluation_id: evaluationId,
        file_id: fileId,
        question_number: questionNumber,
        score: score,
        feedback: feedback
      }, {
        headers: { 
          'Authorization': `Bearer ${getToken()}`,
          'Content-Type': 'application/json'
        }
      });
      
      return res.data; // { message: "Results updated" }
    } catch (error) {
      console.error('Edit question result error:', error);
      if (error.response?.status === 401) {
        throw new Error('Authentication failed. Please try again.');
      }
      throw new Error(error.response?.data?.detail || 'Failed to edit question result');
    }
  }
}; 